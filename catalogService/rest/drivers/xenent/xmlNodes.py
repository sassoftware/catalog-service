#
# Copyright (c) 2008 rPath, Inc.
#


from rpath_xmllib import api1 as xmllib

from catalogService import xmlNode

class UuidNode(xmlNode.BaseNode):
    tag = 'uuid'

    def __repr__(self):
        return "<%s:tag=%s at %#x>" % (self.__class__.__name__, self.tag,
                    id(self))

class UuidHandler(xmllib.DataBinder):
    uuidClass = UuidNode

    def __init__(self):
        xmllib.DataBinder.__init__(self)
        for cls in [ self.uuidClass ]:
            self.registerType(cls, cls.tag)

class ImageNode(xmlNode.BaseNode):
    tag = 'image'

class ImageHandler(xmllib.DataBinder):
    imageClass = ImageNode

    def __init__(self):
        xmllib.DataBinder.__init__(self)
        for cls in [ self.imageClass ]:
            self.registerType(cls, cls.tag)
