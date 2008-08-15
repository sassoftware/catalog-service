#
# Copyright (c) 2008 rPath, Inc.
#

import urllib
from catalogService import xmlNode

class BaseRequest(object):
    __slots__ = [ '_userId', '_password' ]
    def __init__(self):
        self._userId = None
        self._password = None

    def setUser(self, user):
        self._userId = user

    def getUser(self):
        return self._userId

    def setPassword(self, password):
        self._password = password

    def getPassword(self):
        return self._password

    def getContentLength(self):
        cl = self.getHeader('Content-Length')
        if cl is not None:
            return int(cl)
        return 0

    def getAbsoluteURI(self):
        "Return the absolute URI for this request"
        schemeNetloc = self.getSchemeNetloc()
        return "%s%s" % (self.getSchemeNetloc(), self.getRelativeURI())

    def getAbsoluteURIPath(self):
        uri = self.getAbsoluteURI()
        return urllib.splitquery(uri)[0]

    #{ Methods to be redefined in subclasses
    def getSchemeNetloc(self):
        """Return the scheme and network location for this request"""

    def getRelativeURI(self):
        "Return the relative URI for this request"

    def getHeader(self, key):
        "Return a specific header"

    def getRequestIP(self):
        "Returns the IP address from which the request was issued"

    def read(self, amt = None):
        "Called when reading the request body"

    def iterHeaders(self):
        "Iterate over the headers"
    #}


class Response(object):
    __slots__ = [ '_headersOut', '_data', '_file', '_code' ]
    BUFFER_SIZE = 16384
    def __init__(self, contentType = None, headers = None, data = None,
                 fileObj = None, code = None):
        self._headersOut = {}
        self._data = self._file = None
        self._code = code or 200

        if headers is None:
            headers = {}
        if contentType is None:
            contentType = 'application/xml'
        headers['Content-Type'] = contentType

        for k, v in headers.iteritems():
            if isinstance(v, list):
                self.addHeaders(k, v)
            else:
                self.addHeader(k, v)

        if data is not None:
            # We can pass a node directly
            if hasattr(data, 'getElementTree'):
                hndlr = xmlNode.Handler()
                self._data = hndlr.toXml(data)
            else:
                self._data = data
        elif fileObj:
            self._file = fileObj
        elif self._code == 200:
            assert False, "no data present"

    def addHeader(self, key, value):
        self._headersOut[key] = str(value)

    def addHeaders(self, key, values):
        assert(isinstance(values, list))
        self._headersOut[key] = [ str(x) for x in values ]

    def addContentLength(self):
        hname = 'Content-Length'
        if self._data is not None:
            self.addHeader(hname, len(self._data))
            return
        self._file.seek(0, 2)
        fileSize = self._file.tell()
        self._file.seek(0)
        self.addHeader(hname, fileSize)

    def serveResponse(self, write):
        if self._data is not None:
            write(self._data)
            return
        while 1:
            buf = self._file.read(self.BUFFER_SIZE)
            if not buf:
                break
            write(buf)

    def iterHeaders(self):
        for key, val in self._headersOut.items():
            if isinstance(val, list):
                for v in val:
                    yield key, v
            else:
                yield key, val

    def getCode(self):
        return self._code
