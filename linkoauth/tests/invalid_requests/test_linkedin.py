import unittest

from linkoauth.backends.linkedin_ import api
from linkoauth.util import setup_config
from linkoauth.tests.test_base import _ACCOUNT, _CONFIG


class TestBasics(unittest.TestCase):
    def setUp(self):
        setup_config(_CONFIG)
        self.requester = api(_ACCOUNT)

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

    def test_invalid_public_share_type(self):
        args = self.get_args(shareType="public", to="invalid")
        res, error = self.requester.sendmessage('', args, None)
        self.check_error(res, error)

    def test_invalid_connections_share_type(self):
        args = self.get_args(shareType="myConnections", to="invalid")
        res, error = self.requester.sendmessage('', args, None)
        self.check_error(res, error)

    def test_contact_no_to(self):
        args = self.get_args(shareType='contact', to='')
        res, error = self.requester.sendmessage('', args, None)
        self.check_error(res, error)
