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
    _cloudType = None

    def __init__(self, cfg, cloudType, cloudName=None,
                 nodeFactory=None, mintClient=None):
        self.cloudType = cloudType
        self.cloudName = cloudName
        self._cfg = cfg
        self._cloudClient = None
        self._cloudCredentials = None
        if nodeFactory is None:
            nodeFactory = self._createNodeFactory()
        self._nodeFactory = nodeFactory
        self._mintClient = mintClient

    def isValidCloudName(self, cloudName):
        raise NotImplementedError

    def __call__(self, request, cloudName=None):
        # This is a bit of a hack - basically, we're turning this class
        # into a factory w/o doing all the work of splitting out
        # a factory.  Call the instance with a request passed in, and you
        # get an instance that is specific to this particular request.
        self._nodeFactory.baseUrl = request.baseUrl
        self._nodeFactory.cloudName = cloudName
        self._nodeFactory.userId = request.auth[0]
        return self.__class__(self._cfg, self.cloudType, cloudName,
                              self._nodeFactory, request.mintClient)

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

    def drvGetCloudCredentialsForUser(self):
        """
        Authenticate the user and cache the cloud credentials
        """
        if self._cloudCredentials is None:
            self._checkAuth()
            self._cloudCredentials = self._getCloudCredentialsForUser()
        return self._cloudCredentials

    credentials = property(drvGetCloudCredentialsForUser)

    def drvGetCloudClient(self):
        """
        Authenticate the user, cache the cloud credentials and the client
        """
        if not self._cloudClient:
            cred = self.drvGetCloudCredentialsForUser()
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
        # Map rbuilder credentials to a different name structure
        fields = [ (x, cred[y]) for (x, y) in self._credNameMap ]
        # XXX We should validate the credentials too
        return self._nodeFactory.newCredentials(valid = True, fields = fields)

    def getCloudType(self):
        node = self._createCloudTypeNode(self._cloudType)
        return node

    def _createCloudTypeNode(self, cloudTypeName):
        node = self._nodeFactory.newCloudType(
            id = cloudTypeName,
            cloudTypeName = cloudTypeName)
        return node

    def getCredentialsDescriptor(self):
        node = self._nodeFactory.newCredentialsDescriptor()
        return node

    def getCloudConfigurationDescriptor(self):
        desc = self._configDescriptor
        node = self._nodeFactory.newCloudConfigurationDescriptor()
        node.setDisplayName(desc['displayName'])
        for lang, description in desc['descriptions']:
            node.addDescription(description, lang = lang)
        for dataField in desc['fields']:
            node.addDataField(dataField['name'], type = dataField['type'],
                required = dataField.get('required'),
                descriptions = [ descriptor.Description(x[1], x[0])
                    for x in dataField.get('descriptions', [])],
                constraints = dataField.get('constraints', []),
                constraintsDescriptions = [ descriptor.Description(x[1], x[0])
                    for x in dataField.get('constraintsDescriptions', [])])
        return node
