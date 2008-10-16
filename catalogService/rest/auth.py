import base64

from restlib import response

import mint.client
import mint.config
import mint.shimclient

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
        auth = self.getAuthToken(request):
        if not auth:
            # require authentication
            return response.Response(status=403)
        request.auth = auth
        response = self.setMintClient(request)
        # will be None if successful
        return response

    def getMintConfig(self):
        return mint.config.getConfig()

    def setMintClient(self, request, auth):
        if self.cfg.rBuilderUrl:
            mintClient = mint.client.MintClient(
                            self.cfg.rBuilderUrl % tuple(auth[:2]))
        else:
            mintCfg = self.getMintConfig()
            mintClient = mint.shimclient.ShimMintClient(mintCfg,
                                                        auth)
        mintAuth = mintClient.checkAuth()
        if not mintAuth.authorized:
            return response.Response(status=403)
        request.mintClient = mintClient
        request.mintAuth = mintAuth
