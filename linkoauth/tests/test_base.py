import unittest
import httplib2
import json
import urllib2

from linkoauth.util import setup_config
from linkoauth import get_providers, get_provider
from linkoauth import google_


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


class TestBasics(unittest.TestCase):

    def setUp(self):
        setup_config(_CONFIG)
        self.old_httplib2 = httplib2.Http.request
        httplib2.Http.request = _request
        self.old_smtp = google_.SMTP
        google_.SMTPRequestor = _SMTP
        self.old_urlopen = urllib2.urlopen
        urllib2.urlopen = _urlopen

    def tearDown(self):
        httplib2.Http.request = self.old_httplib2
        google_.SMTPRequestor = self.old_smtp
        urllib2.urlopen = self.old_urlopen

    def test_registery(self):
        message = ''
        share_types = {
            'facebook.com': 'wall',
            'twitter.com': 'direct',
            'linkedin.com': 'contact',
        }
        args = {'to': 'tarek@ziade.org',
                'subject': 'xxx',
                'title': 'the title',
                'description': 'some description',
                'link': 'http://example.com',
                'shorturl': 'http://example.com'}

        # just a sanity check to see if every oauth backend
        # can be instanciated and send messages
        #
        for provname in get_providers():
            provider = get_provider(provname)
            api = provider.api(_ACCOUNT)
            this_args = args.copy()
            if provname in share_types:
                this_args['shareType'] = share_types[provname]
            res, error = api.sendmessage(message, this_args)
            self.assertFalse(error, str(error))
            self.assertTrue(res['status'] in (200, 'message sent'))
