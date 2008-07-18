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

def handler(req):
    coveragehook.install()
    try:
        return _handler(req)
    finally:
        coveragehook.save()

def _handler(req):
    r = ApacheRequest(req)
    return apache.OK

class ApacheRequest(brequest.BaseRequest):
    __slots__ = [ '_req', 'read', 'requestline', '_rfile' ]

    def __init__(self, req):
        req.assbackwards = 1
        self._rfile = util.BoundedStringIO()
        util.copyfileobj(req, self._rfile)
        self._rfile.seek(0)
        brequest.BaseRequest.__init__(self)
        self._req = req
        self.requestline = '%s %s %s' % \
                (req.method, req.unparsed_uri, req.protocol)
        self.read = self._read

    def getRelativeURI(self):
        return "%s?%s#%s" % (self._req.parsed_uri[apache.URI_PATH],
                             self._req.parsed_uri[apache.URI_QUERY],
                             self._req.parsed_uri[apache.URI_FRAGMENT])

    def getSchemeNetloc(self):
        via = self._req.headers_in.get('Via')
        if via and self._req.proxyreq:
            # XXX We simply have to err on the side of encrypted requests...
            scheme = 'https'
            hostport = via.split(',')[-1].split()[1]
        else:
            scheme = self._req.is_https() and 'https' or 'http'
            hostport = self._req.headers_in.get('Host')
        return "%s://%s" % (scheme, hostport, )

    def getHeader(self, key):
        return self._req.headers_in.get(key, None)

    def iterHeaders(self):
        return self._req.headers_in.iteritems()

    def makefile(self, mode, bufsize):
        if 'r' in mode:
            self._rfile.seek(0)
            res = util.BoundedStringIO()
            util.copyfileobj(self._rfile, res)
            res.seek(0)
            self._rfile.seek(0)
            return res
        elif 'w' in mode:
            return util.BoundedStringIO()

    def _read(self, *args, **kwargs):
        # SocketServer will close file objects, so we have to work around it
        rfile = self.makefile('r', 0)
        return rfile.read(*arge, **kwargs)

class ApacheHandler(bhandler.BaseRESTHandler):
    def end_headers(self):
        headerData = self.wfile.getvalue()
        if headerData:
            statusLine = headerData.splitlines()[0]
            code, msg = statusLine.split(None, 1)[1].split(None, 1)
            code = int(code)
            if code != 200:
                self.req._req.status = code
        headers = [x.split(': ', 1) for x in headerData.splitlines()[1:] if x]
        for key, val in headers:
            self.req._req.headers_out[key] = val
        bhandler.BaseRESTHandler.end_headers(self)

    def __init__(self, toplevel, storagePath, req, *args, **kwargs):
        bhandler.BaseRESTHandler.__init__(self, req, *args, **kwargs)
        self.toplevel = toplevel
        self.headers = dict(req.iterHeaders())
        self.requestline = req.requestline
        self.request_version = req._req.protocol
        self.path = req._req.unparsed_uri
        self.command = req._req.method
        self.req = req
        # socketserver closes the input and output files
        self.wfile = util.BoundedStringIO()
        self.rfile = self.req.makefile('r', 0)
        self.storageConfig = bhandler.StorageConfig(storagePath = storagePath)

    def setAuthHeader(self, username, passwd):
        self.headers['Authorization'] = 'Basic %s' % \
                base64.b64encode('%s:%s' % (username, passwd))

    def handleApacheRequest(self):
        methodName = 'do_%s' % self.command
        if not hasattr(self, methodName):
            return apache.HTTP_NOT_FOUND
        method = getattr(self, methodName)
        res = method()
        # self.wfile is a BoundedStringIO that the SimpleHTTPServer wrote to
        self.wfile.seek(0)

        util.copyfileobj(self.wfile, self.req._req)
        return 0

    def _createRequest(self):
        bhandler.BaseRESTHandler._createRequest(self)
        return self.req
