#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

import xmlNode

class BaseInstanceUpdateStatusState(xmlNode.BaseNode):
    tag = 'updateState'
    __slots__ = ['id', 'state']

class BaseInstanceUpdateStatusTime(xmlNode.BaseNode):
    tag = 'time'
    __slots__ = ['id', 'time']

class BaseInstanceUpdateStatus(xmlNode.BaseNode):
    tag = 'updateStatus'
    __slots__ = [ 'id', 'state', 'time' ]
    _slotTypeMap = dict(state = BaseInstanceUpdateStatusState,
                        time = BaseInstanceUpdateStatusTime)

class BaseInstance(xmlNode.BaseNode):
    tag = 'instance'
    __slots__ = [ 'id', 'instanceId', 'instanceName',
                  'instanceDescription',
                  'dnsName', 'publicDnsName', 'privateDnsName',
                  'state', 'stateCode', 'shutdownState',
                  'previousState', 'instanceType', 'launchTime',
                  'imageId', 'placement', 'kernel', 'ramdisk',
                  'reservationId', 'ownerId', 'launchIndex',
                  'cloudName', 'cloudType', 'cloudAlias',
                  'updateStatus', 
                  '_xmlNodeHash', 'launchTime', 'productCodes',
                  'placement' ]
    _slotTypeMap = dict(productCodes = list,
                        updateStatus = BaseInstanceUpdateStatus)

class IntegerNode(xmlNode.xmllib.IntegerNode):
    "Basic integer node"

class BaseInstances(xmlNode.BaseNodeCollection):
    tag = "instances"

class InstanceType(xmlNode.BaseNode):
    tag = 'instanceType'
    __slots__ = [ 'id', 'instanceTypeId', 'description' ]

class InstanceTypes(xmlNode.BaseNodeCollection):
    tag = "instanceTypes"

class Handler(xmlNode.Handler):
    instanceClass = BaseInstance
    instanceUpdateStatusClass = BaseInstanceUpdateStatus
    instanceUpdateStatusStateClass = BaseInstanceUpdateStatusState
    instanceUpdateStatusTimeClass = BaseInstanceUpdateStatusTime
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
        self.registerType(self.instanceUpdateStatusClass,
                          self.instanceUpdateStatusClass.tag)
        self.registerType(self.instanceUpdateStatusStateClass,
                          self.instanceUpdateStatusStateClass.tag)
        self.registerType(self.instanceUpdateStatusTimeClass,
                          self.instanceUpdateStatusTimeClass.tag)
