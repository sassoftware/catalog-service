#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
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
