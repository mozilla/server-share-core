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

from webob.exc import HTTPRedirection
from services.pluginreg import PluginRegistry

from linkoauth.backends import facebook_, google_, twitter_, yahoo_, linkedin_
from linkoauth.sstatus import ServicesStatus
from linkoauth.errors import BackendError, DomainNotRegisteredError
from linkoauth.errors import OAuthKeysException

#from linkoauth.live_ import LiveResponder
#from linkoauth.openidconsumer import OpenIDResponder

__all__ = ['Responder', 'get_responder', 'Requester', 'get_requester',
           'Services']


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

    @abc.abstractmethod
    def verify(self, request, url, session):
        """Returns an account object

        Args:
            request: WebOb request object
            url: Routes URL generator callable
            session: Session object

        Returns:
            return json object
        """

# pre-register provided backends
Responder.register(twitter_.TwitterResponder)
Responder.register(facebook_.FacebookResponder)
Responder.register(google_.GoogleResponder)
Responder.register(yahoo_.YahooResponder)
Responder.register(linkedin_.responder)


def get_responder(domain, **kw):
    try:
        return Responder.get(domain, **kw)
    except KeyError:
        raise DomainNotRegisteredError(domain)


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
Requester.register(twitter_.TwitterRequester)
Requester.register(facebook_.FacebookRequester)
Requester.register(google_.GoogleRequester)
Requester.register(yahoo_.YahooRequester)
Requester.register(linkedin_.api)


def get_requester(domain, account, **kw):
    try:
        return Requester.get(domain, account=account, **kw)
    except KeyError:
        raise DomainNotRegisteredError(domain)
    except TypeError, e:
        # XXX We get a TypeError if the oauth values are bad, but are there any
        # other cases which will generate a TypeError?  The string check here
        # is a weak attempt at preventing other TypeErrors from getting turned
        # into OAuthKeysExceptions.
        if "could not load" in str(e):
            raise OAuthKeysException('OAuth values problem w/ %s' % domain)
        else:
            raise


# high-level
class Services(ServicesStatus):

    def __init__(self, services, servers=None, ttl=600,
                 feedback_enabled=True):
        requesters = [req.get_name() for req in Requester._abc_registry]
        responders = [res.get_name() for res in Responder._abc_registry]

        for service in services:
            if service not in requesters:
                raise DomainNotRegisteredError(service)

            if service not in responders:
                raise DomainNotRegisteredError(service)

        self.feedback_enabled = feedback_enabled
        ServicesStatus.__init__(self, services, servers, ttl)

    def _updated(func):
        def __updated(self, domain, *args, **kw):
            domain = str(domain)
            try:
                res = func(self, domain, *args, **kw)
            except BackendError, e:
                if self.feedback_enabled:
                    self.update_status(domain, False)
                return None, e.args[0]
            except HTTPRedirection:
                if self.feedback_enabled:
                    self.update_status(domain, True)
                raise
            else:
                if (len(res) == 2 and res[0] is not None and
                    self.feedback_enabled):
                    self.update_status(domain, True)
            return res
        return __updated

    @_updated
    def sendmessage(self, domain, account, message, options={}, **kw):
        return get_requester(domain, account).sendmessage(message, options,
                                                          **kw)

    @_updated
    def getcontacts(self, domain, account, start=0, page=25, group=None, **kw):
        return get_requester(domain, account, **kw).getcontacts(start, page,
                                                                group)

    def request_access(self, domain, request, url, session, **kw):
        return get_responder(domain, **kw).request_access(request, url,
                                                          session)

    def verify(self, domain, request, url, session, **kw):
        return get_responder(domain, **kw).verify(request, url,
                                                          session)
