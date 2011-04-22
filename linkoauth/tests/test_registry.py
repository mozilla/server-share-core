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
# Contributor(s):
#
import unittest

from linkoauth.backends import get_responder, get_requester
from linkoauth.util import setup_config


_CONFIG = {'oauth.yahoo.com.consumer_key': 'xxx',
           'oauth.yahoo.com.consumer_secret': 'xxx',
           'oauth.linkedin.com.consumer_key': 'xxx',
           'oauth.linkedin.com.consumer_secret': 'xxx',
           'oauth.twitter.com.consumer_key': 'xxx',
           'oauth.twitter.com.consumer_secret': 'xxx'}


class TestRegistry(unittest.TestCase):

    def setUp(self):
        setup_config(_CONFIG)

    def test_registeries(self):

        account = {'oauth_token': 'xxx',
                   'oauth_token_secret': 'xxx'}

        for domain in ('google.com', 'twitter.com', 'facebook.com',
                       'yahoo.com', 'linkedin.com'):
            obj = get_responder(domain)
            self.assertTrue(hasattr(obj, 'request_access'))

            obj = get_requester(domain, account)
            self.assertTrue(hasattr(obj, 'sendmessage'))
            self.assertTrue(hasattr(obj, 'getcontacts'))
