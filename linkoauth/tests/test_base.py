import unittest
import httplib2
import json
import mock
import time
import urllib2

from linkoauth.util import setup_config
from linkoauth.backends import google_
from linkoauth import Services
from linkoauth import sstatus
from linkoauth.errors import DomainNotRegisteredError


_ACCOUNT = {'oauth_token': 'xxx',
            'oauth_token_secret': 'xxx',
            'profile': {'emails':
                        [{'value': 'tarek@ziade.org'}]}}

_CONFIG = {'oauth.yahoo.com.consumer_key': 'xxx',
           'oauth.yahoo.com.consumer_secret': 'xxx',
           'oauth.linkedin.com.consumer_key': 'xxx',
           'oauth.linkedin.com.consumer_secret': 'xxx',
           'oauth.twitter.com.consumer_key': 'xxx',
           'oauth.twitter.com.consumer_secret': 'xxx'}


class _Res(dict):
    def __init__(self, status):
        self.status = status
        self['status'] = status


def _request(*args, **kwargs):
    res = {'status': 200, 'id': 123, 'error': '',
            'result': {'status': 200}}
    return _Res(200), json.dumps(res)


class _SMTP(object):

    def __init__(self, *args):
        pass

    def quit(self):
        pass

    ehlo_or_helo_if_needed = starttls = quit

    def authenticate(self, *args):
        pass

    sendmail = authenticate


class _FakeResult(object):
    headers = {}

    def read(self):
        res = {'id': 123, 'status': 200}
        return json.dumps(res)


def _urlopen(*args):
    return _FakeResult()


class MockCache(object):
    def __init__(self):
        self._cache = dict()
        self._cache_ttl = dict()

    def get(self, key):
        if key in self._cache_ttl:
            now = time.time()
            ttl, last_time = self._cache_ttl[key]
            if now - last_time > ttl:
                del self._cache_ttl[key]
                del self._cache[key]
            else:
                self._cache_ttl[key] = (ttl, now)
        return self._cache.get(key)

    def set(self, key, value, **kwargs):
        self._cache[key] = value
        ttl = kwargs.get('time')
        if ttl is not None:
            self._cache_ttl[key] = (ttl, time.time())

    def incr(self, key):
        self._cache[key] = self._cache[key] + 1


class TestBasics(unittest.TestCase):

    def setUp(self):
        setup_config(_CONFIG)
        self.old_httplib2 = httplib2.Http.request
        httplib2.Http.request = _request
        self.old_smtp = google_.SMTP
        google_.SMTPRequestor = _SMTP
        self.old_urlopen = urllib2.urlopen
        urllib2.urlopen = _urlopen
        self.mcclient_patcher = mock.patch('linkoauth.sstatus.Client')
        self.mcclient_patcher.start()
        self.mock_cache = MockCache()
        sstatus.Client.return_value = self.mock_cache

    def tearDown(self):
        httplib2.Http.request = self.old_httplib2
        google_.SMTPRequestor = self.old_smtp
        urllib2.urlopen = self.old_urlopen
        self.mcclient_patcher.stop()

    def test_callbacks(self):
        message = ''
        args = {'to': 'tarek@ziade.org',
                'subject': 'xxx',
                'title': 'the title',
                'description': 'some description',
                'link': 'http://example.com',
                'shorturl': 'http://example.com'}

        services = Services(['google.com'])
        services.initialize('google.com')

        res, error = services.sendmessage('google.com', _ACCOUNT,
                                          message, args, None)

        status = services.get_status('google.com')
        self.assertEquals(status, (True, 1, 0))

    def test_service_unknown(self):

        # this should fail, as 'a' is not registered
        self.assertRaises(DomainNotRegisteredError,
                          Services, ['google.com', 'a'])

        # this should fail too
        services = Services(['google.com'])
        self.assertRaises(DomainNotRegisteredError, services.sendmessage, 'a',
                          object(), '', '')

    def test_disabled(self):
        message = ''
        args = {'to': 'tarek@ziade.org',
                'subject': 'xxx',
                'title': 'the title',
                'description': 'some description',
                'link': 'http://example.com',
                'shorturl': 'http://example.com'}

        services = Services(['google.com'], feedback_enabled=False)
        services.initialize('google.com')
        res, error = services.sendmessage('google.com', _ACCOUNT,
                                          message, args, None)

        status = services.get_status('google.com')
        self.assertEquals(status, (True, 0, 0))
