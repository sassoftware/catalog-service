#
# Copyright (c) 2008 rPath, Inc.
#

import BaseHTTPServer

class BaseRequest(object):
    #{ Methods to be redefined in subclasses
    def getAbsoluteURI(self):
        "Return the absolute URI for this request"

    def getRelativeURI(self):
        "Return the relative URI for this request"

    def _read(self, amt = None):
        "Called when reading the request body"
    #}

class StandaloneRequest(BaseRequest):
    __slots__ = [ '_req', '_read' ]
    def __init__(self, req):
        BaseRequest.__init__(self)
        self._req = req
        self._read = self._req.rfile.read

    def getRelativeURI(self):
        return self._req.path

    def getAbsoluteURI(self):
        hostport = self._req.host
        if self._req.port != 80 and ':' not in hostport:
            hostport = "%s:%s" % (self._req.host, self._req.port)
        return "http://%s%s" % (hostport, self._req.path)

class Response(object):
    __slots__ = [ '_headersOut', '_data', '_file' ]
    BUFFER_SIZE = 16384
    def __init__(self, contentType = None, headers = None, data = None,
                 fileObj = None):
        self._headersOut = {}
        self._data = self._file = None

        if headers is None:
            headers = {}
        if contentType is not None:
            headers['Content-Type'] = contentType

        for k, v in headers.iteritems():
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

class BaseRESTHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        pass

    def do_GET(self):
        req = self._validateHeaders()
        self._auth()

        if self.path == '/crossdomain.xml':
            return self._handleResponse(self.serveCrossDomainFile())
        if self.path == '/%s/clouds/ec2/images' % self.server.toplevel:
            return self.enumerateImages(req)
        if self.path == '/%s/clouds/ec2/instances' % self.server.toplevel:
            return self.enumerateInstances(req)
        if self.path == '/%s/clouds/ec2/instanceTypes' % self.server.toplevel:
            return self.enumerateInstanceTypes(req)


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

    def _handleResponse(self, response):
        response.addContentLength()
        self.send_response(200)
        for k, v in response.iterHeaders():
            self.send_header(k, v)
        self.end_headers()

        response.serveResponse(self.wfile.write)

    def enumerateImages(self, req):
        import images
        import driver_ec2

        awsPublicKey = '16CVNRTTWQG9MZ517782'
        awsPrivateKey = 'B/kKJ5K+jcr3/Sr2DSMRx6dMXzqdaEv+4yFwOUj/'

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        prefix = req.getAbsoluteURI()
        node = drv.getAllImages(prefix = prefix)
        hndlr = images.Handler()
        data = hndlr.toXml(node)

        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def enumerateInstances(self, req):
        import images
        import driver_ec2

        awsPublicKey = '16CVNRTTWQG9MZ517782'
        awsPrivateKey = 'B/kKJ5K+jcr3/Sr2DSMRx6dMXzqdaEv+4yFwOUj/'

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        prefix = req.getAbsoluteURI()
        node = drv.getAllInstances(prefix = prefix)
        hndlr = images.Handler()
        data = hndlr.toXml(node)

        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def enumerateInstanceTypes(self, req):
        import images
        import driver_ec2

        awsPublicKey = '16CVNRTTWQG9MZ517782'
        awsPrivateKey = 'B/kKJ5K+jcr3/Sr2DSMRx6dMXzqdaEv+4yFwOUj/'

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        prefix = req.getAbsoluteURI()
        node = drv.getAllInstanceTypes(prefix=prefix)

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
        return Response(contentType = 'application/xml', fileObj = f)

class HTTPServer(BaseHTTPServer.HTTPServer):
    toplevel = 'TOPLEVEL'

if __name__ == '__main__':
    h = HTTPServer(("", 1234), BaseRESTHandler)
    h.serve_forever()
