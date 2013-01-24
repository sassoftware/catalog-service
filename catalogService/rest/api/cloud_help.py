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
import urllib

from catalogService import errors
from catalogService.rest.api.base import BaseCloudController
from catalogService.rest.middleware.response import HtmlFileResponse

class CloudHelpController(BaseCloudController):
    # Special controller, that serves static files from a directory
    def getNextController(self, method, subDir, url, args, kwargs):
        path = subDir
        if url:
            path += '/' + url
        return self.serveHelpFile, '', (path, ), {}

    def serveHelpFile(self, request, helpFilePath, *args, **kwargs):
        helpDir = os.path.join(request._helpDir,
            request._driverHelpDir % dict(driverName = self.driver.driverName))

        # Get rid of any potential ..
        pathParts = [ x for x in helpFilePath.split('/') if x not in ['', '..'] ]
        path = os.path.join(helpDir, *pathParts)
        if not os.path.exists(path):
            raise errors.HttpNotFound()
        return HtmlFileResponse(path)
