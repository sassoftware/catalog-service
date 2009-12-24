#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import base64

from conary.lib import coveragehook
from conary.lib import util

from catalogService.utils import logger as rlogging
from restlib.http import modpython

from catalogService import errors
from catalogService.rest.api import site
from catalogService.rest.middleware import auth
from catalogService.rest.middleware import response

class Request(modpython.ModPythonRequest):
    _helpDir = '/usr/share/catalog-service/help'
    _driverHelpDir = 'drivers/%(driverName)s'

class ModPythonHttpHandler(modpython.ModPythonHttpHandler):
    requestClass = Request

class ApacheRESTHandler(object):
    httpHandlerClass = ModPythonHttpHandler
    def __init__(self, restdb):
        self.handler = self.httpHandlerClass(
            site.CatalogServiceController(restdb))
        self.handler.addCallback(errors.ErrorMessageCallback())
        self.addAuthCallback(restdb)
        # It is important that the logger callback is always called, so keep
        # this last
        self.handler.addCallback(rlogging.LoggerCallback())

    def addAuthCallback(self, restdb):
        self.handler.addCallback(auth.AuthenticationCallback(restdb))

    def handle(self, req):
        logger = self.getLogger(req)
        self.handler.setLogger(logger)
        rlogging.LoggerCallback.logger = logger
        return self.handler.handle(req, pathPrefix=self.pathPrefix)

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
    _handler = ApacheRESTHandler('/TOP', restDb)
    return _handler.handle(req)
