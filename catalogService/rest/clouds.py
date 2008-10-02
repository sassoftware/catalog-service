import urllib

from base import BaseHandler, BaseModelHandler
from catalogService import clouds
from catalogService import images
from catalogService import instances
from catalogService import nodeFactory

class ImagesController(BaseModelHandler):
    paramName = 'imageId'
    def index(self, response, request, parameters, url):
        cloudId = parameters['cloudId']
        imgNodes = self.driver.getAllImages(cloudId)
        response.to_xml(imgNodes)

class InstancesController(BaseModelHandler):
    paramName = 'instanceId'
    def index(self, response, request, parameters, url):
        cloudId = parameters['cloudId']
        insts = self.driver.getAllInstances(cloudId)
        response.to_xml(insts)

    def create(self, response, request, parameters, url):
        "launch a new instance"
        cloudId = parameters['cloudId']
        cloudId = urllib.unquote(cloudId)
        instances = self.driver.launchInstance(cloudId, request.read(),
                                               request.host)
        response.to_xml(instances)

    def destroy(self, instanceId, response, request, parameters, url):
        cloudId = parameters['cloudId']
        cloudId = urllib.unquote(cloudId)
        instances = self.driver.terminateInstance(cloudId, instanceId)
        response.to_xml(instances)

class CloudTypeModelController(BaseModelHandler):

    paramName = 'cloudId'

    urls = {'images' : ImagesController,
            'instances' : InstancesController }

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
            )
            driver = driverClass(self.mintClient, cfg, nodeFact)
            controller =  CloudTypeModelController(self, driverName,
                                                   driver, self.cfg,
                                                   self.mintClient)
            self.urls[driverName] = controller
