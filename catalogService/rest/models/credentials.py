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

class BaseField(xmlNode.BaseNode):
    tag = 'field'
    __slots__ = [ 'credentialName', 'value' ]

class BaseFields(xmlNode.BaseNodeCollection):
    tag = "fields"

class BaseCredentials(xmlNode.BaseNode):
    tag = "credentials"
    __slots__ = [ 'fields', 'valid' ]
    _slotTypeMap = dict(valid=bool)

class Handler(xmllib.DataBinder):
    fieldClass = BaseField
    fieldsClass = BaseFields
    credentialsClass = BaseCredentials
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.fieldClass, self.fieldClass.tag)
        self.registerType(self.fieldsClass, self.fieldsClass.tag)
        self.registerType(self.credentialsClass, self.credentialsClass.tag)
