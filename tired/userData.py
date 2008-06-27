#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

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
