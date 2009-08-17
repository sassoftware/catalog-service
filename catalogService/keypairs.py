#
# Copyright (c) 2008 rPath, Inc.
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
