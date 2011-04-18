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

# partially based on code from velruse
import copy
import json
import logging
from urllib import urlencode

import oauth2 as oauth

from linkoauth.oauth import OAuth1, get_oauth_config
from linkoauth.errors import OAuthKeysException
from linkoauth.protocap import OAuth2Requestor

domain = 'twitter.com'
log = logging.getLogger(domain)

# example record for twiter_to_poco:

"""
{'id': 33934767,
 'verified': False,
 'profile_sidebar_fill_color': 'e0ff92',
 'profile_text_color': '000000',
 'followers_count': 47,
 'profile_sidebar_border_color': '87bc44',
 'location': '',
 'profile_background_color': '9ae4e8',
 'utc_offset': None,
 'statuses_count': 36,
 'description': '',
 'friends_count': 58,
 'profile_link_color': '0000ff',
 'profile_image_url':
    'http://a3.twimg.com/profile_images/763050003/me_normal.png',
 'notifications': False,
 'geo_enabled': False,
 'profile_background_image_url':
    'http://s.twimg.com/a/1276197224/images/themes/theme1/bg.png',
 'screen_name': 'mixedpuppy',
 'lang': 'en',
 'profile_background_tile': False,
 'favourites_count': 0,
 'name': 'Shane Caraveo',
 'url': 'http://mixedpuppy.wordpress.com',
 'created_at': 'Tue Apr 21 15:21:25 +0000 2009',
 'contributors_enabled': False,
 'time_zone': None,
 'protected': False,
 'following': False}
"""


def twitter_to_poco(user):
    poco = {
        'displayName': user.get('name', user.get('screen_name')),
    }
    if user.get('url', False):
        poco['urls'] = [{"primary": False, "value": user['url']}]
    if user.get('profile_image_url', False):
        poco['photos'] = [{'type': u'profile',
                           "value": user['profile_image_url']}]
    if user.get('created_at', None):
        poco['published'] = user['created_at']

    account = {'domain': 'twitter.com',
               'userid': user['id'],
               'username': user['screen_name']}
    poco['accounts'] = [account]

    return poco


class TwitterResponder(OAuth1):
    """Handle Twitter OAuth login/authentication"""
    domain = 'twitter.com'

    def __init__(self):
        OAuth1.__init__(self, domain)
        self.domain = domain

    @classmethod
    def get_name(cls):
        return cls.domain

    def _get_credentials(self, access_token):
        # XXX should call twitter.api.VerifyCredentials to get the user object
        # Setup the normalized poco contact object
        username = access_token['screen_name']
        userid = access_token['user_id']

        profile = {}
        profile['providerName'] = 'Twitter'
        profile['displayName'] = username
        profile['identifier'] = 'http://twitter.com/?id=%s' % userid

        account = {'domain': 'twitter.com',
                   'userid': userid,
                   'username': username}
        profile['accounts'] = [account]

        result_data = {'profile': profile,
                      'oauth_token': access_token['oauth_token'],
                      'oauth_token_secret': access_token['oauth_token_secret']}
        result, error = TwitterRequester(
              oauth_token=access_token['oauth_token'],
              oauth_token_secret=access_token['oauth_token_secret']).profile()
        if result:
            profile.update(twitter_to_poco(result))
        return result_data


class TwitterRequester(object):
    def __init__(self, account=None, oauth_token=None,
                 oauth_token_secret=None):
        self.domain = domain
        self.config = get_oauth_config(domain)
        oauth_token = account and account.get('oauth_token') or oauth_token
        oauth_token_secret = (account and account.get('oauth_token_secret')
                              or oauth_token_secret)

        self.account = account
        try:
            self.oauth_token = oauth.Token(key=oauth_token,
                                           secret=oauth_token_secret)
        except ValueError, e:
            # missing oauth tokens, raise our own exception
            raise OAuthKeysException(str(e))
        self.consumer_key = self.config.get('consumer_key')
        self.consumer_secret = self.config.get('consumer_secret')
        self.consumer = oauth.Consumer(key=self.consumer_key,
                                       secret=self.consumer_secret)
        self.sigmethod = oauth.SignatureMethod_HMAC_SHA1()

    @classmethod
    def get_name(cls):
        return domain

    def _make_error(self, data, resp):
        status = int(resp['status'])

        # this should be retreived from www-authenticate if provided there,
        # see above comments
        code = data.get('error_code', 0)
        if isinstance(data.get('error', None), dict):
            error = copy.copy(data['error'])
        # fallback to their rest error message
        elif 'error' in data:
            error = {
                'message': data.get('error', 'it\'s an error, kthx'),
            }
        # who knows, some other abberation
        else:
            error = {
                'message': "expectedly, an unexpected twitter error: %r"
                % (data,),
            }
            log.error(error['message'])

        error.update({'code': code,
                      'provider': domain,
                      'status': status})
        return error

    def rawcall(self, url, params=None, method="GET"):
        client = OAuth2Requestor(self.consumer, self.oauth_token)
        if method == "POST":
            body = urlencode(params)
        else:
            assert params is None
            body = ''
        resp, content = client.request(url, method, body=body)

        data = content and json.loads(content) or resp

        result = error = None
        status = int(resp['status'])
        if status < 200 or status >= 300:
            error = self._make_error(data, resp)
        else:
            result = data
        return result, error

    def sendmessage(self, message, options={}):
        # insert the url if it is not already in the message
        longurl = options.get('link')
        shorturl = options.get('shorturl')
        share_type = options.get('shareType', None)
        if shorturl:
            # if the long url is in the message body, replace it with
            # the short url, otherwise just make sure shorturl is in
            # the body.
            if longurl and longurl in message:
                message = message.replace(longurl, shorturl)
            elif shorturl not in message:
                message += " %s" % shorturl
        elif longurl and longurl not in message:
            # some reason we dont have a short url, add the long url
            message += " %s" % longurl

        if share_type == 'direct':
            direct = options.get('to', None)
            if not direct:
                return None, \
                        {'code': 400,
                         'provider': domain,
                         'message': 'Missing addressee for direct message'}
            url = 'https://api.twitter.com/1/direct_messages/new.json'
            body = {'user': direct, 'text': message}
        elif share_type == 'public':
            url = 'https://api.twitter.com/1/statuses/update.json'
            body = {'status': message}
        else:
            return None, {'code': 400,
                          'provider': domain,
                          'message': 'Share type is missing'}
        return self.rawcall(url, params=body, method="POST")

    def profile(self):
        url = 'https://api.twitter.com/1/account/verify_credentials.json'
        return self.rawcall(url)

    def getcontacts(self, start=0, page=25, group=None):
        url = ('https://api.twitter.com/1/statuses/followers.json'
               '?screen_name=%s' % self.account.get('username'))
        # for twitter we get only those people who we follow and who follow us
        # since this data is used for direct messaging
        contacts = []

        data, error = self.rawcall(url)
        if error:
            return None, error
        for follower in data:
            contacts.append(twitter_to_poco(follower))

        connectedto = {
            'entry': contacts,
            'itemsPerPage': len(contacts),
            'startIndex':   0,
            'totalResults': len(contacts),
        }

        return connectedto, None
