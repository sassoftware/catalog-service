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


from restlib import controller
from catalogService.rest.middleware.response import XmlStringResponse

class BaseGenericController(controller.RestController):
    pass

class BaseController(BaseGenericController):
    def __init__(self, parent, path, cfg, db):
        self.cfg = db.cfg
        self.storageCfg = cfg
        self.db = db
        BaseGenericController.__init__(self, parent, path, [ cfg, db ])

class BaseCloudController(BaseGenericController):
    def __init__(self, parent, path, driver, cfg, db):
        self.cfg = db.cfg
        self.driver = driver
        self.storageCfg = cfg
        self.db = db
        BaseGenericController.__init__(self, parent, path,
            [driver, cfg, db])

    def PermissionDenied(self, request, msg=''):
        if 'HTTP_X_FLASH_VERSION' in request.headers:
            return XmlStringResponse(msg, status=403)
        return XmlStringResponse(msg, status = 401)

    def getController(self, *args, **kwargs):
        # Reset target configuration
        self.driver._targetConfig = None
        return BaseGenericController.getController(self, *args, **kwargs)
