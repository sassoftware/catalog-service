#
# Copyright (c) 2008 rPath, Inc.
#

import base64
import BaseHTTPServer
import os

import config
import storage

class StorageConfig(config.BaseConfig):
    def __init__(self, storagePath):
        config.BaseConfig.__init__(self)
        self.storagePath = storagePath

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
        return None

    #{ Methods to be redefined in subclasses
    def getAbsoluteURI(self):
        "Return the absolute URI for this request"

    def getRelativeURI(self):
        "Return the relative URI for this request"

    def getHeader(self, key):
        "Return a specific header"

    def read(self, amt = None):
        "Called when reading the request body"
    #}

class StandaloneRequest(BaseRequest):
    __slots__ = [ '_req', 'read' ]
    def __init__(self, req):
        BaseRequest.__init__(self)
        self._req = req
        self.read = self._req.rfile.read

    def getRelativeURI(self):
        return self._req.path

    def getAbsoluteURI(self):
        hostport = self._req.host
        if self._req.port != 80 and ':' not in hostport:
            hostport = "%s:%s" % (self._req.host, self._req.port)
        return "http://%s%s" % (hostport, self._req.path)

    def getHeader(self, key):
        return self._req.headers.get(key, None)

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
    toplevel = 'TOPLEVEL'
    storageConfig = StorageConfig(storagePath = "storage")

    def log_message(self, *args, **kwargs):
        pass

    def do_GET(self):
        req = self._createRequest()
        if req is None:
            return

        if self.path == '/crossdomain.xml':
            return self._handleResponse(self.serveCrossDomainFile())
        if self.path == '/%s/clouds/ec2/images' % self.toplevel:
            return self.enumerateImages(req)
        if self.path == '/%s/clouds/ec2/instances' % self.toplevel:
            return self.enumerateInstances(req)
        if self.path == '/%s/clouds/ec2/instanceTypes' % self.toplevel:
            return self.enumerateInstanceTypes(req)
        p = '/%s/users/' % self.toplevel
        if self.path.startswith(p):
            return self._handleResponse(self.getUserData(req, self.path[len(p):]))

    def do_PUT(self):
        req = self._createRequest()
        if req is None:
            return

    def do_POST(self):
        req = self._createRequest()
        if req is None:
            return

        p = '/%s/users/' % self.toplevel
        if self.path.startswith(p):
            self._handleResponse(self.addUserData(req, self.path[len(p):]))

    def do_DELETE(self):
        req = self._createRequest()
        if req is None:
            return

    def _createRequest(self):
        req = self._validateHeaders()
        if req is None:
            return None
        if not self._auth(req):
            return None
        return req

    def _validateHeaders(self):
        if 'Host' not in self.headers:
            # Missing Host: header
            self.send_error(400)
            return

        if 'Authorization' not in self.headers:
            self._send_401()
            return

        self.host = self.headers['Host']
        self.port = self.server.server_port
        req = StandaloneRequest(self)
        return req

    def _send_401(self):
        self.send_response(401, "Unauthorized")
        self.send_header('WWW-Authenticate', 'Basic realm="blah"')
        self.send_header('Content-Type', 'text/html')
        self.send_header('Connection', 'close')
        self.end_headers()

    def _auth(self, req):
        authData = self.headers['Authorization']
        if authData[:6] != 'Basic ':
            self._send_401()
            return False
        authData = authData[6:]
        authData = base64.decodestring(authData)
        authData = authData.split(':', 1)
        req.setUser(authData[0])
        req.setPassword(authData[1])
        return True

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

    def addUserData(self, req, userData):
        # Split the arguments
        userData = userData.split('/')
        if userData[0] != req.getUser():
            raise Exception("XXX 1")

        dataLen = req.getContentLength()
        data = req.read(dataLen)
        store = storage.DiskStorage(self.storageConfig)

        keyPrefix = '/'.join(x for x in userData if x not in ('', '.', '..'))

        newId = store.store(data, keyPrefix = keyPrefix)
        response = '<?xml version="1.0" encoding="UTF-8"?><id>%s/%s</id>' % (
            req.getAbsoluteURI(), os.path.basename(newId))
        return Response(contentType = "text/xml", data = response)

    def getUserData(self, req, userData):
        # Split the arguments
        userData = userData.split('/')
        if userData[0] != req.getUser():
            raise Exception("XXX 1")

        store = storage.DiskStorage(self.storageConfig)
        key = '/'.join(x for x in userData if x not in ('', '.', '..'))
        data = store.get(key)
        return Response(contentType = "application/xml", data = data)

class HTTPServer(BaseHTTPServer.HTTPServer):
    pass

if __name__ == '__main__':
    h = HTTPServer(("", 1234), BaseRESTHandler)
    h.serve_forever()
