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
from catalogService.rest.models import instances

class BaseImage(xmlNode.BaseNode):
    tag = 'image'
    __slots__ = [ 'id', 'imageId', 'ownerId', 'longName', 'shortName',
                  'state', 'isPublic', 'buildDescription',
                  'productName', 'role', 'publisher',
                  'awsAccountNumber', 'buildName',
                  'isPrivate_rBuilder', 'productCode', 'productDescription',
                  'is_rBuilderImage', 'cloudName', 'cloudType',
                  'cloudAlias', 'isDeployed', 'buildId',
                  'internalTargetId', 'architecture',
                  'downloadUrl', 'buildPageUrl', 'baseFileName',
                  'checksum', 'size',
                  '_xmlNodeHash', '_fileId', '_targetImageId', '_imageType',
                  'imageSuffix',
                  ]
    _slotAttributes = set([ 'id' ])
    _slotTypeMap = dict(isPublic = bool, isPrivate_rBuilder = bool,
                        is_rBuilderImage = bool, isDeployed = bool,
                        productCode = instances._ProductCode)

    def __init__(self, attrs = None, nsMap = None, **kwargs):

        longName = kwargs.get('longName')
        if longName:
            shortName = longName.split('/')[-1]
            kwargs['shortName'] = shortName
        else:
            # if shortName is supplied, but longName is not, delete it
            kwargs.pop('shortName', None)

        xmlNode.BaseNode.__init__(self, attrs = attrs, nsMap = nsMap, **kwargs)

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

class Handler(xmlNode.Handler):
    imageClass = BaseImage
    imagesClass = BaseImages
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.imageClass, self.imageClass.tag)
        self.registerType(self.imagesClass, self.imagesClass.tag)

# map the way rBuilder refers to data to the call to set the node's
# data to match.
buildToNodeFieldMap = {'buildDescription': 'setBuildDescription',
            'architecture' : 'setArchitecture',
            'productDescription': 'setProductDescription',
            'productName': 'setProductName',
            'isPrivate': 'setIsPrivate_rBuilder',
            'role': 'setRole',
            'createdBy': 'setPublisher',
            'awsAccountNumber': 'setAwsAccountNumber',
            'buildPageUrl' : 'setBuildPageUrl',
            'buildName': 'setBuildName'}
