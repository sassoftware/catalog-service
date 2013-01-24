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
            email = request.mintAuth.email,
            username = request.mintAuth.username,
            fullName = request.mintAuth.fullName,
            isAdmin = bool(request.mintAuth.admin),
            preferences = preferences,
            displayRepositories = bool(self.hasRepositories()))
        return XmlResponse(response)
    
    def serviceinfo(self, request):
        responseId = self.url(request, "serviceinfo")
        # TODO:  Get proper version/type in here.  See RBL-4191.
        # For type, client needs "full", "limited", or "disabled"
        response = serviceInfo.ServiceInfo(id = responseId,
            version = "1",
            type = "full")
        return XmlResponse(response)

    # See if there are any repositories that the current user can browse
    def hasRepositories(self):
        return len(self.db.listProducts(prodtype = 'Repository').products)
