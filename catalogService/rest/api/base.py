#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

from restlib import controller

class BaseGenericController(controller.RestController):
    pass

class BaseController(BaseGenericController):
    def __init__(self, parent, path, cfg, db):
        self.cfg = cfg
        self.db = db
        BaseGenericController.__init__(self, parent, path, [ cfg, db ])

class BaseCloudController(BaseGenericController):
    def __init__(self, parent, path, driver, cfg, db):
        self.cfg = cfg
        self.driver = driver
        self.db = db
        BaseGenericController.__init__(self, parent, path, [driver, cfg, db])
