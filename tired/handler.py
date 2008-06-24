#
# Copyright (c) 2008 rPath, Inc.
#

import BaseHTTPServer

class BaseRequest(object):
    __slots__ = [ '_headersSent' ]
    BUFFER_SIZE = 16384

    def __init__(self):
        self._headersSent = False

    def write(self, data):
        self._sendHeaders()
        self._write(data)

    def writeFromFile(self, fileObj):
        self._sendHeaders()
        while 1:
            buf = fileObj.read(self.BUFFER_SIZE)
            if not buf:
                break
            self._write(buf)

    def _sendHeaders(self):
        "Send headers"
        if self._headersSent:
            return
        for key, val in self._iterHeadersOut():
            if not isinstance(val, list):
                val = [ val ]
            for v in val:
                self._sendHeader(key, v)
        self._endHeaders(self)
        self._headersSent = True

    #{ Methods to be redefined in subclasses
    def addHeader(self, key, value):
        "Add a single header value"

    def addHeaders(self, key, values):
        "Add a multi-valued header"

    def getAbsoluteURI(self):
        "Return the absolute URI for this request"

    def getRelativeURI(self):
        "Return the relative URI for this request"

    def _read(self, amt = None):
        "Called when reading the request body"

    def _write(self, data):
        "Called when writing the response body"

    def _sendHeader(self, key, value):
        "Called when sending a header"

    def _endHeaders(self):
        "Called when done sending the headers"

    def _iterHeadersOut(self):
        "Iterate over the outgoing headers"
    #}

class StandaloneRequest(BaseRequest):
    __slots__ = [ '_headersOut', '_req', '_read', '_write',
                  '_sendHeader', '_endHeaders' ]
    def __init__(self, req):
        BaseRequest.__init__(self)
        self._headersOut = {}
        self._req = req
        self._read = self._req.rfile.read
        self._write = self._req.wfile.write
        self._sendHeader = self._req.send_header
        self._endHeaders = self._req.end_headers

    def getRelativeURI(self):
        return self._req.path

    def getAbsoluteURI(self):
        hostport = self._req.host
        if self._req.port != 80 and ':' not in hostport:
            hostport = "%s:%s" % (self._req.host, self._req.port)
        return "http://%s%s" % (hostport, self._req.path)

    def _iterHeadersOut(self):
        for key, val in self._headersOut.items():
            if isinstance(val, list):
                for v in val:
                    yield key, v
            else:
                yield key, val

class Response(object):
    __slots__ = [ '_headersOut', '_data', '_file' ]
    def __init__(self, headers = None, data = None, fileObj = None)
        self._headersOut = {}
        for k, v in headers:
            if isinstance(v, list):
                self.addHeaders(k, v)
            else:
                self.addHeader(k, v)
        if data:
            self._data = data
        elif fileObj:
            self._file = fileObj
        else:
            assert False, "no data present"

    def addHeader(self, key, value):
        self._headersOut[key] = str(value)

    def addHeaders(self, key, values):
        assert(isinstance(values, list))
        self._headersOut[key] = [ str(x) for x in values ]

class BaseRESTHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        pass

    def do_GET(self):
        req = self._validateHeaders()
        self._auth()

        if self.path == '/crossdomain.xml':
            return self.serveCrossDomainFile()
        if self.path == '/%s/clouds/ec2/images' % self.server.toplevel:
            return self.enumerateImages(prefix)
        if self.path == '/%s/clouds/ec2/instances' % self.server.toplevel:
            return self.enumerateInstances(prefix)
        if self.path == '/%s/clouds/ec2/instanceTypes' % self.server.toplevel:
            return self.enumerateInstanceTypes(prefix)


    def do_PUT(self):
        req = self._validateHeaders()
        self._auth()

    def do_POST(self):
        req = self._validateHeaders()
        self._auth()

    def do_DELETE(self):
        req = self._validateHeaders()
        self._auth()

    def _validateHeaders(self):
        if 'Host' not in self.headers:
            # Missing Host: header
            self.send_error(400)
            return

        self.host = self.headers['Host']
        self.port = self.server.server_port
        req = StandaloneRequest(self)
        return req

    def _auth(self):
        pass

    def enumerateImages(self, prefix):
        import images
        import driver_ec2

        awsPublicKey = '16CVNRTTWQG9MZ517782'
        awsPrivateKey = 'B/kKJ5K+jcr3/Sr2DSMRx6dMXzqdaEv+4yFwOUj/'

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        node = drv.getAllImages(prefix = prefix)
        hndlr = images.Handler()
        data = hndlr.toXml(node)

        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def enumerateInstances(self):
        import images
        import driver_ec2

        awsPublicKey = '16CVNRTTWQG9MZ517782'
        awsPrivateKey = 'B/kKJ5K+jcr3/Sr2DSMRx6dMXzqdaEv+4yFwOUj/'

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        node = drv.getAllInstances(prefix = prefix)
        hndlr = images.Handler()
        data = hndlr.toXml(node)

        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def enumerateInstanceTypes(self):
        import images
        import driver_ec2

        awsPublicKey = '16CVNRTTWQG9MZ517782'
        awsPrivateKey = 'B/kKJ5K+jcr3/Sr2DSMRx6dMXzqdaEv+4yFwOUj/'

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        hndlr = images.Handler()
        data = hndlr.toXml(node)

        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)


    def serveCrossDomainFile(self):
        path = "crossdomain.xml"
        f = open(path)
        f.seek(2)
        fileSize = f.tell()
        f.seek(0)

        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", fileSize)
        self.end_headers()
        while 1:
            buf = f.read(16384)
            if not buf:
                break
            self.wfile.write(buf)

class HTTPServer(BaseHTTPServer.HTTPServer):
    toplevel = 'TOPLEVEL'

if __name__ == '__main__':
    h = HTTPServer(("", 1234), BaseRESTHandler)
    h.serve_forever()
