#
# Copyright (c) 2008 rPath, Inc.
#

import rpath_xmllib as xmllib

from catalogService import xmlNode

class UserInfo(xmlNode.BaseNode):
    tag = 'userinfo'
    __slots__ = [ 'id', 'username', 'isAdmin' ]
    _slotAttributes = set(['id'])
    _slotTypeMap = dict(isAdmin = bool)

class Handler(xmllib.DataBinder):
    userInfoClass = UserInfo
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        for cls in [ self.userInfoClass, ]:
            self.registerType(cls, cls.tag)
