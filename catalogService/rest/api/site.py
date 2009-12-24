#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import os

import mint.client
import mint.config
import mint.shimclient

from catalogService import storage
from catalogService.rest.models import userInfo
from catalogService.rest.models import serviceInfo
from catalogService.rest.middleware.response import XmlResponse
from catalogService.rest.api import base
from catalogService.rest.api import jobs
from catalogService.rest.api import users
from catalogService.rest.api import clouds

class CatalogServiceController(base.BaseController):
    urls = {'clouds' : clouds.AllCloudController,
            'users' : users.UsersController,
            'userinfo' : 'userinfo',
            'serviceinfo' : 'serviceinfo',
            'jobs' : jobs.JobsController, }

    def __init__(self, restdb):
        storagePath = os.path.join(restdb.cfg.dataPath, 'catalog')

        storageConfig = storage.StorageConfig(storagePath=storagePath)
        base.BaseController.__init__(self, None, None, storageConfig, restdb)
        self.loadCloudTypes()

    def loadCloudTypes(self):
        self._getController('clouds').loadCloudTypes()

    def _getController(self, url):
        return self.urls[url]

    def userinfo(self, request):
        responseId = self.url(request, "userinfo")
        prefhref = self.url(request, "users") + request.mintAuth.username\
            + "/preferences/"
        preferences = userInfo.Preferences(href=prefhref) 
        response = userInfo.UserInfo(id = responseId,
            username = request.mintAuth.username,
            isAdmin = bool(request.mintAuth.admin),
            preferences = preferences)
        return XmlResponse(response)
    
    def serviceinfo(self, request):
        responseId = self.url(request, "serviceinfo")
        # TODO:  Get proper version/type in here.  See RBL-4191.
        # For type, client needs "full", "limited", or "disabled"
        response = serviceInfo.ServiceInfo(id = responseId,
            version = "1",
            type = "full")
        return XmlResponse(response)
