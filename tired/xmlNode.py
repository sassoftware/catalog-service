#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

class BaseNode(xmllib.BaseNode):
    tag = None

    def __init__(self, attrs, nsMap):
        xmllib.BaseNode.__init__(self, attrs, nsMap = nsMap)
        for slot in self.__slots__:
            setattr(self, slot, None)

    def setName(self, name):
        pass

    def getName(self):
        return self.tag

    _getName = getName

    def getAbsoluteName(self):
        return self.tag

    def _iterChildren(self):
        for fName in self.__slots__:
            fVal = getattr(self, fName)
            if hasattr(fVal, "getElementTree"):
                yield fVal

    def _iterAttributes(self):
        return {}

    def addChild(self, node):
        nodeName = node.getName()
        if nodeName in self.__slots__:
            setattr(self, nodeName, node)


