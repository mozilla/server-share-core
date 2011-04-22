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
import json
import oauth2 as oauth
import logging
from rfc822 import AddressList

from linkoauth.oauth import OAuth1, get_oauth_config
from linkoauth.errors import OAuthKeysException
from linkoauth.util import config, render, safeHTML, literal
from linkoauth.protocap import OAuth2Requestor

domain = 'linkedin.com'
log = logging.getLogger(domain)


def extract_li_data(user):
    poco = {
        'displayName': "%s %s" % (user.get('firstName'),
                                  user.get('lastName'))}

    if user.get('publicProfileUrl', False):
        poco['urls'] = [{'type': u'profile',
                         'primary': False,
                         'value': user['publicProfileUrl']}]

    if user.get('siteStandardProfileRequest', False):
        poco['urls'] = [{'type': u'profile',
                         'primary': True,
                         'value': user['siteStandardProfileRequest']['url']}]

    if user.get('pictureUrl', False):
        poco['photos'] = [{'type': u'profile',
                           'value': user['pictureUrl']}]

    account = {'domain': domain,
               'userid': user.get("id"),
               'username': ""}
    poco['accounts'] = [account]

    return poco


class responder(OAuth1):
    """Handle LinkedId OAuth login/authentication"""
    domain = 'linkedin.com'

    def __init__(self):
        OAuth1.__init__(self, domain)

    @classmethod
    def get_name(cls):
        return cls.domain

    def _get_credentials(self, access_token):
        fields = ['id', 'first-name', 'last-name', 'picture-url',
                  'public-profile-url', 'site-standard-profile-request']
        fields = ','.join(fields)
        profile_url = "http://api.linkedin.com/v1/people/~:(%s)" % (fields,)
        consumer = oauth.Consumer(self.consumer_key, self.consumer_secret)
        token = oauth.Token(access_token['oauth_token'],
                            access_token['oauth_token_secret'])
        client = OAuth2Requestor(consumer, token)
        headers = {}
        headers['x-li-format'] = 'json'

        resp, content = client.request(profile_url, method='GET',
                                       headers=headers)

        if resp['status'] != '200':
            client.save_capture("non 200 credentials response")
            raise Exception("Error status: %r", resp['status'])

        li_profile = json.loads(content)
        profile = extract_li_data(li_profile)
        result_data = {'profile': profile,
                   'oauth_token': access_token['oauth_token'],
                   'oauth_token_secret': access_token['oauth_token_secret']}
        return result_data


class api(object):
    def __init__(self, account):
        self.config = get_oauth_config(domain)
        self.account = account
        try:
            self.oauth_token = oauth.Token(key=account.get('oauth_token'),
                    secret=account.get('oauth_token_secret'))
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

    def rawcall(self, url, body=None, method="GET"):
        client = OAuth2Requestor(self.consumer, self.oauth_token)
        headers = {}
        headers['x-li-format'] = 'json'

        if body is not None:
            body = json.dumps(body)
            headers['Content-Type'] = 'application/json'
            headers['Content-Length'] = str(len(body))

        resp, content = client.request(url, method=method,
                                       headers=headers, body=body)

        data = content and json.loads(content) or resp
        result = error = None
        status = int(resp['status'])
        if status < 200 or status >= 300:
            client.save_capture("non 2xx response")
            error = data
        else:
            result = data

        return result, error

    def sendmessage(self, message, options=None):
        if options is None:
            options = {}
        share_type = str(options.get('shareType', ''))
        if not share_type or share_type not in \
            ('public', 'myConnections', 'contact'):
            return None, {'code': 400,
                          'provider': 'linkedin',
                          'message': 'Invalid share type'}

        # TODO: this needs a bit work, it is not really "direct".
        if share_type in ('public', 'myConnections'):
            direct = options.get('to', 'anyone')
            if (share_type == 'public' and direct != 'anyone') or \
               (share_type == 'myConnections' and
                direct != 'connections-only'):
                return None, {'code': 400,
                              'provider': 'linkedin',
                              'message': 'Incorrect addressing for post'}
            url = "http://api.linkedin.com/v1/people/~/shares"
            body = {
                "comment": message,
                "content": {
                    "title": options.get('subject', ''),
                    "submitted-url": options.get('link', ''),
                    "submitted-image-url": options.get('picture', ''),
                    "description": options.get('description', ''),
                },
                "visibility": {
                    "code": direct
                }
            }
        else:
            # we have to do a direct message, different api
            url = "http://api.linkedin.com/v1/people/~/mailbox"

            profile = self.account.get('profile', {})
            from_ = profile.get('verifiedEmail')
            fullname = profile.get('displayName')

            to_addrs = AddressList(options['to'])
            subject = options.get('subject',
                             config.get('share_subject',
                                 'A web link has been shared with you'))
            title = options.get('title', options.get('link',
                options.get('shorturl', '')))
            description = options.get('description', '')[:280]

            to_ = []
            ids = [a[1] for a in to_addrs.addresslist]
            if not ids:
                return None, {'code': 400,
                              'message': 'Missing contacts for direct messaging.'}
            for id in ids:
                to_.append({'person': {'_path': '/people/' + id}})

            extra_vars = {'safeHTML': safeHTML}
            extra_vars['options'] = options

            # insert the url if it is not already in the message
            extra_vars['longurl'] = options.get('link')
            extra_vars['shorturl'] = options.get('shorturl')

            # get the title, or the long url or the short url or nothing
            # wrap these in literal for text email
            extra_vars['from_name'] = literal(fullname)
            extra_vars['subject'] = literal(subject)
            extra_vars['from_header'] = literal(from_)
            extra_vars['to_header'] = literal(to_)
            extra_vars['title'] = literal(title)
            extra_vars['description'] = literal(description)
            extra_vars['message'] = literal(message)

            text_message = render('/text_email.mako',
                                  extra_vars=extra_vars).encode('utf-8')

            body = {
                'recipients': {'values': to_},
                'subject': subject,
                'body': text_message}

        return self.rawcall(url, body, method="POST")

    def getcontacts(self, options=None):
        if options is None:
            options = {}
        start = int(options.get('start', 0))
        page = int(options.get('page', 25))
        contacts = []
        url = 'http://api.linkedin.com/v1/people/~/connections?count=%d' % page
        if start > 0:
            url = url + "&start=%d" % (start,)

        result, error = self.rawcall(url, method="GET")
        if error:
            return result, error

        # poco-ize the results
        entries = result.get('values', [])
        contacts = []
        for entry in entries:
            contacts.append(extract_li_data(entry))

        count = result.get('_count', result.get('_total', 0))
        start = result.get('_start', 0)
        total = result.get('_total', 0)
        connectedto = {
            'entry': contacts,
        }
        if start + count < total:
            connectedto['pageData'] = {
                'count': count,
                'start': start + count,
            }

        return connectedto, error
