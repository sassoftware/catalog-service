import base64

from restlib import response

import mint.client
import mint.config
import mint.shimclient

class AuthenticationCallback(object):

    def __init__(self, cfg):
        self.cfg = cfg

    def processRequest(self, request):
        if not 'Authorization' in request.headers:
            # require authentication
            return response.Response(status=403)
        type, user_pass = request.headers['Authorization'].split(' ', 1)
        user_name, password = base64.decodestring(user_pass).split(':', 1)
        request.auth = (user_name, password)
        response = self.setMintClient(request)
        # will be None if successful
        return response

    def setMintClient(self, request):
        if self.cfg.rBuilderUrl:
            mintClient = mint.client.MintClient(
                            self.cfg.rBuilderUrl % tuple(request.auth[:2]))
        else:
            mintCfg = mint.config.getConfig()
            mintClient = mint.shimclient.ShimMintClient(mintCfg,
                                                        request.auth)
        mintAuth = mintClient.checkAuth()
        if not mintAuth.authorized:
            return response.Response(status=403)
        request.mintClient = mintClient
        request.mintAuth = mintAuth
