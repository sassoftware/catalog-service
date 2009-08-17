#
# Copyright (c) 2008 rPath, Inc.
#

import rpath_xmllib as xmllib

import xmlNode

class BaseSecurityGroup(xmlNode.BaseNode):
    tag = 'securityGroup'
    __slots__ = [ 'id', 'ownerId', 'groupName', 'description', 'permission' ]
    _slotAttributes = set(['id'])

class BaseSecurityGroups(xmlNode.BaseNodeCollection):
    tag = 'securityGroups'

class Handler(xmllib.DataBinder):
    securityGroupClass = BaseSecurityGroup
    securityGroupsClass = BaseSecurityGroups
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        classes = [ self.securityGroupClass, self.securityGroupsClass ]
        while classes:
            cls = classes.pop()
            self.registerType(cls, cls.tag)
            for k, v in getattr(cls, '_slotTypeMap', {}).items():
                if type(v) is type:
                    classes.append(v)
