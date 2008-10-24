from restlib import controller

from base import BaseController

from catalogService import cloud_types

from catalogService.rest import cloud_instances
from catalogService.rest import descriptor_controllers
from catalogService.rest.base_cloud import BaseCloudController
from catalogService.rest.response import XmlResponse

class CloudTypeController(BaseCloudController):
    urls = {
        'instances' : cloud_instances.CloudTypeModelController,
        'descriptor' : descriptor_controllers.DescriptorController,
    }

SUPPORTED_MODULES = ['ec2', 'vws', 'xenent' ]

class AllCloudController(BaseController):

    def index(self, request):
        cloudTypeNodes = cloud_types.CloudTypes()
        for cloudType, cloudController in sorted(self.urls.items()):
            cloudTypeNodes.append(cloudController.driver(request).getCloudType())
        return XmlResponse(cloudTypeNodes)

    def loadCloudTypes(self):
        drivers = []
        self.urls = {}
        moduleDir =  __name__.rsplit('.', 1)[0] + '.drivers'
        for driverName in SUPPORTED_MODULES:
            # FIXME: I'm not sure why putting driver here instead of drivers
            # allows it this to work.
            driverClass = __import__('%s.%s' % (moduleDir, driverName),
                                      {}, {}, ['driver']).driver
            # XXX we should make this a class method
            driverName = driverClass._cloudType
            driver = driverClass(self.cfg, driverName)
            controller =  CloudTypeController(self, driverName,
                                              driver, self.cfg)
            self.urls[driverName] = controller
