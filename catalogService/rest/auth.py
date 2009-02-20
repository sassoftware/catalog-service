import base64

from restlib import response

import mint.client
import mint.config
import mint.shimclient

# Decorator for public (unauthenticated) methods/functions
def public(deco):
    deco.public = True
    return deco

class AuthenticationCallback(object):

    def __init__(self, cfg):
        self.cfg = cfg

    def getAuth(self, request):
        if not 'Authorization' in request.headers:
            return None
        type, user_pass = request.headers['Authorization'].split(' ', 1)
        user_name, password = base64.decodestring(user_pass).split(':', 1)
        return (user_name, password)

    def processRequest(self, request):
        auth = self.getAuth(request)
        request.auth = auth
        response = self.setMintClient(request, auth)
        # will be None if successful
        return response

    def processMethod(self, request, viewMethod, args, kwargs):
        if getattr(viewMethod, 'public', None) or request.mintAuth is not None:
            return
        return response.Response(status=403)

    def getMintConfig(self):
        return mint.config.getConfig()

    def setMintClient(self, request, auth):
        request.mintClient = None
        request.mintAuth = None

        if auth is None:
            # Not authenticated
            return

        if self.cfg.rBuilderUrl:
            mintClient = mint.client.MintClient(
                            self.cfg.rBuilderUrl % tuple(auth[:2]))
        else:
            mintCfg = self.getMintConfig()
            mintClient = mint.shimclient.ShimMintClient(mintCfg,
                                                        auth)
        mintAuth = mintClient.checkAuth()
        if not mintAuth.authorized:
            # Bad auth info
            return
        request.mintClient = mintClient
        request.mintAuth = mintAuth
