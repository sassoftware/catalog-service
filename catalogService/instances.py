#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

import xmlNode

class Linker(object):
    baseUrl = None

    def instanceUrl(self, cloudType, cloudName, instanceId):
        instanceId = self._urlquote(instanceId)
        return '%s/clouds/%s/%s/instances/%s' % (self.baseUrl,
                                    cloudType, cloudName, instanceId)

    def imageUrl(self, cloudType, cloudName, imageId):
        imageId = self._urlquote(imageId)
        return '%s/clouds/%s/%s/images/%s' % (self.baseUrl,
                                    cloudType, cloudName, imageId)

class InstanceFactory(object):
    def __init__(self):
        self.linker = Linker()

    def __call__(self, *args, **kw):
        instance = BaseInstance(*args, **kw)
        instance.setId(self.linker.instanceUrl(instance.getCloudType(),
                                              instance.getCloudName(),
                                              instance.getId()))
        instance.setImageId(self.linker.imageUrl(instance.getCloudType(),
                                                 instance.getCloudName(),
                                                 instance.getImageId()))
        return instance


class BaseInstance(xmlNode.BaseNode):
    tag = 'instance'
    __slots__ = [ 'id', 'instanceId',
                  'dnsName', 'publicDnsName', 'privateDnsName',
                  'state', 'stateCode', 'keyName', 'shutdownState',
                  'previousState', 'instanceType', 'launchTime',
                  'imageId', 'placement', 'kernel', 'ramdisk',
                  'reservationId', 'ownerId', 'launchIndex',
                  'cloudName', 'cloudType', 'cloudAlias', ]


class IntegerNode(xmlNode.xmllib.IntegerNode):
    "Basic integer node"

class BaseInstances(xmlNode.BaseNodeCollection):
    tag = "instances"

class InstanceType(xmlNode.BaseNode):
    tag = 'instanceType'
    __slots__ = [ 'id', 'instanceTypeId', 'description' ]

class InstanceTypes(xmlNode.BaseNodeCollection):
    tag = "instanceTypes"

class Handler(xmllib.DataBinder):
    instanceClass = BaseInstance
    instancesClass = BaseInstances
    launchIndexClass = IntegerNode
    instanceTypeClass = InstanceType
    instanceTypesClass = InstanceTypes
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.launchIndexClass, 'launchIndex')
        self.registerType(self.instanceClass, self.instanceClass.tag)
        self.registerType(self.instancesClass, self.instancesClass.tag)
        self.registerType(self.instanceTypeClass, self.instanceTypeClass.tag)
        self.registerType(self.instanceTypesClass, self.instanceTypesClass.tag)
