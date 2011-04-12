import unittest

from linkoauth.util import setup_config
from linkoauth import get_provider
from linkoauth.tests.test_base import _ACCOUNT, _CONFIG


class TestBasics(unittest.TestCase):
    def setUp(self):
        setup_config(_CONFIG)
    
    def get_args(self, **kw):
        args = {'subject': 'xxx',
                'title': 'the title',
                'description': 'some description',
                'link': 'http://example.com',
                'shorturl': 'http://example.com'}
        args.update(kw)
        return args

    def check_error(self, res, error, expected_code=400):
        self.assertFalse(res)
        self.assertTrue('code' in error, error)
        self.assertEqual(error['code'], expected_code)

    def test_no_share_type(self):
        provider = get_provider("twitter.com")
        api = provider.api(_ACCOUNT)
        res, error = api.sendmessage('', self.get_args())
        self.check_error(res, error)

    def test_invalid_share_type(self):
        provider = get_provider("twitter.com")
        api = provider.api(_ACCOUNT)
        res, error = api.sendmessage('', self.get_args(shareType="invalid"))
        self.check_error(res, error)

    def test_direct_no_to(self):
        provider = get_provider("twitter.com")
        api = provider.api(_ACCOUNT)
        args = self.get_args(shareType='direct', to='')
        res, error = api.sendmessage('', args)
        self.check_error(res, error)
