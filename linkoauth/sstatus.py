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
from pylibmc import Client
from linkoauth.errors import BackendError


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
            enabled = self._cache.get(_key('service', service, 'on'))
            if enabled is None:
                self.initialize(service)

    def initialize(self, service):
        # XXX see if one key is better wrt R/W numbers
        # to do a single memcached call here
        self._cache.set(_key('service', service, 'on'), True)
        self._cache.set(_key('service', service, 'succ'), 0)
        self._cache.set(_key('service', service, 'fail'), 0)

    def enable(self, service):
        self._cache.set(_key('service', service, 'on'), True)

    def disable(self, service):
        self._cache.set(_key('service', service, 'on'), False)

    def get_status(self, service):
        enabled = self._cache.get(_key('service', service, 'on'))
        succ = self._cache.get(_key('service', service, 'succ'))
        fail = self._cache.get(_key('service', service, 'fail'))
        return enabled, succ, fail

    def update_status(self, service, success):
        if success:
            key = _key('service', service, 'succ')
        else:
            key = _key('service', service, 'fail')

        return self._cache.incr(key)


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
        target_service = environ.get('HTTP_X_TARGET_SERVICE')
        try:
            index = self.services.index(target_service)
        except ValueError:
            index = -1

        if index != -1:
            on, succ, fail = self._status_checker.get_status(target_service)
            if not on:
                return self._503(start_response)

            if fail != 0:
                ratio = float(succ) / float(fail)
                if ratio < self.tresholds[index]:
                    return self._503(start_response)

        return self.app(environ, start_response)
