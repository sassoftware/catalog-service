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

class BaseKeyPair(xmlNode.BaseNode):
    tag = 'keyPair'
    __slots__ = [ 'id', 'keyName', 'keyFingerprint' ]

class BaseKeyPairs(xmlNode.BaseNodeCollection):
    tag = 'keyPairs'

class Handler(xmllib.DataBinder):
    keyPairClass = BaseKeyPair
    keyPairsClass = BaseKeyPairs
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.keyPairClass, self.keyPairClass.tag)
        self.registerType(self.keyPairsClass, self.keyPairsClass.tag)
