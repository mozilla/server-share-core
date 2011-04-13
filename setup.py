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
from setuptools import setup, find_packages

VERSION = '0.1'

setup(
    name='linkoauth',
    version=VERSION,
    description='F1 core lib',
    author='Mozilla Messaging',
    author_email='linkdrop@googlegroups.com',
    url='http://f1.mozillamessaging.com/',
    install_requires=[
        "httplib2",
        "oauth2",
        "python-dateutil",
        "python-openid",
        "gdata",   # google api support
        "twitter>=1.4.2",
        "Paste",
        "Mako",
        "WebOb",
        "WebHelpers",
        "simplejson",
        "nose",
        "pylibmc",
        "Services"],
    packages=find_packages(exclude=['ez_setup']),
    include_package_data=True,
    test_suite='nose.collector',
    zip_safe=False)
