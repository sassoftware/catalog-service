#!/usr/bin/python
#
# Copyright (c) SAS Institute Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


from rpath_storage import api1
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
