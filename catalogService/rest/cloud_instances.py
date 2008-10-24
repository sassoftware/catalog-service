
import urllib

from catalogService import credentials

from catalogService.rest.base_cloud import BaseCloudController
from catalogService.rest.response import XmlResponse, XmlStringResponse

class ImagesController(BaseCloudController):
    modelName = 'imageId'

    def index(self, request, cloudName):
        imgNodes = self.driver(request, cloudName).getAllImages()
        return XmlResponse(imgNodes)

class InstancesController(BaseCloudController):
    modelName = 'instanceId'
    def index(self, request, cloudName):
        insts = self.driver(request, cloudName).getAllInstances()
        return XmlResponse(insts)

    def create(self, request, cloudName):
        "launch a new instance"
        insts = self.driver(request, cloudName).launchInstance(request.read(),
                                                               request.host)
        return XmlResponse(insts)

    def destroy(self, request, cloudName, instanceId):
        insts = self.driver(request, cloudName).terminateInstance(instanceId)
        return XmlResponse(insts)

class InstanceTypesController(BaseCloudController):
    modelName = 'instanceTypeId'

    def index(self, request, cloudName):
        return XmlResponse(self.driver(request, cloudName).getInstanceTypes())

class UserEnvironmentController(BaseCloudController):
    def index(self, request, cloudName, userName):
        if userName != request.auth[0]:
            return XmlStringResponse("", status = 403)
        return XmlResponse(self.driver(request, cloudName).getEnvironment())

class CredentialsController(BaseCloudController):
    def index(self, request, cloudName, userName):
        if userName != request.auth[0]:
            return XmlStringResponse("", status = 403)
        return XmlResponse(self.driver(request, cloudName).getUserCredentials())

    def update(self, request, cloudName, userName):
        if userName != request.auth[0]:
            return XmlStringResponse("", status = 403)
        dataLen = request.getContentLength()
        data = request.read(dataLen)

        return XmlResponse(self.driver(request, cloudName).setUserCredentials(
            data))

class ConfigurationController(BaseCloudController):
    def index(self, request, cloudName):
        return XmlResponse(self.driver(request, cloudName).getConfiguration())

class UsersController(BaseCloudController):
    modelName = 'userName'

    urls = dict(environment = UserEnvironmentController,
                credentials = CredentialsController)


class CloudTypeModelController(BaseCloudController):

    modelName = 'cloudName'

    urls = dict(configuration = ConfigurationController,
                images = ImagesController,
                instances = InstancesController,
                users = UsersController,
                instanceTypes = InstanceTypesController)

    def splitId(self, url):
        cloudName, rest = BaseCloudController.splitId(self, url)
        cloudName = urllib.unquote(cloudName)
        # note - may want to do further validation at the time of
        # passing the cloud name into the function...
        if not self.driver.isValidCloudName(cloudName):
            raise UnsupportedCloudId(cloudName)
        return cloudName, rest

    def index(self, request):
        'iterate available clouds'
        return XmlResponse(self.driver(request).listClouds())

    def create(self, request):
        return XmlResponse(self.driver(request).createCloud(request.read()))

