#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import os
import urllib

from catalogService.rest.models import clouds
from catalogService.rest.models import cloud_types

class NodeFactory(object):
    __slots__ = [ 'cloudConfigurationDescriptorFactory',
        'credentialsDescriptorFactory',
        'cloudFactory', 'cloudTypeFactory', 'credentialsFactory',
        'credentialsFieldFactory', 'credentialsFieldsFactory',
        'imageFactory', 'instanceFactory', 'instanceUpdateStatusFactory',
        'instanceTypeFactory', 'instanceLaunchJobFactory',
        'jobTypeFactory', 'keyPairFactory',
        'securityGroupFactory',
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
        searchParams = dict(cloudName = node.getCloudName(),
                cloudType = self.cloudType,
                status = 'Running')
        node.setActiveJobs(clouds.ActiveJobs(href = self.getJobSearchUrl(
            'instance-launch', searchParams)))
        return node

    def newCloudConfigurationDescriptor(self, descr):
        cloudTypeUrl = self._getCloudTypeUrl(self.cloudType)

        for field in descr.getDataFields():
            for helpNode in (field.help or []):
                href = helpNode.href
                if '://' not in href:
                    helpNode.href = "%s/help/%s" % (cloudTypeUrl, href)
        return descr

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
        return self.refreshInstance(node)

    def refreshInstance(self, node):
        instanceUrl = self.getInstanceUrl(node)
        node.setId(instanceUrl)
        node.setForceUpdateUrl("%s/forceUpdate" % instanceUrl)
        node.setCloudType(self.cloudType)
        updateStatus = self.instanceUpdateStatusFactory()
        updateStatus.setState('')
        updateStatus.setTime('')
        node.setUpdateStatus(updateStatus)
        node.setOutOfDate(False)
        # Software stuff
        for instSoftware in (node.getInstalledSoftware() or []):
            isid = instSoftware.getId()
            isid = "%s/installedSoftware/%s" % (instanceUrl, isid)
            instSoftware.setId(isid)

            tc = instSoftware.getTroveChanges()
            if tc:
                href = tc.getHref()
                if href:
                    tc.setHref("%s/troveChanges" % isid)
        for availUpdate in (node.getAvailableUpdate() or []):
            href = os.path.basename(availUpdate.getId())
            availUpdate.setId("%s/availableUpdates/%s" %
                (instanceUrl, href))
            instSoftware = availUpdate.getInstalledSoftware()
            href = os.path.basename(instSoftware.getHref())
            instSoftware.setHref("%s/installedSoftware/%s" %
                (instanceUrl, href))
            troveChanges = availUpdate.getTroveChanges()
            href = os.path.basename(troveChanges.getHref())
            troveChanges.setHref("%s/availableUpdates/%s/troveChanges" %
                (instanceUrl, href))
        return node

    def newInstanceLaunchJob(self, node):
        node.set_id(self.getJobIdUrl(node.get_id(), node.get_type()))
        imageId = node.get_imageId()
        if imageId:
            node.set_imageId(self._getImageUrl(node, imageId))
        for result in (node.get_resultResource() or []):
            href = result.get_href()
            if href:
                result.set_href(self._getInstanceUrl(node, href))
        return node

    def newLaunchDescriptor(self, descriptor):
        cloudTypeUrl = self._getCloudTypeUrl(self.cloudType)

        for field in descriptor.getDataFields():
            for helpNode in field.help:
                href = helpNode.href
                if '://' not in href:
                    helpNode.href = "%s/help/%s" % (cloudTypeUrl, href)
        return descriptor

    def newSecurityGroup(self, instanceId, secGroup):
        sgId = self.join(self._getCloudUrl(self.cloudType, self.cloudName),
            'instances', instanceId, 'securityGroups',
            self._quote(secGroup.getId()))
        secGroup.setId(sgId)
        return secGroup

    def getJobIdUrl(self, jobId, jobType):
        jobId = str(jobId)
        jobType = os.path.basename(jobType)
        return self.join(self.baseUrl, 'jobs', 'types', jobType, 'jobs',
            jobId)

    def getJobSearchUrl(self, jobType, params):
        q = urllib.quote_plus
        params = sorted(params.items())
        params = '&'.join("%s=%s" % (q(x, safe=':'), q(y, safe=':'))
            for (x, y) in params)
        return self.join(self.baseUrl, 'jobs', 'types', jobType,
            'jobs?' + params)

    @classmethod
    def join(cls, *args):
        """Join the arguments into a URL"""
        if args[0][-1] == '/':
            args = list(args)
            args[0] = args[0][:-1]
        return '/'.join(args)

    def getCloudUrl(self, node):
        if hasattr(node, "get_cloudName"):
            cloudName = node.get_cloudName()
        else:
            cloudName = node.getCloudName()
        return self._getCloudUrl(self.cloudType, cloudName)

    def getImageUrl(self, node):
        return self._getImageUrl(node, node.getId())

    def _getImageUrl(self, node, imageId):
        if imageId is None:
            return None
        return self.join(self.getCloudUrl(node), 'images',
                        self._quote(imageId))

    def getInstanceUrl(self, node):
        return self._getInstanceUrl(node, node.getId())

    def _getInstanceUrl(self, node, instanceId):
        if instanceId is None:
            return None
        instanceId = instanceId.split('/')[-1]
        return self.join(self.getCloudUrl(node), 'instances',
                        self._quote(instanceId))

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
