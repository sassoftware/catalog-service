#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

import xmlNode

class BaseImage(xmlNode.BaseNode):
    tag = 'image'
    __slots__ = [ 'id', 'imageId', 'ownerId', 'longName', 'shortName',
            'state', 'isPublic', 'buildDescription', 'productName',
            'role', 'publisher', 'awsAccountNumber', 'buildName',
            'isPrivate_rBuilder', 'productDescription']
    def __init__(self, attrs = None, nsMap = None, **kwargs):
        xmlNode.BaseNode.__init__(self, attrs = attrs, nsMap = nsMap)

        self.setId(kwargs.get('id'))
        self.setImageId(kwargs.get('imageId'))
        shortName = None
        longName = kwargs.get('longName')
        if longName:
            shortName = longName.split('/')[-1]
        self.setLongName(longName)
        self.setShortName(shortName)
        self.setState(kwargs.get('state'))
        self.setIsPublic(kwargs.get('isPublic'))
        self.setOwnerId(kwargs.get('ownerId'))
        self.setBuildDescription(kwargs.get('buildDescription'))
        self.setProductDescription(kwargs.get('productDescription'))
        self.setProductName(kwargs.get('productName'))
        self.setRole(kwargs.get('role'))
        self.setPublisher(kwargs.get('publisher'))
        self.setAwsAccountNumber(kwargs.get('awsAccountNumber'))
        self.setBuildName(kwargs.get('buildName'))
        self.setIsPrivate_rBuilder(kwargs.get('isPrivate_rBuilder'))

    def setId(self, data):
        self.id = None
        if data is None:
            return self
        self.id = xmllib.GenericNode().setName('id').characters(data)
        return self

    def getId(self):
        if self.id is None:
            return None
        return self.id.getText()

    def setImageId(self, data):
        self.imageId = None
        if data is None:
            return self
        self.imageId = xmllib.GenericNode().setName('imageId').characters(data)
        return self

    def getImageId(self):
        if self.imageId is None:
            return None
        return self.imageId.getText()

    def setOwnerId(self, data):
        self.ownerId = None
        if data is None:
            return self
        self.ownerId = xmllib.GenericNode().setName('ownerId').characters(data)
        return self

    def getOwnerId(self):
        if self.ownerId is None:
            return None
        return self.ownerId.getText()

    def setLongName(self, data):
        self.longName = None
        if data is None:
            return self
        self.longName = xmllib.GenericNode().setName('longName').characters(data)
        return self

    def getLongName(self):
        if self.longName is None:
            return None
        return self.longName.getText()

    def setShortName(self, data):
        self.shortName = None
        if data is None:
            return self
        self.shortName = xmllib.GenericNode().setName('shortName').characters(data)
        return self

    def getShortName(self):
        if self.shortName is None:
            return None
        return self.shortName.getText()

    def setState(self, data):
        self.state = None
        if data is None:
            return self
        self.state = xmllib.GenericNode().setName('state').characters(data)
        return self

    def getState(self):
        if self.state is None:
            return None
        return self.state.getText()

    def setIsPublic(self, data):
        self.isPublic = None
        if data is None:
            return self
        data = xmllib.BooleanNode.toString(data)
        self.isPublic = xmllib.GenericNode().setName('isPublic').characters(data)
        return self

    def getIsPublic(self):
        if self.isPublic is None:
            return None
        return xmllib.BooleanNode.fromString(self.isPublic.getText())

    def setBuildDescription(self, data):
        self.buildDescription = None
        if data is None:
            return self
        self.buildDescription = xmllib.GenericNode().setName('buildDescription').characters(data)
        return self

    def getBuildDescription(self):
        if self.buildDescription is None:
            return None
        return self.buildDescription.getText()

    def setProductDescription(self, data):
        self.productDescription = None
        if data is None:
            return self
        self.productDescription = xmllib.GenericNode().setName('productDescription').characters(data)
        return self

    def getProductDescription(self):
        if self.productDescription is None:
            return None
        return self.productDescription.getText()

    def setProductName(self, data):
        self.productName = None
        if data is None:
            return self
        self.productName = xmllib.GenericNode().setName('productName').characters(data)
        return self

    def getProductName(self):
        if self.productName is None:
            return None
        return self.productName.getText()

    def setRole(self, data):
        self.role = None
        if data is None:
            return self
        self.role = xmllib.GenericNode().setName('role').characters(data)
        return self

    def getRole(self):
        if self.role is None:
            return None
        return self.role.getText()

    def setPublisher(self, data):
        self.publisher = None
        if data is None:
            return self
        self.publisher = xmllib.GenericNode().setName('publisher').characters(data)
        return self

    def getPublisher(self):
        if self.publisher is None:
            return None
        return self.publisher.getText()

    def setAwsAccountNumber(self, data):
        self.awsAccountNumber = None
        if data is None:
            return self
        self.awsAccountNumber = xmllib.GenericNode().setName('awsAccountNumber').characters(data)
        return self

    def getAwsAccountNumber(self):
        if self.awsAccountNumber is None:
            return None
        return self.awsAccountNumber.getText()

    def setBuildName(self, data):
        self.buildName = None
        if data is None:
            return self
        self.buildName = xmllib.GenericNode().setName('buildName').characters(data)
        return self

    def getBuildName(self):
        if self.buildName is None:
            return None
        return self.buildName.getText()

    def setIsPrivate_rBuilder(self, data):
        self.isPrivate_rBuilder = None
        if data is None:
            return self
        data = xmllib.BooleanNode.toString(data)
        self.isPrivate_rBuilder = xmllib.GenericNode().setName('isPrivate_rBuilder').characters(data)
        return self

    def getIsPrivate_rBuilder(self):
        if self.isPrivate_rBuilder is None:
            return None
        return xmllib.BooleanNode.fromString(self.isPrivate_rBuilder.getText())

    def __repr__(self):
        return "<%s:id=%s at %#x>" % (self.__class__.__name__, self.getId(),
            id(self))

class BaseImages(xmlNode.BaseNodeCollection):
    tag = "images"

class BaseImageType(xmlNode.BaseNode):
    tag = "imageType"
    __slots__ = [ 'label', 'description' ]



class BaseImageTypes(xmlNode.BaseNodeCollection):
    tag = "imageTypes"

class Handler(xmllib.DataBinder):
    imageClass = BaseImage
    imagesClass = BaseImages
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.imageClass, self.imageClass.tag)
        self.registerType(self.imagesClass, self.imagesClass.tag)
