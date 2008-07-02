#
# Copyright (c) 2008 rPath, Inc.
#

from mod_python import apache

from conary.lib import coveragehook

from catalogService import request as brequest

def handler(req):
    coveragehook.install()
    try:
        return _handler(req)
    finally:
        coveragehook.save()

def _handler(req):
    r = ApacheRequest(req)
    import epdb; epdb.serve(9998)
    return apache.OK

class ApacheRequest(brequest.BaseRequest):
    __slots__ = [ '_req', 'read' ]

    def __init__(self, req):
        brequest.BaseRequest.__init__(self)
        self._req = req
        self.read = self._req.read

    def getRelativeURI(self):
        return "%s?%s#%s" % (self._req.parsed_uri[apache.URI_PATH],
                             self._req.parsed_uri[apache.URI_QUERY],
                             self._req.parsed_uri[apache.URI_FRAGNENT])

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
        return self._req.header_in.iteritems()
