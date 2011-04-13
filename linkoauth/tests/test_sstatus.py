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
import time
import unittest
from linkoauth.sstatus import ServicesStatus, ServicesStatusMiddleware


class FakeEnviron(dict):
    pass


class FakeWSGIApp(object):
    def __call__(self, environ, start_response):
        headers = [('Content-Type', 'text/plain')]
        start_response('200 OK', headers)
        return ['Hello World']


class TestServiceStatus(unittest.TestCase):

    def setUp(self):
        self.services = ServicesStatus(['a', 'b', 'c'])

    def tearDown(self):
        for service in ['a', 'b', 'c']:
            self.services.initialize(service)

    def test_io(self):
        self.assertEqual(self.services.get_status('a'),
                         (True, 0, 0))

        self._ping_status()
        self.assertEqual(self.services.get_status('a'),
                         (True, 10, 20))

    def _ping_status(self, service='a', succ=10, fail=20):
        for i in range(succ):
            self.services.update_status(service, True)

        for i in range(fail):
            self.services.update_status(service, False)

    def test_middleware(self):
        origin_app = FakeWSGIApp()
        services = ['a', 'b', 'c']
        tresholds = [0.5, 0.9, 0.1]
        app = ServicesStatusMiddleware(origin_app, services, tresholds)

        # 10 successes, 20 failures
        self._ping_status()

        responses = []
        request = FakeEnviron()

        def start_response(status, headers):
            responses.append((status, headers))

        # no particular header
        res = app(request, start_response)
        self.assertEqual(res[0], 'Hello World')

        # adding X-Target-Service
        request['HTTP_X_TARGET_SERVICE'] = 'a'
        res = app(request, start_response)
        # still under ratio
        self.assertEqual(res[0], 'Hello World')

        # 20 failures
        self._ping_status(succ=0, fail=20)

        res = app(request, start_response)
        # gone
        self.assertEqual(res[0], 'The service is unavailable')

        # let's re-init it, and disable it
        self.services.initialize('a')
        self.services.disable('a')

        # not available
        res = app(request, start_response)
        self.assertEqual(res[0], 'The service is unavailable')

        # we should have a Retry-After header
        headers = dict(responses[-1][1])
        self.assertEqual(headers['Retry-After'], '600')

        # back online
        self.services.enable('a')
        res = app(request, start_response)
        self.assertEqual(res[0], 'Hello World')

    def test_ttl(self):
        services = ServicesStatus(['d'], ttl=1)
        try:
            for i in range(10):
                services.update_status('d', True)

            status = self.services.get_status('d')
            self.assertEqual(status, (True, 10, 0))

            time.sleep(1.)
            status = self.services.get_status('d')
            self.assertEqual(status, (True, 0, 0))

        finally:
            services.initialize('d')
