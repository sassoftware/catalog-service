#!/usr/bin/python
#
# Copyright (c) 2008 rPath, Inc.
#

import os
import sys

from conary.lib import util

from catalogService import clouds
from catalogService import errors
from catalogService import instanceStore
from catalogService import storage

from catalogService.rest import baseDriver

class StorageMixin(object):
    instanceStorageClass = storage.DiskStorage

    @classmethod
    def configureCloud(cls, store, config):
        cloudName = cls._sanitizeKey(cls._getCloudNameFromConfig(config))
        for k, v in config.iteritems():
            store.set("%s/%s" % (cloudName, k), v)

    def _enumerateConfiguredClouds(self):
        store = self._getConfigurationDataStore()
        ret = []
        for cloudName in sorted(store.enumerate()):
            ret.append(self._getCloudConfiguration(cloudName))
        return ret

    def _getCredentialsDataStore(self):
        path = os.path.join(self._cfg.storagePath, 'credentials',
            self.cloudType)
        cfg = storage.StorageConfig(storagePath = path)
        return storage.DiskStorage(cfg)

    def _getConfigurationDataStore(self, cloudName = None):
        path = os.path.join(self._cfg.storagePath, 'configuration',
            self.cloudType)
        if cloudName is not None:
            path += '/' + self._sanitizeKey(cloudName)
        cfg = storage.StorageConfig(storagePath = path)
        return storage.DiskStorage(cfg)

    def _getInstanceStore(self, keyPrefix):
        path = os.path.join(self._cfg.storagePath, 'instances',
            self.cloudType)
        cfg = storage.StorageConfig(storagePath = path)

        dstore = self.instanceStorageClass(cfg)
        return instanceStore.InstanceStore(dstore, keyPrefix)

    def _getCloudCredentialsForUser(self, cloudName):
        return self._getCredentialsForCloudName(cloudName)[1]

    def _getCredentialsForCloudName(self, cloudName):
        cloudConfig = self._getCloudConfiguration(cloudName)
        if not cloudConfig:
            return {}, {}

        store = self._getCredentialsDataStore()
        creds = self._readCredentialsFromStore(store, self.userId, cloudName)
        if not creds:
            return cloudConfig, creds
        # Protect the password fields
        credDesc = self.getCredentialsDescriptor()
        for field in credDesc.getDataFields():
            if field.password and field.name in creds:
                creds[field.name] = util.ProtectedString(creds[field.name])
        return cloudConfig, creds

    @classmethod
    def _sanitizeKey(cls, key):
        return key.replace('/', '_')

    @classmethod
    def _writeCredentialsToStore(cls, store, userId, cloudName, credentials):
        userId = userId.replace('/', '_')
        for k, v in credentials.iteritems():
            key = "%s/%s/%s" % (userId, cloudName, k)
            store.set(key, v)

    @classmethod
    def _readCredentialsFromStore(cls, store, userId, cloudName):
        userId = userId.replace('/', '_')
        return dict(
            (os.path.basename(k), store.get(k))
                for k in store.enumerate("%s/%s" % (userId, cloudName)))

    def _getCloudConfiguration(self, cloudName):
        store = self._getConfigurationDataStore(cloudName)
        return dict((k, store.get(k)) for k in store.enumerate())

    def drvGetCloudConfiguration(self, isAdmin = False):
        return self._getCloudConfiguration(self.cloudName)

    def drvCreateCloud(self, descriptorData):
        cloudName = self._getCloudNameFromDescriptorData(descriptorData)
        config = dict((k.getName(), k.getValue())
            for k in descriptorData.getFields())
        self.drvVerifyCloudConfiguration(config)
        store = self._getConfigurationDataStore()
        if store.exists(cloudName):
            raise errors.CloudExists()
        self.configureCloud(store, config)
        return self._createCloudNode(config)

    def drvVerifyCloudConfiguration(self, config):
        pass

    def drvSetUserCredentials(self, fields):
        valid = self.drvValidateCredentials(fields)
        if not valid:
            raise errors.PermissionDenied(
                message = "The supplied credentials are invalid")
        data = dict((x.getName(), x.getValue()) for x in fields.getFields())
        store = self._getCredentialsDataStore()
        self._writeCredentialsToStore(store, self.userId, self.cloudName, data)
        node = self._nodeFactory.newCredentials(valid)
        return node

    def drvValidateCredentials(self, credentials):
        cdata = dict((x.getName(), x.getValue()) for x in credentials.getFields())
        try:
            self.drvCreateCloudClient(cdata)
        except errors.PermissionDenied:
            return False
        return True

    def drvRemoveCloud(self):
        store = self._getConfigurationDataStore()
        store.delete(self.cloudName)

    @classmethod
    def _addImageDataFromMintData(cls, image, mintImageData, methodMap):
        shortName = os.path.basename(mintImageData['baseFileName'])
        longName = "%s/%s" % (mintImageData['buildId'], shortName)
        image.setShortName(shortName)
        image.setLongName(longName)
        image.setDownloadUrl(mintImageData['downloadUrl'])
        image.setBuildPageUrl(mintImageData['buildPageUrl'])
        image.setBaseFileName(mintImageData['baseFileName'])
        image.setBuildId(mintImageData['buildId'])

        for key, methodName in methodMap.iteritems():
            getattr(image, methodName)(mintImageData.get(key))

    @classmethod
    def _sanitizeKey(cls, key):
        return key.replace('/', '_')

    def _setState(self, instanceId, state):
        self.log_debug("Instance %s: setting state to `%s'", instanceId, state)
        return self._instanceStore.setState(instanceId, state)

    def getLaunchInstanceParameters(self, image, descriptorData):
        params = baseDriver.BaseDriver.getLaunchInstanceParameters(self, image,
            descriptorData)
        imageId = params['imageId']
        instanceName = params['instanceName']
        instanceId = self._instanceStore.newKey(imageId = imageId)
        self._instanceStore.setInstanceName(instanceId, instanceName)
        self._instanceStore.setState(instanceId, 'Creating')

        params['instanceId'] = instanceId
        return params

    def launchInstanceInBackground(self, image, **params):
        instanceId = params['instanceId']
        self._instanceStore.setPid(instanceId)
        try:
            self.launchInstanceProcess(image, **params)
        finally:
            self._instanceStore.deletePid(instanceId)
            self.launchInstanceInBackgroundCleanup(image, **params)

    def launchInstanceInBackgroundCleanup(self, image, **params):
        pass
