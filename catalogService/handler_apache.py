#
# Copyright (c) 2008 rPath, Inc.
#

import os
import base64

from conary.lib import coveragehook
from conary.lib import util

from catalogService import logger as rlogging
from restlib.http import modpython

from catalogService import storage
from catalogService.rest import response, site

class ApacheRESTHandler(object):
    __slots__ = [ '_basePath', '_req', '_storageConfig' ]
    def __init__(self, basePath, storagePath):
        self._basePath = basePath
        self._storageConfig = storage.StorageConfig(storagePath = storagePath)

    def handle(self, req):
        coveragehook.install()
        self.preProcess(req)
        authData = self.getAuthData(req)
        logger = self.getLogger(req)
        controller = site.SiteHandler(authData, self._storageConfig)
        handler = modpython.ModPythonHttpHandler(controller,
            responseClass=response.CatalogResponse, logger = logger)
        return handler.handle(req, self._basePath, authData)

    def preProcess(self, req):
        """
        Hook that executes prior to the handler's main code
        """

    def getAuthData(self, req):
        """
        Extract the user's credentials from the request
        @return: the user's credentials
        @rtype: C{tuple}
        """
        return ("user", "pass")

    def getLogger(self, req):
        logger = rlogging.getLogger('catalog-service', None)
        logger.setAddress('1.2.3.4')
        return logger

def handler(req):
    """Test handler"""
    storageDir = os.path.abspath(os.path.join(req.document_root(),
        '..', '..', 'storage'))
    return ApacheRESTHandler('/TOP', storageDir).handle(req)
