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

class AvailableUpdateVersion(xmlNode.BaseNode):
    tag = "version"

    __slots__ = [ 'full', 'label', 'ordering', 'revision' ] 

    _slotTypeMap = dict(full = str,
                        label = str,
                        ordering = str,
                        revision = str)

class _Trove(xmlNode.BaseNode):
    tag = 'trove'
    __slots__ = [ 'id', 'name', 'version', 'flavor' ]
    _slotTypeMap = dict(name = str,
                        version = AvailableUpdateVersion,
                        flavor = str)
    _slotAttributes = set(['id'])

    def __init__(self, *args, **kw):
        xmlNode.BaseNode.__init__(self, *args, **kw)
        if kw.has_key('name'):
            self.name = xmllib.GenericNode().setName("name").characters(kw['name'])

class AvailableUpdate(xmlNode.BaseNode):
    tag = 'availableUpdate'
    multiple = True
    __slots__ = [ 'trove' ]
    _slotTypeMap = dict(trove=_Trove)

class SoftwareVersion(xmlNode.BaseNode):
    tag = "softwareVersion"
    multiple = True
    __slots__ = [ 'trove' ]
    _slotTypeMap = dict(trove=_Trove)

    def getText(self):
        name = self.getTrove().name.getText()
        version = self.getTrove().getVersion().getFull()
        flavor = self.getTrove().getFlavor()

        nvf = "%s=%s" % (name, version)
        if flavor and flavor != 'None':
            nvf += "[%s]" % flavor

        return str(nvf)

class StageHref(xmlNode.BaseNode):
    tag = "stage"
    __slots__ = ['href']
    _slotAttributes = set(['href'])

class VersionHref(xmlNode.BaseNode):
    tag = "version"
    __slots__ = ['href']
    _slotAttributes = set(['href'])

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
                  'version',
                  'stage'
                  ]
    _slotTypeMap = dict(updateStatus = BaseInstanceUpdateStatus,
                        productCode = _ProductCode,
                        softwareVersionLastChecked = int,
                        softwareVersionNextCheck = int,
                        softwareVersion = SoftwareVersion,
                        availableUpdate = AvailableUpdate,
                        outOfDate = bool,
                        version = VersionHref,
                        stage = StageHref)

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
    softwareVersionClass = SoftwareVersion
    availableUpdateClass = AvailableUpdate
    troveClass = _Trove
    availableUpdateVersionClass = AvailableUpdateVersion
    stageHrefClass = StageHref
    versionHrefClass = VersionHref
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
        self.registerType(self.troveClass,
                          self.troveClass.tag)
        # self.registerType(self.stageHrefClass,
                          # self.stageHrefClass.tag)
        # self.registerType(self.versionHrefClass,
                          # self.versionHrefClass.tag)
