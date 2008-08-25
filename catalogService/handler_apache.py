#
# Copyright (c) 2008 rPath, Inc.
#

import os
import base64
from mod_python import apache

from conary.lib import coveragehook
from conary.lib import util

from catalogService import request as brequest
from catalogService import handler as bhandler

class ApacheRequest(brequest.BaseRequest):
    __slots__ = [ '_req', 'read', 'path' ]

    def __init__(self, req):
        brequest.BaseRequest.__init__(self)
        self._req = req
        self.read = self._req.read
        self.setPath(self._req.unparsed_uri)

    def setPath(self, path):
        if path.lower().startswith('http'):
            if path.count('/') > 2:
                self.path = '/' + path.split('/', 3)[-1]
            else:
                self.path = '/'
        else:
            self.path = path

    def getRelativeURI(self):
        return self.path

    def getSchemeNetloc(self):
        via = self._req.headers_in.get('Via')
        if via and self._req.proxyreq:
            # XXX We simply have to err on the side of encrypted requests...
            scheme = 'http'
            hostport = via.split(',')[-1].split()[1]
        else:
            secure = (self._req.subprocess_env.get('HTTPS', 'off').lower() == 'on')
            scheme = secure and 'https' or 'http'
            hostport = self._req.headers_in.get('Host')
        return "%s://%s" % (scheme, hostport, )

    def getHeader(self, key):
        return self._req.headers_in.get(key, None)

    def getRequestIP(self):
        return self.getHeader('X-Forwarded-For') or \
                self._req.get_remote_host(apache.REMOTE_NOLOOKUP)

    def iterHeaders(self):
        return self._req.headers_in.iteritems()

    def getServerPort(self):
        return self._req.server.port

class ApacheHandler(bhandler.BaseRESTHandler):
    _successStatusCodes = set([apache.OK, apache.HTTP_OK])

    def __init__(self, toplevel, storagePath, req, *args, **kwargs):
        self.toplevel = toplevel
        self.request_version = req._req.protocol
        self.command = req._req.method
        self.req = req
        self.storageConfig = bhandler.StorageConfig(storagePath = storagePath)
        bhandler.BaseRESTHandler.__init__(self, req, *args, **kwargs)

    def handleApacheRequest(self):
        methodName = 'do_%s' % self.command
        if not hasattr(self, methodName):
            return apache.HTTP_NOT_FOUND
        method = getattr(self, methodName)
        res = method()

        if self.req._req.status in self._successStatusCodes:
            return apache.OK
        return self.req._req.status

    # We are overriding methods from BaseHTTPRequestHandler to make it work in
    # the mod_python case
    def send_header(self, keyword, value):
        if self.req._req.status in self._successStatusCodes:
            table = self.req._req.headers_out
        else:
            table = self.req._req.err_headers_out

        table[keyword] = value

    def send_response(self, code, message = None):
        self.req._req.status = code

    def end_headers(self):
        # Supposedly this is optional with newer mod_pythons, but it doesn't
        # hurt to use it
        self.req._req.send_http_header()

    def handle(self):
        # We don't need the request handler to read from the file descriptors,
        # the request object is already created by mod_python
        pass

    def finish(self):
        # Nothing to be done here in the mod_python case
        pass

    def setup(self):
        # Nothing to be done here in the mod_python case
        pass

    def _sendContentType(self, contentType):
        self.req._req.content_type = contentType

    def _getWriteMethod(self):
        return self.req._req.write

    def _newRequest(self):
        # Request was created outside of the handler, so just pass it through
        return self.req
