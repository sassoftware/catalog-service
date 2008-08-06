#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

import xmlNode

from catalogService import instances
from catalogService import keypairs
from catalogService import securityGroups

class BaseCloud(xmlNode.BaseNode):
    tag = 'cloud'
    __slots__ = [ 'id', 'cloudName', 'cloudType', 'cloudAlias',
                  'instanceTypes', 'keyPairs', 'securityGroups' ]

class BaseEnvironment(xmlNode.BaseNodeCollection):
    tag = 'environment'

class Handler(xmllib.DataBinder):
    keyPairClass = keypairs.BaseKeyPair
    keyPairsClass = keypairs.BaseKeyPairs
    instanceTypeClass = instances.InstanceType
    instanceTypesClass = instances.InstanceTypes
    securityGroupClass = securityGroups.BaseSecurityGroup
    securityGroupsClass = securityGroups.BaseSecurityGroups
    cloudClass = BaseCloud
    environmentClass = BaseEnvironment
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.cloudClass, self.cloudClass.tag)
        self.registerType(self.environmentClass, self.environmentClass.tag)
        self.registerType(self.keyPairClass, self.keyPairClass.tag)
        self.registerType(self.keyPairsClass, self.keyPairsClass.tag)
        self.registerType(self.instanceTypeClass, self.instanceTypeClass.tag)
        self.registerType(self.instanceTypesClass, self.instanceTypesClass.tag)
        self.registerType(self.securityGroupClass, self.securityGroupClass.tag)
        self.registerType(self.securityGroupsClass, self.securityGroupsClass.tag)
