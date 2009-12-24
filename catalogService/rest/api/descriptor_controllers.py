#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

from catalogService.rest.api.base import BaseCloudController
from catalogService.rest.middleware.response import XmlResponse

class CredentialsDescriptorController(BaseCloudController):
    def index(self, request):
        return XmlResponse(self.driver.getCredentialsDescriptor())

class ConfigurationDescriptorController(BaseCloudController):
    def index(self, request):
        return XmlResponse(self.driver(request).getCloudConfigurationDescriptor())

class DescriptorController(BaseCloudController):
    urls = dict(
        credentials = CredentialsDescriptorController,
        configuration = ConfigurationDescriptorController,
    )
