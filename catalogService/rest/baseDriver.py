from catalogService import nodeFactory
from catalogService import clouds, images, instances
from catalogService import environment, keypairs, securityGroups

class BaseDriver(object):
    Cloud            = clouds.BaseCloud
    Image            = images.BaseImage
    Instance         = instances.BaseInstance
    InstanceType     = instances.InstanceType
    Environment      = environment.BaseEnvironment
    EnvironmentCloud = environment.BaseCloud
    KeyPair          = keypairs.BaseKeyPair
    SecurityGroup    = securityGroups.BaseSecurityGroup

    def __init__(self, cfg, cloudType, cloudName=None,
                 nodeFactory=None, mintClient=None):
        self.cloudType = cloudType
        self.cloudName = cloudName
        self._cfg = cfg
        self._client = None
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
        return self.__class__(self._cfg, self.cloudType, cloudName,
                              self._nodeFactory, request.mintClient)

    def _createNodeFactory(self):
        factory = nodeFactory.NodeFactory(
            cloudType = self.cloudType,
            cloudFactory = self.Cloud,
            imageFactory = self.Image,
            instanceFactory = self.Instance,
            instanceTypeFactory = self.InstanceType,
            environmentFactory = self.Environment,
            environmentCloudFactory = self.EnvironmentCloud,
            keyPairFactory = self.KeyPair,
            securityGroupFactory = self.SecurityGroup,
        )
        return factory
