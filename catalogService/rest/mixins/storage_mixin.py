#!/usr/bin/python
#
# Copyright (c) 2008 rPath, Inc.
#

import os
import sys
import time

from conary.lib import util

from catalogService import errors
from catalogService import instanceStore
from catalogService import storage
from catalogService.rest import baseDriver
from catalogService.rest.models import clouds

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

    @classmethod
    def _getCloudNameFromConfig(cls, config):
        return config['name']

    @classmethod
    def _getCloudNameFromDescriptorData(cls, descriptorData):
        return descriptorData.getField('name')

    def isValidCloudName(self, cloudName):
        cloudConfig = self._getCloudConfiguration(cloudName)
        return bool(cloudConfig)

