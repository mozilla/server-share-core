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
import os
import sgmllib
import string
import sys
from urllib import urlencode

from webob.exc import status_map
from webhelpers.html import literal
from paste.registry import StackedObjectProxy
from paste.config import DispatchingConfig
from mako.lookup import TemplateLookup


def redirect(url, code=302):
    """Raises a redirect exception to the specified URL

    Optionally, a code variable may be passed with the status code of
    the redirect, ie::

        redirect(url(controller='home', action='index'), code=303)

    """
    exc = status_map[code]
    raise exc(location=url).exception


def asbool(obj):
    if isinstance(obj, (str, unicode)):
        obj = obj.strip().lower()
        if obj in ['true', 'yes', 'on', 'y', 't', '1']:
            return True
        elif obj in ['false', 'no', 'off', 'n', 'f', '0']:
            return False
        else:
            raise ValueError(
                "String is not true/false: %r" % obj)
    return bool(obj)


_TMPLDIR = os.path.join(os.path.dirname(__file__), 'templates')
# XXX
_CACHEDIR = '/tmp'


def _handle_mako_error(context, exc):
    try:
        exc.is_mako_exception = True
    except:
        pass
    raise exc, None, sys.exc_info()[2]   # NOQA


_LOOKUP = TemplateLookup(
        directories=_TMPLDIR,
        error_handler=_handle_mako_error,
        module_directory=os.path.join(_CACHEDIR, 'templates'),
        input_encoding='utf-8', default_filters=['escape'],
        imports=['from webhelpers.html import escape'])


def render(template_name, extra_vars=None, cache_key=None,
           cache_type=None, cache_expire=None):
    """Render a template with Mako

    Accepts the cache options ``cache_key``, ``cache_type``, and
    ``cache_expire``.

    """
    # Create a render callable for the cache function
    def render_template():
        # Pull in extra vars if needed
        globs = extra_vars or {}

        # Grab a template reference
        template = _LOOKUP.get_template(template_name)

        return literal(template.render_unicode(**globs))

    return _cached_template(template_name, render_template,
                            cache_key=cache_key,
                            cache_type=cache_type, cache_expire=cache_expire)


_CACHE = StackedObjectProxy(name="cache")


def build_url(url, **params):
    return '%s?%s' % (url, urlencode(params))


config = DispatchingConfig()


def setup_config(appconfig):
    config.push_process_config(appconfig)


def _cached_template(template_name, render_func, ns_options=(),
                    cache_key=None, cache_type=None, cache_expire=None,
                    **kwargs):
    # If one of them is not None then the user did set something
    if cache_key is not None or cache_expire is not None or cache_type \
        is not None:

        if not cache_type:
            cache_type = 'dbm'
        if not cache_key:
            cache_key = 'default'
        if cache_expire == 'never':
            cache_expire = None
        namespace = template_name
        for name in ns_options:
            namespace += str(kwargs.get(name))
        cache = _CACHE.get_cache(namespace, type=cache_type)
        content = cache.get_value(cache_key, createfunc=render_func,
            expiretime=cache_expire)
        return content
    else:
        return render_func()

## {{{ http://code.activestate.com/recipes/52281/ (r1) PSF License


class StrippingParser(sgmllib.SGMLParser):

    # These are the HTML tags that we will leave intact
    valid_tags = ('b', 'a', 'i', 'br', 'p')

    def __init__(self):
        sgmllib.SGMLParser.__init__(self)
        self.result = ""
        self.endTagList = []

    def handle_data(self, data):
        if data:
            self.result = self.result + data

    def handle_charref(self, name):
        self.result = "%s&#%s;" % (self.result, name)

    def handle_entityref(self, name):
        if self.entitydefs.has_key(name):      # NOQA
            x = ';'
        else:
            # this breaks unstandard entities that end with ';'
            x = ''
        self.result = "%s&%s%s" % (self.result, name, x)

    def unknown_starttag(self, tag, attrs):
        """ Delete all tags except for legal ones """
        if tag in self.valid_tags:
            self.result = self.result + '<' + tag
            for k, v in attrs:
                if (string.lower(k[0:2]) != 'on' and
                    string.lower(v[0:10]) != 'javascript'):
                    self.result = '%s %s="%s"' % (self.result, k, v)
            endTag = '</%s>' % tag
            self.endTagList.insert(0, endTag)
            self.result = self.result + '>'

    def unknown_endtag(self, tag):
        if tag in self.valid_tags:
            self.result = "%s</%s>" % (self.result, tag)
            remTag = '</%s>' % tag
            self.endTagList.remove(remTag)

    def cleanup(self):
        """ Append missing closing tags """
        for j in range(len(self.endTagList)):
                self.result = self.result + self.endTagList[j]


def safeHTML(s):
    """ Strip illegal HTML tags from string s """
    parser = StrippingParser()
    parser.feed(s)
    parser.close()
    parser.cleanup()
    return parser.result
## end of http://code.activestate.com/recipes/52281/ }}}
