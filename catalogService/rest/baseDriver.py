#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import os
import sys
import subprocess
import time
import urllib
import urllib2

from conary.lib import util

from catalogService import cimupdater
from catalogService import errors
from catalogService import nodeFactory
from catalogService import descriptor
from catalogService import cloud_types, clouds, credentials, images, instances
from catalogService import instanceStore
from catalogService import keypairs, securityGroups
from catalogService import storage
from catalogService import x509

class BaseDriver(object):
    # Enumerate the factories we support.
    CloudConfigurationDescriptor = descriptor.ConfigurationDescriptor
    CredentialsDescriptor = descriptor.CredentialsDescriptor
    Cloud            = clouds.BaseCloud
    CloudType        = cloud_types.CloudType
    Credentials      = credentials.BaseCredentials
    CredentialsField = credentials.BaseField
    CredentialsFields = credentials.BaseFields
    Image            = images.BaseImage
    Instance         = instances.BaseInstance
    InstanceUpdateStatus = instances.BaseInstanceUpdateStatus
    InstanceType     = instances.InstanceType
    KeyPair          = keypairs.BaseKeyPair
    SecurityGroup    = securityGroups.BaseSecurityGroup

    _credNameMap = []
    cloudType = None

    updateStatusStateUpdating = 'updating'
    updateStatusStateDone = 'done'
    updateStatusStateException = 'error'

    instanceStorageClass = storage.DiskStorage

    def __init__(self, cfg, driverName, cloudName=None,
                 nodeFactory=None, mintClient=None, userId = None):
        self.userId = userId
        self.cloudName = cloudName
        self.driverName = driverName
        self._cfg = cfg
        self._cloudClient = None
        self._cloudCredentials = None
        if nodeFactory is None:
            nodeFactory = self._createNodeFactory()
        self._nodeFactory = nodeFactory
        self._mintClient = mintClient
        self._nodeFactory.userId = userId
        self._logger = None
        self._instanceStore = None
        self._x509Cert = None
        self._x509Key = None

    def _getInstanceStore(self):
        keyPrefix = '%s/%s' % (self._sanitizeKey(self.cloudName),
                               self._getUserIdForInstanceStore())
        path = os.path.join(self._cfg.storagePath, 'instances',
            self.cloudType)
        cfg = storage.StorageConfig(storagePath = path)

        dstore = self.instanceStorageClass(cfg)
        return instanceStore.InstanceStore(dstore, keyPrefix)

    def _getUserIdForInstanceStore(self):
        return self._sanitizeKey(self.userId)

    @classmethod
    def _sanitizeKey(cls, key):
        return key.replace('/', '_')

    def setLogger(self, logger):
        self._logger = logger

    def log_debug(self, *args, **kwargs):
        if self._logger:
            return self._logger.debug(*args, **kwargs)

    def log_info(self, *args, **kwargs):
        if self._logger:
            return self._logger.info(*args, **kwargs)

    def log_error(self, *args, **kwargs):
        if self._logger:
            return self._logger.error(*args, **kwargs)

    def log_exception(self, *args, **kwargs):
        if self._logger:
            return self._logger.exception(*args, **kwargs)

    def isValidCloudName(self, cloudName):
        raise NotImplementedError

    def __call__(self, request, cloudName=None):
        # This is a bit of a hack - basically, we're turning this class
        # into a factory w/o doing all the work of splitting out
        # a factory.  Call the instance with a request passed in, and you
        # get an instance that is specific to this particular request.
        self._nodeFactory.baseUrl = request.baseUrl
        self._nodeFactory.cloudName = cloudName
        drv =  self.__class__(self._cfg, self.driverName, cloudName,
                              self._nodeFactory, request.mintClient,
                              userId = request.auth[0])
        drv.setLogger(request.logger)
        return drv

    def _createNodeFactory(self):
        factory = nodeFactory.NodeFactory(
            cloudType = self.cloudType,
            cloudConfigurationDescriptorFactory = self.CloudConfigurationDescriptor,
            credentialsDescriptorFactory = self.CredentialsDescriptor,
            cloudTypeFactory = self.CloudType,
            cloudFactory = self.Cloud,
            credentialsFactory = self.Credentials,
            credentialsFieldFactory = self.CredentialsField,
            credentialsFieldsFactory = self.CredentialsFields,
            imageFactory = self.Image,
            instanceFactory = self.Instance,
            instanceUpdateStatusFactory = self.InstanceUpdateStatus,
            instanceTypeFactory = self.InstanceType,
            keyPairFactory = self.KeyPair,
            securityGroupFactory = self.SecurityGroup,
        )
        return factory

    def listClouds(self):
        self._checkAuth()
        ret = clouds.BaseClouds()
        if not self.isDriverFunctional():
            return ret
        for cloudConfig in self._enumerateConfiguredClouds():
            cloudNode = self._createCloudNode(cloudConfig)
            creds = self._getCloudCredentialsForUser(cloudNode.getCloudName())
            # RBL-4055: no longer erase launch descriptor if the credentials
            # are not set
            ret.append(cloudNode)
        return ret

    def getCloud(self, cloudName):
        ret = clouds.BaseClouds()
        if not self.isDriverFunctional():
            return ret
        for cloud in self.listClouds():
            if cloud.getCloudName() == cloudName:
                ret.append(cloud)
                return ret
        return ret

    def getAllImages(self):
        return self.getImages(None)

    def getImages(self, imageIds):
        if self.client is None:
            raise errors.MissingCredentials("Target credentials not set for user")
        return self.drvGetImages(imageIds)

    def getAllInstances(self):
        return self.getInstances(None)

    def getInstances(self, instanceIds):
        if self.client is None:
            raise errors.MissingCredentials("Target credentials not set for user")
        return self.drvGetInstances(instanceIds)

    def getInstance(self, instanceId):
        if self.client is None:
            raise errors.MissingCredentials("Target credentials not set for user")
        return self.drvGetInstance(instanceId)

    def drvGetInstance(self, instanceId):
        ret = self.drvGetInstances([instanceId])
        if ret:
            return ret[0]
        raise errors.HttpNotFound()

    def drvGetCloudCredentialsForUser(self):
        """
        Authenticate the user and cache the cloud credentials
        """
        if self._cloudCredentials is None:
            self._checkAuth()
            self._cloudCredentials = self._getCloudCredentialsForUser(
                                                            self.cloudName)
        return self._cloudCredentials

    credentials = property(drvGetCloudCredentialsForUser)

    def drvGetCloudClient(self):
        """
        Authenticate the user, cache the cloud credentials and the client
        """
        if self._cloudClient is None:
            cred = self.drvGetCloudCredentialsForUser()
            if not cred:
                return None
            self._cloudClient = self.drvCreateCloudClient(cred)
            self._instanceStore = self._getInstanceStore()
        return self._cloudClient

    client = property(drvGetCloudClient)

    def getCloudAlias(self):
        cloudConfig = self.drvGetCloudConfiguration()
        return cloudConfig['alias']

    def _checkAuth(self):
        """rBuilder authentication"""
        self._mintAuth = self._mintClient.checkAuth()
        if not self._mintAuth.authorized:
            raise PermissionDenied

    def getUserCredentials(self):
        cred = self.credentials
        # XXX We should validate the credentials too
        descr = self.getCredentialsDescriptor()
        descrData = descriptor.DescriptorData(descriptor = descr)
        if not cred:
            raise errors.MissingCredentials(status = 404,
                message = "User credentials not configured")
        for descrName, localName in self._credNameMap:
            descrData.addField(descrName, value = cred[localName])
        descrData.checkConstraints()
        return self._nodeFactory.newCredentialsDescriptorData(descrData)

    def getCloudType(self):
        node = self._createCloudTypeNode(self.cloudType)
        return node

    def _createCloudTypeNode(self, cloudTypeName):
        node = self._nodeFactory.newCloudType(
            id = cloudTypeName,
            cloudTypeName = cloudTypeName)
        return node

    def getCredentialsDescriptor(self):
        descr = descriptor.ConfigurationDescriptor(
            fromStream = self.credentialsDescriptorXmlData)
        return descr

    def getCloudConfigurationDescriptor(self):
        descr = descriptor.ConfigurationDescriptor(
            fromStream = self.configurationDescriptorXmlData)
        descr = self._nodeFactory.newCloudConfigurationDescriptor(descr)
        return descr

    def getLaunchDescriptor(self):
        cred = self.credentials
        if not cred:
            raise errors.HttpNotFound(message = "User has no credentials set")
        descr = descriptor.LaunchDescriptor()
        # We require an image ID
        descr.addDataField("imageId",
            descriptions = "Image ID",
            hidden = True, required = True, type = "str",
            constraints = dict(constraintName = 'range',
                               min = 1, max = 32))

        self.drvPopulateLaunchDescriptor(descr)
        descr = self._nodeFactory.newLaunchDescriptor(descr)
        return descr

    def launchInstance(self, xmlString, requestIPAddress, auth):
        # Grab the launch descriptor
        descr = self.getLaunchDescriptor()
        descr.setRootElement('newInstance')
        # Parse the XML string into descriptor data
        descrData = descriptor.DescriptorData(fromStream = xmlString,
            descriptor = descr)
        return self.launchInstanceFromDescriptorData(descrData, requestIPAddress, auth)

    def launchInstanceFromDescriptorData(self, descriptorData, requestIPAddress, auth):
        client = self.client
        cloudConfig = self.drvGetCloudConfiguration()

        imageId = os.path.basename(descriptorData.getField('imageId'))

        images = self.getImages([imageId])
        if not images:
            raise errors.HttpNotFound()
        image = images[0]

        params = self.getLaunchInstanceParameters(image, descriptorData)

        self.backgroundRun(self.launchInstanceInBackground, image, auth,
                           **params)
        newInstanceParams = self.getNewInstanceParameters(image,
            descriptorData, params)
        instanceList = instances.BaseInstances()
        instance = self._nodeFactory.newInstance(**newInstanceParams)
        instanceList.append(instance)
        return instanceList

    def getLaunchInstanceParameters(self, image, descriptorData):
        getField = descriptorData.getField
        imageId = image.getImageId()
        instanceName = getField('instanceName')
        instanceName = instanceName or self.getInstanceNameFromImage(image)
        instanceDescription = getField('instanceDescription')
        instanceDescription = (instanceDescription
                               or self.getInstanceDescriptionFromImage(image)
                               or instanceName)
        return dict(
            imageId = imageId,
            instanceName = instanceName,
            instanceDescription = instanceDescription,
            instanceType = getField('instanceType'),
        )

    def getNewInstanceParameters(self, image, descriptorData, launchParams):
        imageId = launchParams['imageId']
        instanceId = launchParams['instanceId']
        return dict(
            id = instanceId,
            instanceId = instanceId,
            imageId = imageId,
            instanceName = launchParams.get('instanceName'),
            instanceDescription = launchParams.get('instanceDescription'),
            cloudName = self.cloudName,
            cloudAlias = self.getCloudAlias(),
        )

    def createCloud(self, cloudConfigurationData):
        # Grab the configuration descriptor
        descr = self.getCloudConfigurationDescriptor()
        # Instantiate the descriptor data
        try:
            descrData = descriptor.DescriptorData(
                fromStream = cloudConfigurationData,
                descriptor = descr)
        except descriptor.InvalidXML:
            # XXX
            raise
        return self.drvCreateCloud(descrData)

    def removeCloud(self):
        cloudConfig = self.drvGetCloudConfiguration()
        if not cloudConfig:
            # Cloud does not exist
            raise errors.InvalidCloudName(self.cloudName)
        self.drvRemoveCloud()
        return clouds.BaseClouds()

    def setUserCredentials(self, credentialsData):
        # Authenticate
        _ = self.credentials

        # Grab the configuration descriptor
        descr = self.getCredentialsDescriptor()
        # Instantiate the descriptor data
        try:
            descrData = descriptor.DescriptorData(
                fromStream = credentialsData,
                descriptor = descr)
        except descriptor.InvalidXML:
            # XXX
            raise
        return self.drvSetUserCredentials(descrData)

    def getConfiguration(self):
        # Authenticate
        _ = self.credentials

        # Grab the configuration descriptor
        descr = self.getCloudConfigurationDescriptor()
        descrData = descriptor.DescriptorData(descriptor = descr)

        cloudConfig = self.drvGetCloudConfiguration(isAdmin = True)
        for k, v in sorted(cloudConfig.items()):
            if k not in descr._dataFieldsHash:
                continue
            descrData.addField(k, value = v, checkConstraints=False)
        return self._nodeFactory.newCloudConfigurationDescriptorData(descrData)

    def getInstanceNameFromImage(self, imageNode):
        if imageNode is None:
            return None
        for method in [ imageNode.getBuildName, imageNode.getProductName,
                        imageNode.getShortName ]:
            val = method()
            if val is not None:
                return val
        return None

    def extractImage(self, path):
        if path.endswith('.zip'):
            workdir = path[:-4]
            util.mkdirChain(workdir)
            cmd = 'unzip -d %s %s' % (workdir, path)
        elif path.endswith('.tgz'):
            workdir = path[:-4]
            util.mkdirChain(workdir)
            cmd = 'tar zxSf %s -C %s' % (path, workdir)
        else:
            raise errors.CatalogError('unsupported rBuilder image archive format')
        p = subprocess.Popen(cmd, shell = True, stderr = file(os.devnull, 'w'))
        p.wait()
        return workdir

    @classmethod
    def downloadFile(cls, url, destFile, headers = None):
        """Download the contents of the url into a file"""
        req = urllib2.Request(url, headers = headers or {})
        resp = urllib2.urlopen(req)
        if resp.headers['Content-Type'].startswith("text/html"):
            # We should not get HTML content out of rbuilder - most likely
            # a private project to which we don't have access
            raise errors.DownloadError("Unable to download file")
        util.copyfileobj(resp, file(destFile, 'w'))

    def _downloadImage(self, image, tmpDir, auth = None, extension = '.tgz'):
        imageId = image.getImageId()
        build = self._mintClient.getBuild(image.getBuildId())

        downloadUrl = image.getDownloadUrl()
        imageId = os.path.basename(image.getId())
        downloadFilePath = os.path.join(tmpDir, '%s%s' % (imageId, extension))

        headers = {}
        if image.getIsPrivate_rBuilder() and auth:
            # We need to acquire a pysid cookie
            netloc = urllib2.urlparse.urlparse(downloadUrl)[1]
            # XXX we don't allow for weird port numbers
            host, port = urllib.splitnport(netloc)
            pysid = CookieClient(host, auth[0], auth[1]).getCookie()
            if pysid is not None:
                headers['Cookie'] = pysid
            # If we could not fetch the pysid, we'll still try to download
        self.downloadFile(downloadUrl, downloadFilePath, headers = headers)
        return downloadFilePath

    def getInstanceDescriptionFromImage(self, imageNode):
        if imageNode is None:
            return None
        for method in [ imageNode.getBuildDescription,
                        imageNode.getProductDescription, ]:
            val = method()
            if val is not None:
                return val
        return None

    def updateInstances(self, instanceIds):
        instanceList = self.getInstances(instanceIds)

        for instance in instanceList:
            dnsName = instance.getPublicDnsName()
            if not dnsName:
                # We can't do anything unless we know how to contact the box
                continue
            newState = self.updateStatusStateUpdating
            self._setInstanceUpdateStatus(instance, newState)
            self.backgroundRun(self._updateInstance, instance, dnsName)

        instanceList.sort(key = lambda x: (x.getState(), x.getInstanceId()))
        return instanceList

    def updateInstance(self, instanceId):
        return self.updateInstances([instanceId])

    def _updateInstance(self, instance, dnsName):
        host = 'https://%s' % dnsName
        instanceId = instance.getInstanceId()
        self.log_debug("Updating instance %s (%s))", instanceId, dnsName)
        certFile, keyFile = self._instanceStore.getX509Files(instanceId)
        self.log_debug("Updating %s: cert %s, key %s", instanceId, certFile, keyFile)
        x509Dict = dict(cert_file = certFile, key_file = keyFile)
        updater = cimupdater.CIMUpdater(host, x509Dict)
        try:
            updater.checkAndApplyUpdate()
        except:
            # XXX FIXME: do something with the exception
            newState = self.updateStatusStateException
        else:
            # Mark the update status as done.
            newState = self.updateStatusStateDone
        self._setInstanceUpdateStatus(instance, newState)

    def _setInstanceUpdateStatus(self, instance, newState, newTime = None):
        if newTime is None:
            newTime = int(time.time())
        instance.getUpdateStatus().setState(newState)
        instance.getUpdateStatus().setTime(newTime)
        # Save the update status in the instance store
        instanceId = instance.getId()
        self._instanceStore.setUpdateStatusState(instanceId, newState)
        self._instanceStore.setUpdateStatusTime(instanceId, newTime)
        # Set the expiration to 3 hours for now.
        self._instanceStore.setExpiration(instanceId, 10800)

    def backgroundRun(self, function, *args, **kw):
        pid = os.fork()
        if pid:
            os.waitpid(pid, 0)
            return
        # Re-open the cloud client in the child
        self._cloudClient = None
        try:
            try:
                pid = os.fork()
                if pid:
                    # The first child exits and is waited by the parent
                    # the finally part will do the os._exit
                    return
                # Redirect stdin, stdout, stderr
                fd = os.open(os.devnull, os.O_RDWR)
                #os.dup2(fd, 0)
                #os.dup2(fd, 1)
                #os.dup2(fd, 2)
                os.close(fd)
                # Create new process group
                #os.setsid()

                os.chdir('/')
                function(*args, **kw)
            except Exception:
                try:
                    ei = sys.exc_info()
                    self.log_error('Daemonized process exception',
                                   exc_info = ei)
                finally:
                    os._exit(1)
        finally:
            os._exit(0)

    def addMintDataToImageList(self, imageList, imageType):
        cloudAlias = self.getCloudAlias()

        mintImages = self._mintClient.getAllBuildsByType(imageType)
        # Convert the list into a map keyed on the sha1 converted into
        # uuid format
        mintImages = dict((self.getImageIdFromMintImage(x), x) for x in mintImages)

        for image in imageList:
            imageId = image.getImageId()
            mintImageData = mintImages.pop(imageId, {})
            image.setIs_rBuilderImage(bool(mintImageData))
            image.setIsDeployed(True)
            if not mintImageData:
                continue
            self.addImageDataFromMintData(image, mintImageData,
                images.buildToNodeFieldMap)

        # Add the rest of the images coming from mint
        for uuid, mintImageData in sorted(mintImages.iteritems()):
            image = self._nodeFactory.newImage(id=uuid,
                    imageId=uuid, isDeployed=False,
                    is_rBuilderImage=True,
                    cloudName=self.cloudName,
                    cloudAlias=cloudAlias)
            self.addImageDataFromMintData(image, mintImageData,
                images.buildToNodeFieldMap)
            imageList.append(image)
        return imageList

    @classmethod
    def addImageDataFromMintData(cls, image, mintImageData, methodMap):
        shortName = os.path.basename(mintImageData['baseFileName'])
        longName = "%s/%s" % (mintImageData['buildId'], shortName)
        image.setShortName(shortName)
        image.setLongName(longName)
        image.setDownloadUrl(mintImageData['downloadUrl'])
        image.setBuildPageUrl(mintImageData['buildPageUrl'])
        image.setBaseFileName(mintImageData['baseFileName'])
        image.setBuildId(mintImageData['buildId'])

        for key, methodName in methodMap.iteritems():
            getattr(image, methodName)(mintImageData.get(key))

    def getWbemClientCert(self):
        return self.getWbemX509()[0]

    def getWbemX509(self):
        if self._x509Cert:
            # Already generated for this instance
            return self._x509Cert, self._x509Key
        certDir = os.path.join(self._cfg.storagePath, 'x509')
        self._x509Cert, self._x509Key = self.newX509(certDir)
        return self._x509Cert, self._x509Key

    def cleanUpX509(self):
        if not self._x509Cert:
            return
        certs = self.getWbemX509()
        for c in certs:
            try:
                os.unlink(c)
            except OSError:
                pass

    def computeX509CertHash(self, certFile):
        return x509.X509.computeHash(certFile)

    def newX509(self, certDir):
        netloc = urllib2.urlparse.urlparse(self._nodeFactory.baseUrl)[1]
        host, port = urllib.splitnport(netloc)

        commonName = 'Client certificate for %s' % host
        util.mkdirChain(certDir)
        return x509.X509.new(commonName, certDir = certDir)

    def getCredentialsIsoFile(self):
        certFile = self.getWbemClientCert()
        certDir = os.path.dirname(certFile)
        util.mkdirChain(certDir)
        isoDir = os.path.join(self._cfg.storagePath, 'credentials')
        util.mkdirChain(isoDir)
        fd, isoFile = x509.tempfile.mkstemp(dir = isoDir,
             prefix = 'credentials-', suffix = '.iso')
        os.close(fd)

        # Create an empty file for our signature
        empty = os.path.join(certDir, "EMPTY")
        file(empty, "w")

        # Load the cert, we need the hash
        certHash = self.computeX509CertHash(certFile)

        # Make ISO, if it doesn't exist already
        cmd = [ "/usr/bin/mkisofs", "-r", "-J", "-graft-points",
            "-o", isoFile,
            "SECURITY-CONTEXT-BOOTSTRAP=%s" % empty,
            "etc/sfcb/clients/%s.0=%s" % (certHash, certFile) ]

        devnull = file(os.devnull, "w")
        p = subprocess.Popen(cmd, shell = False, stdout=devnull,
            stderr = devnull)
        p.wait()
        return isoFile

class CookieClient(object):
    def __init__(self, server, username, password):
        self.server = server
        self.username = username
        self.password = password

        self.opener = urllib2.OpenerDirector()
        self.opener.add_handler(urllib2.HTTPSHandler())
        self.opener.add_handler(urllib2.HTTPHandler())
        self._cookie = None

    def getCookie(self):
        if self._cookie is not None:
            return self._cookie

        loginUrl = "https://%s/processLogin" % self.server
        data = urllib.urlencode([
            ('username', self.username),
            ('password', self.password),
            ('rememberMe', "1"),
            ('to', urllib.quote('http://%s/' % self.server)),
        ])
        ret = self.makeRequest(loginUrl, data, {})
        cookie = ret.headers.get('set-cookie')
        if not cookie or not cookie.startswith('pysid'):
            return None
        self._cookie = cookie.split(';', 1)[0]
        return self._cookie

    def makeRequest(self, loginUrl, data, headers):
        req = urllib2.Request(loginUrl, data = data, headers = headers)
        ret = self.opener.open(req)
        # Junk the response
        ret.read()
        return ret
