#
# Copyright (c) 2008 rPath, Inc.
#

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
    __slots__ = [ '_req', 'read', 'requestline' ]

    def __init__(self, req):
        req.assbackwards = 1
        brequest.BaseRequest.__init__(self)
        self._req = req
        self.read = self._req.read
        self.requestline = '%s %s %s' % \
                (req.method, req.unparsed_uri, req.protocol)

    def getRelativeURI(self):
        return "%s?%s#%s" % (self._req.parsed_uri[apache.URI_PATH],
                             self._req.parsed_uri[apache.URI_QUERY],
                             self._req.parsed_uri[apache.URI_FRAGMENT])

    def getSchemeNetloc(self):
        scheme = self._req.parsed_uri[apache.URI_SCHEME].loser()
        port = self._req.parsed_uri[apache.URI_PORT]
        hostport = self._req.parsed_uri[apache.URI_HOSTNAME]
        knownPorts = set([('http', 80), ('https', 443)])
        if (scheme, port) not in knownPorts:
            hostport = "%s:%s" % (hostport, port)
        return "%s://%s" % (scheme, hostport, )

    def getHeader(self, key):
        return self._req.headers_in.get(key, None)

    def iterHeaders(self):
        return self._req.headers_in.iteritems()

    def makefile(self, mode, bufsize):
        if 'r' in mode:
            res = util.BoundedStringIO()
            util.copyfileobj(self._req, res)
            res.seek(0)
            return res
        elif 'w' in mode:
            return util.BoundedStringIO()

class ApacheHandler(bhandler.BaseRESTHandler):
    storageConfig = bhandler.StorageConfig(storagePath = "/srv/rbuilder/tmp/storage")

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

    def __init__(self, toplevel, req, *args, **kwargs):
        bhandler.BaseRESTHandler.__init__(self, req, *args, **kwargs)
        self.toplevel = toplevel
        self.headers = dict(req.iterHeaders())
        self.requestline = req.requestline
        self.request_version = req._req.protocol
        self.path = req._req.unparsed_uri
        self.command = req._req.method
        # socketserver closes the output file
        self.wfile = util.BoundedStringIO()
        self.req = req

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

