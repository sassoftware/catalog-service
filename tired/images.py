#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

import xmlNode

class BaseImage(xmlNode.BaseNode):
    tag = 'image'
    __slots__ = [ 'id', 'location', 'state', 'isPublic' ]
    def __init__(self, attrs = None, nsMap = None, **kwargs):
        xmlNode.BaseNode.__init__(self, attrs = attrs, nsMap = nsMap)

        self.setId(kwargs.get('id'))
        self.setLocation(kwargs.get('location'))
        self.setState(kwargs.get('state'))
        self.setIsPublic(kwargs.get('isPublic'))

    def setId(self, data):
        self.id = None
        if data is None:
            return
        self.id = xmllib.GenericNode().setName('id').characters(data)
        return self

    def getId(self):
        if self.id is None:
            return None
        return self.id.getText()

    def setLocation(self, data):
        self.location = None
        if data is None:
            return
        self.location = xmllib.GenericNode().setName('location').characters(data)
        return self

    def getLocation(self):
        if self.location is None:
            return None
        return self.location.getText()

    def setState(self, data):
        self.state = None
        if data is None:
            return
        self.state = xmllib.GenericNode().setName('state').characters(data)
        return self

    def getState(self):
        if self.state is None:
            return None
        return self.state.getText()

    def setIsPublic(self, data):
        self.isPublic = None
        if data is None:
            return
        data = xmllib.BooleanNode.toString(data)
        self.isPublic = xmllib.GenericNode().setName('isPublic').characters(data)
        return self

    def getIsPublic(self):
        if self.isPublic is None:
            return None
        return xmllib.BooleanNode.fromString(self.isPublic.getText())

    def __repr__(self):
        return "<%s:id=%s at %#x>" % (self.__class__.__name__, self.getId(),
            id(self))

class BaseImages(xmlNode.BaseNodeCollection):
    tag = "images"

class Handler(xmllib.DataBinder):
    imageClass = BaseImage
    imagesClass = BaseImages
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.imageClass, self.imageClass.tag)
        self.registerType(self.imagesClass, self.imagesClass.tag)
