#
# Copyright (c) 2011 rPath, Inc.  All Rights Reserved.
#

import inspect
from catalogService.rest.models import xmlNode

handler = xmlNode.Handler()

class _BaseNode(xmlNode.BaseNode):
    NS =  "http://www.vmware.com/vcloud/v1"
    StrictOrdering = True
    __slots__ = []
    _slotAttributes = set()
    _slotTypeMap = dict()
    def _getLocalNamespaces(self):
        return { None : self.NS }
    def getId(self):
        return ""

    @classmethod
    def _inherit(cls, baseClass, attributes=None, elements=None):
        slots = baseClass.__slots__[:]
        slotAttributes = set(baseClass._slotAttributes)
        slotTypeMap = dict(baseClass._slotTypeMap)
        if attributes is None:
            attributes = {}
        elif isinstance(attributes, list):
            attributes = dict((x, None) for x in attributes)
        for attName, attType in attributes.items():
            slots.append(attName)
            slotAttributes.add(attName)
            if attType is not None:
                slotTypeMap[attName] = attType
        for element in elements or []:
            if isinstance(element, basestring):
                elementName = element
                element = None
            else:
                if isinstance(element, tuple):
                    elementName, element = element
                else:
                    elementName = element.tag
            slots.append(elementName)
            if element is not None:
                slotTypeMap[elementName] = element
        return slots, slotAttributes, slotTypeMap

class _ReferenceType(_BaseNode):
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(_BaseNode,
        attributes=['type', 'name', 'href', ])

class _LinkType(_ReferenceType):
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(_ReferenceType,
        attributes=['rel'])

class Link(_LinkType):
    tag = 'Link'
    multiple = True

    def _asTuple(self):
        return (self.rel, self.type, self.href, self.name)

    def __hash__(self):
        return hash(self._asTuple())

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self._asTuple() == other._asTuple()

class _ResourceType(_BaseNode):
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(_BaseNode,
        attributes=['href', 'type'], elements=[Link])

class Tasks(xmlNode.BaseNodeCollection):
    tag = "Tasks"

class _EntityType(_ResourceType):
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(_ResourceType,
        attributes=['name'], elements=['Description', Tasks])

class VAppTemplateParams(_BaseNode):
    tag = 'UploadVAppTemplateParams'
    __slots__ = [ 'name', 'Description', 'manifestRequired' ]
    _slotAttributes = set([ 'name', 'manifestRequired' ])
    _slotTypeMap = dict(manifestRequired=bool)

class File(_EntityType):
    tag = 'File'
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(_EntityType,
        attributes=dict(size=int, bytesTransferred=int, checksum=None))

class Files(xmlNode.BaseNodeCollection):
    tag = 'Files'

class Error(_BaseNode):
    tag = 'Error'
    __slots__ = [ 'minorErrorCode', 'majorErrorCode', 'message', ]
    _slotAttributes = [ 'minorErrorCode', 'majorErrorCode', 'message', ]

class Owner(_ReferenceType):
    tag = 'Owner'

class Task(_BaseNode):
    tag = 'Task'
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(_ResourceType,
        attributes=['status', 'operation', 'startTime', 'endTime',
            'expiryTime',],
        elements = [ Error, Owner, ])

class _ResourceEntityType(_EntityType):
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(_EntityType,
        attributes=dict(status=int), elements=[Files])

class VAppTemplate(_ResourceEntityType):
    tag = 'VAppTemplate'
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(_ResourceEntityType,
        attributes=dict(ovfDescriptorUploaded=bool), elements=['Children'])

class Media(_ResourceEntityType):
    tag = 'Media'
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(_ResourceEntityType,
        attributes=dict(size=int, imageType=None))

class ResourceEntity(_ResourceEntityType):
    tag = 'ResourceEntity'

class ResourceEntities(xmlNode.BaseNodeCollection):
    tag = "ResourceEntities"

class AvailableNetworks(xmlNode.BaseNodeCollection):
    tag = 'AvailableNetworks'

class AvailableNetwork(_ReferenceType):
    tag = 'Network'

class VDC(_EntityType):
    tag = "Vdc"
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(_EntityType,
        attributes=dict(status=int),
        elements=[ResourceEntities, AvailableNetworks,
            ('NicQuota', int), ('NetworkQuota', int), ('VmQuota', int),
            ('IsEnabled', bool), ])

class Org(_EntityType):
    tag = 'Org'
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(_EntityType,
        elements = ['FullName'])

class Entity(_ReferenceType):
    tag = 'Entity'

class _PropertyType(_BaseNode):
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(_BaseNode,
        attributes=['name'])

class Property(_PropertyType):
    tag = 'Property'

class CatalogItem(_EntityType):
    tag = 'CatalogItem'
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(_EntityType,
        elements=[Entity, Property])

class CatalogItems(xmlNode.BaseNodeCollection):
    tag = 'CatalogItems'

class Catalog(_EntityType):
    tag = 'Catalog'
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(_EntityType,
        elements=[CatalogItems, ('IsPublished', bool)])

class IpScope(_BaseNode):
    tag = 'IpScope'
    __slots__ = ['IsInherited', 'Gateway', 'Netmask', 'Dns1', 'Dns2',
        'DnsSuffix', 'IpRanges', 'AllocatedIpAddresses', ]
    _slotTypeMap = dict(IsInherited=bool)

class NetworkFeatures(_BaseNode):
    tag = 'NetworkFeatures'
    __slots__ = ['DhcpService', 'FirewallService', 'NatService', ]

class ParentNetwork(_ReferenceType):
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

class Source(_ReferenceType):
    tag = 'Source'

class VAppParent(_ReferenceType):
    tag = 'VAppParent'

class InstantiateVAppTemplateParams(_BaseNode):
    tag = 'InstantiateVAppTemplateParams'
    __slots__ = [ 'name', 'Description', 'deploy', 'powerOn',
        'VAppParent', 'InstantiationParams', 'Source', 'IsSourceDelete',
        'linkedClone', ]
    _slotAttributes = set(['name', 'deploy', 'powerOn',])
    _slotTypeMap = dict(deploy=bool, powerOn=bool, VAppParent=VAppParent,
        InstantiationParams=InstantiationParams,
        linkedClone=bool, IsSourceDelete=bool, Source=Source)

class Children(_BaseNode):
    tag = 'Children'
    __slots__ = ['VApp']
    _slotTypeMap = dict()

# Resolve circular reference
VAppTemplate._slotTypeMap.update(Children=Children)

class AbstractVApp(_ResourceEntityType):
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(_ResourceEntityType,
        elements=['VAppParent', 'NetworkSection', ('deployed', bool)])

class VApp(AbstractVApp):
    tag = 'VApp'
    multiple = True
    __slots__, _slotAttributes, _slotTypeMap = _BaseNode._inherit(AbstractVApp,
        attributes=dict(ovfDescriptorUploaded=bool),
        elements=[Children])

# Resolve circular reference
Children._slotTypeMap.update(VApp=VApp)

for k, v in globals().items():
    if k.startswith('_') or not inspect.isclass(v):
        continue
    if not issubclass(v, (xmlNode.BaseNode, xmlNode.BaseNodeCollection)):
        continue
    if v.tag is None:
        continue
    handler.registerType(v, v.tag)
