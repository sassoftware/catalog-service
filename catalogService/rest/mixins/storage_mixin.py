#!/usr/bin/python
#
# Copyright (c) 2008 rPath, Inc.
#

import os

from catalogService import instanceStore
from catalogService import storage

class StorageMixin(object):
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
