import mint.client
import mint.config
import mint.shimclient

from restlib.controller import RestController

from catalogService import userInfo
from catalogService.rest.response import XmlResponse, XmlStringResponse
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
        responseId = "%s/userinfo" % request.baseUrl
        response = userInfo.UserInfo(id = responseId,
            username = request.mintAuth.username,
            isAdmin = bool(request.mintAuth.admin))
        return XmlResponse(response)
