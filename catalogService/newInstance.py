#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

from catalogService import images
from catalogService import instances
from catalogService import keypairs
from catalogService import securityGroups
from catalogService import xmlNode

class BaseCount(xmlNode.xmllib.IntegerNode):
    pass

class BaseNewInstance(xmlNode.BaseNode):
    tag = 'newInstance'
    __slots__ = [ 'image', 'minCount', 'maxCount', 'keyPair',
                  'securityGroups', 'userData', 'instanceType',
                  'duration', 'remoteIp' ]

    def __repr__(self):
         return "<%s:image=%s at %#x>" % (self.__class__.__name__,
            self.getImage(), id(self))

class Handler(xmllib.DataBinder):
    countClass = BaseCount
    newInstanceClass = BaseNewInstance
    keyPairClass = keypairs.BaseKeyPair
    imageClass = images.BaseImage
    instanceTypeClass = instances.InstanceType
    securityGroupClass = securityGroups.BaseSecurityGroup
    securityGroupsClass = securityGroups.BaseSecurityGroups

    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.countClass, 'minCount')
        self.registerType(self.countClass, 'maxCount')
        self.registerType(self.countClass, 'duration')
        self.registerType(self.newInstanceClass, self.newInstanceClass.tag)
        self.registerType(self.keyPairClass, self.keyPairClass.tag)
        self.registerType(self.imageClass, self.imageClass.tag)
        self.registerType(self.instanceTypeClass, self.instanceTypeClass.tag)
        self.registerType(self.securityGroupClass, self.securityGroupClass.tag)
        self.registerType(self.securityGroupsClass, self.securityGroupsClass.tag)

class ResponseHandler(xmllib.DataBinder):
    instanceClass = instances.BaseInstance
    instancesClass = instances.BaseInstances

    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.instanceClass, self.instanceClass.tag)
        self.registerType(self.instancesClass, self.instancesClass.tag)
