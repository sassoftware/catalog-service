#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import rpath_xmllib as xmllib

import xmlNode

class UserInfo(xmlNode.BaseNode):
    tag = 'userinfo'
    __slots__ = [ 'id', 'username', 'isAdmin', 'preferences',
        'displayRepositories', 'email', 'fullName', ]
    _slotAttributes = set(['id'])
    _slotTypeMap = dict(isAdmin = bool, displayRepositories = bool)

class Preferences(xmlNode.BaseNode):
    tag = "preferences"
    __slots__ = [ 'href' ]
    _slotAttributes = set(['href'])

class Handler(xmllib.DataBinder):
    userInfoClass = UserInfo
    preferencesClass = Preferences
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        for cls in [ self.userInfoClass, self.preferencesClass]:
            self.registerType(cls, cls.tag)
