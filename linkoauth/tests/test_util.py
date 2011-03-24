import unittest
from linkoauth.util import build_url


class TestUtil(unittest.TestCase):

    def test_build_url(self):
        profile_url = 'https://graph.facebook.com/me'
        access_token = 'xxxx'
        fields = ('id,first_name,last_name,name,link,'
                  'birthday,email,website,verified,'
                  'picture,gender,timezone')

        res = build_url(profile_url, access_token=access_token, fields=fields)
        expect = 'https://graph.facebook.com/me?access_token=xxxx&fields=id%2Cf'
        self.assertTrue(res.startswith(expect))
