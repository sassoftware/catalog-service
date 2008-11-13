#
# Copyright (c) 2008 rPath, Inc.
#


from rpath_common.xmllib import api1 as xmllib

from catalogService import xmlNode

class UuidNode(xmlNode.BaseNode):
    tag = 'uuid'

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
