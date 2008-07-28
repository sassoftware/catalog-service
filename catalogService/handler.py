#
# Copyright (c) 2008 rPath, Inc.
#

import base64
import BaseHTTPServer
import os, sys
import urllib

from catalogService import clouds
from catalogService import config
from catalogService import newInstance
from catalogService import request as brequest
from catalogService import storage
from catalogService import userData
from catalogService import errors
from catalogService import images

# Make it easy for the producers of responses
Response = brequest.Response

# Monkeypatch BaseHTTPServer for older Python (e.g. the one that
# rLS1 has) to include a function that we rely on. Yes, this is gross.
if not hasattr(BaseHTTPServer, '_quote_html'):
    def _quote_html(html):
        # XXX this data is needed unre-formed by the flex frontend
        return html
        return html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    BaseHTTPServer._quote_html = _quote_html

class StorageConfig(config.BaseConfig):
    def __init__(self, storagePath):
        config.BaseConfig.__init__(self)
        self.storagePath = storagePath

class StandaloneRequest(brequest.BaseRequest):
    __slots__ = [ '_req', 'read' ]

    def __init__(self, req):
        brequest.BaseRequest.__init__(self)
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
        res = self._req.headers.get(key, None)
        if not res:
            for hdrKey, val in self.iterHeaders():
                if key.upper() == hdrKey.upper():
                    res = val
        return res

    def iterHeaders(self):
        for k, v in self._req.headers.items():
            yield k, v

    def setPath(self, path):
        self._req.path = path

class BaseRESTHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    toplevel = 'TOPLEVEL'
    storageConfig = StorageConfig(storagePath = "storage")
    logLevel = 1
    error_message_format = '\n'.join(('<?xml version="1.0" encoding="UTF-8"?>',
            '<fault>',
            '  <code>%(code)s</code>',
            '  <message>%(message)s</message>',
            '</fault>'))


    def send_error(self, code, message = '', shortMessage = ''):
        # we have to override this method because the superclass assumes
        # we want to send back HTML. other than the content type, we're
        # not really changing much
        try:
            short, long = self.responses[code]
        except KeyError:
            short, long = '???', '???'
        if message is None:
            message = short
        if shortMessage is None:
            shortMessage = short
        self.log_error("code %d, message %s", code, message)
        print >> sys.stderr, "code %d, message %s" % (code, message)
        sys.stderr.flush()
        content = (self.error_message_format %
               {'code': code, 'message': BaseHTTPServer._quote_html(message)})
        self.send_response(code, shortMessage)
        self.send_header("Content-Type", "application/xml")
        self.send_header('Connection', 'close')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        if self.command != 'HEAD' and code >= 200 and code not in (204, 304):
            self.wfile.write(content)

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
        if self.logLevel > 0:
            # Dump the headers
            for k, v in sorted(self.headers.items()):
                print >> sys.stderr, "    %-20s : %s" % (k, v)
                sys.stderr.flush()

        req = self._createRequest()
        if req is None:
            # _createRequest does all the work to send back the error codes
            return
        try:
            return method(req)
        except Exception, e:
            errcode = 500
            if hasattr(e, 'errcode'):
                errcode = e.errcode
            self.send_error(errcode, str(e), repr(e))
            return errcode

    def _do_GET(self, req):
        # we know the method, we're just using common code to strip it.
        path, method = self._get_method(req.getRelativeURI(), 'GET')
        # now record the stripped path as the original path for consistency
        req.setPath(path)
        if path == '/crossdomain.xml':
            return self._handleResponse(self.serveCrossDomainFile())
        # We serve clouds both with and without trailing /
        validCloudsPaths = [ '/%s/clouds' % self.toplevel ]
        validCloudsPaths.append(validCloudsPaths[0] + '/')
        if path in validCloudsPaths:
            return self._handleResponse(self.enumerateClouds(req))
        if path == '/%s/clouds/vws' % self.toplevel:
            return self._handleResponse(self.enumerateVwsClouds(req))
        if path == '/%s/clouds/ec2/images' % self.toplevel:
            return self._handleResponse(self.enumerateEC2Images(req))
        if path == '/%s/clouds/ec2/instances' % self.toplevel:
            return self._handleResponse(self.enumerateEC2Instances(req))
        if path == '/%s/clouds/ec2/instanceTypes' % self.toplevel:
            return self.enumerateEC2InstanceTypes(req)
        pathInfo = self._getPathInfo(path)
        if pathInfo.get('cloud') == 'vws':
            cloudId = urllib.unquote(pathInfo.get('cloudId'))
            cli = self._getVwsClient(cloudId)

            if pathInfo.get('resource') == 'images':
                return self._handleResponse(self.enumerateVwsImages(req,
                        cli))
            if pathInfo.get('resource') == 'instances':
                return self._handleResponse(self.enumerateVwsInstances(req,
                        cli))
        if path == '/%s/userinfo' % self.toplevel:
            return self.enumerateUserInfo(req)
        p = '/%s/users/' % self.toplevel
        if path.startswith(p):
            return self._handleResponse(self.getUserData(req, p, path[len(p):]))
        if pathInfo.get('resource') == 'users':
            # Grab the user part
            arr = pathInfo['instanceId'].split('/')
            userId = urllib.unquote(arr[0])
            if userId != req.getUser():
                for k, v in req.iterHeaders():
                    print >> sys.stderr, "%s: %s" % (k, v)
                    sys.stderr.flush()
                raise Exception("XXX 1", userId, req.getUser())
            cloudPrefix = '%s/clouds/%s' % (self.toplevel, pathInfo['cloud'])
            if 'cloudId' in pathInfo:
                cloudPrefix += '/%s' % pathInfo['cloudId']
            if arr[1:] == ['environment']:
                if pathInfo['cloud'] == 'ec2':
                    return self._handleResponse(self.getEnvironmentEC2(req,
                        cloudPrefix))
                return self._handleResponse(self.getEnvironmentVWS(req,
                    cloudPrefix, pathInfo['cloudId']))
        raise errors.HttpNotFound

    def _do_PUT(self, req):
        p = '/%s/users/' % self.toplevel
        if self.path.startswith(p):
            return self._handleResponse(self.setUserData(req, self.path[len(p):]))

    def _do_POST(self, req):
        p = '/%s/users/' % self.toplevel
        # Look for a method
        path, method = self._get_method(req.getRelativeURI(), 'POST')
        if method == 'GET':
            return self._do_GET(req)

        if path.startswith(p):
            pRest = path[len(p):]
            if method == 'POST':
                self._handleResponse(self.addUserData(req, pRest))
            elif method == 'DELETE':
                self._handleResponse(self.deleteUserData(req, pRest))
            elif method == 'PUT':
                self._handleResponse(self.setUserData(req, pRest))
            return

        pathInfo = self._getPathInfo(path)
        if pathInfo.get('resource') == 'instances':
            self._handleInstances(req, method, pathInfo)

    def _do_DELETE(self, req):
        p = '/%s/users/' % self.toplevel
        if self.path.startswith(p):
            self._handleResponse(self.deleteUserData(req, self.path[len(p):]))

        path = self.path
        pathInfo = self._getPathInfo(path)
        if pathInfo.get('resource') == 'instances':
            self._handleInstances(req, 'DELETE', pathInfo)

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

    def _getVwsClient(self, cloudId):
        creds = self.getVwsCredentials()
        cloudCred = [ x for x in creds if x['factory'] == cloudId ]
        if not cloudCred:
            raise errors.HttpNotFound
        cloudCred = cloudCred[0]

        from catalogService import globuslib
        props = globuslib.WorkspaceCloudProperties()
        props.set('vws.factory', cloudCred['factory'])
        props.set('vws.repository', cloudCred['repository'])
        props.set('vws.factory.identity', cloudCred['factoryIdentity'])
        props.set('vws.repository.identity', cloudCred['repositoryIdentity'])
        cli = globuslib.WorkspaceCloudClient(props, cloudCred['caCert'],
            cloudCred['userCert'], cloudCred['userKey'])
        return cli

    def _getPathInfo(self, path):
        """
        returns dict containing useful information about the path

        This function generally expects URIs of the form:
        /<toplevel>/clouds/<cloudname>{/cloudId}/<resource>{/instanceId}
        cloudId is omitted for EC2 since there's only one
        """
        try:
            res = {}
            prefix = '/%s/clouds/' % (self.toplevel)
            if path.startswith(prefix):
                pRest = path[len(prefix):]
                cloud, pRest = pRest.split('/', 1)
                if cloud == 'ec2':
                    cloudId = None
                else:
                    cloudId, pRest = pRest.split('/', 1)
                if '/' in pRest:
                    resource, pRest = pRest.split('/', 1)
                else:
                    resource, pRest = pRest, ''
                res['cloud'] = cloud
                if cloudId is not None:
                    res['cloudId'] = cloudId
                if pRest:
                    res['instanceId'] = pRest
                    prefix = path[:- len(pRest)]
                else:
                    prefix = path
                res['resource'] = resource
                res['prefix'] = prefix
            return res
        except:
            # an empty dict indicates a URL we couldn't handle, which
            # ultimately results in a 404
            return {}

    def _handleInstances(self, req, method, pathInfo):
        cloudName = pathInfo.get('cloud')
        cloudMap = dict(ec2 = 'EC2', vws = 'Vws')
        if cloudName not in cloudMap:
            # these are currently the only two clouds we handle
            raise errors.HttpNotFound
        cloudId = pathInfo.get('cloudId')
        if method == 'DELETE':
            methodName = 'terminate%sInstance' % cloudMap[cloudName]
            method = getattr(self, methodName)
            instanceId = pathInfo.get('instanceId')
            prefix = pathInfo.get('prefix', '')
            return self._handleResponse(method(req, cloudId, instanceId,
                prefix))
        methodName = 'new%sInstance' % cloudMap[cloudName]
        method = getattr(self, methodName)
        return self._handleResponse(method(req, cloudId))

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
            self._send_403()
            return

        self.host = self.headers['Host']
        self.port = self.server.server_port
        req = StandaloneRequest(self)
        return req

    def _send_403(self):
        self.send_response(403, "Forbidden")
        self.send_header('Content-Type', 'text/html')
        self.send_header('Connection', 'close')
        self.end_headers()

    def _auth(self, req):
        authData = self.headers['Authorization']
        if authData[:6] != 'Basic ':
            self._send_403()
            return False
        authData = authData[6:]
        authData = base64.decodestring(authData)
        authData = authData.split(':', 1)
        req.setUser(authData[0])
        req.setPassword(authData[1])
        self.mintClient = self._getMintClient(authData)
        # explicitly authenticate the credentials against rBuilder to get
        # the rBuilder userId. raise permission denied if we're not authorized
        self.mintAuth = self.mintClient.checkAuth()
        if not self.mintAuth.authorized:
            self._send_403()
            return False
        return True

    def _handleResponse(self, response):
        response.addContentLength()
        self.send_response(response.getCode())
        for k, v in response.iterHeaders():
            self.send_header(k, v)
        self.end_headers()

        response.serveResponse(self.wfile.write)

    def _getMintConfig(self):
        import mint.config
        if not hasattr(self, 'mintCfg'):
            self.mintCfg = mint.config.getConfig()
        return self.mintCfg


    def _getMintClient(self, authToken):
        if self.storageConfig.rBuilderUrl:
            import mint.client
            return mint.client.MintClient( \
                    self.storageConfig.rBuilderUrl % tuple(authToken[:2]))
        else:
            import mint.shimclient
            mintCfg = self._getMintConfig()
            return mint.shimclient.ShimMintClient(mintCfg, authToken)

    def getEC2Credentials(self):
        import mint.mint_error
        try:
            cred = self.mintClient.getEC2CredentialsForUser(self.mintAuth.userId)
        except mint.mint_error.PermissionDenied:
            raise errors.PermissionDenied
        for key in ('awsPublicAccessKeyId', 'awsSecretAccessKey'):
            if key not in cred or not cred[key]:
                raise errors.MissingCredentials
        return (cred.get('awsPublicAccessKeyId'),
            cred.get('awsSecretAccessKey'))

    def enumerateEC2Images(self, req):
        import driver_ec2

        awsPublicKey, awsPrivateKey = self.getEC2Credentials()

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        prefix = req.getAbsoluteURI()
        imgs = drv.getAllImages(prefix = prefix)
        imageDataLookup = self.mintClient.getAllAMIBuilds()
        for image in imgs:
            imageId = image.imageId.getText()
            imgData = imageDataLookup.get(imageId, {})
            image.setIs_rBuilderImage(bool(imgData))
            for key, methodName in images.buildToNodeFieldMap.iteritems():
                val = imgData.get(key)
                method = getattr(image, methodName)
                method(val)

        return Response(data = imgs)

    def getVwsCredentials(self):
        from catalogService import globuslib
        if not globuslib.WorkspaceCloudClient.isFunctional():
            return []
        return [
            dict(factory = tmp_cloud1,
                 repository = tmp_repo1,
                 factoryIdentity = tmp_factoryIdentity,
                 repositoryIdentity = tmp_repoIdentity,
                 caCert = tmp_caCert,
                 userCert = tmp_userCert,
                 userKey = tmp_userKey,
                 description = tmp_cloud1Desc),
            dict(factory = tmp_cloud2,
                 repository = tmp_repo2,
                 factoryIdentity = tmp_factoryIdentity,
                 repositoryIdentity = tmp_repoIdentity,
                 caCert = tmp_caCert,
                 userCert = tmp_userCert,
                 userKey = tmp_userKey,
                 description = tmp_cloud2Desc),
        ]

    def enumerateClouds(self, req):
        import driver_ec2
        nodes = clouds.BaseClouds()
        prefix = req.getAbsoluteURI()
        # Strip trailing /
        prefix = prefix.rstrip('/')
        try:
            _, _ = self.getEC2Credentials()
            nodes.append(driver_ec2.Cloud(id = prefix + '/ec2',
                cloudName = '', description = "Amazon Elastic Compute Cloud"))
        except errors.MissingCredentials:
            pass
        nodes.extend(self._enumerateVwsClouds(prefix + '/vws'))
        return Response(data = nodes)

    def enumerateVwsClouds(self, req):
        prefix = req.getAbsoluteURI()
        nodes = self._enumerateVwsClouds(prefix)
        return Response(data = nodes)

    def enumerateVwsImages(self, req, cloudClient):
        import driver_workspaces

        cfg = driver_workspaces.Config()
        drv = driver_workspaces.Driver(cloudClient, cfg, self.mintClient)

        prefix = req.getAbsoluteURI()
        imgs = drv.getImages(prefix = prefix)

        return Response(data = imgs)

    def enumerateVwsInstances(self, req, cloudClient):
        import driver_workspaces

        cfg = driver_workspaces.Config()
        drv = driver_workspaces.Driver(cloudClient, cfg, self.mintClient)

        prefix = req.getAbsoluteURI()
        nodes = drv.getInstances(prefix = prefix)
        return Response(data = nodes)

    def enumerateEC2Instances(self, req):
        import driver_ec2

        awsPublicKey, awsPrivateKey = self.getEC2Credentials()

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        prefix = req.getAbsoluteURI()
        node = drv.getAllInstances(prefix = prefix)
        return Response(data = node)

    def enumerateEC2InstanceTypes(self, req):
        import images
        import driver_ec2

        awsPublicKey, awsPrivateKey = self.getEC2Credentials()

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

    def enumerateUserInfo(self, req):
        # we have to authenticate to get here, so we'll have a mintAuth obejct
        # XXX should this call be a UserInfo xml marshalling object?
        data = "<userinfo><username>%s</username></userinfo>" % \
                self.mintAuth.username

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

        xmlHeader = '<?xml version="1.0" encoding="UTF-8"?>'
        if key != keyPath:
            # A trailing / means retrieving the contents from a collection
            if not store.isCollection(key):
                data = xmlHeader + '<list></list>'
                return Response(contentType = "application/xml", data = data, code = 200)
                #raise Exception("XXX 2", prefix, keyPath)

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
            data = xmlHeader + '<list>%s</list>' % ''.join(data)
            return Response(contentType = "application/xml", data = data, code = 200)

        data = store.get(key)
        if data is None:
            raise errors.HttpNotFound
        return Response(data = data)

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

    def getEnvironmentEC2(self, req, cloudPrefix):
        import environment
        import driver_ec2

        awsPublicKey, awsPrivateKey = self.getEC2Credentials()

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        prefix = "%s%s" % (req.getSchemeNetloc(), cloudPrefix)
        node = drv.getEnvironment(prefix=prefix)

        hndlr = environment.Handler()
        data = hndlr.toXml(node)

        return Response(data = data)

    def getEnvironmentVWS(self, req, cloudPrefix, cloudId):
        import environment
        import driver_workspaces

        cloudClient = self._getVwsClient(cloudId)

        cfg = driver_workspaces.Config()
        drv = driver_workspaces.Driver(cloudClient, cfg, self.mintClient)

        prefix = "%s%s" % (req.getSchemeNetloc(), cloudPrefix)
        node = drv.getEnvironment(cloudId, prefix=prefix)

        hndlr = environment.Handler()
        data = hndlr.toXml(node)
        return Response(data = data)


    def newEC2Instance(self, req, cloudId):
        import driver_ec2
        awsPublicKey, awsPrivateKey = self.getEC2Credentials()

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        dataLen = req.getContentLength()
        data = req.read(dataLen)

        prefix = req.getAbsoluteURI()
        response = drv.newInstance(data, prefix = prefix)

        hndlr = newInstance.Handler()
        data = hndlr.toXml(response)

        return Response(contentType="application/xml", data = data)

    def newVwsInstance(self, req, cloudId):
        if cloudId is None:
            raise HttpNotFound
        cloudId = urllib.unquote(cloudId)

        cloudClient = self._getVwsClient(cloudId)

        dataLen = req.getContentLength()
        data = req.read(dataLen)

        prefix = req.getAbsoluteURI()

        from catalogService import driver_workspaces

        cfg = driver_workspaces.Config()
        drv = driver_workspaces.Driver(cloudClient, cfg, self.mintClient)

        response = drv.newInstance(data, prefix = prefix)

        hndlr = newInstance.Handler()
        data = hndlr.toXml(response)

        return Response(contentType="application/xml", data = data)

    def terminateEC2Instance(self, req, cloudId, instanceId, prefix):
        import driver_ec2

        awsPublicKey, awsPrivateKey = self.getEC2Credentials()

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        prefix = req.getSchemeNetloc() + prefix
        response = drv.terminateInstance(instanceId, prefix = prefix)

        hndlr = driver_ec2.instances.Handler()
        data = hndlr.toXml(response)

        return Response(contentType="application/xml", data = data)

    def terminateVwsInstance(self, req, cloudId, instanceId, prefix):
        import driver_workspaces

        cfg = driver_workspaces.Config()

        drv = driver_workspaces.Driver(cloudId, cfg, self.mintClient)

        dataLen = req.getContentLength()
        data = req.read(dataLen)

        prefix = req.getSchemeNetloc() + prefix
        response = drv.terminateInstance(instanceId, prefix = prefix)

        hndlr = driver_ec2.instances.Handler()
        data = hndlr.toXml(response)

        return Response(contentType="application/xml", data = data)

    def _enumerateVwsClouds(self, prefix):
        import driver_workspaces
        creds = self.getVwsCredentials()

        nodes = driver_workspaces.clouds.BaseClouds()
        for cred in creds:
            nodeName = cred['factory']
            node = driver_workspaces.Cloud(cloudName = nodeName,
                description = cred['description'])
            nodeId = "%s/%s" % (prefix, urllib.quote(nodeName, safe=":"))
            node.setId(nodeId)
            nodes.append(node)
        return nodes


class HTTPServer(BaseHTTPServer.HTTPServer):
    pass

tmp_cloud1 = "speedy.eng.rpath.com:8443"
tmp_cloud1Desc = "Super Speedy Super Cloud"
tmp_repo1 = "speedy.eng.rpath.com:2811"
tmp_cloud2 = "snaily.eng.rpath.com:8443"
tmp_cloud2Desc = "Super Slow Micro Cloud"
tmp_repo2 = "speedy.eng.rpath.com:2811"

tmp_factoryIdentity = "/O=rPath Inc/CN=host/speedy"
tmp_repoIdentity = "/O=rPath Inc/CN=host/speedy"

tmp_caCert = """\
Certificate:
    Data:
        Version: 3 (0x2)
        Serial Number:
            f2:d7:4d:55:79:d2:75:60
        Signature Algorithm: sha1WithRSAEncryption
        Issuer: O=rPath Inc, CN=Certificate Authority
        Validity
            Not Before: Jul 18 20:39:42 2008 GMT
            Not After : Apr 17 20:39:42 2018 GMT
        Subject: O=rPath Inc, CN=Certificate Authority
        Subject Public Key Info:
            Public Key Algorithm: rsaEncryption
            RSA Public Key: (2048 bit)
                Modulus (2048 bit):
                    00:97:8f:ea:ad:d7:55:97:18:cf:ae:c1:57:66:4e:
                    18:80:d9:b0:65:bd:d1:15:44:77:a7:6a:5b:de:4e:
                    e8:cc:66:d8:95:d0:fc:53:3f:8e:f3:4f:e9:8b:67:
                    68:4d:16:99:3c:ef:f3:87:7f:4f:86:b4:68:c1:f1:
                    78:44:af:ad:0e:57:03:7d:29:27:57:dd:80:c6:d9:
                    e9:07:87:20:c5:b1:2f:70:29:83:76:01:2e:f9:67:
                    7b:ee:74:d1:e1:76:7b:c8:4c:77:8c:12:11:2f:dc:
                    69:7e:f9:20:ef:c3:28:c4:d6:10:f5:b5:67:c2:23:
                    14:e2:08:eb:60:fe:f4:47:40:79:cb:d7:6e:75:ef:
                    c6:69:34:b2:e5:a9:da:90:92:db:32:b1:eb:14:b4:
                    8b:76:f9:f3:48:2f:5d:d4:50:c8:a9:73:d2:24:ba:
                    5f:8a:e0:86:0f:0d:f8:65:7f:5a:1d:06:e9:ca:50:
                    c9:1e:f4:8c:44:99:03:6e:9d:a1:be:a5:f9:02:fa:
                    11:60:6f:b9:d2:de:f1:f3:ac:4f:75:39:32:35:40:
                    21:fd:69:a7:a7:78:29:5a:35:b9:71:93:f0:9e:a7:
                    e5:b0:ca:38:29:06:e3:b3:f1:0e:2f:1b:25:00:0d:
                    7d:af:0d:ae:2c:7c:81:dd:04:c4:e1:68:ef:c3:f0:
                    4c:b7
                Exponent: 65537 (0x10001)
        X509v3 extensions:
            X509v3 Subject Key Identifier: 
                E1:CF:00:7C:98:E0:48:40:CC:C6:97:AA:A2:27:1E:8E:4D:0D:E5:2C
            X509v3 Authority Key Identifier: 
                keyid:E1:CF:00:7C:98:E0:48:40:CC:C6:97:AA:A2:27:1E:8E:4D:0D:E5:2C
                DirName:/O=rPath Inc/CN=Certificate Authority
                serial:F2:D7:4D:55:79:D2:75:60

            X509v3 Basic Constraints: 
                CA:TRUE
    Signature Algorithm: sha1WithRSAEncryption
        2f:37:3c:22:a8:e2:60:fd:1d:f9:8c:2e:02:7d:2e:e2:da:e0:
        07:fb:77:19:d3:f9:8c:34:3a:8a:73:e4:ee:f2:94:16:c4:c5:
        48:d4:63:47:4c:d5:78:42:6c:c9:90:07:16:d4:7a:ad:cf:6d:
        91:4b:64:08:45:3d:c4:fe:d0:6d:a2:be:41:32:be:df:52:c7:
        6d:be:db:01:d6:2b:a4:22:14:b5:7e:4f:ca:3b:45:3e:d4:93:
        a0:52:e2:b0:df:34:e3:b5:a9:71:51:3b:4a:71:2f:55:53:64:
        91:da:0f:c3:77:f1:d1:b4:0a:00:7e:3f:46:10:13:bd:33:b3:
        ce:b8:00:6a:0c:57:c8:d2:7b:bf:2d:9f:49:31:d7:10:d3:9e:
        8b:b9:17:65:2b:1a:81:47:58:b5:5c:bc:81:d0:c3:b8:b2:45:
        25:45:2d:b9:cd:a0:8d:e2:17:80:93:2b:81:6a:af:41:98:47:
        1a:50:87:63:63:e0:5a:4c:6d:f9:aa:2e:5a:cc:36:70:0c:9d:
        59:60:06:c8:32:b6:5c:ea:c1:ba:80:6b:4d:e9:d7:52:fb:53:
        ef:90:bd:e5:bc:93:92:bd:c2:f2:24:48:27:8d:5d:c5:c1:1f:
        44:da:5d:34:27:19:84:5b:4d:0a:f6:e4:c3:ca:ff:e0:25:d8:
        05:b6:90:82
-----BEGIN CERTIFICATE-----
MIIDgjCCAmqgAwIBAgIJAPLXTVV50nVgMA0GCSqGSIb3DQEBBQUAMDQxEjAQBgNV
BAoTCXJQYXRoIEluYzEeMBwGA1UEAxMVQ2VydGlmaWNhdGUgQXV0aG9yaXR5MB4X
DTA4MDcxODIwMzk0MloXDTE4MDQxNzIwMzk0MlowNDESMBAGA1UEChMJclBhdGgg
SW5jMR4wHAYDVQQDExVDZXJ0aWZpY2F0ZSBBdXRob3JpdHkwggEiMA0GCSqGSIb3
DQEBAQUAA4IBDwAwggEKAoIBAQCXj+qt11WXGM+uwVdmThiA2bBlvdEVRHenalve
TujMZtiV0PxTP47zT+mLZ2hNFpk87/OHf0+GtGjB8XhEr60OVwN9KSdX3YDG2ekH
hyDFsS9wKYN2AS75Z3vudNHhdnvITHeMEhEv3Gl++SDvwyjE1hD1tWfCIxTiCOtg
/vRHQHnL125178ZpNLLlqdqQktsysesUtIt2+fNIL13UUMipc9Ikul+K4IYPDfhl
f1odBunKUMke9IxEmQNunaG+pfkC+hFgb7nS3vHzrE91OTI1QCH9aaeneClaNblx
k/Cep+WwyjgpBuOz8Q4vGyUADX2vDa4sfIHdBMThaO/D8Ey3AgMBAAGjgZYwgZMw
HQYDVR0OBBYEFOHPAHyY4EhAzMaXqqInHo5NDeUsMGQGA1UdIwRdMFuAFOHPAHyY
4EhAzMaXqqInHo5NDeUsoTikNjA0MRIwEAYDVQQKEwlyUGF0aCBJbmMxHjAcBgNV
BAMTFUNlcnRpZmljYXRlIEF1dGhvcml0eYIJAPLXTVV50nVgMAwGA1UdEwQFMAMB
Af8wDQYJKoZIhvcNAQEFBQADggEBAC83PCKo4mD9HfmMLgJ9LuLa4Af7dxnT+Yw0
Oopz5O7ylBbExUjUY0dM1XhCbMmQBxbUeq3PbZFLZAhFPcT+0G2ivkEyvt9Sx22+
2wHWK6QiFLV+T8o7RT7Uk6BS4rDfNOO1qXFRO0pxL1VTZJHaD8N38dG0CgB+P0YQ
E70zs864AGoMV8jSe78tn0kx1xDTnou5F2UrGoFHWLVcvIHQw7iyRSVFLbnNoI3i
F4CTK4Fqr0GYRxpQh2Nj4FpMbfmqLlrMNnAMnVlgBsgytlzqwbqAa03p11L7U++Q
veW8k5K9wvIkSCeNXcXBH0TaXTQnGYRbTQr25MPK/+Al2AW2kII=
-----END CERTIFICATE-----
-----BEGIN RSA PRIVATE KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: DES-EDE3-CBC,0986ABFCDBC144AB

wz3kysVWNjJtkHs7YDVy1wVwgNZ5G1LnNxnaB3I9ENw+Itk83jBU/P+0msvkFzt1
RvBy+GTE/bS0h5CupKjiqcBigckKnTZp0HPW15GWbug9mzFq9/uEcxYMf7IvKwO4
iKgLK1D0Ozm7lcXAB1zGhLAzJht65lruuSG3NqaCSTfL+jWmz8WBXOcZAMB672Hn
MKwttIwAxWmIQK2Ph8FzW9bu7PgycVfeAS2QeRcnsmPaOj7HOTYwtVGq1GDdLu3b
NfdX6zgPsg6g+Fci/NHaEPfbf9EwZsLi5V+YYoWM44GiSdmEn3Fqk2xbpwilHv1l
JaZzQ1dTbkkvW2uBEHrW4niLgJUIYsQnVUNwldZ/lnIn7kl68SRmmXWNgrHTdj2k
vn6IKaFeyOvooEJmMwVrvPxiS3FITwaD9K48gi3qNfWaHl3se+BVy/AAFSxxHs5b
irNZt/AUTEo13/iQtK478bmpiN229NktLOWaGkLbjPU/nsFbjvqdtGOu5EVMUTdI
ODF4zI+yWYab0P0tGynvp0obAyoGs5e5NYC5k4SIWf5YwJljFJcgWnID1e9OJQQ9
zh2xuRtU4AQaYvofcw0nS3qUg0q1s6Z2mi9PoAARTWB7kbtQfZg21A9MI1xCPcGG
u8tGXZftss7iatoZtdB0npHePid80xFaBl7siCTinPbYpWaq6gOW7gq7mqWws+dS
YoUgPWxjJDW39YzGPVew2dIkrsdvsgxE6tYIWW75aiAkekzhrg7FrJxy2+zKaga9
VnCJV3lnUJRPucDVuWLFvBbl6AcTuf6v+szTSa8i8GyJs3hqeLcOdX/TNxkw2uIq
Dxf9eNTSSTAyQs8RR8PwvYvPtwffP5xEhD13xLoMatcA5MzxLYEkRNb4RM19rR7Y
bIOH6gRaRpHlc9sHsbl9e/sFzbyJrrrjYLS88EXn1Jq+bo72q932EgelNrXW1jU+
TI7bm3/5zQUZvSkSIvvoh+itSRrahBBCA1fSpdpVUsXbf8z/4bILWySzdMgSJxft
Wd/X+N9r9aMyO/jXMk7N4O83gFepcbZ7qhtd6+Lze0JzzXtkgf5bWW1ZX5rYZVD2
NeK7ZR6R4qii8LzbTqt8nbYxaajq/F7ySfEvu/311RWGbwdO3e2nHUZxOeI5+KsK
eZqkVw67kcFDt2RJYTwO6u577hEvz6HUArW8PgIbxj+MrCP/JeNiGVA2pJdjVqmL
mPNOs8NzcE2K2aB9/noWQxec5W0OwgbY3RdXcwvK/EnPZS384yHHPsJ9SN2GrVrN
OmZ3autp5XvEMAgEioz1KMMWwHxUwuiR07vM7TU7ZJCpA1ciNwnFUMGBxf3Kbvfb
uwDJ7QO63PNWaONmwZ+3HGQ+LJyXJqVQsAScauAlrw7VPhOI/5u2KhpUQSMFQEQq
ruRr4g036UBtaDoaJ2meQSxWtTyCJNd1Ri0RZMXBsc6/uDJR0pAdDgf8AWrSFXKN
URNDOfrup8+TssU+PhcOr9snlq/DZA2aCIRaZ0/lvOKYd0fWvQfd4Z73N40MjYM2
Xp667Y4iNuSD8aZ+hkGA6WQdqo1S72+lhOd0nG5sdZ1nS3i7CyYcpg==
-----END RSA PRIVATE KEY-----
"""

tmp_userCert = """\
Certificate:
    Data:
        Version: 3 (0x2)
        Serial Number: 6 (0x6)
        Signature Algorithm: md5WithRSAEncryption
        Issuer: O=rPath Inc, CN=Certificate Authority
        Validity
            Not Before: Jul 18 20:50:34 2008 GMT
            Not After : Jul 18 20:50:34 2009 GMT
        Subject: O=rPath Inc, CN=globus/emailAddress=misa@rpath.com
        Subject Public Key Info:
            Public Key Algorithm: rsaEncryption
            RSA Public Key: (1024 bit)
                Modulus (1024 bit):
                    00:ae:e0:15:00:65:c4:0a:48:f1:43:16:fd:9e:23:
                    47:6f:ce:b6:a8:2e:21:b0:09:42:15:f0:48:5c:ff:
                    cd:b5:a7:01:47:7d:8e:77:ba:1e:2a:a8:09:12:98:
                    af:95:2c:69:94:a1:1f:72:9a:3e:2a:4a:ce:a1:97:
                    86:39:f1:d5:04:c8:34:b8:26:0f:60:2b:1d:51:be:
                    9f:93:32:80:ba:52:12:1e:f7:f8:48:08:16:f5:b0:
                    24:3a:91:97:e3:e0:27:86:c9:94:08:2c:11:a0:ed:
                    1b:97:22:65:6e:47:7f:4c:12:aa:94:a7:63:7e:13:
                    95:89:37:4f:44:fb:28:4d:0d
                Exponent: 65537 (0x10001)
        X509v3 extensions:
            X509v3 Basic Constraints: 
                CA:FALSE
            X509v3 Extended Key Usage: 
                TLS Web Server Authentication, TLS Web Client Authentication
            Netscape Cert Type: 
                SSL Server
            X509v3 Key Usage: 
                Digital Signature, Key Encipherment
            X509v3 Subject Key Identifier: 
                13:4C:85:54:67:7F:79:51:26:13:DB:14:8F:D0:27:14:27:80:2B:AE
            X509v3 Authority Key Identifier: 
                keyid:E1:CF:00:7C:98:E0:48:40:CC:C6:97:AA:A2:27:1E:8E:4D:0D:E5:2C
                DirName:/O=rPath Inc/CN=Certificate Authority
                serial:F2:D7:4D:55:79:D2:75:60

    Signature Algorithm: md5WithRSAEncryption
        34:c3:de:da:1c:e7:96:f2:20:53:ae:64:7c:39:23:c1:e5:2a:
        01:84:1a:fa:b6:76:fc:e9:56:b4:03:42:cc:14:09:10:03:26:
        be:6d:95:5d:85:da:cd:b2:30:61:38:5f:91:a8:9b:6d:1d:cd:
        87:97:32:73:64:5f:0c:fc:46:87:c9:b2:c0:01:eb:88:74:dc:
        9f:82:37:47:22:48:dd:f2:40:81:98:ef:17:d2:b7:12:7b:ff:
        d9:b7:44:6c:57:7c:d9:d9:29:9a:b5:e5:ce:7a:ad:3c:a9:63:
        9f:49:b5:04:da:c3:8a:0e:6e:b6:11:7d:4a:96:30:12:f2:f8:
        a4:5d:ee:58:13:26:a3:cf:4d:42:c6:93:fe:51:5a:f1:24:f0:
        c7:1b:21:84:15:be:50:7e:8e:97:a3:d4:9b:44:09:db:5c:21:
        65:c8:0b:fb:aa:7d:f2:7a:d2:f2:99:f4:93:74:c6:e4:75:eb:
        14:7e:68:45:01:74:e4:9d:02:34:23:ed:ea:95:4f:c0:18:3b:
        93:53:48:a7:4e:36:96:13:03:6f:91:70:fd:e2:a1:1d:25:70:
        8b:31:63:84:bf:92:8e:83:85:7b:83:27:9b:8e:d0:22:60:96:
        3a:34:df:0b:36:fc:25:08:19:02:c7:94:f7:c6:a5:2f:fb:5c:
        b9:a9:4f:dd
-----BEGIN CERTIFICATE-----
MIIDQjCCAiqgAwIBAgIBBjANBgkqhkiG9w0BAQQFADA0MRIwEAYDVQQKEwlyUGF0
aCBJbmMxHjAcBgNVBAMTFUNlcnRpZmljYXRlIEF1dGhvcml0eTAeFw0wODA3MTgy
MDUwMzRaFw0wOTA3MTgyMDUwMzRaMEQxEjAQBgNVBAoTCXJQYXRoIEluYzEPMA0G
A1UEAxMGZ2xvYnVzMR0wGwYJKoZIhvcNAQkBFg5taXNhQHJwYXRoLmNvbTCBnzAN
BgkqhkiG9w0BAQEFAAOBjQAwgYkCgYEAruAVAGXECkjxQxb9niNHb862qC4hsAlC
FfBIXP/NtacBR32Od7oeKqgJEpivlSxplKEfcpo+KkrOoZeGOfHVBMg0uCYPYCsd
Ub6fkzKAulISHvf4SAgW9bAkOpGX4+AnhsmUCCwRoO0blyJlbkd/TBKqlKdjfhOV
iTdPRPsoTQ0CAwEAAaOB0jCBzzAJBgNVHRMEAjAAMB0GA1UdJQQWMBQGCCsGAQUF
BwMBBggrBgEFBQcDAjARBglghkgBhvhCAQEEBAMCBkAwCwYDVR0PBAQDAgWgMB0G
A1UdDgQWBBQTTIVUZ395USYT2xSP0CcUJ4ArrjBkBgNVHSMEXTBbgBThzwB8mOBI
QMzGl6qiJx6OTQ3lLKE4pDYwNDESMBAGA1UEChMJclBhdGggSW5jMR4wHAYDVQQD
ExVDZXJ0aWZpY2F0ZSBBdXRob3JpdHmCCQDy101VedJ1YDANBgkqhkiG9w0BAQQF
AAOCAQEANMPe2hznlvIgU65kfDkjweUqAYQa+rZ2/OlWtANCzBQJEAMmvm2VXYXa
zbIwYThfkaibbR3Nh5cyc2RfDPxGh8mywAHriHTcn4I3RyJI3fJAgZjvF9K3Env/
2bdEbFd82dkpmrXlznqtPKljn0m1BNrDig5uthF9SpYwEvL4pF3uWBMmo89NQsaT
/lFa8STwxxshhBW+UH6Ol6PUm0QJ21whZcgL+6p98nrS8pn0k3TG5HXrFH5oRQF0
5J0CNCPt6pVPwBg7k1NIp042lhMDb5Fw/eKhHSVwizFjhL+SjoOFe4Mnm47QImCW
OjTfCzb8JQgZAseU98alL/tcualP3Q==
-----END CERTIFICATE-----
"""

tmp_userKey = """\
-----BEGIN RSA PRIVATE KEY-----
MIICXAIBAAKBgQCu4BUAZcQKSPFDFv2eI0dvzraoLiGwCUIV8Ehc/821pwFHfY53
uh4qqAkSmK+VLGmUoR9ymj4qSs6hl4Y58dUEyDS4Jg9gKx1Rvp+TMoC6UhIe9/hI
CBb1sCQ6kZfj4CeGyZQILBGg7RuXImVuR39MEqqUp2N+E5WJN09E+yhNDQIDAQAB
AoGAAenHsQpr+6TSpuZAfhNqu6lqTCq9CZ0AURcg44uU55DdLbgM7/hkThkqiD6N
ZTdoLE0a9/kCBxpsak4rFMU1jGQrHIpsK1fvaIS8Lym3ik82KzV+Na/UbUk0tPah
5E7/pLEclOyVpciG/OiAPtzwIaTpAR5LafUMwDWTqv68EsECQQDz8s0hI4L3w26C
Mldx37U+THay75it85CR/hrH+TwR1xEXpcFBK0qJZ88r+W9kLuZMwgDT641XtnyF
MhyUlB+9AkEAt4O3xXifZRGaWRimiy2vebc5tP77B/pLL0ogBgMBdn+zMaeR1lga
WABj0OCea7TgOVvkaTyUzuYZE0YDe0NPkQJBAMv2pvHdKiST3zK2eox4WaaD8f67
+zD941NdXPDz/vh/lAfsi788Pe7Sv9HplOvzlpR45I5LdPrwVf5bnq/PhRUCQF+4
jLqr2DhXnjKq8PPXuJe8QpVuCnJ205CvEVURbEnrAgT8as1q1xLf4TCqePelOO+y
Rsm9l8DztFChTF+XFIECQEfnlq/2nKJ9tPjwpnEMAvgG8ZPETySVOMXWw5D+8X0i
dbYb5MZfyowL0QZsEJAhSo1R5vzLTXjYAUCJrPZ0LKo=
-----END RSA PRIVATE KEY-----
"""

if __name__ == '__main__':
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-c', '--config-file', dest = 'configFile',
            help = 'location of config file to use')
    parser.add_option('-p', '--port', dest = 'port', type = 'int',
            default = 1234, help = 'port to listen on')

    options, args = parser.parse_args()
    storageConfig = StorageConfig(storagePath = "storage")
    if options.configFile:
        storageConfig.read(options.configFile)
    BaseRESTHandler.storageConfig = storageConfig

    h = HTTPServer(("", options.port), BaseRESTHandler)
    h.serve_forever()
