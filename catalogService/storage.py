#!/usr/bin/python2.4
#
# Copyright (c) 2008-2009 rPath, Inc.
#

from rpath_common.storage import api1
from catalogService import config

DiskStorage = api1.DiskStorage
StorageError = api1.StorageError
InvalidKeyError = api1.InvalidKeyError
KeyNotFoundError = api1.KeyNotFoundError

class StorageConfig(config.BaseConfig, api1.StorageConfig):
    """
    A storage config class inheriting from our base configuration
    """
    def __init__(self, *args, **kwargs):
        config.BaseConfig.__init__(self)
        api1.StorageConfig.__init__(self, *args, **kwargs)

