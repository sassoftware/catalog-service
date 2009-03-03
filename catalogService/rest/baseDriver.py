from catalogService import errors
from catalogService import nodeFactory
from catalogService import descriptor
from catalogService import cloud_types, clouds, credentials, images, instances
from catalogService import environment, keypairs, securityGroups

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
    InstanceType     = instances.InstanceType
    Environment      = environment.BaseEnvironment
    EnvironmentCloud = environment.BaseCloud
    KeyPair          = keypairs.BaseKeyPair
    SecurityGroup    = securityGroups.BaseSecurityGroup

    _credNameMap = []
    cloudType = None

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
            instanceTypeFactory = self.InstanceType,
            environmentFactory = self.Environment,
            environmentCloudFactory = self.EnvironmentCloud,
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
        return self._cloudClient

    client = property(drvGetCloudClient)

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

    def launchInstance(self, xmlString, requestIPAddress):
        # Grab the launch descriptor
        descr = self.getLaunchDescriptor()
        descr.setRootElement('newInstance')
        # Parse the XML string into descriptor data
        descrData = descriptor.DescriptorData(fromStream = xmlString,
            descriptor = descr)
        return self.drvLaunchInstance(descrData, requestIPAddress)

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
            descrData.addField(k, value = v)
        descrData.checkConstraints()
        return self._nodeFactory.newCloudConfigurationDescriptorData(descrData)

    def _getInstanceNameFromImage(self, imageNode):
        if imageNode is None:
            return None
        for method in [ imageNode.getBuildName, imageNode.getProductName,
                        imageNode.getShortName ]:
            val = method()
            if val is not None:
                return val
        return None

    @classmethod
    def downloadFile(self, url, destFile, headers = None):
        """Download the contents of the url into a file"""
        req = urllib2.Request(url, headers = headers or {})
        resp = urllib2.urlopen(req)
        if resp.headers['Content-Type'].startswith("text/html"):
            # We should not get HTML content out of rbuilder - most likely
            # a private project to which we don't have access
            raise errors.DownloadError("Unable to download file")
        util.copyfileobj(resp, file(destFile, 'w'))

    def _downloadImage(self, image, tmpDir):
        imageId = image.getImageId()
        build = self._mintClient.getBuild(image.getBuildId())

        downloadUrl = image.getDownloadUrl()
        imageId = os.path.basename(image.getId())
        downloadFilePath = os.path.join(tmpDir, '%s.tgz' % imageId)

        self.downloadFile(downloadUrl, downloadFilePath)
        return downloadFilePath
    def _getInstanceDescriptionFromImage(self, imageNode):
        if imageNode is None:
            return None
        for method in [ imageNode.getBuildDescription,
                        imageNode.getProductDescription, ]:
            val = method()
            if val is not None:
                return val
        return None
