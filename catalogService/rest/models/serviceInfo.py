#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import rpath_xmllib as xmllib

import xmlNode

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
