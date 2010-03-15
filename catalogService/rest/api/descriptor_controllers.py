#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import StringIO
from catalogService.rest.api.base import BaseCloudController
from catalogService.rest.middleware.response import XmlSerializableObjectResponse

class CredentialsDescriptorController(BaseCloudController):
    def index(self, request):
        descr = self.driver.getCredentialsDescriptor()
        return XmlSerializableObjectResponse(descr)

class ConfigurationDescriptorController(BaseCloudController):
    def index(self, request):
        descr = self.driver(request).getCloudConfigurationDescriptor()
        return XmlSerializableObjectResponse(descr)

class DescriptorController(BaseCloudController):
    urls = dict(
        credentials = CredentialsDescriptorController,
        configuration = ConfigurationDescriptorController,
    )
