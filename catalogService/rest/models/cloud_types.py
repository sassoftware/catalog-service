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


import rpath_xmllib as xmllib

from catalogService.rest.models import instances
import xmlNode

class CloudType(xmlNode.BaseNode):
    tag = 'cloudType'
    __slots__ = [ 'id', 'description', 'cloudTypeName',
        'descriptorCredentials',
        'descriptorInstanceConfiguration',
        'cloudInstances' ]
    _slotAttributes = set(['id'])

class CloudTypes(xmlNode.BaseNodeCollection):
    tag = "cloudTypes"

class CloudInstances(xmlNode.BaseNode):
    tag = "cloudInstances"
    __slots__ = [ 'href' ]
    _slotAttributes = set(['href'])

class DescriptorCredentials(xmlNode.BaseNode):
    tag = "descriptorCredentials"
    __slots__ = [ 'href' ]
    _slotAttributes = set(['href'])

class DescriptorInstanceConfiguration(xmlNode.BaseNode):
    tag = "descriptorInstanceConfiguration"
    __slots__ = [ 'href' ]
    _slotAttributes = set(['href'])

class Handler(xmllib.DataBinder):
    cloudTypeClass = CloudType
    cloudTypesClass = CloudTypes
    cloudInstancesClass = CloudInstances
    descriptorCredentialsClass = DescriptorCredentials
    descriptorInstanceConfigurationClass = DescriptorInstanceConfiguration
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.cloudTypeClass, self.cloudTypeClass.tag)
        self.registerType(self.cloudTypesClass, self.cloudTypesClass.tag)
        self.registerType(self.cloudInstancesClass, self.cloudInstancesClass.tag)
        self.registerType(self.descriptorCredentialsClass,
            self.descriptorCredentialsClass.tag)
        self.registerType(self.descriptorInstanceConfigurationClass,
            self.descriptorInstanceConfigurationClass.tag)
