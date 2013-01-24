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


import xmlNode


class IdNode(xmlNode.xmllib.GenericNode):
    tag = 'id'
    def addChild(self, child):
        pass

    @classmethod
    def _getName(cls):
        return cls.tag

class IdsNode(xmlNode.BaseNodeCollection):
    tag = 'ids'

class Handler(xmlNode.xmllib.DataBinder):
    def __init__(self):
        xmlNode.xmllib.DataBinder.__init__(self)
        self.registerType(IdNode, IdNode.tag)
        self.registerType(IdsNode, IdsNode.tag)
