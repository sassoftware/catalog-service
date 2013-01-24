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
