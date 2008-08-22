#
# Copyright (c) 2008 rPath, Inc.
#

import urllib
from conary.lib import util

from catalogService import xmlNode

class BaseRequest(object):
    """
    This is the base class for a request object coming in from the HTTP server
    implementation.
    Most of the methods will have to be overridden to link to the underlying
    request object used by the HTTP server. For instance, C{mod_python}
    based servers define their own C{request} object, whereas standalone
    Python HTTP servers do not.
    """
    __slots__ = [ '_userId', '_password' ]
    def __init__(self):
        self._userId = None
        self._password = None

    def setUser(self, user):
        self._userId = user

    def getUser(self):
        return self._userId

    def setPassword(self, password):
        self._password = util.ProtectedString(password)

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

    def getServerPort(self):
        "Return the server port"
    #}


class Response(object):
    """
    Abstraction of a response being sent back to a web server.
    The intention is to simplify the job for methods returning useful data to
    the HTTP client.
    """
    __slots__ = [ '_headersOut', '_data', '_file', '_code', '_contentType' ]
    BUFFER_SIZE = 16384
    def __init__(self, contentType = None, headers = None, data = None,
                 fileObj = None, code = None):
        """
        @param contentType: Content type for the response. Defaults to
            C{application/xml}.
        @type contentType: C{str} or None
        @param headers: Additional headers to be sent back to the client.
        @type headers: C{dict} or None
        @param data: Response body, as a string. Exactly one of C{data} and
            C{fileObj} should be defined.
        @type data: C{str} or None
        @param fileObj: Response body, as a file object. Exactly one of
            C{data} and C{fileObj} should be defined.
        @type fileObj: C{file} or None
        @param code: HTTP status code. Defaults to 200.
        @type code: C{int} or None
        """
        self._headersOut = {}
        self._data = self._file = None
        self._code = code or 200

        if headers is None:
            headers = {}
        if contentType is None:
            contentType = 'application/xml'
        self._contentType = contentType

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
        """
        Define additional HTTP headers to be passed down to the client.
        """
        self._headersOut[key] = str(value)

    def addHeaders(self, key, values):
        """
        Define additional HTTP headers to be passed down to the client.
        """
        assert(isinstance(values, list))
        self._headersOut[key] = [ str(x) for x in values ]

    def getContentType(self):
        return self._contentType

    def addContentLength(self):
        """
        Add a C{Content-Length} header to the response.
        The length is derived from the data string or from the data in the
        file object that were passed in at initialization time.
        """
        hname = 'Content-Length'
        if self._data is None and self._file is None:
            return
        if self._data is not None:
            self.addHeader(hname, len(self._data))
            return
        self._file.seek(0, 2)
        fileSize = self._file.tell()
        self._file.seek(0)
        self.addHeader(hname, fileSize)

    def serveResponseBody(self, write):
        """
        Write the response body to the HTTP server.
        """
        if self._data is not None:
            write(self._data)
            return
        if self._file is None:
            return
        while 1:
            buf = self._file.read(self.BUFFER_SIZE)
            if not buf:
                break
            write(buf)

    def iterHeaders(self):
        """
        Iterate over this response's headers.
        """
        for key, val in self._headersOut.items():
            if isinstance(val, list):
                for v in val:
                    yield key, v
            else:
                yield key, val

    def getCode(self):
        """
        @return: the HTTP status code for this response.
        @rtype: C{int}
        """
        return self._code
