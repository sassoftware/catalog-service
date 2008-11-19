#!/usr/bin/python2.4
#
# Copyright (c) 2008 rPath, Inc.  All Rights Reserved.
#

import os
import urllib

from catalogService import errors
from catalogService.rest.base_cloud import BaseCloudController
from catalogService.rest.response import HtmlFileResponse

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
