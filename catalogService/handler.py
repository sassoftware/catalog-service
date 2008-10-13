#
# Copyright (c) 2008 rPath, Inc.
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

import base64
import BaseHTTPServer
import logging

from catalogService import config
from catalogService import storage

# Monkeypatch BaseHTTPServer for older Python (e.g. the one that
# rLS1 has) to include a function that we rely on. Yes, this is gross.
if not hasattr(BaseHTTPServer, '_quote_html'):
    def _quote_html(html):
        # XXX this data is needed unre-formed by the flex frontend
        return html
        return html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    BaseHTTPServer._quote_html = _quote_html


class BaseRESTHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    storageConfig = storage.StorageConfig(storagePath = "storage")
    logLevel = 1
    error_message_format = '\n'.join(('<?xml version="1.0" encoding="UTF-8"?>',
            '<fault>',
            '  <code>%(code)s</code>',
            '  <message>%(message)s</message>',
            '</fault>'))
    _logFile = None

    def do(self):
        authData = self.headers.get('Authorization', None)
        if authData and authData[:6] == 'Basic ':
            authData = authData[6:]
            authData = base64.decodestring(authData)
            authData = authData.split(':', 1)
        from catalogService.rest import response, site
        from restlib.http import simplehttp

        # XXX don't assume always /TOPLEVEL
        baseUrl = self.path[:9]
        self.path = self.path[9:]
        self._logger = self._getLogger(self.address_string())
        self.handler = simplehttp.SimpleHttpHandler(
                                        site.SiteHandler(authData,
                                                         self.storageConfig),
                                        responseClass=response.CatalogResponse,
                                        logger = self._logger)
        self.handler.handle(self, baseUrl, authData)
    do_GET = do_POST = do_PUT = do_DELETE = do

    @classmethod
    def _getLogger(cls, address):
        if cls._logFile is None:
            handler = logging.StreamHandler()
        else:
            handler = logging.FileHandler(cls._logFile)

        formatter = Formatter()
        handler.setFormatter(formatter)
        logger = Logger('catalog-service')
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

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

class LogRecord(logging.LogRecord):
    def __init__(self, address, *args, **kwargs):
        logging.LogRecord.__init__(self, *args, **kwargs)
        self.address = address

class Logger(logging.Logger):
    def setAddress(self, address):
        self.address = address

    def makeRecord(self, *args, **kwargs):
        address = getattr(self, 'address', '')
        return LogRecord(address, *args, **kwargs)

class Formatter(logging.Formatter):
    _fmt = "%(address)s %(asctime)s %(pathname)s(%(lineno)s) %(levelname)s - %(message)s"

    def __init__(self):
        logging.Formatter.__init__(self, self.__class__._fmt)

    def formatException(self, ei):
        from conary.lib import util
        import StringIO
        excType, excValue, tb = ei
        sio = StringIO.StringIO()
        util.formatTrace(excType, excValue, tb, stream = sio,
            withLocals = False)
        util.formatTrace(excType, excValue, tb, stream = sio,
            withLocals = True)
        return sio.getvalue().rstrip()
