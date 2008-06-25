#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

import xmlNode

class BaseSecurityGroup(xmlNode.BaseNode):
    tag = 'security-group'
    __slots__ = [ 'id', 'ownerId', 'groupName', 'description' ]

class BaseSecurityGroups(xmlNode.BaseNodeCollection):
    tag = 'security-groups'

class Handler(xmllib.DataBinder):
    securityGroupClass = BaseSecurityGroup
    securityGroupsClass = BaseSecurityGroups
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.securityGroupClass, self.securityGroupClass.tag)
        self.registerType(self.securityGroupsClass, self.securityGroupsClass.tag)
