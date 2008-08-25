#
# Copyright (c) 2008 rPath, Inc.
#
"""
Summary
=======
This module implements the abstract interface with a web server, and HTTP
method handles for the abstraction.

URL format
==========
C{/<TOPLEVEL>/clouds}
    - (GET): enumerate available clouds
        Return an enumeration of clouds, with the ID in the format::
            /<TOPLEVEL>/clouds/<cloudName>
        C{<cloudName>} is generally composed of C{<cloudType>} or
        C{<cloudType>/<cloudId>}
        (for the cases where the cloud only exists as a single deployment, like
        Amazon's EC2, or, respectively, as multiple deployments, like Globus
        clouds).

C{/<TOPLEVEL>/clouds/<cloudType>}
    - (GET): enumerate available clouds for this type

C{/<TOPLEVEL>/clouds/<cloudName>/images}
    - (GET): enumerate available images for this cloud.
        - Return an enumeration of images, with the ID in the format::
            /<TOPLEVEL>/clouds/<cloudName>/images/<imageId>
    - (POST): publish a new image for this cloud (not valid for EC2).

C{/<TOPLEVEL>/clouds/<cloudName>/instances}
    - (GET): enumerate available images for this cloud.
        - Return an enumeration of instances, with the ID in the format::
            /<TOPLEVEL>/clouds/<cloudName>/instances/<instanceId>
    - (POST): Launch a new instance.

C{/<TOPLEVEL>/clouds/<cloudName>/instanceTypes}
    - (GET): enumerate available instance types.

C{/<TOPLEVEL>/clouds/<cloudName>/instances/<instanceId>}
    - (DELETE): Terminate a running instance.

C{/<TOPLEVEL>/clouds/<cloudName>/users/<user>/environment}
    - (GET): retrieve the launch environment

C{/<TOPLEVEL>/users/<user>}
    - (GET): Enumerate the keys defined in the store.
        - Return an enumeration of URIs in the format::
            /<TOPLEVEL>/users/<user>/<key>
    - (POST): Create a new entry in the store.

C{/<TOPLEVEL>/users/<user>/<key>}
    - (GET): Retrieve the contents of a key (if not a collection), or
      enumerate the collection.
    - (PUT): Update a key (if not a collection).
    - (POST): Create a new entry in a collection.
"""

import base64
import BaseHTTPServer
import os, sys
import urllib

from conary.lib import util

from catalogService import clouds
from catalogService import config
from catalogService import environment
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
    """
    Storage configuration object.
    @ivar storagePath: Path used for persisting the values.
    @type storagePath: C{str}
    """
    def __init__(self, storagePath):
        config.BaseConfig.__init__(self)
        self.storagePath = storagePath

class StandaloneRequest(brequest.BaseRequest):
    """
    Request object, qualified for a standalone HTTP server.
    """
    __slots__ = [ '_req', 'read' ]

    def __init__(self, req):
        brequest.BaseRequest.__init__(self)
        self._req = req
        self.read = self._req.rfile.read

        # We need to initialize the auth data
        authData = self.getHeader('Authorization')
        if authData and authData[:6] == 'Basic ':
            authData = authData[6:]
            authData = base64.decodestring(authData)
            authData = authData.split(':', 1)
            self.setUser(authData[0])
            self.setPassword(authData[1])

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

    def getRequestIP(self):
        return self.getHeader('X-Forwarded-For') or self._req.host

    def iterHeaders(self):
        for k, v in self._req.headers.items():
            yield k, v

    def setPath(self, path):
        self._req.path = path

    def getServerPort(self):
        return self._req.server.server_port

class BaseRESTHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """
    Request handler for a REST HTTP server.
    The implementation does not assume a particular implementation of a web
    server. This can be subclassed to handle mod_python based REST servers.
    As such, server-specific details like the format of requests, the way one
    reads incoming HTTP headers or sends outgoing HTTP headers etc are
    abstracted out into C{Request} and C{Response} objects.

    @cvar toplevel: a prefix for the path part of the URI, that can change
    based on how the service is deployed. For example, a deployment may choose
    to use C{/catalog} while another one may use C{/rest}.
    @type toplevel: C{str}

    @cvar storageConfig: Storage configuration object.
    @type storageConfig: L{StorageConfig} instance

    @cvar logLevel: Log level.
    @type logLevel: C{int}

    @newfield rest_url: REST URL, REST URLs
    @newfield rest_method: REST Method, REST Methods
    """
    toplevel = 'TOPLEVEL'
    storageConfig = StorageConfig(storagePath = "storage")
    logLevel = 1
    error_message_format = '\n'.join(('<?xml version="1.0" encoding="UTF-8"?>',
            '<fault>',
            '  <code>%(code)s</code>',
            '  <message>%(message)s</message>',
            '</fault>'))
    _logDestination = None

    def send_error(self, code, message = '', shortMessage = ''):
        # we have to override this method because the superclass assumes
        # we want to send back HTML. other than the content type, we're
        # not really changing much
        short, long = self.responses.get(code, ("???", "???"))
        if message is None:
            message = short
        if shortMessage is None:
            shortMessage = short
        self.log_error("code %d, message %s", code, message)
        sys.stderr.flush()
        content = (self.error_message_format %
               {'code': code, 'message': BaseHTTPServer._quote_html(message)})
        self.send_response(code, shortMessage)
        self.send_header("Content-Type", "application/xml")
        self.send_header('Connection', 'close')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        if self.command != 'HEAD' and code >= 200 and code not in (204, 304):
            self._getWriteMethod()(content)
        self._ret_status_code = code

    def log_message(self, format, *args):
        self.log(1, format, *args)

    def log_error(self, format, *args):
        self.log(0, format, tag = "ERROR", *args)

    def log_request(self, code="-", size="-"):
        self.log(0, '"%s" %s %s',
                  self.requestline, str(code), str(size))

    def log(self, logLevel, format, *args, **kwargs):
        if logLevel > self.logLevel:
            return
        dargs = dict(addressString = self.address_string(),
            timestamp = self.log_date_time_string(),
            data = format % args,
            )
        tag = kwargs.pop('tag', None)
        if tag is None:
            templ = "%(addressString)s - - [%(timestamp)s] %(data)s\n"
        else:
            templ = "%(addressString)s - - [%(timestamp)s] (%(tag)s) %(data)s\n"
            dargs['tag'] = tag
        f, shouldClose = self.getLogStream()
        f.write(templ % dargs)
        if shouldClose:
            f.close()

    def getLogStream(self):
        # Default to stderr
        ld = self._logDestination
        if ld is None:
            ld = sys.stderr

        if hasattr(ld, 'write'):
            f = ld
            shouldClose = False
        else:
            f = file(ld, "a")
            shouldClose = True

        return f, shouldClose

    def do_GET(self):
        """
        Respond to a GET request
        """
        return self.processRequest(self._do_GET)

    def do_POST(self):
        """
        Respond to a POST request
        """
        return self.processRequest(self._do_POST)

    def do_PUT(self):
        """
        Respond to a PUT request
        """
        return self.processRequest(self._do_PUT)

    def do_DELETE(self):
        """
        Respond to a DELETE request
        """
        return self.processRequest(self._do_DELETE)

    def processRequest(self, method):
        """
        Wrapper for calling a method. This method deals with creating request
        objects, exception handling etc.
        """
        req = self._createRequest()
        if req is None:
            # _createRequest does all the work to send back the error codes
            return self._ret_status_code

        try:
            response = method(req)
            return self._handleResponse(response)
        except:
            stream, shouldClose = self.getLogStream()
            excType, excValue, tb = sys.exc_info()

            errcode = getattr(excValue, 'errcode', 500)
            if errcode == 500:
                util.formatTrace(excType, excValue, tb, stream = stream,
                    withLocals = False)
                util.formatTrace(excType, excValue, tb, stream = stream,
                    withLocals = True)
            if shouldClose:
                stream.close()

            self.send_error(errcode, str(excValue), repr(excValue))
            return errcode

    #{ Real implementation for HTTP method handling
    def _do_GET(self, req):
        """
        Handle a GET request.

        @param req: Requst object.
        @type req: L{brequest.BaseRequest}

        @rest_method: C{GET}
        """
        self.log(1, "_do_GET")
        # we know the method, we're just using common code to strip it.
        path, method = self._get_HTTP_method(req.getRelativeURI(), 'GET')
        # now record the stripped path as the original path for consistency
        # We do this because we sometimes tunnel GET/PUT/DELETE methods
        # through POST.
        req.setPath(path)
        # This is only handled by standalone servers. In a mod_python
        # environment, most likely crossdomain.xml is handled directly by
        # apache.
        if path == '/crossdomain.xml':
            return self.serveCrossDomainFile()
        pathInfo = self._getPathInfo(path)
        resourceType = pathInfo.get('resourceType')
        if resourceType == 'clouds':
            resourceName = pathInfo.get('resourceName')
            if resourceName == 'users':
                resourceId = pathInfo.get('resourceId')
                if resourceId != 'environment':
                    raise errors.HttpNotFound
                userId = pathInfo.get('userId')
                if userId != req.getUser():
                    for k, v in req.iterHeaders():
                        print >> sys.stderr, "%s: %s" % (k, v)
                        sys.stderr.flush()
                    raise Exception("XXX 1", userId, req.getUser())
                cloudType = pathInfo.get('cloudType')
                if cloudType == 'ec2':
                    method = self.getEnvironmentEC2
                elif cloudType == 'vws':
                    method = self.getEnvironmentVWS
                else:
                    raise errors.HttpNotFound
                return method(req, pathInfo)
            return self._do_GET_clouds(req, pathInfo)

        if resourceType == 'userinfo':
            return self.enumerateUserInfo(req)

        if resourceType == 'users':
            return self.getUserData(req, pathInfo)

        raise errors.HttpNotFound

    def _do_GET_clouds(self, req, pathInfo):
        cloudType = pathInfo.get('cloudType')
        if cloudType is None:
            return self.enumerateClouds(req)
        # XXX do not hardcode the cloud type here
        cloudId = pathInfo.get('cloudId')
        resourceName = pathInfo.get('resourceName')
        if cloudType == 'ec2':
            if resourceName == 'images':
                return self.enumerateEC2Images(req)
            if resourceName == 'instances':
                return self.enumerateEC2Instances(req)
            if resourceName == 'instanceTypes':
                return self.enumerateEC2InstanceTypes(req)
        if cloudType == 'vws':
            if cloudId is None:
                return self.enumerateVwsClouds(req)
            cloudId = urllib.unquote(cloudId)
            cli = self._getVwsClient(cloudId, req)

            try:
                if resourceName == 'images':
                    return self.enumerateVwsImages(req, cli)
                if resourceName == 'instances':
                    return self.enumerateVwsInstances(req, cli)
            finally:
                cli.close()

    def _do_PUT(self, req):
        """
        Handle a PUT request.

        @param req: Requst object.
        @type req: L{brequest.BaseRequest}

        @rest_method: C{PUT}
        """
        self.log(1, "_do_PUT")
        path, method = self._get_HTTP_method(req.getRelativeURI(), 'PUT')
        pathInfo = self._getPathInfo(path)
        resourceType = pathInfo.get('resourceType')
        if resourceType == 'users':
            return self.setUserData(req, pathInfo)

    def _do_POST(self, req):
        """
        Handle a POST request.

        @param req: Requst object.
        @type req: L{brequest.BaseRequest}

        @rest_method: C{POST}
        """
        self.log(1, "_do_POST")
        # Look for a method
        path, method = self._get_HTTP_method(req.getRelativeURI(), 'POST')
        if method == 'GET':
            return self._do_GET(req)

        pathInfo = self._getPathInfo(path)
        resourceType = pathInfo.get('resourceType')
        if resourceType == 'users':
            if method == 'POST':
                return self.addUserData(req, pathInfo)
            elif method == 'DELETE':
                return self.deleteUserData(req, pathInfo)
            elif method == 'PUT':
                return self.setUserData(req, pathInfo)
            raise errors.HttpNotFound

        resourceName = pathInfo.get('resourceName')
        if (resourceType, resourceName) == ('clouds', 'instances'):
            return self._handleInstances(req, method, pathInfo)

    def _do_DELETE(self, req):
        """
        Handle a DELETE request.

        @param req: Requst object.
        @type req: L{brequest.BaseRequest}

        @rest_method: C{DELETE}
        """
        self.log(1, "_do_DELETE")
        path, method = self._get_HTTP_method(req.getRelativeURI(), 'DELETE')
        pathInfo = self._getPathInfo(path)
        resourceType = pathInfo.get('resourceType')
        if resourceType == 'users':
            return self.deleteUserData(req, pathInfo)
        resourceName = pathInfo.get('resourceName')
        if resourceType == 'clouds' and resourceName == 'instances':
            return self._handleInstances(req, method, pathInfo)

    #} Real implementation for HTTP method handling

    @classmethod
    def _get_HTTP_method(cls, path, defaultMethod):
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
        """
        Instantiate a Globus Virtual Workspaces client.
        """
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

        prefix = '/%s/' % self.toplevel
        if not path.startswith(prefix):
            # URL doesn't start with the toplevel prefix
            return {}
        pRest = path[len(prefix):]

        # Split and eliminate double slashes
        pComps = [ x for x in pRest.split('/') if x ]
        if not pComps:
            return {}

        res = {}
        res['prefix'] = prefix + '/'.join(pComps)
        res['resourceType'] = resourceType = pComps.pop(0)

        if resourceType == 'clouds':
            if not pComps:
                # We are only enumerating clouds
                return res

            res['cloudType'] = cloudType = pComps.pop(0)

            # XXX We should not hardcode things here
            if cloudType == 'ec2':
                if not pComps:
                    return {}
                res['cloudId'] = 'ec2'
            elif pComps:
                res['cloudId'] = pComps.pop(0)
            if not pComps:
                return res
            res['resourceName'] = resourceName = pComps.pop(0)
            if not pComps:
                return res
            if resourceName == 'users':
                res['userId'] = userId = pComps.pop(0)
            if not pComps:
                # We need more stuff specified here
                return {}
            res['resourceId'] = pComps.pop(0)
            if pComps:
                # Extra junk at the end
                return {}
            # Chop off the last part of the prefix, generally when a resource
            # ID is available we are prepending it at the end ourselves
            res['prefix'] = os.path.dirname(res['prefix'])
            return res

        if resourceType == 'userinfo':
            # Nothing more than userinfo supported
            if pComps:
                return {}
            return res

        if resourceType == 'users':
            # We need a user ID first
            if not pComps:
                return {}
            res['userId'] = userId = pComps.pop(0)
            # It is important for users if the path ends with a /
            if path.endswith('/'):
                pComps.append('')
            res['storeKey'] = '/'.join(pComps)
            # The prefix should not have the store key
            res['prefix'] = prefix + '/'.join([resourceType, userId, ""])
            return res

        # an empty dict indicates a URL we couldn't handle, which
        # ultimately results in a 404
        return {}

    def _handleInstances(self, req, httpMethod, pathInfo):
        """
        """
        cloudType = pathInfo.get('cloudType')
        cloudMap = dict(ec2 = 'EC2', vws = 'Vws')
        if cloudType not in cloudMap:
            # these are currently the only two clouds we handle
            raise errors.HttpNotFound
        cloudId = pathInfo.get('cloudId')
        if httpMethod == 'DELETE':
            methodName = 'terminate%sInstance' % cloudMap[cloudType]
            method = getattr(self, methodName)
            instanceId = pathInfo.get('resourceId')
            prefix = pathInfo.get('prefix', '')
            return method(req, cloudId, instanceId, prefix)
        methodName = 'new%sInstance' % cloudMap[cloudType]
        method = getattr(self, methodName)
        return method(req, cloudId)

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
        req = self._newRequest()
        host = req.getHeader('Host')
        if host is None:
            # Missing Host: header
            self.send_error(400)
            return

        self.host = host
        self.port = req.getServerPort()
        return req

    def _newRequest(self):
        req = StandaloneRequest(self)
        return req

    def _send_403(self):
        self._ret_status_code = 403
        return self._handleResponse(
            Response(code = 403, contentType = "text/html",
                     headers = dict(Connection = 'close')))

    def _auth(self, req):
        """
        Authenticate a request. If no authentication information is present,
        or if the authentication information does not verify, an HTTP 403
        (Forbidden) is sent back.
        """
        if req.getUser() is None:
            self._send_403()
            return False
        self.mintClient = self._getMintClient((req.getUser(), req.getPassword()))
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
        self._sendContentType(response.getContentType())
        for k, v in response.iterHeaders():
            self.send_header(k, v)
        self.end_headers()

        response.serveResponseBody(self._getWriteMethod())

    def _sendContentType(self, contentType):
        self.send_header('Content-Type', contentType)

    def _getWriteMethod(self):
        return self.wfile.write

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
        """
        Enumerate available clouds.

        @param req: Requst object.
        @type req: L{brequest.BaseRequest}

        @rest_method: C{GET}
        @rest_url: C{/clouds}
        """
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
        """
        Enumerate available Globus Virtual Workspaces clouds.

        @param req: Requst object.
        @type req: L{brequest.BaseRequest}

        @rest_method: C{GET}
        @rest_url: C{/clouds/vws}
        """
        prefix = req.getAbsoluteURI()
        nodes = self._enumerateVwsClouds(prefix, req)
        return Response(data = nodes)

    def enumerateVwsImages(self, req, cloudClient):
        """
        @rest_method: C{GET}
        @rest_url: C{/clouds/vws/.../images}
        """
        import driver_workspaces

        cfg = driver_workspaces.Config()
        drv = driver_workspaces.Driver(cloudClient, cfg, self.mintClient)

        prefix = req.getAbsoluteURI()
        imgs, imgFiles = drv.getImages(prefix = prefix)

        return Response(data = imgs)

    def enumerateVwsInstances(self, req, cloudClient):
        """
        @rest_method: C{GET}
        @rest_url: C{/clouds/vws/.../instances}
        """
        import driver_workspaces

        cfg = driver_workspaces.Config()
        drv = driver_workspaces.Driver(cloudClient, cfg, self.mintClient)

        prefix = req.getAbsoluteURI()
        nodes = drv.getInstances(store = self._getInstanceDataStore(),
            prefix = prefix)
        return Response(data = nodes)

    def enumerateEC2Instances(self, req):
        """
        @rest_method: C{GET}
        @rest_url: C{/clouds/ec2/instances}
        """
        import driver_ec2

        awsPublicKey, awsPrivateKey = self.getEC2Credentials()

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        prefix = req.getAbsoluteURI()
        node = drv.getAllInstances(prefix = prefix)
        return Response(data = node)

    def enumerateEC2InstanceTypes(self, req):
        """
        @rest_method: C{GET}
        @rest_url: C{/clouds/ec2/instanceTypes}
        """
        import images
        import driver_ec2

        awsPublicKey, awsPrivateKey = self.getEC2Credentials()

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        prefix = req.getAbsoluteURI()
        node = drv.getAllInstanceTypes(prefix=prefix)

        return Response(data = node)

    def enumerateUserInfo(self, req):
        """
        @rest_method: C{GET}
        @rest_url: C{/userinfo}
        """
        # we have to authenticate to get here, so we'll have a mintAuth obejct
        # XXX should this call be a UserInfo xml marshalling object?
        data = "<userinfo><username>%s</username></userinfo>" % \
                self.mintAuth.username

        return Response(data = data)

    def serveCrossDomainFile(self):
        """
        @rest_method: C{GET}
        @rest_url: C{/crossdomain.xml}
        """
        path = "crossdomain.xml"
        f = open(path)
        return Response(fileObj = f)

    def addUserData(self, req, pathInfo):
        """
        @rest_method: C{POST}
        @rest_url: C{/users/<userId>}
        """
        # Split the arguments
        userId = pathInfo.get('userId')
        if userId != req.getUser():
            raise Exception("XXX 1", userId, req.getUser())

        dataLen = req.getContentLength()
        data = req.read(dataLen)
        store = self._getUserDataStore()

        # POSTing to a URL with a trailing / should work (RDST-551)
        storeKey = pathInfo['storeKey'].rstrip('/')
        # Sanitize key
        keyPrefix = self._sanitizeKey(storeKey)

        newId = store.store(data, keyPrefix = keyPrefix)
        response = '<?xml version="1.0" encoding="UTF-8"?><id>%s/%s</id>' % (
            req.getAbsoluteURI(), os.path.basename(newId))
        return Response(data = response)

    def getUserData(self, req, pathInfo):
        """
        @rest_method: C{GET}
        @rest_url: C{/users/<userId>/<key>}
        @rest_url: C{/users/<userId>/<key>/}
        """
        userId = pathInfo['userId']
        if userId != req.getUser():
            raise Exception("XXX 1", userId, req.getUser())

        keyPath = self._sanitizeKey(pathInfo['storeKey'])

        prefix = pathInfo['prefix']
        prefix = "%s%s" % (req.getSchemeNetloc(), prefix)
        store = self._getUserDataStore()

        key = keyPath.rstrip('/')

        xmlHeader = '<?xml version="1.0" encoding="UTF-8"?>'
        if key != keyPath:
            # A trailing / means retrieving the contents from a collection
            if not store.isCollection(key):
                data = xmlHeader + '<list></list>'
                return Response(data = data)
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
            return Response(data = data)

        data = store.get(key)
        if data is None:
            raise errors.HttpNotFound
        return Response(data = data)

    def setUserData(self, req, pathInfo):
        """
        @rest_method: C{PUT}
        @rest_url: C{/users/<userId>/<key>}
        """
        userId = pathInfo['userId']
        if userId != req.getUser():
            raise Exception("XXX 1", userId, req.getUser())

        dataLen = req.getContentLength()
        data = req.read(dataLen)

        key = self._sanitizeKey(pathInfo['storeKey'])

        store = self._getUserDataStore()
        store.set(key, data)
        response = '<?xml version="1.0" encoding="UTF-8"?><id>%s</id>' % (
            req.getAbsoluteURIPath(), )
        return Response(data = response)

    def deleteUserData(self, req, pathInfo):
        """
        @rest_method: C{DELETE}
        @rest_url: C{/users/<userId>/<key>}
        """
        userId = pathInfo['userId']
        if userId != req.getUser():
            raise Exception("XXX 1", userId, req.getUser())

        store = self._getUserDataStore()

        storeKey = pathInfo['storeKey']
        key = self._sanitizeKey(storeKey)
        store.delete(key)
        response = '<?xml version="1.0" encoding="UTF-8"?><id>%s</id>' % (
            req.getAbsoluteURIPath(), )
        return Response(data = response)

    def getEnvironmentEC2(self, req, pathInfo):
        """
        @rest_method: C{DELETE}
        @rest_url: C{/clouds/ec2/users/.../environment}
        """
        import driver_ec2

        cloudPrefix = pathInfo['prefix']
        awsPublicKey, awsPrivateKey = self.getEC2Credentials()

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        prefix = "%s%s" % (req.getSchemeNetloc(), cloudPrefix)
        node = drv.getEnvironment(prefix=prefix)

        hndlr = environment.Handler()
        data = hndlr.toXml(node)

        return Response(data = data)

    def getEnvironmentVWS(self, req, pathInfo):
        """
        @rest_method: C{DELETE}
        @rest_url: C{/clouds/vws/.../users/.../environment}
        """
        import driver_workspaces

        cloudPrefix = pathInfo['prefix']
        cloudId = urllib.unquote(pathInfo['cloudId'])
        cloudClient = self._getVwsClient(cloudId, req)

        cfg = driver_workspaces.Config()
        drv = driver_workspaces.Driver(cloudClient, cfg, self.mintClient)

        prefix = "%s%s" % (req.getSchemeNetloc(), cloudPrefix)
        node = drv.getEnvironment(cloudId, prefix=prefix)

        cloudClient.close()
        return Response(data = node)


    def newEC2Instance(self, req, cloudId):
        """
        @rest_method: C{POST}
        @rest_url: C{/clouds/ec2/instances}
        """
        import driver_ec2
        awsPublicKey, awsPrivateKey = self.getEC2Credentials()

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        dataLen = req.getContentLength()
        data = req.read(dataLen)

        prefix = req.getAbsoluteURI()
        response = drv.newInstance(data, prefix = prefix,
                requestIPAddress = req.getRequestIP())

        return Response(data = response)

    def newVwsInstance(self, req, cloudId):
        """
        @rest_method: C{POST}
        @rest_url: C{/clouds/vws/.../instances}
        """
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
        """
        @rest_method: C{DELETE}
        @rest_url: C{/clouds/ec2/instances/...}
        """
        import driver_ec2

        awsPublicKey, awsPrivateKey = self.getEC2Credentials()

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        prefix = req.getSchemeNetloc() + prefix
        response = drv.terminateInstance(instanceId, prefix = prefix)

        return Response(data = response)

    def terminateVwsInstance(self, req, cloudId, instanceId, prefix):
        """
        @rest_method: C{DELETE}
        @rest_url: C{/clouds/vws/.../instances/...}
        """
        import driver_workspaces

        cfg = driver_workspaces.Config()

        cli = self._getVwsClient(cloudId, req)
        drv = driver_workspaces.Driver(cli, cfg, self.mintClient)

        dataLen = req.getContentLength()
        data = req.read(dataLen)

        prefix = req.getSchemeNetloc() + prefix
        response = drv.terminateInstances(self._getInstanceDataStore(),
            [instanceId], prefix = prefix)

        return Response(data = response[0])

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

    @classmethod
    def _sanitizeKey(cls, key):
        return '/'.join(x for x in key.split('/') if x not in ('.', '..'))
