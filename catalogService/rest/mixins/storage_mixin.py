#!/usr/bin/python
#
# Copyright (c) 2008 rPath, Inc.
#

import os
import sys
import time

from conary.lib import util

from catalogService import clouds
from catalogService import errors
from catalogService import instanceStore
from catalogService import storage

from catalogService.rest import baseDriver

class StorageMixin(object):

    @classmethod
    def configureCloud(cls, store, config):
        cloudName = cls._sanitizeKey(cls._getCloudNameFromConfig(config))
        for k, v in config.iteritems():
            store.set("%s/%s" % (cloudName, k), v)

    def _enumerateConfiguredClouds(self):
        if not self.isDriverFunctional():
            return []
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

    def launchInstanceInBackground(self, image, auth, **params):
        instanceId = params['instanceId']
        self._instanceStore.setPid(instanceId)
        try:
            try:
                realInstanceId = self.launchInstanceProcess(image, auth, **params)
                if realInstanceId:
                    x509Cert, x509Key = self.getWbemX509()
                    self._instanceStore.storeX509(realInstanceId, x509Cert, x509Key)
            except:
                self._setState(instanceId, 'Error')
                raise
        finally:
            self._instanceStore.deletePid(instanceId)
            self.launchInstanceInBackgroundCleanup(image, **params)

    def launchInstanceInBackgroundCleanup(self, image, **params):
        self.cleanUpX509()

    def getInstanceFromStore(self, instanceId):
        instanceId = os.path.basename(instanceId)
        storeKey = os.path.join(self._instanceStore._prefix, instanceId)
        expiration = self._instanceStore.getExpiration(instanceId)
        if expiration is None or time.time() > float(expiration):
            # This instance exists only in the store, and expired
            self._instanceStore.delete(storeKey)
            return None
        imageId = self._instanceStore.getImageId(storeKey)
        updateData = self._instanceStore.getUpdateStatusState(storeKey)
        imagesL = self.getImages([imageId])

        # If there were no images read from the instance store, but there
        # was update data present, just continue, so that the update data
        # doesn't get deleted from the store.
        if not imagesL and updateData:
            return None
        if not imagesL:
            # We no longer have this image. Junk the instance
            self._instanceStore.delete(storeKey)
            return None
        image = imagesL[0]

        instanceName = self._instanceStore.getInstanceName(storeKey)
        if not instanceName:
            instanceName = self.getInstanceNameFromImage(image)
        instanceDescription = self.getInstanceDescriptionFromImage(image) \
            or instanceName

        inst = self._nodeFactory.newInstance(id = instanceId,
            imageId = imageId,
            instanceId = instanceId,
            instanceName = instanceName,
            instanceDescription = instanceDescription,
            dnsName = 'UNKNOWN',
            publicDnsName = 'UNKNOWN',
            privateDnsName = 'UNKNOWN',
            state = self._instanceStore.getState(storeKey),
            launchTime = None,
            cloudName = self.cloudName,
            cloudAlias = self.getCloudAlias())

        # Check instance store for updating status, and if it's present,
        # set the data on the instance object.
        updateStatusState = self._instanceStore.getUpdateStatusState(storeKey, None)
        updateStatusTime = self._instanceStore.getUpdateStatusTime(storeKey, None)
        if updateStatusState:
            inst.getUpdateStatus().setState(updateStatusState)
        if updateStatusTime:
            inst.getUpdateStatus().setTime(updateStatusTime)

        return inst

    def getInstancesFromStore(self):
        instanceList = []
        storeInstanceKeys = self._instanceStore.enumerate()
        for storeKey in storeInstanceKeys:
            inst = self.getInstanceFromStore(storeKey)
            if inst is None:
                continue

            instanceList.append(inst)
        return instanceList

    @classmethod
    def _getCloudNameFromConfig(cls, config):
        return config['name']

    @classmethod
    def _getCloudNameFromDescriptorData(cls, descriptorData):
        return descriptorData.getField('name')

    def isValidCloudName(self, cloudName):
        cloudConfig = self._getCloudConfiguration(cloudName)
        return bool(cloudConfig)

    def _createCloudNode(self, cloudConfig):
        cld = self._nodeFactory.newCloud(cloudName = cloudConfig['name'],
                         description = cloudConfig['description'],
                         cloudAlias = cloudConfig['alias'])
        return cld

