import urllib

from base import BaseHandler, BaseModelHandler
from catalogService import images,instances

class ImagesController(BaseModelHandler):
    paramName = 'imageId'
    def index(self, response, request, parameters, url):
        cloudId = parameters['cloudId']
        images = self.driver.getAllImages(cloudId)
        response.to_xml(images)

class InstancesController(BaseModelHandler):
    paramName = 'instanceId'
    def index(self, response, request, parameters, url):
        cloudId = parameters['cloudId']
        instances = self.driver.getAllInstances(cloudId)
        response.to_xml(instances)

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

    def index(self, request, response, paramaters, url):
        'iterate available clouds'
        clouds = []
        for cloudId in self.driver.listClouds():
            cloud = {'cloudId' : cloudId, url : self.url(request, cloudId)}
        response.to_xml({'clouds' : clouds, 
                         'metadata' : self.url(request, 'metadata')})

SUPPORTED_MODULES = ['ec2', 'vws']

class AllCloudModelController(BaseHandler):

    paramName = 'cloudType'

    def index(self, request, response, parameters, url):
        self.to_xml([{'id' : x, 'url' : self.url(request, x)}
                     for x in self.urls.keys()])

    def loadCloudTypes(self, auth, cfg):
        drivers = []
        self.urls = {}
        moduleDir =  __name__.rsplit('.', 1)[0] + '.drivers'
        for driverName in SUPPORTED_MODULES:
            driverClass = __import__('%s.%s' % (moduleDir, driverName),
                                     {}, {}, ['drivers']).driver
            instanceFactory = instances.InstanceFactory()
            imageFactory = images.ImageFactory()
            driver = driverClass(self.mintClient, cfg,
                                 instanceFactory, imageFactory)
            controller =  CloudTypeModelController(self, driverName,
                                                   driver, self.cfg,
                                                   self.mintClient)
            self.urls[driverName] = controller
