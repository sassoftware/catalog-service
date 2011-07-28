#
# Copyright (c) 2011 rPath, Inc.  All Rights Reserved.
#

import inspect
from catalogService.rest.models import xmlNode

handler = xmlNode.Handler()

class _BaseNode(xmlNode.BaseNode):
    NS =  "http://www.vmware.com/vcloud/v1"
    StrictOrdering = True
    def _getLocalNamespaces(self):
        return { None : self.NS }
    def getId(self):
        return ""

class VAppTemplateParams(_BaseNode):
    tag = 'UploadVAppTemplateParams'
    __slots__ = [ 'name', 'Description', 'manifestRequired' ]
    _slotAttributes = set([ 'name', 'manifestRequired' ])
    _slotTypeMap = dict(manifestRequired=bool)

class Link(_BaseNode):
    tag = 'Link'
    __slots__ = ['rel', 'type', 'href', 'name', ]
    _slotAttributes = set([ 'rel', 'type', 'href', 'name', ])
    multiple = True

    def _asTuple(self):
        return (self.rel, self.type, self.href, self.name)

    def __hash__(self):
        return hash(self._asTuple())

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self._asTuple() == other._asTuple()

class File(_BaseNode):
    tag = 'File'
    __slots__ = [ 'size', 'bytesTransferred', 'Link', 'name', 'checksum', ]
    _slotAttributes = set([ 'size', 'bytesTransferred', 'name', 'checksum', ])
    _slotTypeMap = dict(size=int, bytesTransferred=int, Link=Link)

class Files(xmlNode.BaseNodeCollection):
    tag = 'Files'

class Error(_BaseNode):
    tag = 'Error'
    __slots__ = [ 'minorErrorCode', 'majorErrorCode', 'message', ]
    _slotAttributes = [ 'minorErrorCode', 'majorErrorCode', 'message', ]

class Task(_BaseNode):
    tag = 'Task'
    __slots__ = [ 'status', 'operation', 'type', 'href', 'Error',
        'startTime', 'endTime', 'expiryTime', ]
    _slotAttributes = [ 'status', 'operation', 'type', 'href', 'startTime',
        'endTime', 'expiryTime', ]
    _slotTypeMap = dict(Error=Error)

class Tasks(xmlNode.BaseNodeCollection):
    tag = "Tasks"

class _ResourceEntityType(_BaseNode):
    __slots__ = [ 'href', 'status', 'name', 'type', 'Description', 'Tasks', ]
    _slotAttributes = set([ 'href', 'status', 'name', 'type', ])
    _slotTypeMap = dict(status=int, Tasks=Tasks)

class VAppTemplate(_ResourceEntityType):
    tag = 'VAppTemplate'
    __slots__ = _ResourceEntityType.__slots__ + [ 'Files', 'ovfDescriptorUploaded', ]
    _slotAttributes = _ResourceEntityType._slotAttributes.union([
        'ovfDescriptorUploaded', ])
    _slotTypeMap = dict(_ResourceEntityType._slotTypeMap)
    _slotTypeMap.update(ovfDescriptorUploaded=bool, Files=Files)

class Media(_ResourceEntityType):
    tag = 'Media'
    __slots__ = _ResourceEntityType.__slots__ + [ 'imageType', 'size', ]
    _slotAttributes = _ResourceEntityType._slotAttributes.union([
        'imageType', 'size', ])
    _slotTypeMap = dict(_ResourceEntityType._slotTypeMap)
    _slotTypeMap.update(size=int)

class ResourceEntity(_ResourceEntityType):
    tag = 'ResourceEntity'

class ReferenceType(_BaseNode):
    __slots__ = [ 'type', 'name', 'href', ]
    _slotAttributes = set([ 'type', 'name', 'href', ])

class ResourceEntities(xmlNode.BaseNodeCollection):
    tag = "ResourceEntities"

class AvailableNetworks(xmlNode.BaseNodeCollection):
    tag = 'AvailableNetworks'

class AvailableNetwork(ReferenceType):
    tag = 'Network'

class VDC(_BaseNode):
    tag = "Vdc"
    __slots__ = ['name', 'type', 'href', 'status', 'ResourceEntities',
        'AvailableNetworks', 'VmQuota', 'Link', 'IsEnabled', ]
    _slotAttributes = set([ 'name', 'type', 'href', 'status', ])
    _slotTypeMap = dict(VmQuota=int, ResourceEntities=ResourceEntities,
        Link=Link, AvailableNetworks=AvailableNetworks, IsEnabled=bool)

class Org(_BaseNode):
    tag = 'Org'
    __slots__ = [ 'name', 'type', 'href', 'Description', 'FullName', 'Link', ]
    _slotAttributes = set([ 'name', 'type', 'href', ])
    _slotTypeMap = dict(Link=Link, )

class Entity(_BaseNode):
    tag = 'Entity'
    __slots__ = [ 'href' ]
    _slotAttributes = set([ 'href' ])

class CatalogItem(_BaseNode):
    tag = 'CatalogItem'
    __slots__ = [ 'name', 'type', 'href', 'Link', 'Entity', 'Description', ]
    _slotAttributes = set([ 'name', 'type', 'href', ])
    _slotTypeMap = dict(Link=Link, Entity=Entity)

class CatalogItems(xmlNode.BaseNodeCollection):
    tag = 'CatalogItems'

class Catalog(_BaseNode):
    tag = 'Catalog'
    __slots__ = [ 'name', 'type', 'href', 'Description', 'IsPublished',
        'CatalogItems', ]
    _slotAttributes = set([ 'name', 'type', 'href', ])
    _slotTypeMap = dict(IsPublished=bool, Link=Link, CatalogItems=CatalogItems)

class IpScope(_BaseNode):
    tag = 'IpScope'
    __slots__ = ['IsInherited', 'Gateway', 'Netmask', 'Dns1', 'Dns2',
        'DnsSuffix', 'IpRanges', 'AllocatedIpAddresses', ]
    _slotTypeMap = dict(IsInherited=bool)

class NetworkFeatures(_BaseNode):
    tag = 'NetworkFeatures'
    __slots__ = ['DhcpService', 'FirewallService', 'NatService', ]

class ParentNetwork(ReferenceType):
    tag = 'ParentNetwork'

class OVFInfo(_BaseNode):
    NS = "http://schemas.dmtf.org/ovf/envelope/1"
    name = 'Info'
    __slots__ = [ '_text' ]
    def __init__(self, text):
        self._text = text
    def getText(self):
        return self._text
    def _getName(self):
        return "{%s}%s" % (self.NS, self.__class__.name)
    def _getLocalNamespaces(self):
        return { 'ovf' : self.NS, }

class NetworkConfiguration(_BaseNode):
    tag = 'Configuration'
    __slots__ = [ 'IpScope', 'ParentNetwork', 'FenceMode', 'Features', ]
    _slotTypeMap = dict(IpScope=IpScope, ParentNetwork=ParentNetwork,
        Features=NetworkFeatures)

class NetworkConfig(_BaseNode):
    tag = 'NetworkConfig'
    __slots__ = [ 'Description', 'Configuration', 'IsDeployed', 'networkName' ]
    _slotAttributes = set([ 'networkName', ])
    _slotTypeMap = dict(IsDeployed=bool, Configuration=NetworkConfiguration)

class NetworkConfigSection(_BaseNode):
    tag = 'NetworkConfigSection'
    __slots__ = ['Info', 'Link', 'NetworkConfig', 'type', 'href']
    _slotAttributes = set(['type', 'href'])
    _slotTypeMap = dict(NetworkConfig=NetworkConfig, Link=Link, Info=OVFInfo)

class InstantiationParams(_BaseNode):
    tag = 'InstantiationParams'
    __slots__ = ['NetworkConfigSection', ]
    _slotTypeMap = dict(NetworkConfigSection=NetworkConfigSection)

class Source(ReferenceType):
    tag = 'Source'

class InstantiateVAppTemplateParams(_BaseNode):
    tag = 'InstantiateVAppTemplateParams'
    __slots__ = [ 'name', 'Description', 'deploy', 'powerOn',
        'VAppParent', 'InstantiationParams', 'Source', 'IsSourceDelete',
        'linkedClone', ]
    _slotAttributes = set(['name', 'deploy', 'powerOn',])
    _slotTypeMap = dict(deploy=bool, powerOn=bool, VAppParent=ReferenceType,
        InstantiationParams=InstantiationParams,
        linkedClone=bool, IsSourceDelete=bool, Source=Source)

class Children(_BaseNode):
    tag = 'Children'
    __slots__ = ['VApp']
    _slotTypeMap = dict()

class AbstractVApp(_ResourceEntityType):
    __slots__ = _ResourceEntityType.__slots__ + [
        'VAppParent', 'NetworkSection', 'deployed', ]
    _slotAttributes = _ResourceEntityType._slotAttributes.union(['deployed'])
    _slotTypeMap = _ResourceEntityType._slotTypeMap.copy()
    _slotTypeMap.update(deployed=bool)

class VApp(AbstractVApp):
    tag = 'VApp'
    multiple = True
    __slots__ = AbstractVApp.__slots__ + [ 'Children', 'ovfDescriptorUploaded', ]
    _slotAttributes = AbstractVApp._slotAttributes.union(['ovfDescriptorUploaded'])
    _slotTypeMap = AbstractVApp._slotTypeMap.copy()
    _slotTypeMap.update(Children=Children)

Children._slotTypeMap.update(VApp=VApp)

for k, v in globals().items():
    if k.startswith('_') or not inspect.isclass(v):
        continue
    if not issubclass(v, (xmlNode.BaseNode, xmlNode.BaseNodeCollection)):
        continue
    if v.tag is None:
        continue
    handler.registerType(v, v.tag)
