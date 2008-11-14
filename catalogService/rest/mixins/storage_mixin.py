#!/usr/bin/python
#
# Copyright (c) 2008 rPath, Inc.
#

import os

from catalogService import clouds
from catalogService import instanceStore
from catalogService import storage

class StorageMixin(object):
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
            self._cloudType)
        cfg = storage.StorageConfig(storagePath = path)
        return storage.DiskStorage(cfg)

    def _getConfigurationDataStore(self, cloudName = None):
        path = os.path.join(self._cfg.storagePath, 'configuration',
            self._cloudType)
        if cloudName is not None:
            path += '/' + self._sanitizeKey(cloudName)
        cfg = storage.StorageConfig(storagePath = path)
        return storage.DiskStorage(cfg)

    def _getInstanceStore(self, keyPrefix):
        path = os.path.join(self._cfg.storagePath, 'instances',
            self._cloudType)
        cfg = storage.StorageConfig(storagePath = path)

        dstore = storage.DiskStorage(cfg)
        return instanceStore.InstanceStore(dstore, keyPrefix)

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

    def drvGetCloudConfiguration(self):
        return self._getCloudConfiguration(self.cloudName)

    def drvCreateCloud(self, descriptorData):
        cloudName = self._getCloudNameFromDescriptorData(descriptorData)
        config = dict((k.getName(), k.getValue())
            for k in descriptorData.getFields())
        store = self._getConfigurationDataStore()
        self.configureCloud(store, config)
        return self._createCloudNode(config)

    def drvSetUserCredentials(self, fields):
        data = dict((x.getName(), x.getValue()) for x in fields.getFields())
        store = self._getCredentialsDataStore()
        self._writeCredentialsToStore(store, self.userId, self.cloudName, data)
        # XXX validate
        valid = True
        node = self._nodeFactory.newCredentials(valid)
        return node

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

    def _daemonize(self, function, *args, **kw):
        pid = os.fork()
        if pid:
            os.waitpid(pid, 0)
            return
        try:
            try:
                pid = os.fork()
                if pid:
                    # The first child exits and is waited by the parent
                    # the finally part will do the os._exit
                    return
                # Redirect stdin, stdout, stderr
                fd = os.open(os.devnull, os.O_RDWR)
                os.dup2(fd, 0)
                os.dup2(fd, 1)
                os.dup2(fd, 2)
                os.close(fd)
                # Create new process group
                os.setsid()

                os.chdir('/')
                function(*args, **kw)
            except Exception:
                os._exit(1)
        finally:
            os._exit(0)

    def _setState(self, instanceId, state):
        self.log_debug("Instance %s: setting state to `%s'", instanceId, state)
        return self._instanceStore.setState(instanceId, state)

