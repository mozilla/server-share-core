# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Raindrop.
#
# The Initial Developer of the Original Code is
# Mozilla Messaging, Inc..
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Tarek Ziade <tarek@ziade.org>
#   Rob Miller (rmiller@mozilla.com)
#
"""
This module provides:

- a middleware that can be used to reject requests when the third-party
  service that is being used was detected as being down.

  The rejection is based on the presence of a X-Target-Service header
  and the value of the successes/failures ratio in the DB.

  Note that it's better to reject the requests earlier in the stack
  if you can (at the load balancer level for instance) to avoid
  extra CPU cycles for this.


- A class that can be used to interact with the DB:

  - disable(service) -> True or False
  - enable(service) -> True or False
  - get_status(service_name) -> status, successes, failures
  - update_status(service_name, success_or_failure) -> True or False


The statuses are saved in a membase backend that can be replicated around
using the peer-to-peer replication feature.
"""
import sys
from functools import wraps

from pylibmc import Client, SomeErrors, WriteError
from _pylibmc import NotFound

from linkoauth.errors import StatusReadError, StatusWriteError


def _key(*args):
    return ':'.join(args)


def cache_initialized(fn):
    @wraps(fn)
    def initializer(self, *args, **kwargs):
        if getattr(self, '_initialized', False):
            # already initialized, scrap the decorator
            setattr(self, fn.__name__, fn)
        else:
            for service in self.services:
                # initialize if not found
                try:
                    enabled = self._cache.get(_key('service', service, 'on'))
                except SomeErrors:
                    raise StatusReadError()
                if enabled is None:
                    self.initialize(service)
        return fn(self, *args, **kwargs)
    return initializer


class ServicesStatusCache(object):
    """Thin wrapper around cache client to allow for graceful initialization"""
    def __init__(self, servers, services, ttl, binary):
        self.services = services
        self.ttl = ttl
        self._cache = Client(servers, binary=binary)
        self._cache.behaviors = {"no_block": True}

    def initialize(self, service):
        # XXX see if one key is better wrt R/W numbers
        # to do a single memcached call here
        try:
            self._cache.set(_key('service', service, 'on'), True)
            self._cache.set(_key('service', service, 'succ'), 0,
                            time=self.ttl)
            self._cache.set(_key('service', service, 'fail'), 0,
                            time=self.ttl)
            return True
        except WriteError:
            raise StatusWriteError()

    @cache_initialized
    def get(self, key):
        return self._cache.get(key)

    @cache_initialized
    def set(self, key, *args, **kwargs):
        return self._cache.set(key, *args, **kwargs)

    @cache_initialized
    def incr(self, key):
        return self._cache.incr(key)


class ServicesStatus(object):

    def __init__(self, services, servers=None, ttl=600):
        self.ttl = ttl
        if servers is None:
            servers = ['127.0.0.1:11211']
        self._cache = ServicesStatusCache(servers, services, ttl, binary=True)

    def initialize(self, service):
        self._cache.initialize(service)

    def enable(self, service):
        try:
            self._cache.set(_key('service', service, 'on'), True)
        except WriteError:
            raise StatusWriteError()

    def disable(self, service):
        try:
            self._cache.set(_key('service', service, 'on'), False)
        except WriteError:
            raise StatusWriteError()

    def get_status(self, service):
        try:
            enabled = self._cache.get(_key('service', service, 'on'))
            succ = self._cache.get(_key('service', service, 'succ'))
            if succ is None:
                succ = 0

            fail = self._cache.get(_key('service', service, 'fail'))
            if fail is None:
                fail = 0

            return enabled, succ, fail
        except SomeErrors:
            # could not read the status
            raise StatusReadError()

    def update_status(self, service, success):
        if success:
            key = _key('service', service, 'succ')
            other_key = _key('service', service, 'fail')
        else:
            key = _key('service', service, 'fail')
            other_key = _key('service', service, 'succ')

        try:
            return self._cache.incr(key)
        except NotFound:
            # the key ttl-ed
            self._cache.set(key, 1, time=self.ttl)
            self._cache.set(other_key, 0, time=self.ttl)
            return 1
        except WriteError:
            raise StatusWriteError()


class ServicesStatusMiddleware(object):

    def __init__(self, app, services, tresholds, retry_after=600,
                 cache_servers=None):
        self.app = app
        self.services = services
        self.tresholds = tresholds
        self.retry_after = retry_after
        self._status_checker = ServicesStatus(services, cache_servers)

    def _503(self, start_response):
        headers = [('Content-Type', 'text/plain'),
                   ('Retry-After', str(self.retry_after))]

        start_response('503 Service Unavailable', headers)
        return ['The service is unavailable']

    def __call__(self, environ, start_response):
        target_service = environ.get('HTTP_X_TARGET_DOMAIN')
        try:
            index = self.services.index(target_service)
        except ValueError:
            index = -1

        if index != -1:
            try:
                on, succ, fail = \
                    self._status_checker.get_status(target_service)
            except StatusReadError:
                # could not read the status
                on, succ, fail = True, 0, 0

            if not on:
                return self._503(start_response)

            if fail != 0:
                ratio = float(succ) / float(fail)
                if ratio < self.tresholds[index]:
                    return self._503(start_response)

        return self.app(environ, start_response)


_USAGE = """\
Usage : sstatus server domain action [options]

Available actions:
    - status: returns a status for the domain
    - enable: enable the domain
    - disable: disable the domain
    - reset: reset the domain by setting the counters to 0 and enabling it

Example:

    $ sstatus 127.0.0.1:11211 google.com status
    This service is enabled.
    12653 successes, 3 failures.

"""

def _ask(question):
    answer = raw_input(question + ' ')
    answer = answer.lower().strip()
    return answer in ('y', 'yes')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(_USAGE)
        sys.exit(1)

    server = sys.argv[1]
    domain = sys.argv[2]
    action = sys.argv[3]
    options = sys.argv[4:]

    server = ServicesStatus([domain], [server])
    if action == 'status':
        try:
            enabled, success, fail = server.get_status(domain)
        except StatusReadError:
            print('Ooops, could not read the status.')
            sys.exit(1)

        if not enabled:
            print('This service has been disabled')
        else:
            print('This service is enabled.')
            print('%d successes, %d failures.' % (success, fail))
        sys.exit(0)
    elif action == 'enable':
        try:
            server.enable(domain)
        except StatusWriteError:
            print('Ooops, could not enable the service.')
            sys.exit(1)

        print('Service enabled.')
        sys.exit(0)
    elif action == 'disable':
        if _ask('Are you sure you want to disable "%s" ?' % domain):
            try:
                server.disable(domain)
            except StatusWriteError:
                print('Ooops, could not disable the service.')
                sys.exit(1)

            print('Service disabled.')
        else:
            print('Aborted.')
        sys.exit(0)
    elif action == 'reset':
        if _ask('Are you sure you want to reset "%s" ?' % domain):
            try:
                server.initialize(domain)
            except StatusWriteError:
                print('Ooops, could not disable the service.')
                sys.exit(1)

            print('Service reseted.')
        else:
            print('Aborted.')
        sys.exit(0)
    else:
        print('Unknown action.')
        print(usage)
        sys.exit(1)
