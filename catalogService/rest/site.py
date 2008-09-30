
from base import BaseHandler
import users
import clouds
from catalogService import instances

import mint.client
import mint.config
import mint.shimclient

from restlib.handler import RestHandler

class CatalogServiceController(RestHandler):
    urls = {'clouds' : clouds.AllCloudModelController,
            'users' : users.UsersController,
            'userinfo' : 'userinfo'}

    def __init__(self, parent, path, cfg, mintClient):
        RestHandler.__init__(self, parent, path, [cfg, mintClient])

    def _getController(self, url):
        return self.urls[url]

    def userinfo(self, response, request, parameters, url):
        data = "<userinfo><username>%s</username></userinfo>" % \
                parameters['mintAuth'].username
        response.write(data)


class SiteHandler(object):
    def __init__(self, auth, cfg):
        self.mintCfg = None
        self.mintClient = self._getMintClient(auth, cfg)
        self.restController = CatalogServiceController(None, None,
                                                       cfg, self.mintClient)
        self.restController._getController('clouds').loadCloudTypes(auth, cfg)


    def _getMintClient(self, authToken, cfg):
        if cfg.rBuilderUrl:
            mintClient = mint.client.MintClient(
                                        cfg.rBuilderUrl % tuple(authToken[:2]))
        else:
            mintCfg = mint.config.getConfig()
            mintClient = mint.shimclient.ShimMintClient(self.mintCfg, 
                                                             authToken)
        return mintClient


    def handle(self, response, request, parameters, url):
        try:
            mintAuth = self.mintClient.checkAuth()
            if not mintAuth.authorized:
                response.status = 403
                return
            else:
                parameters['mintAuth'] = mintAuth
                instances.Linker.baseUrl = request.baseUrl
            return self.restController.handle(response, request,
                                              parameters, url)
        except NotImplementedError:
            raise
        except Exception, e:
            raise
            import epdb
            import sys
            epdb.post_mortem(sys.exc_info()[2])

