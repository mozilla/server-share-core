import unittest

from linkoauth import get_provider
from linkoauth.tests.test_base import _ACCOUNT


class TestBasics(unittest.TestCase):
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
        provider = get_provider("facebook.com")
        api = provider.api(_ACCOUNT)
        res, error = api.sendmessage('', self.get_args())
        self.check_error(res, error)

    def test_invalid_share_type(self):
        provider = get_provider("facebook.com")
        api = provider.api(_ACCOUNT)
        res, error = api.sendmessage('', self.get_args(shareType="invalid"))
        self.check_error(res, error)

    def test_no_wall_name(self):
        provider = get_provider("facebook.com")
        api = provider.api(_ACCOUNT)
        args = self.get_args(shareType="groupWall")
        res, error = api.sendmessage('', )
        self.check_error(res, error)
