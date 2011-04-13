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
# Contributor(s): Tarek Ziade <tarek@mozilla.com>
#

class BadVersionError(Exception):
    pass


class BackendError(Exception):
    """Happens when there was a problem with the
    third-party service failed
    """

class DomainNotRegisteredError(Exception):
    pass


class OptionError(Exception):
    pass


class StatusReadError(Exception):
    pass


class StatusWriteError(Exception):
    pass


class OAuthKeysException(Exception):
    pass


class AccessException(Exception):
    pass


class ServiceUnavailableException(Exception):
    def __init__(self, debug_message=None):
        self.debug_message = debug_message
