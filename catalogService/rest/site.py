import mint.client
import mint.config
import mint.shimclient

from restlib.controller import RestController

from catalogService.rest.response import XmlStringResponse
from catalogService.rest import users
from catalogService.rest import clouds

class CatalogServiceController(RestController):
    urls = {'clouds' : clouds.AllCloudController,
            'users' : users.UsersController,
            'userinfo' : 'userinfo'}

    def __init__(self, cfg):
        RestController.__init__(self, None, None, [cfg])
        self.loadCloudTypes()

    def loadCloudTypes(self):
        self._getController('clouds').loadCloudTypes()


    def _getController(self, url):
        return self.urls[url]

    def userinfo(self, request):
        data = "<userinfo><username>%s</username></userinfo>" % request.mintAuth.username
        return XmlStringResponse(data)
