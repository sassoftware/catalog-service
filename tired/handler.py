#
# Copyright (c) 2008 rPath, Inc.
#

import base64
import BaseHTTPServer
import os
import urllib

from tired import config
from tired import storage
from tired import userData
from tired import xmlNode

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

    def read(self, amt = None):
        "Called when reading the request body"

    def iterHeaders(self):
        "Iterate over the headers"
    #}

class StandaloneRequest(BaseRequest):
    __slots__ = [ '_req', 'read' ]
    def __init__(self, req):
        BaseRequest.__init__(self)
        self._req = req
        self.read = self._req.rfile.read

    def getRelativeURI(self):
        return self._req.path

    def getSchemeNetloc(self):
        hostport = self._req.host
        if self._req.port != 80 and ':' not in hostport:
            hostport = "%s:%s" % (self._req.host, self._req.port)
        return "http://%s" % (hostport, )

    def getHeader(self, key):
        return self._req.headers.get(key, None)

    def iterHeaders(self):
        for k, v in self._req.headers.items():
            yield k, v

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
        if contentType is not None:
            headers['Content-Type'] = contentType or 'application/xml'

        for k, v in headers.iteritems():
            if isinstance(v, list):
                self.addHeaders(k, v)
            else:
                self.addHeader(k, v)

        if data:
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

class BaseRESTHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    toplevel = 'TOPLEVEL'
    storageConfig = StorageConfig(storagePath = "storage")
    logLevel = 1

    def log_message(self, *args, **kwargs):
        if self.logLevel > 0:
            BaseHTTPServer.BaseHTTPRequestHandler.log_message(self,
                *args, **kwargs)

    def do_GET(self):
        return self.processRequest(self._do_GET)

    def do_POST(self):
        return self.processRequest(self._do_POST)

    def do_PUT(self):
        return self.processRequest(self._do_PUT)

    def do_DELETE(self):
        return self.processRequest(self._do_DELETE)

    def processRequest(self, method):
        # Dump the headers
        for k, v in sorted(self.headers.items()):
            print "    %-20s : %s" % (k, v)
        req = self._createRequest()
        if req is None:
            # _createRequest does all the work to send back the error codes
            return

        try:
            return method(req)
        except:
            # XXX
            raise

    def _do_GET(self, req):
        path = req.getRelativeURI()
        if path == '/crossdomain.xml':
            return self._handleResponse(self.serveCrossDomainFile())
        if path == '/%s/clouds/ec2/images' % self.toplevel:
            return self.enumerateImages(req)
        if path == '/%s/clouds/ec2/instances' % self.toplevel:
            return self.enumerateInstances(req)
        if path == '/%s/clouds/ec2/instanceTypes' % self.toplevel:
            return self.enumerateInstanceTypes(req)
        p = '/%s/users/' % self.toplevel
        if path.startswith(p):
            return self._handleResponse(self.getUserData(req, p, path[len(p):]))
        p = '/%s/clouds/ec2/users/' % self.toplevel
        if self.path.startswith(p):
            rp = self.path[len(p):]
            cloudPrefix = '/%s/clouds/ec2' % self.toplevel
            # Grab the user part
            arr = rp.split('/')
            userId = urllib.unquote(arr[0])
            if userId != req.getUser():
                for k, v in req.iterHeaders():
                    print "%s: %s" % (k, v)
                raise Exception("XXX 1", userId, req.getUser())
            if arr[1:] == ['environment']:
                return self._handleResponse(self.getEnvironment(req,
                    cloudPrefix))

    def _do_PUT(self, req):
        p = '/%s/users/' % self.toplevel
        if self.path.startswith(p):
            return self._handleResponse(self.setUserData(req, self.path[len(p):]))

    def _do_POST(self, req):
        p = '/%s/users/' % self.toplevel
        # Look for a method
        path, method = self._get_method(req.getRelativeURI(), 'POST')

        if path.startswith(p):
            pRest = path[len(p):]
            if method == 'POST':
                self._handleResponse(self.addUserData(req, pRest))
            elif method == 'DELETE':
                self._handleResponse(self.deleteUserData(req, pRest))
            elif method == 'PUT':
                self._handleResponse(self.setUserData(req, pRest))
            return

        p = '/%s/clouds/ec2/instances' % self.toplevel
        if path == p:
            self._handleResponse(self.newInstance(req))
            return
        p += '/'
        if path.startswith(p):
            pRest = path[len(p):]
            if method == 'DELETE':
                arr = pRest.split('/')
                if arr:
                    instanceId = arr[0]
                    self._handleResponse(self.terminateInstance(req, instanceId,
                                         prefix = p))
            return

    def _do_DELETE(self, req):
        p = '/%s/users/' % self.toplevel
        if self.path.startswith(p):
            self._handleResponse(self.deleteUserData(req, self.path[len(p):]))

        p = '/%s/clouds/ec2/instances/' % self.toplevel
        if self.path.startswith(p):
            arr = self.path[len(p):].split('/')
            if arr:
                instanceId = arr[0]
                self._handleResponse(self.terminateInstance(req, instanceId,
                                     prefix = p))

    @classmethod
    def _get_method(cls, path, defaultMethod):
        """
        Given a path, retrieve the method from it (part of the query)
        Return path and method (None if no method)
        """
        path, query = urllib.splitquery(path)
        if not query:
            return path, defaultMethod
        rMap = cls._split_query(query)
        return path, rMap.get('_method', defaultMethod)

    @staticmethod
    def _split_query(query):
        rMap = {}
        for v in query.split('&'):
            arr = v.split('=', 1)
            if len(arr) != 2:
                continue
            rMap[arr[0]] = arr[1]
        return rMap

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
        self.send_response(response.getCode())
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
            raise Exception("XXX 1", userData[0], req.getUser())

        dataLen = req.getContentLength()
        data = req.read(dataLen)
        store = storage.DiskStorage(self.storageConfig)

        keyPrefix = '/'.join(x for x in userData if x not in ('', '.', '..'))

        newId = store.store(data, keyPrefix = keyPrefix)
        response = '<?xml version="1.0" encoding="UTF-8"?><id>%s/%s</id>' % (
            req.getAbsoluteURI(), os.path.basename(newId))
        return Response(contentType = "text/xml", data = response)

    def getUserData(self, req, prefix, keyPath):
        # Split the arguments
        arr = keyPath.split('/')
        if arr[0] != req.getUser():
            raise Exception("XXX 1", arr[0], req.getUser())

        prefix = "%s%s" % (req.getSchemeNetloc(), prefix)
        store = storage.DiskStorage(self.storageConfig)

        key = keyPath.rstrip('/')

        if key != keyPath:
            # A trailing / means retrieving the contents from a collection
            if not store.isCollection(key):
                raise Exception("XXX 2", prefix, keyPath)

        if store.isCollection(key):
            node = userData.IdsNode()
            snodes = store.enumerate(keyPrefix = key)

            if key == keyPath:
                # No trailing /
                snodes = [ userData.IdNode().characters("%s%s" % (prefix, x))
                         for x in snodes ]
                node.extend(snodes)
                return Response(data = node)
            # Grab contents and wrap them in some XML
            data = [ store.get(x) for x in snodes ]
            data = '<list>%s</list>' % ''.join(data)
            return Response(data = data)

        data = store.get(key)
        code = None
        if data is None:
            data = '<?xml version="1.0" encoding="UTF-8"?><error></error>'
            code = 404
        return Response(contentType = "application/xml", data = data,
                        code = code)

    def setUserData(self, req, userData):
        userData = userData.split('/')
        if userData[0] != req.getUser():
            raise Exception("XXX 1")

        dataLen = req.getContentLength()
        data = req.read(dataLen)

        store = storage.DiskStorage(self.storageConfig)
        key = '/'.join(x for x in userData if x not in ('', '.', '..'))
        store.set(key, data)
        response = '<?xml version="1.0" encoding="UTF-8"?><id>%s</id>' % (
            req.getAbsoluteURIPath(), )
        return Response(contentType = "text/xml", data = response)

    def deleteUserData(self, req, userData):
        userData = userData.split('/')
        if userData[0] != req.getUser():
            raise Exception("XXX 1")

        store = storage.DiskStorage(self.storageConfig)
        key = '/'.join(x for x in userData if x not in ('', '.', '..'))
        store.delete(key)
        response = '<?xml version="1.0" encoding="UTF-8"?><id>%s</id>' % (
            req.getAbsoluteURIPath(), )
        return Response(contentType = "text/xml", data = response)

    def getEnvironment(self, req, cloudPrefix):
        import environment
        import driver_ec2

        awsPublicKey = '16CVNRTTWQG9MZ517782'
        awsPrivateKey = 'B/kKJ5K+jcr3/Sr2DSMRx6dMXzqdaEv+4yFwOUj/'

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        prefix = "%s%s" % (req.getSchemeNetloc(), cloudPrefix)
        node = drv.getEnvironment(prefix=prefix)

        hndlr = environment.Handler()
        data = hndlr.toXml(node)

        return Response(contentType="application/xml", data = data)


    def newInstance(self, req):
        import newInstance
        import driver_ec2
        awsPublicKey = '16CVNRTTWQG9MZ517782'
        awsPrivateKey = 'B/kKJ5K+jcr3/Sr2DSMRx6dMXzqdaEv+4yFwOUj/'

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        dataLen = req.getContentLength()
        data = req.read(dataLen)

        prefix = req.getAbsoluteURI()
        response = drv.newInstance(data, prefix = prefix)

        hndlr = newInstance.Handler()
        data = hndlr.toXml(response)

        return Response(contentType="application/xml", data = data)

    def terminateInstance(self, req, instanceId, prefix):
        import driver_ec2

        awsPublicKey = '16CVNRTTWQG9MZ517782'
        awsPrivateKey = 'B/kKJ5K+jcr3/Sr2DSMRx6dMXzqdaEv+4yFwOUj/'

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        prefix = req.getSchemeNetloc() + prefix
        response = drv.terminateInstance(instanceId, prefix = prefix)

        hndlr = driver_ec2.instances.Handler()
        data = hndlr.toXml(response)

        return Response(contentType="application/xml", data = data)


class HTTPServer(BaseHTTPServer.HTTPServer):
    pass

if __name__ == '__main__':
    h = HTTPServer(("", 1234), BaseRESTHandler)
    h.serve_forever()
