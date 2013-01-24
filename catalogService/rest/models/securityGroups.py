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
