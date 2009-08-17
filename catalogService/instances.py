#
# Copyright (c) 2008 rPath, Inc.
#

import rpath_xmllib as xmllib

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

class _ProductCode(xmlNode.BaseNode):
    tag = "productCode"
    __slots__ = ['code', 'url']
    multiple = True

    def __init__(self, attrs = None, nsMap = None, item = None):
        xmlNode.BaseNode.__init__(self, attrs, nsMap = nsMap)
        if item is None:
            self.code = None
            self.url = None
            return
        code, url = item[:2]
        self.code = xmllib.GenericNode().setName("code").characters(code)
        self.url = xmllib.GenericNode().setName("url").characters(url)

    def getId(self):
        return "code:%s;url:%s" % (self.code.getText(), self.url.getText())

class _SoftwareVersion(xmlNode.BaseNode):
    tag = "softwareVersion"
    multiple = True

    def __init__(self, attrs = None, nsMap = None, item = None):
        xmlNode.BaseNode.__init__(self, attrs, nsMap = nsMap)
        if item is None:
            return
        self.characters(str(item))

    def getId(self):
        return "softwareVersion: %s" % self.getText()

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
                  '_xmlNodeHash', 'launchTime', 'productCode',
                  'placement',
                  'softwareVersion',
                  'softwareVersionJobId',
                  'softwareVersionJobStatus',
                  'softwareVersionLastChecked',
                  'softwareVersionNextCheck',
                  ]
    _slotTypeMap = dict(updateStatus = BaseInstanceUpdateStatus,
                        productCode = _ProductCode,
                        softwareVersionLastChecked = int,
                        softwareVersionNextCheck = int,
                        softwareVersion = _SoftwareVersion)

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
    softwareVersionClass = _SoftwareVersion
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
        self.registerType(self.softwareVersionClass,
                          self.softwareVersionClass.tag)
