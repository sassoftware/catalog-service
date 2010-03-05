#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
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

class _SoftwareVersion(xmlNode.BaseMultiNode):
    tag = "softwareVersion"

class AvailableUpdateVersion(xmlNode.BaseNode):
    tag = "version"

    __slots__ = [ 'full', 'label', 'ordering', 'revision' ] 

    _slotTypeMap = dict(full = str,
                        label = str,
                        ordering = str,
                        revision = str)

class _AvailableUpdate(xmlNode.BaseNode):
    tag = 'availableUpdate'
    multiple = True

    __slots__ = [ 'name', 'version', 'flavor' ]

    _slotTypeMap = dict(name = str,
                        version = AvailableUpdateVersion,
                        flavor = str)

    def __init__(self, *args, **kw):
        xmlNode.BaseNode.__init__(self, *args, **kw)
        self.name = xmllib.GenericNode().setName("name").characters(kw['name'])

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
                  'availableUpdate',
                  'outOfDate',
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
                        softwareVersion = _SoftwareVersion,
                        availableUpdate = _AvailableUpdate,
                        outOfDate = bool)

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
    availableUpdateClass = _AvailableUpdate
    availableUpdateVersionClass = AvailableUpdateVersion
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
        self.registerType(self.availableUpdateClass,
                          self.availableUpdateClass.tag)
        self.registerType(self.availableUpdateVersionClass,
                          self.availableUpdateVersionClass.tag)
