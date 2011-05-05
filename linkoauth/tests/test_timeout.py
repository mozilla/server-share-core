import unittest
from ssl import SSLError
from functools import wraps

from linkoauth.backends.twitter_ import TwitterRequester
from linkoauth.util import setup_config
from linkoauth.protocap import OAuth2Requestor


_ACCOUNT = {'oauth_token': 'xxx',
            'oauth_token_secret': 'xxx',
            'profile': {'emails':
                        [{'value': 'tarek@ziade.org'}]}}


_CONFIG = {'oauth.twitter.com.timeout': '1',
           'oauth.twitter.com.consumer_key': 'xxx',
           'oauth.twitter.com.consumer_secret': 'xxx'}


def _timeout(*args, **kw):
    raise SSLError('_ssl.c:475: The handshake operation timed out')


def patch(klass, attr, new):
    def _patch(func):
        @wraps(func)
        def __patch(*args, **kw):
            old = getattr(klass, attr)
            setattr(klass, attr, new)
            try:
                return func(*args, **kw)
            finally:
                setattr(klass, attr, new)
        return __patch
    return _patch


class TestTimeout(unittest.TestCase):


    def setUp(self):
        setup_config(_CONFIG)

    @patch(OAuth2Requestor, 'request', _timeout)
    def test_twitter(self):
        req = TwitterRequester(_ACCOUNT, 'token', 'secret')
        self.assertEquals(req.timeout, 1)
        options = {'shareType': 'public'}
        res, resp = req.sendmessage('message', options, {})

        self.assertEquals(res, None)
        self.assertEquals(resp['status'], 503)
        self.assertEquals(resp['message'],
                          '_ssl.c:475: The handshake operation timed out')

