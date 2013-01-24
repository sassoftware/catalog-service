#!/usr/bin/python
#
# Copyright (c) SAS Institute Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


from restlib import controller

from catalogService.rest.models import cloud_types

from catalogService.rest.api import cloud_help
from catalogService.rest.api import cloud_instances
from catalogService.rest.api import descriptor_controllers
from catalogService.rest.api.base import BaseController, BaseCloudController
from catalogService.rest.middleware.response import XmlResponse

class CloudTypeController(BaseCloudController):
    urls = {
        'instances' : cloud_instances.CloudTypeModelController,
        'descriptor' : descriptor_controllers.DescriptorController,
        'help' : cloud_help.CloudHelpController,
    }

SUPPORTED_MODULES = [ 'ec2', 'eucalyptus', 'openstack', 'vcloud', 'vmware', 'xenent' ]

class AllCloudController(BaseController):

    def index(self, request):
        cloudTypeNodes = cloud_types.CloudTypes()
        for cloudType, cloudController in sorted(self.urls.items()):
            if not cloudController.driver.isDriverFunctional():
                continue
            cloudTypeNodes.append(cloudController.driver(request).getCloudType())
        return XmlResponse(cloudTypeNodes)

    def loadCloudTypes(self):
        drivers = []
        self.urls = {}
        moduleDir =  __name__.rsplit('.', 2)[0] + '.drivers'
        for driverName in SUPPORTED_MODULES:
            # FIXME: I'm not sure why putting driver here instead of drivers
            # allows it this to work.
            driverClass = __import__('%s.%s' % (moduleDir, driverName),
                                      {}, {}, ['driver']).driver
            # XXX we should make this a class method
            cloudType = driverClass.cloudType
            driver = driverClass(self.storageCfg, driverName, db = self.db)
            controller =  CloudTypeController(self, cloudType,
                                              driver, self.storageCfg, self.db)
            self.urls[cloudType] = controller
