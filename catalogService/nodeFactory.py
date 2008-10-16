#
# Copyright (c) 2008 rPath, Inc.
#

import urllib

class NodeFactory(object):
    __slots__ = [ 'cloudFactory', 'credentialsFactory',
        'credentialsFieldFactory', 'credentialsFieldsFactory',
        'environmentCloudFactory', 'environmentFactory',
        'imageFactory', 'instanceFactory',
        'instanceTypeFactory', 'keyPairFactory', 'securityGroupFactory',
        'baseUrl', 'cloudType', 'cloudName']

    def __init__(self, **kwargs):
        for slot in self.__slots__:
            if not slot.startswith('_'):
                setattr(self, slot, kwargs.get(slot, None))

    def newCloud(self, *args, **kwargs):
        node = self.cloudFactory(*args, **kwargs)
        node.setId(self.getCloudUrl(node))
        return node

    def newCredentials(self, valid, fields = None):
        if fields is None:
            fields = []
        fieldsNode = self.credentialsFieldsFactory()
        for credName, credVal in fields:
            fieldsNode.append(self.credentialsFieldFactory(
                credentialName = credName, value = credVal))
        credsNode = self.credentialsFactory(fields = fieldsNode,
                                            valid = valid)
        return credsNode

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

    def getCloudUrl(self, node):
        return self._getCloudUrl(node.getCloudType(), node.getCloudName())

    def getImageUrl(self, node):
        return self.join(self.getCloudUrl(node), 'images',
                        self._quote(node.getId()))

    def getInstanceUrl(self, node):
        return self.join(self.getCloudUrl(node), 'instances',
                        self._quote(node.getId()))

    def getInstanceTypeUrl(self, node):
        cloudUrl = self._getCloudUrlFromParams()
        return self.join(cloudUrl, 'instanceTypes', self._quote(node.getId()))

    def getKeyPairUrl(self, node):
        cloudUrl = self._getCloudUrlFromParams()
        return self.join(cloudUrl, 'keyPairs', self._quote(node.getId()))

    def getSecurityGroupUrl(self, node):
        cloudUrl = self._getCloudUrlFromParams()
        return self.join(cloudUrl, 'securityGroups',
                         self._quote(node.getId()))

    def _getCloudUrl(self, cloudType, cloudName):
        return self.join(self.baseUrl, 'clouds', cloudType, cloudName)

    def _getCloudUrlFromParams(self):
        return self._getCloudUrl(self.cloudType,
                                 self.cloudName)

    @classmethod
    def _quote(cls, data):
        return urllib.quote(data, safe="")
