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
        self.addAuthCallback()
        # It is important that the logger callback is always called, so keep
        # this last
        self.handler.addCallback(rlogging.LoggerCallback())

    def addAuthCallback(self):
        self.handler.addCallback(auth.AuthenticationCallback(self.storageConfig))

    def handle(self, req):
        logger = self.getLogger(req)
        self.handler.setLogger(logger)
        rlogging.LoggerCallback.logger = logger
        return self.handler.handle(req, req.unparsed_uri[len(self.pathPrefix):])

    def getLogger(self, req):
        logger = rlogging.getLogger('catalog-service', None)
        logger.setAddress(req.connection.remote_ip)
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
