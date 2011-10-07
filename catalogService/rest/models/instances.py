#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import rpath_xmllib as xmllib

from catalogService.rest.models import xmlNode

class BaseInstanceUpdateStatusState(xmlNode.BaseNode):
    tag = 'updateState'
    __slots__ = ['id', 'state']
    _slotAttributes = set([ 'id' ])

class BaseInstanceUpdateStatusTime(xmlNode.BaseNode):
    tag = 'time'
    __slots__ = ['id', 'time']
    _slotAttributes = set([ 'id' ])

class BaseInstanceUpdateStatus(xmlNode.BaseNode):
    tag = 'updateStatus'
    __slots__ = [ 'id', 'state', 'time' ]
    _slotTypeMap = dict(state = BaseInstanceUpdateStatusState,
                        time = BaseInstanceUpdateStatusTime)
    _slotAttributes = set([ 'id' ])

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

class _TroveChangesHref(xmlNode.BaseNode):
    tag = "troveChanges"
    __slots__ = ['href']
    _slotAttributes = set(['href'])

class _VersionChange(xmlNode.BaseNode):
    tag = "versionChange"
    __slots__ = [ 'from', 'to' ]

class _FlavorChange(xmlNode.BaseNode):
    tag = "flavorChange"
    __slots__ = [ 'from', 'to' ]

class _TroveChangeMinimal(xmlNode.BaseNode):
    tag = 'troveChange'
    __slots__ = [ 'versionChange', 'flavorChange' ]
    _slotTypeMap = dict(versionChange = _VersionChange,
        flavorChange = _FlavorChange)

class SoftwareMixIn(object):
    def setTroveChangesHref(self, href):
        node = _TroveChangesHref()
        node.setHref(href)
        self.setTroveChanges(node)

    def setTroveChangeNode(self, fromVersion = None, toVersion = None,
            fromFlavor = None, toFlavor = None):
        versionChange = None
        flavorChange = None
        if not (fromVersion is None and toVersion is None):
            versionChange = _VersionChange()
            versionChange.setFrom(fromVersion)
            versionChange.setTo(toVersion)
        if not (fromFlavor is None and toFlavor is None):
            flavorChange = _FlavorChange()
            flavorChange.setFrom(fromFlavor)
            flavorChange.setTo(toFlavor)
        if versionChange is None and flavorChange is None:
            return
        tc = _TroveChangeMinimal()
        tc.setVersionChange(versionChange)
        tc.setFlavorChange(flavorChange)
        self.setTroveChange(tc)


class InstalledSoftware(xmlNode.BaseNode, SoftwareMixIn):
    tag = "installedSoftware"
    multiple = True
    __slots__ = [ 'id', 'href', 'isTopLevel', 'troveChanges', 'troveChange', 'trove' ]
    _slotTypeMap = dict(trove = _Trove,
        troveChange = _TroveChangeMinimal,
        troveChanges = _TroveChangesHref,
        isTopLevel = bool,
    )
    _slotAttributes = set(['id', 'href'])

class AvailableUpdate(xmlNode.BaseNode, SoftwareMixIn):
    tag = 'availableUpdate'
    multiple = True
    __slots__ = [ 'id', 'troveChanges', 'troveChange', 'trove',
        'installedSoftware', ]
    _slotTypeMap = dict(trove = _Trove,
        troveChange = _TroveChangeMinimal,
        troveChanges = _TroveChangesHref,
        installedSoftware = InstalledSoftware)
    _slotAttributes = set(['id'])

    def setInstalledSoftwareHref(self, href):
        node = InstalledSoftware()
        node.setHref(href)
        self.setInstalledSoftware(node)

class StageHref(xmlNode.BaseNode):
    tag = "stage"
    __slots__ = ['href']
    _slotAttributes = set(['href'])

class VersionHref(xmlNode.BaseNode):
    tag = "version"
    __slots__ = ['href']
    _slotAttributes = set(['href'])

class UpdateHref(xmlNode.BaseNode):
    tag = "version"
    __slots__ = ['href']
    _slotAttributes = set(['href'])

class BaseInstanceJobHref(xmlNode.BaseNode):
    tag = "job"
    __slots__ = ['id', 'href']
    _slotAttributes = set(['id', 'href'])

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
                  'installedSoftware',
                  'softwareVersionJobId',
                  'softwareVersionJobStatus',
                  'softwareVersionLastChecked',
                  'softwareVersionNextCheck',
                  'version',
                  'stage',
                  'repositoryUrl',
                  'forceUpdateUrl', # force refresh the installed sw data
                  'update',      # update the sw on the system
                  'job',
                  '_opaqueId',
                  ]
    _slotTypeMap = dict(updateStatus = BaseInstanceUpdateStatus,
                        productCode = _ProductCode,
                        softwareVersionLastChecked = int,
                        softwareVersionNextCheck = int,
                        installedSoftware = InstalledSoftware,
                        availableUpdate = AvailableUpdate,
                        outOfDate = bool,
                        version = VersionHref,
                        stage = StageHref,
                        update = UpdateHref,
                        job = BaseInstanceJobHref)
    _slotAttributes = set([ 'id' ])

class IntegerNode(xmlNode.xmllib.IntegerNode):
    "Basic integer node"

class BaseInstances(xmlNode.BaseNodeCollection):
    tag = "instances"

class InstanceType(xmlNode.BaseNode):
    tag = 'instanceType'
    __slots__ = [ 'id', 'instanceTypeId', 'description' ]
    _slotAttributes = set([ 'id' ])

class InstanceTypes(xmlNode.BaseNodeCollection):
    tag = "instanceTypes"

class Handler(xmlNode.Handler):
    launchIndexClass = IntegerNode
    instanceClass = BaseInstance
    instancesClass = BaseInstances
    instanceTypeClass = InstanceType
    instanceTypesClass = InstanceTypes
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.launchIndexClass, 'launchIndex')
        self.registerType(self.instanceClass, self.instanceClass.tag)
        self.registerType(self.instancesClass, self.instancesClass.tag)
        self.registerType(self.instanceTypeClass, self.instanceTypeClass.tag)
        self.registerType(self.instanceTypesClass, self.instanceTypesClass.tag)
