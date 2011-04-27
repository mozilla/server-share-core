import unittest

from linkoauth.backends.facebook_ import FacebookRequester
from linkoauth.tests.test_base import _ACCOUNT


class TestBasics(unittest.TestCase):
    def setUp(self):
        self.requester = FacebookRequester(_ACCOUNT)

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
        res, error = self.requester.sendmessage('', self.get_args(), None)
        self.check_error(res, error)

    def test_invalid_share_type(self):
        res, error = self.requester.sendmessage(
            '', self.get_args(shareType="invalid"), None)
        self.check_error(res, error)

    def test_no_wall_name(self):
        args = self.get_args(shareType="groupWall")
        res, error = self.requester.sendmessage('', args, None)
        self.check_error(res, error)
