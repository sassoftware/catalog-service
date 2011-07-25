#
# Copyright (c) 2011 rPath, Inc.  All Rights Reserved.
#

from catalogService.rest.models import xmlNode

handler = xmlNode.Handler()

class _BaseNode(xmlNode.BaseNode):
    NS =  "http://www.vmware.com/vcloud/v1"
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
    __slots__ = [ 'href', 'status', 'name', 'type', 'Files', 'Tasks', ]
    _slotAttributes = set([ 'href', 'status', 'name', 'type' ])
    _slotTypeMap = dict(status=int, Files=Files, Tasks=Tasks)

class VAppTemplate(_ResourceEntityType):
    tag = 'VAppTemplate'
    __slots__ = _ResourceEntityType.__slots__ + [ 'ovfDescriptorUploaded', ]
    _slotAttributes = _ResourceEntityType._slotAttributes.union([
        'ovfDescriptorUploaded', ])
    _slotTypeMap = dict(_ResourceEntityType._slotTypeMap)
    _slotTypeMap.update(ovfDescriptorUploaded=bool)

class Media(_ResourceEntityType):
    tag = 'Media'
    __slots__ = _ResourceEntityType.__slots__ + [ 'imageType', 'size', ]
    _slotAttributes = _ResourceEntityType._slotAttributes.union([
        'imageType', 'size', ])
    _slotTypeMap = dict(_ResourceEntityType._slotTypeMap)
    _slotTypeMap.update(size=int)

class ResourceEntity(_BaseNode):
    tag = 'ResourceEntity'
    __slots__ = [ 'type', 'name', 'href', ]
    _slotAttributes = set([ 'type', 'name', 'href', ])

class ResourceEntities(xmlNode.BaseNodeCollection):
    tag = "ResourceEntities"

class VDC(_BaseNode):
    tag = "Vdc"
    __slots__ = ['name', 'type', 'href', 'status', 'ResourceEntities',
        'VmQuota', 'Link', ]
    _slotAttributes = set([ 'name', 'type', 'href', 'status', ])
    _slotTypeMap = dict(VmQuota=int, ResourceEntities=ResourceEntities,
        Link=Link)

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

handler.registerType(VAppTemplate, VAppTemplate.tag)
handler.registerType(Files, Files.tag)
handler.registerType(File, File.tag)
handler.registerType(Tasks, Tasks.tag)
handler.registerType(Task, Task.tag)
handler.registerType(VDC, VDC.tag)
handler.registerType(ResourceEntities, ResourceEntities.tag)
handler.registerType(ResourceEntity, ResourceEntity.tag)
handler.registerType(Entity, Entity.tag)
handler.registerType(Org, Org.tag)
handler.registerType(Catalog, Catalog.tag)
handler.registerType(CatalogItems, CatalogItems.tag)
handler.registerType(CatalogItem, CatalogItem.tag)

