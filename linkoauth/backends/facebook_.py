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

import urlparse
import json
import urllib
import random
import copy
import logging

from linkoauth.oauth import OAuth2
from linkoauth.errors import OAuthKeysException
from linkoauth.util import build_url, config
from linkoauth.protocap import HttpRequestor

domain = 'facebook.com'
log = logging.getLogger(domain)

# this function is a derivative of:
# http://code.activestate.com/recipes/
#   146306-http-client-to-post-using-multipartform-data/
## {{{ http://code.activestate.com/recipes/146306/ (r1)


def encode_multipart_formdata(body):
    BOUNDARY = '----------$_BOUNDARY_' + str(random.getrandbits(128)) + '_$'
    CRLF = '\r\n'
    L = []
    for key in body:
        L.append('--' + BOUNDARY)
        L.append('Content-Disposition: form-data; name="%s"' % key)
        L.append('')
        L.append(body[key])
    L.append('--' + BOUNDARY + '--')
    L.append('')
    body = CRLF.join(L)
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    return content_type, body.encode('utf-8')


# borrowed from velruse
def extract_fb_data(data):
    #import sys; print >> sys.stderr, data
    # Setup the normalized poco contact object
    nick = None

    # Setup the nick and preferred username to the last portion of the
    # FB link URL if its not their ID
    # if a user sets up their personal link, they get a url that looks like:
    # https://www.facebook.com/mixedpuppy, otherwise they have something
    # like: http://www.facebook.com/profile.php?id=100001556529144
    link = data.get('link')
    if link:
        link = urlparse.urlparse(link)
        path = link.path[1:].split('/')[0]
        if (not link.query and path is not 'profile.php' and
            path is not data['id']):
            nick = path

    profile = {
        'providerName': 'Facebook',
        'identifier': 'https://graph.facebook.com/%s' % data['id'],
        'displayName': data['name'],
        'emails': [data.get('email')],
        'verifiedEmail': data.get('verified') and data.get('email'),
        'gender': data.get('gender'),
        'preferredUsername': nick or data['name'],
    }

    account = {'domain': 'facebook.com',
               'userid': data['id'],
               'username': nick or data['name']}
    profile['accounts'] = [account]

    tz = data.get('timezone')
    if tz:
        parts = str(tz).split(':')
        if len(parts) > 1:
            h, m = parts
        else:
            h, m = parts[0], '00'
        if len(h) >= 2:
            h = '%s0%s' % (h[0], h[1])
        data['utfOffset'] = ':'.join([h, m])
    bday = data.get('birthday')
    if bday:
        mth, day, yr = bday.split('/')
        profile['birthday'] = '-'.join([yr, mth, day])
    name = {}
    pcard_map = {'first_name': 'givenName', 'last_name': 'familyName'}
    for key, val in pcard_map.items():
        part = data.get(key)
        if part:
            name[val] = part
    name['formatted'] = data.get('name')

    profile['name'] = name

    # facebook gives us an absolute url, these work and redirect to their CDN
    profile['photos'] = [{'type': "thumbnail",
                          'value': "https://graph.facebook.com/" +
                                   data['id'] + "/picture?type=square"},
                          {'type': "profile",
                           'value': "https://graph.facebook.com/" +
                                    data['id'] + "/picture?type=large"}]

    # Now strip out empty values
    for k, v in profile.items():
        if not v or (isinstance(v, list) and not v[0]):
            del profile[k]

    return profile


class FacebookResponder(OAuth2):
    """Handle Facebook OAuth login/authentication"""

    profile_url = 'https://graph.facebook.com/me'
    domain = 'facebook.com'

    def __init__(self):
        OAuth2.__init__(self, domain)

    @classmethod
    def get_name(cls):
        return cls.domain

    def _get_credentials(self, access_token):
        profile_url = config.get("oauth.facebook.com.profile",
                                 self.profile_url)
        fields = ('id,first_name,last_name,name,link,birthday,email,'
                  'website,verified,picture,gender,timezone')
        client = HttpRequestor()
        url = build_url(profile_url, access_token=access_token, fields=fields)
        resp, content = client.request(url)
        if resp['status'] != '200':
            reason = "Error status: %r", resp['status']
            client.save_capture(reason)
            raise Exception(reason)

        try:
            fb_profile = json.loads(content)
        except ValueError:
            client.save_capture('non-json facebook 200 response')
            raise

        profile = extract_fb_data(fb_profile)
        result_data = {'profile': profile,
                      'oauth_token': access_token}

        return result_data


class FacebookRequester(object):
    def __init__(self, account):
        self.domain = domain
        self.account = account
        self.access_token = account.get('oauth_token')
        if not self.access_token:
            raise OAuthKeysException()

    @classmethod
    def get_name(cls):
        return domain

    def _make_error(self, client, data, resp):
        # Facebook makes error handling fun!  So much for standards.
        # handle the various error mechanisms they deliver and hope
        # something works. (this is in part, proper oauth2 error
        # handling, in part facebook oauth error handling and facebook
        # rest api error handling).

        # brainbook sends a 400 status to get us to authenticate, check
        # for the authenticate header, though its almost forgivable
        # considering the state of the oauth 2.0 draft text.  They FAIL
        # at getting the format of the value for www-authenticate correct
        # so we wont even bother with it, but the real error_code is
        # hidden within.
        if 'invalid_token' in resp.get('www-authenticate', ''):
            status = 401
        else:
            status = int(resp['status'])

        # this should be retreived from www-authenticate if provided there,
        # see above comments
        code = data.get('error_code', 0)

        # try oauth 2.0-10 first, facebook points to api libraries that
        # do it this way, perhaps some sandbox got updated.
        if 'error_description' in data:
            error = {
                 'message': data.get('error_description',
                                    'This is very descriptive'),
                 'uri': data.get('error_uri', ''),
                 'state': data.get('state', 'of decay'),
            }
        # now try what fb currenty gives us (i.e. oauth 2.0-00 kind of)
        elif isinstance(data.get('error', None), dict):
            error = copy.copy(data['error'])
        # fallback to their rest error message
        elif 'error_msg' in data:
            error = {
                 'message': data.get('error_msg', 'it\'s an error, kthx'),
            }
        # who knows, some other abberation
        else:
            client.save_capture('nonsensical response')
            error = {'message':
                    "expectedly, an unexpected facebook error: %r" % (data,)}
            log.error(error['message'])

        error.update({'code': code,
                      'provider': domain,
                      'status': status})
        return error

    def rawcall(self, url, body=None, method="GET", params=None):
        if params is None:
            params = {}
        params['access_token'] = self.access_token
        url = url + "?" + urllib.urlencode(params)
        headers = None
        if body:
            content_type, body = encode_multipart_formdata(body)
            headers = {'Content-type': content_type,
                       'Content-Length': str(len(body))}

        client = HttpRequestor()
        resp, content = client.request(url, method=method, headers=headers,
                                       body=body)

        try:
            data = json.loads(content)
        except ValueError, e:
            # json decode error, just call _make_error
            # _make_error will capture the response if it has trouble
            # making sense of it.
            return None, self._make_error(client, {'exception': str(e)}, resp)

        result = error = None
        if 'id' in data:
            result = data
            result[domain] = data['id']
        elif 'data' in data:
            result = data
            result[domain] = None
        else:
            error = self._make_error(client, data, resp)

        return result, error

    # feed supports message, picture, link, name, caption, description, source
    # map our stuff to theirs
    post_map = {
        'link': 'link',
        'title': 'name',
        'description': 'description',
        'picture': 'picture',
        'caption': 'caption',
        'source': 'source'}

    def sendmessage(self, message, options=None):
        if options is None:
            options = {}
        share_type = options.get('shareType', None)
        if share_type == 'groupWall':
            direct = options.get('to', None)
            if not direct:
                return None, {'code': 400, 'message': 'Wall name is missing'}
            url = "https://graph.facebook.com/%s/feed" % (direct,)
        elif share_type == 'wall':
            url = config.get("oauth.facebook.com.feed",
                             "https://graph.facebook.com/me/feed")
        else:
            return None, {'code': 400, 'message': 'Share type is missing'}
        body = {"message": message}
        for ours, yours in self.post_map.items():
            if ours in options:
                body[yours] = options[ours]

        return self.rawcall(url, body, "POST")

    def getcontacts(self, options=None):
        if options is None:
            options = {}
        offset = int(options.get('offset', 0))
        limit = int(options.get('limit', 25))
        type_ = options.get('type', 'groups')
        params = {
            'offset': offset,
            'limit': limit,
            'type': type_,
        }
        # using 'friends' would turn this into posting to a friends wall.
        url = "https://graph.facebook.com/me/%s" % type_
        result, error = self.rawcall(url, params=params)
        if error:
            return result, error

        groups = []
        for group in result['data']:
            groups.append({
                'displayName': group.get('name'),
                'type': type_,
                'accounts': [{'userid': group.get('id'),
                               'username': None, 'domain': domain}]})

        count = len(groups)
        connectedto = {
            'entry': groups,
            'itemsPerPage': count,
            'startIndex':   offset,
        }

        if count > 0:
            connectedto['pageData'] = {
                'offset': offset + count,
                'limit': limit,
                'type': type_,
            }

        return connectedto, None
