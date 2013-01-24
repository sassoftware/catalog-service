#!/usr/bin/python
#
# Copyright (c) SAS Institute Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
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
