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
import abc
from services.pluginreg import PluginRegistry

from linkoauth import facebook_, google_, twitter_, yahoo_, linkedin_
#from linkoauth.live_ import LiveResponder
#from linkoauth.openidconsumer import OpenIDResponder

__all__ = ['get_provider']

# XXX need a better way to do this
_providers = {
    twitter_.domain:  twitter_,
    facebook_.domain: facebook_,
    google_.domain: google_,
    "googleapps.com": google_,
    yahoo_.domain: yahoo_,
    linkedin_.domain: linkedin_
}


class Responder(PluginRegistry):
    """Abstract Base Class for the responder APIs."""
    plugin_type = 'responder'

    @abc.abstractmethod
    def get_name(self):
        """Returns the name of the plugin."""

    @abc.abstractmethod
    def request_access(self, request, url, session):
        """Returns a redirect url

        Args:
            request: WebOb request object
            url: Routes URL generator callable
            session: Session object

        Returns:
            return url
        """

# pre-register provided backends
Responder.register(twitter_.responder)
Responder.register(facebook_.responder)
Responder.register(google_.responder)
Responder.register(yahoo_.responder)
Responder.register(linkedin_.responder)


def get_responder(domain, **kw):
    return Responder.get(domain, **kw)


class Requester(PluginRegistry):
    """Abstract Base Class for the requester APIs."""
    plugin_type = 'requester'

    @abc.abstractmethod
    def get_name(self):
        """Returns the name of the plugin."""

    @abc.abstractmethod
    def sendmessage(self, message, options={}):
        """xxx"""

    @abc.abstractmethod
    def getcontacts(self, start=0, page=25, group=None):
        """xxx"""


# pre-register provided backends
Requester.register(twitter_.api)
Requester.register(facebook_.FacebookRequester)
Requester.register(google_.GoogleRequester)
Requester.register(yahoo_.api)
Requester.register(linkedin_.api)


def get_requester(domain, account, **kw):
    return Requester.get(domain, account=account, **kw)


#
# XXX to be removed
#
def get_providers():
    """Returns provider names"""
    return _providers.keys()

def get_provider(provider):
    return _providers.get(provider)
