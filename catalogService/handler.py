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
            cli = self._getVwsClient(cloudId, req)

            try:
                if pathInfo.get('resource') == 'images':
                    return self._handleResponse(self.enumerateVwsImages(req,
                            cli))
                if pathInfo.get('resource') == 'instances':
                    return self._handleResponse(self.enumerateVwsInstances(req,
                            cli))
            finally:
                cli.close()
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

    def _getVwsClient(self, cloudId, req):
        creds = self.getVwsCredentials(req)
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
            cloudCred['userCert'], cloudCred['userKey'],
            cloudCred['sshPubKey'], cloudCred['alias'])
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
                    res['cloudId'] = urllib.unquote(cloudId)
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

    def getVwsCredentials(self, req):
        from catalogService import globuslib
        if not globuslib.WorkspaceCloudClient.isFunctional():
            return []
        store = self._getCredentialsDataStore()
        user = urllib.quote(req.getUser(), safe="")
        # XXX in the future we'll have the credentials split by user
        user = "demo"
        clouds = store.enumerate(user)
        keys = ['alias', 'factory', 'repository', 'factoryIdentity',
            'repositoryIdentity', 'caCert', 'userCert', 'userKey',
            'sshPubKey', 'description', ]
        ret = []
        for cloud in clouds:
            d = dict((k, store.get("%s/%s" % (cloud, k)))
                for k in keys)
            ret.append(d)
        return ret

    def enumerateClouds(self, req):
        import driver_ec2
        nodes = clouds.BaseClouds()
        prefix = req.getAbsoluteURI()
        # Strip trailing /
        prefix = prefix.rstrip('/')
        try:
            _, _ = self.getEC2Credentials()
            nodes.append(driver_ec2.Cloud(id = prefix + '/ec2',
                cloudName = 'ec2',
                description = "Amazon Elastic Compute Cloud",
                cloudAlias = 'ec2'))
        except errors.MissingCredentials:
            pass
        nodes.extend(self._enumerateVwsClouds(prefix + '/vws', req))
        return Response(data = nodes)

    def enumerateVwsClouds(self, req):
        prefix = req.getAbsoluteURI()
        nodes = self._enumerateVwsClouds(prefix, req)
        return Response(data = nodes)

    def enumerateVwsImages(self, req, cloudClient):
        import driver_workspaces

        cfg = driver_workspaces.Config()
        drv = driver_workspaces.Driver(cloudClient, cfg, self.mintClient)

        prefix = req.getAbsoluteURI()
        imgs, imgFiles = drv.getImages(prefix = prefix)

        return Response(data = imgs)

    def enumerateVwsInstances(self, req, cloudClient):
        import driver_workspaces

        cfg = driver_workspaces.Config()
        drv = driver_workspaces.Driver(cloudClient, cfg, self.mintClient)

        prefix = req.getAbsoluteURI()
        nodes = drv.getInstances(store = self._getInstanceDataStore(),
            prefix = prefix)
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
        return Response(fileObj = f)

    def addUserData(self, req, userData):
        # Split the arguments
        userData = userData.split('/')
        if userData[0] != req.getUser():
            raise Exception("XXX 1", userData[0], req.getUser())

        dataLen = req.getContentLength()
        data = req.read(dataLen)
        store = self._getUserDataStore()

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
        store = self._getUserDataStore()

        key = keyPath.rstrip('/')

        xmlHeader = '<?xml version="1.0" encoding="UTF-8"?>'
        if key != keyPath:
            # A trailing / means retrieving the contents from a collection
            if not store.isCollection(key):
                data = xmlHeader + '<list></list>'
                return Response(data = data, code = 200)
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
            return Response(data = data, code = 200)

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

        store = self._getUserDataStore()
        key = '/'.join(x for x in userData if x not in ('', '.', '..'))
        store.set(key, data)
        response = '<?xml version="1.0" encoding="UTF-8"?><id>%s</id>' % (
            req.getAbsoluteURIPath(), )
        return Response(contentType = "text/xml", data = response)

    def deleteUserData(self, req, userData):
        userData = userData.split('/')
        if userData[0] != req.getUser():
            raise Exception("XXX 1")

        store = self._getUserDataStore()
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

        cloudClient = self._getVwsClient(cloudId, req)

        cfg = driver_workspaces.Config()
        drv = driver_workspaces.Driver(cloudClient, cfg, self.mintClient)

        prefix = "%s%s" % (req.getSchemeNetloc(), cloudPrefix)
        node = drv.getEnvironment(cloudId, prefix=prefix)

        cloudClient.close()
        return Response(data = node)


    def newEC2Instance(self, req, cloudId):
        import driver_ec2
        awsPublicKey, awsPrivateKey = self.getEC2Credentials()

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        dataLen = req.getContentLength()
        data = req.read(dataLen)

        prefix = req.getAbsoluteURI()
        response = drv.newInstance(data, prefix = prefix)

        return Response(data = response)

    def newVwsInstance(self, req, cloudId):
        if cloudId is None:
            raise errors.HttpNotFound
        cloudId = urllib.unquote(cloudId)

        cloudClient = self._getVwsClient(cloudId, req)

        dataLen = req.getContentLength()
        data = req.read(dataLen)

        prefix = req.getAbsoluteURI()

        from catalogService import driver_workspaces

        cfg = driver_workspaces.Config()
        drv = driver_workspaces.Driver(cloudClient, cfg, self.mintClient)

        store = self._getInstanceDataStore()
        try:
            response = drv.newInstance(store, data, prefix = prefix)
        except:
            cloudClient.close()
            raise
        # Don't close the client on success, the driver will do it for us

        return Response(data = response)

    def terminateEC2Instance(self, req, cloudId, instanceId, prefix):
        import driver_ec2

        awsPublicKey, awsPrivateKey = self.getEC2Credentials()

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        prefix = req.getSchemeNetloc() + prefix
        response = drv.terminateInstance(instanceId, prefix = prefix)

        return Response(data = response)

    def terminateVwsInstance(self, req, cloudId, instanceId, prefix):
        import driver_workspaces

        cfg = driver_workspaces.Config()

        drv = driver_workspaces.Driver(cloudId, cfg, self.mintClient)

        dataLen = req.getContentLength()
        data = req.read(dataLen)

        prefix = req.getSchemeNetloc() + prefix
        response = drv.terminateInstances([instanceId], prefix = prefix)

        return Response(data = response)

    def _getUserDataStore(self):
        path = self.storageConfig.storagePath + '/userData'
        cfg = StorageConfig(storagePath = path)
        return storage.DiskStorage(cfg)

    def _getInstanceDataStore(self):
        path = self.storageConfig.storagePath + '/instances'
        cfg = StorageConfig(storagePath = path)
        return storage.DiskStorage(cfg)

    def _getCredentialsDataStore(self):
        path = self.storageConfig.storagePath + '/credentials'
        cfg = StorageConfig(storagePath = path)
        return storage.DiskStorage(cfg)

    def _enumerateVwsClouds(self, prefix, req):
        import driver_workspaces
        creds = self.getVwsCredentials(req)

        nodes = driver_workspaces.clouds.BaseClouds()
        for cred in creds:
            nodeName = cred['factory']
            cloudName = "vws/%s" % cred['factory']
            node = driver_workspaces.Cloud(cloudName = cloudName,
                description = cred['description'],
                cloudAlias = cred['alias'])
            nodeId = "%s/%s" % (prefix, urllib.quote(nodeName, safe=":"))
            node.setId(nodeId)
            nodes.append(node)
        return nodes


class HTTPServer(BaseHTTPServer.HTTPServer):
    pass

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
