import os
import urllib
from boto.ec2.connection import EC2Connection
from boto.exception import EC2ResponseError

from catalogService import clouds
from catalogService import environment
from catalogService import errors
from catalogService import instances
from catalogService import images
from catalogService import keypairs
from catalogService import securityGroups
from catalogService.rest import baseDriver

CATALOG_DEF_SECURITY_GROUP = 'catalog-default'
CATALOG_DEF_SECURITY_GROUP_DESC = 'Default EC2 Catalog Security Group'
CATALOG_DEF_SECURITY_GROUP_PERMS = (
        # proto  start_port  end_port
        ('tcp',  22,         22),
        ('tcp',  80,         80),
        ('tcp',  443,        443),
        ('tcp',  8003 ,      8003),
)

EC2_DESCRIPTION = "Amazon Elastic Compute Cloud"

class EC2_Image(images.BaseImage):
    "EC2 Image"

    _constructorOverrides = dict(cloudName = 'aws', cloudAlias = 'ec2')

class EC2_Instance(instances.BaseInstance):
    "EC2 Instance"

    _constructorOverrides = EC2_Image._constructorOverrides.copy()

class EC2_Cloud(clouds.BaseCloud):
    "EC2 Cloud"

    _constructorOverrides = EC2_Image._constructorOverrides.copy()
    _constructorOverrides['description'] = EC2_DESCRIPTION

class EC2_EnvironmentCloud(environment.BaseCloud):
    "EC2 Environment Cloud"
    _constructorOverrides = EC2_Image._constructorOverrides.copy()

class EC2_InstanceTypes(instances.InstanceTypes):
    "EC2 Instance Types"

    idMap = [
        ('m1.small', "Small"),
        ('m1.large', "Large"),
        ('m1.xlarge', "Extra Large"),
        ('c1.medium', "High-CPU Medium"),
        ('c1.xlarge', "High-CPU Extra Large"),
    ]

class LaunchInstanceParameters(object):
    def __init__(self, xmlString=None, requestIPAddress = None):
        if xmlString:
            self.load(xmlString, requestIPAddress = requestIPAddress)

    def load(self, xmlString, requestIPAddress):
        from catalogService import newInstance
        node = newInstance.Handler().parseString(xmlString)
        image = node.getImage()
        imageId = image.getId()
        self.imageId = self._extractId(imageId)

        self.minCount = node.getMinCount() or 1
        self.maxCount = node.getMaxCount() or 1

        keyPair = node.getKeyPair()
        if not keyPair:
            raise errors.ParameterError('keyPair was not specified')
        keyName = keyPair.getId()
        self.keyName = self._extractId(keyName)

        self.securityGroups = []
        clientSuppliedRemoteIP = None
        for sg in (node.getSecurityGroups() or []):
            sgId = sg.getId()
            sgId = self._extractId(sgId)
            self.securityGroups.append(sgId)
            if sgId == CATALOG_DEF_SECURITY_GROUP:
                clientSuppliedRemoteIP = sg.getRemoteIp()

        self.remoteIPAddress = clientSuppliedRemoteIP or requestIPAddress

        self.userData = node.getUserData()

        instanceType = node.getInstanceType()
        if instanceType is None:
            instanceType = 'm1.small'
        else:
            instanceType = instanceType.getId() or 'm1.small'
            instanceType = self._extractId(instanceType)
        self.instanceType = instanceType

    @staticmethod
    def _extractId(value):
        if value is None:
            return None
        return urllib.unquote(os.path.basename(value))

_configurationDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>EC2 Cloud Configuration</displayName>
    <descriptions>
      <desc>Configure AWS EC2 Cloud</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>name</name>
      <descriptions>
        <desc>Name</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
    </field>
    <field>
      <name>cloudAlias</name>
      <descriptions>
        <desc>Cloud Alias</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
    </field>
    <field>
      <name>fullDescription</name>
      <descriptions>
        <desc>Full Description</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
    </field>
  </dataFields>
</descriptor>"""

_credentialsDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>EC2 User Credentials</displayName>
    <descriptions>
      <desc>User Credentials for Amazon EC2</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>accountId</name>
      <descriptions>
        <desc>Amazon Account Number</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Maximum Characters</desc>
        </descriptions>
        <length>12</length>
      </constraints>
      <required>true</required>
    </field>
    <field>
      <name>publicAccessKeyId</name>
      <descriptions>
        <desc>Access Key</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Maximum Characters</desc>
        </descriptions>
        <length>100</length>
      </constraints>
      <required>true</required>
    </field>
    <field>
      <name>secretAccessKey</name>
      <descriptions>
        <desc>Secret Key</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Maximum Characters</desc>
        </descriptions>
        <length>256</length>
      </constraints>
      <required>true</required>
    </field>
  </dataFields>
</descriptor>
"""

class EC2Client(baseDriver.BaseDriver):
    _cloudType = 'ec2'

    Cloud = EC2_Cloud
    EnvironmentCloud = EC2_EnvironmentCloud
    Image = EC2_Image
    Instance = EC2_Instance

    _instanceBotoMap = dict(
                dnsName = 'dns_name',
                imageId = 'image_id',
                instanceType = 'instance_type',
                kernel = 'kernel',
                keyName = 'key_name',
                launchTime = 'launch_time',
                placement = 'placement',
                previousState = 'previous_state',
                privateDnsName = 'private_dns_name',
                publicDnsName = 'public_dns_name',
                ramdisk = 'ramdisk',
                shutdownState = 'shutdown_state',
                stateCode = 'state_code',
                state = 'state',
    )

    _credNameMap = [
        ('accountId', 'awsAccountNumber'),
        ('publicAccessKeyId', 'awsPublicAccessKeyId'),
        ('secretAccessKey', 'awsSecretAccessKey'),
     ]

    configurationDescriptorXmlData = _configurationDescriptorXmlData
    credentialsDescriptorXmlData = _credentialsDescriptorXmlData

    def drvCreateCloudClient(self, credentials):
        for key in ('awsPublicAccessKeyId', 'awsSecretAccessKey'):
            if key not in credentials or not credentials[key]:
                raise errors.MissingCredentials()
        return EC2Connection(credentials['awsPublicAccessKeyId'],
                             credentials['awsSecretAccessKey'])

    @classmethod
    def drvGetCloudConfiguration(cls):
        return dict(name = 'aws', cloudAlias = 'ec2', fullDescription = EC2_DESCRIPTION)

    def _getCloudCredentialsForUser(self):
        try:
            return self._mintClient.getEC2CredentialsForUser(
                                                    self._mintAuth.userId)
        except mint.mint_error.PermissionDenied:
            raise errors.PermissionDenied

    def isValidCloudName(self, cloudName):
        return cloudName == 'aws'

    def drvSetUserCredentials(self, fields):
        awsAccountNumber = fields.getField('accountId')
        awsAccessKeyId = fields.getField('publicAccessKeyId')
        awsSecretAccessKey = fields.getField('secretAccessKey')

        valid = self._mintClient.setEC2CredentialsForUser(
            self._mintAuth.userId, awsAccountNumber, awsAccessKeyId,
            awsSecretAccessKey)

        return self._nodeFactory.newCredentials(valid = valid)

    def listClouds(self):
        ret = clouds.BaseClouds()
        ret.append(self._nodeFactory.newCloud())
        return ret

    def updateCloud(self, parameters):
        parameters = CloudParameters(parameters)
        pass

    def launchInstance(self, xmlString, requestIPAddress):
        parameters = LaunchInstanceParameters(xmlString,
            requestIPAddress = requestIPAddress)
        if (parameters.remoteIPAddress
            and CATALOG_DEF_SECURITY_GROUP in parameters.securityGroups):
            # Create/update the default security group that opens TCP
            # ports 80, 443, and 8003 for traffic from the requesting IP address
            self._updateCatalogDefaultSecurityGroup(parameters.remoteIPAddress)

        reservation = self.client.run_instances(parameters.imageId,
                min_count=parameters.minCount,
                max_count=parameters.maxCount,
                key_name=parameters.keyName,
                security_groups=parameters.securityGroups,
                user_data=parameters.userData,
                instance_type=parameters.instanceType)
        return self._getInstancesFromReservation(reservation)

    def terminateInstances(self, instanceIds):
        resultSet = self.client.terminate_instances(instance_ids=instanceIds)
        return self._getInstancesFromResult(resultSet)

    def terminateInstance(self, instanceId):
        return self.terminateInstances([instanceId])[0]

    def getAllInstances(self):
        return self.getInstances(None)

    def getInstances(self, instanceIds):
        resultSet = self.client.get_all_instances(instance_ids = instanceIds)
        insts = instances.BaseInstances()
        for reservation in resultSet:
            insts.extend(self._getInstancesFromReservation(reservation))
        return insts

    def getAllImages(self):
        return self.getImages(None)

    def getImages(self, imageIds):
        rs = self.client.get_all_images(image_ids = imageIds)
        # avoid returning amazon kernel images.
        rs = [ x for x in rs if x.id.startswith('ami-') ]
        return self._getImagesFromResult(rs)

    def getEnvironment(self):
        instTypeNodes = self._getInstanceTypes()
        keyPairNodes = self._getKeyPairs()
        securityGroupNodes = self._getSecurityGroups()

        cloud = self._nodeFactory.newEnvironmentCloud(
            instanceTypes = instTypeNodes, keyPairs = keyPairNodes,
            securityGroups = securityGroupNodes)

        env = self._nodeFactory.newEnvironment()
        env.append(cloud)
        return env

    def getInstanceTypes(self):
        return self._getInstanceTypes()

    def _updateCatalogDefaultSecurityGroup(self, remoteIPAddress):
        assert(remoteIPAddress)
        # add the security group if it's not present already
        try:
            self.client.create_security_group(CATALOG_DEF_SECURITY_GROUP,
                    CATALOG_DEF_SECURITY_GROUP_DESC)
        except EC2ResponseError, e:
            if e.status == 400 and e.code == 'InvalidGroup.Duplicate':
                pass # ignore this error
            else:
                raise errors.ResponseError(e.status, e.reason, e.body)

        # open ingress for ports 80, 443, and 8003 on TCP
        # for the IP address
        for proto, from_port, to_port in CATALOG_DEF_SECURITY_GROUP_PERMS:
            try:
                self.client.authorize_security_group(CATALOG_DEF_SECURITY_GROUP,
                        ip_protocol=proto, from_port=from_port, to_port=to_port,
                        cidr_ip='%s/32' % remoteIPAddress)
            except EC2ResponseError, e:
                if e.status == 400 and e.code == 'InvalidPermission.Duplicate':
                    pass # ignore this error
                else:
                    raise errors.ResponseError(e.status, e.reason, e.body)

        return CATALOG_DEF_SECURITY_GROUP

    def _getInstancesFromResult(self, resultSet):
        instanceList = instances.BaseInstances()
        for i in resultSet:
            instanceList.append(self._getInstance(i))
        return instanceList

    def _getInstancesFromReservation(self, reservation):
        insts = instances.BaseInstances()
        for instance in reservation.instances:
            insts.append(self._getInstance(instance, reservation))
        return insts

    def _getInstance(self, instance, reservation=None):
        properties = {}
        if reservation:
            properties.update(ownerId=reservation.owner_id,
                              reservationId=reservation.id)
        if hasattr(instance, 'ami_launch_index'):
            properties['launchIndex'] = int(instance.ami_launch_index)
        for attr, botoAttr in self._instanceBotoMap.items():
            properties[attr] = getattr(instance, botoAttr, None)
        i = self._nodeFactory.newInstance(id=instance.id,
                                          instanceId=instance.id,
                                          **properties)
        return i


    def _getImagesFromResult(self, results):
        imageList = images.BaseImages()
        for image in results:
            i = self._nodeFactory.newImage(id=image.id, imageId=image.id,
                                           ownerId=image.ownerId,
                                           longName=image.location,
                                           state=image.state,
                                           isPublic=image.is_public)
            imageList.append(i)
        imageDataDict = self._mintClient.getAllAMIBuilds()
        for image in imageList:
            imageData = imageDataDict.get(image.imageId.getText(), {})
            image.setIs_rBuilderImage(bool(imageData))
            for key, methodName in images.buildToNodeFieldMap.iteritems():
                getattr(image, methodName)(imageData.get(key))
        return imageList

    def _getInstanceTypes(self):
        ret = EC2_InstanceTypes()
        ret.extend(self._nodeFactory.newInstanceType(
                id = x, instanceTypeId = x, description = y)
            for (x, y) in EC2_InstanceTypes.idMap)
        return ret

    def _getKeyPairs(self, keynames = None):
        ret = keypairs.BaseKeyPairs()
        try:
            rs = self.client.get_all_key_pairs(keynames = keynames)
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, e.reason, e.body)
        ret.extend(self._nodeFactory.newKeyPair(id = x.name, keyName = x.name,
            keyFingerprint = x.fingerprint) for x in rs)
        return ret

    def _getSecurityGroups(self, groupNames = None):
        ret = securityGroups.BaseSecurityGroups()
        try:
            rs = self.client.get_all_security_groups(groupnames = groupNames)
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, e.reason, e.body)
        defSecurityGroup = None
        for sg in rs:
            sgObj = self._nodeFactory.newSecurityGroup(
                id = sg.name, groupName = sg.name, ownerId = sg.owner_id,
                description = sg.description)
            if sg.name == CATALOG_DEF_SECURITY_GROUP:
                # We will add this group as the first one
                defSecurityGroup = sgObj
                continue
            ret.append(sgObj)
        if defSecurityGroup is None:
            defSecurityGroup = self._nodeFactory.newSecurityGroup(
                id = CATALOG_DEF_SECURITY_GROUP,
                groupName = CATALOG_DEF_SECURITY_GROUP,
                description = CATALOG_DEF_SECURITY_GROUP_DESC)
        ret.insert(0, defSecurityGroup)
        return ret

