#
# Copyright (c) 2008 rPath, Inc.
#

import os
import base64

from conary.lib import coveragehook
from conary.lib import util

from catalogService import logger as rlogging
from restlib.http import modpython

from catalogService import errors
from catalogService import storage
from catalogService.rest import auth
from catalogService.rest import response, site

class ApacheRESTHandler(object):
    def __init__(self, pathPrefix, storagePath):
        self.pathPrefix = pathPrefix
        self.storageConfig = storage.StorageConfig(storagePath=storagePath)
        self.handler = modpython.ModPythonHttpHandler(
                            site.CatalogServiceController(self.storageConfig))
        self.handler.addCallback(errors.ErrorMessageCallback())


    def addAuthCallback(self):
        self.handler.addCallback(auth.AuthenticationCallback(self.storageConfig))

    def handle(self, req):
        self.handler.setLogger(self.getLogger(req))
        return self.handler.handle(req, req.uri[len(self.pathPrefix):])

    def getLogger(self, req):
        logger = rlogging.getLogger('catalog-service', None)
        logger.setAddress('1.2.3.4')
        return logger

def handler(req):
    """
    The presence of this function in the module allows it to be added directly
    into apache as a mod_python handler.

    The function is for testing purposes only.
    """
    coveragehook.install()
    storageDir = os.path.abspath(os.path.join(req.document_root(),
        '..', '..', 'storage'))
    _handler = ApacheRESTHandler('/TOP', storageDir)
    return _handler.handle(req)
