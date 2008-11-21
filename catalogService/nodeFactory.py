#
# Copyright (c) 2008 rPath, Inc.
#

import urllib

from catalogService import clouds
from catalogService import cloud_types

class NodeFactory(object):
    __slots__ = [ 'cloudConfigurationDescriptorFactory',
        'credentialsDescriptorFactory',
        'cloudFactory', 'cloudTypeFactory', 'credentialsFactory',
        'credentialsFieldFactory', 'credentialsFieldsFactory',
        'environmentCloudFactory', 'environmentFactory',
        'imageFactory', 'instanceFactory',
        'instanceTypeFactory', 'keyPairFactory', 'securityGroupFactory',
        'baseUrl', 'cloudType', 'cloudName', 'userId']

    def __init__(self, **kwargs):
        for slot in self.__slots__:
            if not slot.startswith('_'):
                setattr(self, slot, kwargs.get(slot, None))

    def newCloudType(self, *args, **kwargs):
        node = self.cloudTypeFactory(*args, **kwargs)
        cloudTypeId = self._getCloudTypeUrl(self.cloudType)
        node.setId(cloudTypeId)
        node.setCloudInstances(cloud_types.CloudInstances(
            href = self.join(cloudTypeId, 'instances')))
        node.setDescriptorCredentials(cloud_types.DescriptorCredentials(
            href = self.join(cloudTypeId, 'descriptor', 'credentials')))
        node.setDescriptorInstanceConfiguration(
            cloud_types.DescriptorInstanceConfiguration(
                href = self.join(cloudTypeId, 'descriptor', 'configuration')))
        return node

    def newCloud(self, *args, **kwargs):
        node = self.cloudFactory(*args, **kwargs)
        cloudId = self.getCloudUrl(node)
        node.setId(cloudId)
        cloudType = clouds.Type(href = self._getCloudTypeUrl(self.cloudType)).characters(self.cloudType)
        node.setType(cloudType)
        node.setImages(clouds.Images(href = self.join(cloudId, 'images')))
        node.setInstances(clouds.Instances(href = self.join(cloudId, 'instances')))
        node.setUserCredentials(clouds.UserCredentials(href = self.join(cloudId, 'users', self.userId, 'credentials')))
        node.setConfiguration(clouds.Configuration(href = self.join(cloudId,
            'configuration')))
        node.setDescriptorLaunch(clouds.DescriptorLaunch(href =
                                 self.join(cloudId, 'descriptor', 'launch')))
        return node

    def newCloudConfigurationDescriptor(self, *args, **kwargs):
        node = self.cloudConfigurationDescriptorFactory(*args, **kwargs)
        return node

    def newCredentialsDescriptor(self, *args, **kwargs):
        node = self.credentialsDescriptorFactory(*args, **kwargs)
        return node

    def newCloudConfigurationDescriptorData(self, node):
        node.setId(self.join(self._getCloudUrlFromParams(), 'configuration'))
        return node

    def newCredentialsDescriptorData(self, node):
        node.setId(self.join(self._getCloudUrlFromParams(), 'users', self.userId,
            'credentials'))
        return node

    def newCredentials(self, valid, fields = None):
        # XXX deprecated
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
        node.setCloudType(self.cloudType)
        return node

    def newInstance(self, *args, **kwargs):
        node = self.instanceFactory(*args, **kwargs)
        node.setId(self.getInstanceUrl(node))
        node.setCloudType(self.cloudType)
        return node

    def newEnvironment(self, *args, **kwargs):
        node = self.environmentFactory(*args, **kwargs)
        return node

    def newEnvironmentCloud(self, *args, **kwargs):
        node = self.environmentCloudFactory(*args, **kwargs)
        node.setId(self.getCloudUrl(node))
        node.setCloudType(self.cloudType)
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

    def newLaunchDescriptor(self, descriptor):
        cloudTypeUrl = self._getCloudTypeUrl(self.cloudType)

        for field in descriptor.iterRawDataFields():
            for helpNode in field.help:
                href = helpNode.href
                if '://' not in href:
                    helpNode.href = "%s/help/%s" % (cloudTypeUrl, href)
        return descriptor

    @classmethod
    def join(cls, *args):
        """Join the arguments into a URL"""
        return '/'.join(args)

    def getCloudUrl(self, node):
        return self._getCloudUrl(self.cloudType, node.getCloudName())

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

    def _getCloudTypeUrl(self, cloudType):
        return self.join(self.baseUrl, 'clouds', cloudType)

    def _getCloudUrl(self, cloudType, cloudName):
        return self.join(self._getCloudTypeUrl(cloudType), 'instances',
            cloudName)

    def _getCloudUrlFromParams(self):
        return self._getCloudUrl(self.cloudType,
                                 self.cloudName)

    @classmethod
    def _quote(cls, data):
        return urllib.quote(data, safe="")
