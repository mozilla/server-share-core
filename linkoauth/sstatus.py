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
# Contributor(s): Tarek Ziade <tarek@ziade.org>
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
from pylibmc import Client, SomeErrors, WriteError
from _pylibmc import NotFound

from linkoauth.errors import StatusReadError, StatusWriteError


def _key(*args):
    return ':'.join(args)


class ServicesStatus(object):

    def __init__(self, services, servers=None, ttl=600):
        self.ttl = ttl
        if servers is None:
            servers = ['127.0.0.1:11211']
        self._cache = Client(servers, binary=True)
        self._cache.behaviors = {"no_block": True}
        for service in services:
            # initialize if not found
            try:
                enabled = self._cache.get(_key('service', service, 'on'))
            except SomeErrors:
                raise StatusReadError()

            if enabled is None:
                self.initialize(service)

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
