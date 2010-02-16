#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
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
