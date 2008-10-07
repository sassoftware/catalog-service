import urllib

from base import BaseHandler, BaseModelHandler
from catalogService import clouds
from catalogService import environment
from catalogService import images
from catalogService import instances
from catalogService import keypairs
from catalogService import nodeFactory
from catalogService import securityGroups

class CloudIdMixIn(object):
    def getCloudName(self, parameters):
        cloudName = parameters['cloudName']
        cloudName = urllib.unquote(cloudName)
        if not self.driver.isValidCloudName(cloudName):
            raise UnsupportedCloudId(cloudName)
        return cloudName

class BaseCloudController(BaseHandler, CloudIdMixIn):
    "Base class for Cloud Controllers"

class BaseCloudModelController(BaseModelHandler, CloudIdMixIn):
    "Base class for Cloud Model Controllers"

class ImagesController(BaseCloudModelController):
    paramName = 'imageId'
    def index(self, response, request, parameters, url):
        cloudName = self.getCloudName(parameters)
        imgNodes = self.driver.getAllImages(cloudName)
        response.to_xml(imgNodes)

class InstancesController(BaseCloudModelController):
    paramName = 'instanceId'
    def index(self, response, request, parameters, url):
        cloudName = self.getCloudName(parameters)
        insts = self.driver.getAllInstances(cloudName)
        response.to_xml(insts)

    def create(self, response, request, parameters, url):
        "launch a new instance"
        cloudName = self.getCloudName(parameters)
        instances = self.driver.launchInstance(cloudName, request.read(),
                                               request.host)
        response.to_xml(instances)

    def destroy(self, instanceId, response, request, parameters, url):
        cloudName = self.getCloudName(parameters)
        instances = self.driver.terminateInstance(cloudName, instanceId)
        response.to_xml(instances)

class InstanceTypesController(BaseCloudModelController):
    paramName = 'instanceTypeId'

    def index(self, response, request, parameters, url):
        cloudName = self.getCloudName(parameters)
        instTypes = self.driver.getInstanceTypes()
        response.to_xml(instTypes)

class UserEnvironmentController(BaseCloudModelController):
    paramName = 'userName'
    def index(self, response, request, parameters, url):
        cloudName = self.getCloudName(parameters)
        response.to_xml(self.driver.getEnvironment())


class UsersController(BaseCloudModelController):
    paramName = 'userName'

    urls = dict(environment = UserEnvironmentController)

class CloudTypeModelController(BaseModelHandler):

    paramName = 'cloudName'

    urls = dict(images = ImagesController,
                instances = InstancesController,
                users = UsersController,
                instanceTypes = InstanceTypesController)

    def __init__(self, parent, path, driver, cfg, mintClient):
        BaseModelHandler.__init__(self, parent, path, driver, cfg, mintClient)

    def index(self, response, request, paramaters, url):
        'iterate available clouds'
        response.to_xml(self.driver.listClouds())

SUPPORTED_MODULES = ['ec2', 'vws']

class AllCloudModelController(BaseHandler):

    paramName = 'cloudType'

    def index(self, response, request, parameters, url):
        cloudNodes = clouds.BaseClouds()
        for cloudType, cloudController in sorted(self.urls.items()):
            cloudNodes.extend(cloudController.driver.listClouds())
        response.to_xml(cloudNodes)

    def loadCloudTypes(self, auth, cfg):
        drivers = []
        self.urls = {}
        moduleDir =  __name__.rsplit('.', 1)[0] + '.drivers'
        for driverName in SUPPORTED_MODULES:
            driverClass = __import__('%s.%s' % (moduleDir, driverName),
                                      {}, {}, ['drivers']).driver
            nodeFact = nodeFactory.NodeFactory(
                cloudFactory = getattr(driverClass, 'Cloud',
                    clouds.BaseCloud),
                imageFactory = getattr(driverClass, 'Image',
                    images.BaseImage),
                instanceFactory = getattr(driverClass, 'Instance',
                    instances.BaseInstance),
                instanceTypeFactory = getattr(driverClass, 'InstanceType',
                    instances.InstanceType),
                environmentFactory = getattr(driverClass, 'Environment',
                    environment.BaseEnvironment),
                environmentCloudFactory = getattr(driverClass, 'EnvironmentCloud',
                    environment.BaseCloud),
                keyPairFactory = getattr(driverClass, 'KeyPair',
                    keypairs.BaseKeyPair),
                securityGroupFactory = getattr(driverClass, 'SecurityGroup',
                    securityGroups.BaseSecurityGroup),
            )
            driver = driverClass(self.mintClient, cfg, nodeFact)
            controller =  CloudTypeModelController(self, driverName,
                                                   driver, self.cfg,
                                                   self.mintClient)
            self.urls[driverName] = controller

    def _updateController(self, controller, paramName, response, request):
        if isinstance(controller, CloudTypeModelController):
            controller.driver.urlParams = request.urlParams

