#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

from catalogService import xmlNode

class ServiceInfo(xmlNode.BaseNode):
    tag = 'serviceinfo'
    __slots__ = [ 'id', 'version', 'type' ]
    _slotAttributes = set(['id'])
    _slotTypeMap = dict(version = str, type = str)

class Handler(xmllib.DataBinder):
    serviceInfoClass = ServiceInfo
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        for cls in [ self.serviceInfoClass, ]:
            self.registerType(cls, cls.tag)
