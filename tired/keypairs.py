#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

import xmlNode

class BaseKeyPair(xmlNode.BaseNode):
    tag = 'key-pair'
    __slots__ = [ 'id', 'keyName', 'keyFingerprint' ]

class BaseKeyPairs(xmlNode.BaseNodeCollection):
    tag = 'key-pairs'

class Handler(xmllib.DataBinder):
    keyPairClass = BaseKeyPair
    keyPairsClass = BaseKeyPairs
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.keyPairClass, self.keyPairClass.tag)
        self.registerType(self.keyPairsClass, self.keyPairsClass.tag)
