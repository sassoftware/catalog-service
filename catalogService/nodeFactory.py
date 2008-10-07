#
# Copyright (c) 2008 rPath, Inc.
#

class NodeFactory(object):
    baseUrl = None
    __slots__ = [ '_urlParams',
        'cloudFactory', 'environmentCloudFactory',
        'environmentFactory', 'imageFactory', 'instanceFactory',
        'instanceTypeFactory', 'keyPairFactory', 'securityGroupFactory', ]

    def __init__(self, **kwargs):
        for slot in self.__slots__:
            if not slot.startswith('_'):
                setattr(self, slot, kwargs.get(slot, None))
        self._urlParams = None

    def newCloud(self, *args, **kwargs):
        node = self.cloudFactory(*args, **kwargs)
        node.setId(self.getCloudUrl(node))
        return node

    def newImage(self, *args, **kwargs):
        node = self.imageFactory(*args, **kwargs)
        node.setId(self.getImageUrl(node))
        return node

    def newInstance(self, *args, **kwargs):
        node = self.instanceFactory(*args, **kwargs)
        node.setId(self.getInstanceUrl(node))
        return node

    def newEnvironment(self, *args, **kwargs):
        node = self.environmentFactory(*args, **kwargs)
        return node

    def newEnvironmentCloud(self, *args, **kwargs):
        node = self.environmentCloudFactory(*args, **kwargs)
        node.setId(self.getCloudUrl(node))
        return node

    def newInstanceType(self, *args, **kwargs):
        node = self.instanceTypeFactory(*args, **kwargs)
        node.setId(self.getInstanceTypeUrl(node))
        return node

    def newKeyPair(self, *args, **kwargs):
        node = self.keyPairFactory(*args, **kwargs)
        node.setId(self.getKeyPairUrl(node))
        return node

    def newSecurityGroup(self, *args, **kwargs):
        node = self.securityGroupFactory(*args, **kwargs)
        node.setId(self.getSecurityGroupUrl(node))
        return node

    @classmethod
    def join(cls, *args):
        """Join the arguments into a URL"""
        return '/'.join(args)

    @classmethod
    def getCloudUrl(cls, node):
        return cls._getCloudUrl(node.getCloudType(), node.getCloudName())

    @classmethod
    def getImageUrl(cls, node):
        return cls.join(cls.getCloudUrl(node), 'images', node.getId())

    @classmethod
    def getInstanceUrl(cls, node):
        return cls.join(cls.getCloudUrl(node), 'instances', node.getId())

    def getInstanceTypeUrl(self, node):
        cloudUrl = self._getCloudUrlFromParams()
        return self.join(cloudUrl, 'instanceTypes', node.getId())

    def getKeyPairUrl(self, node):
        cloudUrl = self._getCloudUrlFromParams()
        return self.join(cloudUrl, 'keyPairs', node.getId())

    def getSecurityGroupUrl(self, node):
        cloudUrl = self._getCloudUrlFromParams()
        return self.join(cloudUrl, 'securityGroups', node.getId())

    @classmethod
    def _getCloudUrl(cls, cloudType, cloudName):
        return cls.join(cls.baseUrl, 'clouds', cloudType, cloudName)

    def _getCloudUrlFromParams(self):
        return self._getCloudUrl(self._urlParams['cloudType'],
                                 self._urlParams['cloudName'])

    def _getUrlParams(self):
        return self._urlParams

    def _setUrlParams(self, urlParams):
        self._urlParams = urlParams

    urlParams = property(_getUrlParams, _setUrlParams)
