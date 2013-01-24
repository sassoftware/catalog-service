#
# Copyright (c) SAS Institute Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


import urlparse
import urllib

# This is copied from mint for testing purposes.

def urlSplit(url, defaultPort = None):
    """A function to split a URL in the format
    <scheme>://<user>:<pass>@<host>:<port>/<path>;<params>#<fragment>
    into a tuple
    (<scheme>, <user>, <pass>, <host>, <port>, <path>, <params>, <fragment>)
    Any missing pieces (user/pass) will be set to None.
    If the port is missing, it will be set to defaultPort; otherwise, the port
    should be a numeric value.
    """
    scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
    userpass, hostport = urllib.splituser(netloc)
    host, port = urllib.splitnport(hostport, None)
    if userpass:
        user, passwd = urllib.splitpasswd(userpass)
    else:
        user, passwd = None, None
    return scheme, user, passwd, host, port, path, \
        query or None, fragment or None

def urlUnsplit(urlTuple):
    """Recompose a split URL as returned by urlSplit into a single string
    """
    scheme, user, passwd, host, port, path, query, fragment = urlTuple
    userpass = None
    if user and passwd:
        userpass = urllib.quote("%s:%s" % (user, passwd), safe = ':')
    hostport = host
    if port:
        hostport = urllib.quote("%s:%s" % (host, port), safe = ':')
    netloc = hostport
    if userpass:
        netloc = "%s@%s" % (userpass, hostport)
    return urlparse.urlunsplit((scheme, netloc, path, query, fragment))
