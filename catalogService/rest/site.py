import mint.client
import mint.config
import mint.shimclient

from catalogService import userInfo
from catalogService import serviceInfo
from catalogService.rest.response import XmlResponse
from catalogService.rest import base
from catalogService.rest import jobs
from catalogService.rest import users
from catalogService.rest import clouds

class CatalogServiceController(base.BaseController):
    urls = {'clouds' : clouds.AllCloudController,
            'users' : users.UsersController,
            'userinfo' : 'userinfo',
            'serviceinfo' : 'serviceinfo',
            'jobs' : jobs.JobsController, }

    def __init__(self, cfg):
        base.BaseController.__init__(self, None, None, cfg)
        self.loadCloudTypes()

    def loadCloudTypes(self):
        self._getController('clouds').loadCloudTypes()

    def _getController(self, url):
        return self.urls[url]

    def userinfo(self, request):
        responseId = self.url(request, "userinfo")
        response = userInfo.UserInfo(id = responseId,
            username = request.mintAuth.username,
            isAdmin = bool(request.mintAuth.admin))
        return XmlResponse(response)
    
    def serviceinfo(self, request):
        responseId = self.url(request, "serviceinfo")
        # TODO:  Get proper version/type in here.  See RBL-4191.
        # For type, client needs "full", "limited", or "disabled"
        response = serviceInfo.ServiceInfo(id = responseId,
            version = "1",
            type = "full")
        return XmlResponse(response)
