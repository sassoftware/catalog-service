#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#
"""
Summary
=======
This module implements the abstract interface with a web server, and HTTP
method handles for the abstraction.

URL format
==========
C{/<TOPLEVEL>/clouds}
    - (GET): enumerate available clouds
        Return an enumeration of clouds, with the ID in the format::
            /<TOPLEVEL>/clouds/<cloudName>
        C{<cloudName>} is generally composed of C{<cloudType>} or
        C{<cloudType>/<cloudId>}
        (for the cases where the cloud only exists as a single deployment, like
        Amazon's EC2, or, respectively, as multiple deployments, like Globus
        clouds).

C{/<TOPLEVEL>/clouds/<cloudType>}
    - (GET): enumerate available clouds for this type

C{/<TOPLEVEL>/clouds/<cloudName>/images}
    - (GET): enumerate available images for this cloud.
        - Return an enumeration of images, with the ID in the format::
            /<TOPLEVEL>/clouds/<cloudName>/images/<imageId>
    - (POST): publish a new image for this cloud (not valid for EC2).

C{/<TOPLEVEL>/clouds/<cloudName>/instances}
    - (GET): enumerate available images for this cloud.
        - Return an enumeration of instances, with the ID in the format::
            /<TOPLEVEL>/clouds/<cloudName>/instances/<instanceId>
    - (POST): Launch a new instance.

C{/<TOPLEVEL>/clouds/<cloudName>/instanceTypes}
    - (GET): enumerate available instance types.

C{/<TOPLEVEL>/clouds/<cloudName>/instances/<instanceId>}
    - (DELETE): Terminate a running instance.

C{/<TOPLEVEL>/clouds/<cloudName>/users/<user>/environment}
    - (GET): retrieve the launch environment

C{/<TOPLEVEL>/clouds/<cloudName>/users/<user>/credentials}
    - (GET): Retrieve the user's credentials (and validate them)
    - (POST): Store new credentials

C{/<TOPLEVEL>/users/<user>}
    - (GET): Enumerate the keys defined in the store.
        - Return an enumeration of URIs in the format::
            /<TOPLEVEL>/users/<user>/<key>
    - (POST): Create a new entry in the store.

C{/<TOPLEVEL>/users/<user>/<key>}
    - (GET): Retrieve the contents of a key (if not a collection), or
      enumerate the collection.
    - (PUT): Update a key (if not a collection).
    - (POST): Create a new entry in a collection.
"""
import BaseHTTPServer
import logging

from restlib.http import simplehttp
from catalogService.utils import logger as rlogging

from catalogService import config
from catalogService import errors
from catalogService import storage
from catalogService.rest.middleware import auth
from catalogService.rest.api import site

# Monkeypatch BaseHTTPServer for older Python (e.g. the one that
# rLS1 has) to include a function that we rely on. Yes, this is gross.
if not hasattr(BaseHTTPServer, '_quote_html'):
    def _quote_html(html):
        # XXX this data is needed unre-formed by the flex frontend
        return html
        return html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    BaseHTTPServer._quote_html = _quote_html

class Request(simplehttp.SimpleHttpRequest):
    _helpDir = '/usr/share/catalog-service/help'
    _driverHelpDir = 'drivers/%(driverName)s'

class SimpleHttpHandler(simplehttp.SimpleHttpHandler):
    requestClass = Request

def getHandler(restDb):
    controller = site.CatalogServiceController(restDb)
    handler = SimpleHttpHandler(controller)
    handler.addCallback(auth.AuthenticationCallback(restDb, controller))
    handler.addCallback(errors.ErrorMessageCallback())
    # It is important that the logger callback is always called, so keep this
    # last
    handler.addCallback(rlogging.LoggerCallback())
    return handler

class BaseRESTHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    pathPrefix = '/TOPLEVEL'
    logLevel = 1
    _logFile = None
    handler = None

    @classmethod
    def updateHandler(class_, restDb):
        # Note: this is needed for testing
        class_.handler = getHandler(restDb)

    def do(self):
        self._logger = self._getLogger(self.address_string())
        self.handler.setLogger(self._logger)
        rlogging.LoggerCallback.logger = self._logger
        self.handler.handle(self, pathPrefix=self.pathPrefix)
    do_GET = do_POST = do_PUT = do_DELETE = do

    @classmethod
    def _getLogger(cls, address):
        logger = rlogging.getLogger('catalog-service', cls._logFile)
        logger.setAddress(address)
        return logger

    def _log(self, level, msg, *args, **kwargs):
        if not hasattr(self, '_logger'):
            return BaseHTTPServer.BaseHTTPRequestHandler.log_message(self,
                msg, *args)
        return self._logger.log(level, msg, *args, **kwargs)

    def log_message(self, format, *args):
        return self._log(logging.INFO, format, *args)

    def log_error(self, format, *args):
        return self._log(logging.ERROR, format, *args)
