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


import base64
from mint import mint_error
from restlib.response import Response

# Decorator for public (unauthenticated) methods/functions
def public(deco):
    deco.public = True
    return deco

# Decorator for admin (authenticated) methods/functions
def admin(deco):
    deco.admin = True
    return deco

class AuthenticationCallback(object):
    def __init__(self, cfg, db, controller):
        self.cfg = cfg
        self.db = db
        self.controller = controller

    def getAuth(self, request):
        if not 'Authorization' in request.headers:
            return None
        type, user_pass = request.headers['Authorization'].split(' ', 1)
        try:
            user_name, password = base64.decodestring(user_pass).split(':', 1)
            return (user_name, password)
        except (base64.binascii.Error, ValueError):
            raise mint_error.AuthHeaderError

    def processRequest(self, request):
        token = self.getAuth(request)
        if not token:
            request.auth = request.mintAuth = None
            return None
        username, password = token
        request.auth = token
        mintAuth = self.db.db.users.checkAuth((username, password))
        mintAuth = Authorization(**mintAuth)
        request.mintAuth = mintAuth
        self.db.setAuth(mintAuth, request.auth)
        self.db.siteAuth = False

    def processMethod(self, request, viewMethod, args, kwargs):
        if request.mintAuth is None:
            if 'HTTP_X_FLASH_VERSION' in request.headers:
                return Response(status=403)
            return Response(status=401,
               headers={'WWW-Authenticate' : 'Basic realm="rBuilder"'})

class Authorization(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
