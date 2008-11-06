import os
import urllib
from boto.ec2.connection import EC2Connection
from boto.exception import EC2ResponseError

from mint.mint_error import EC2Exception as MintEC2Exception

from catalogService import clouds
from catalogService import descriptor
from catalogService import environment
from catalogService import errors
from catalogService import instances
from catalogService import images
from catalogService import keypairs
from catalogService import securityGroups
from catalogService import storage
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

    __slots__ = instances.BaseInstance.__slots__ + [
                'keyName', ]

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

        self.keyName = None
        keyPair = node.getKeyPair()
        if keyPair:
            keyName = keyPair.getId()
            self.keyName = self._extractId(keyName)

        self.securityGroups = []
        clientSuppliedRemoteIP = None
        for sg in (node.getSecurityGroups() or []):
            # Ignore nodes we don't expect
            if sg.getName() != securityGroups.BaseSecurityGroup.tag:
                continue
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

    def drvGetCloudConfiguration(self):
        store = self._getConfigurationDataStore()
        if store.get('disabled'):
            return {}
        return dict(name = 'aws', cloudAlias = 'ec2', fullDescription = EC2_DESCRIPTION)

    def _getCloudCredentialsForUser(self):
        cloudConfig = self.drvGetCloudConfiguration()
        if not cloudConfig:
            return {}
        try:
            return self._mintClient.getEC2CredentialsForUser(
                                                    self._mintAuth.userId)
        except mint.mint_error.PermissionDenied:
            raise errors.PermissionDenied

    def drvRemoveCloud(self):
        store = self._getConfigurationDataStore()
        store.set('disabled', "1")

    def drvCreateCloud(self, descriptorData):
        # Nothing fancy, just remove the disabled flag
        store = self._getConfigurationDataStore()
        store.delete('disabled')
        return self.listClouds()[0]

    def isDriverFunctional(self):
        return True

    def isValidCloudName(self, cloudName):
        return self.drvGetCloudConfiguration() and cloudName == 'aws'

    def drvSetUserCredentials(self, fields):
        awsAccountNumber = str(fields.getField('accountId'))
        awsAccessKeyId = str(fields.getField('publicAccessKeyId'))
        awsSecretAccessKey = str(fields.getField('secretAccessKey'))

        try:
            valid = self._mintClient.setEC2CredentialsForUser(
                self._mintAuth.userId, awsAccountNumber, awsAccessKeyId,
                awsSecretAccessKey, False)
        except MintEC2Exception, e:
            raise errors.PermissionDenied(message = str(e))

        return self._nodeFactory.newCredentials(valid = valid)

    def _enumerateConfiguredClouds(self):
        if not self.drvGetCloudConfiguration():
            # Cloud is not configured
            return []
        return [ None ]

    def _createCloudNode(self, cloudConfig):
        return self._nodeFactory.newCloud()

    def updateCloud(self, parameters):
        parameters = CloudParameters(parameters)
        pass

    def drvLaunchInstance(self, descriptorData, requestIPAddress):
        getField = descriptorData.getField
        remoteIp = getField('remoteIp')
        if remoteIp:
            requestIPAddress = remoteIp
        if CATALOG_DEF_SECURITY_GROUP in getField('securityGroups'):
            # Create/update the default security group that opens TCP
            # ports 80, 443, and 8003 for traffic from the requesting IP address
            self._updateCatalogDefaultSecurityGroup(requestIPAddress)

        reservation = self.client.run_instances(getField('imageId'),
                min_count=getField('minCount'),
                max_count=getField('maxCount'),
                key_name=getField('keyName'),
                security_groups=getField('securityGroups'),
                user_data=getField('userData'),
                instance_type=getField('instanceType'))
        return self._getInstancesFromReservation(reservation)

    def terminateInstances(self, instanceIds):
        resultSet = self.client.terminate_instances(instance_ids=instanceIds)
        return self._getInstancesFromResult(resultSet)

    def terminateInstance(self, instanceId):
        return self.terminateInstances([instanceId])[0]

    def drvGetInstances(self, instanceIds):
        resultSet = self.client.get_all_instances(instance_ids = instanceIds)
        insts = instances.BaseInstances()
        for reservation in resultSet:
            insts.extend(self._getInstancesFromReservation(reservation))
        return insts

    def drvGetImages(self, imageIds):
        rs = self.client.get_all_images(image_ids = imageIds)
        # avoid returning amazon kernel images.
        rs = [ x for x in rs if x.id.startswith('ami-') ]
        return self._getImagesFromResult(rs)

    def drvPopulateLaunchDescriptor(self, descr):
        descr.setDisplayName("Amazon EC2 Launch Parameters")
        descr.addDescription("Amazon EC2 Launch Parameters")
        descr.addDataField("instanceType",
            descriptions = "Instance Size", required = True,
            type = descriptor.EnumeratedType(
                descriptor.ValueWithDescription(x,
                    descriptions = y)
                  for (x, y) in EC2_InstanceTypes.idMap)
            )
        descr.addDataField("minCount",
            descriptions = "Minimum Number of Instances",
            type = "int", required = True,
            constraints = dict(constraintName = 'range',
                               min = 1, max = 100))
        descr.addDataField("maxCount",
            descriptions = "Maximum Number of Instances",
            type = "int", required = True,
            constraints = dict(constraintName = 'range',
                               min = 1, max = 100))
        descr.addDataField("keyPair",
            descriptions = "Key Pair",
            type = descriptor.EnumeratedType(
                descriptor.ValueWithDescription(x[0], descriptions = x[0])
                for x in self._cliGetKeyPairs()
            ))
        descr.addDataField("securityGroups",
            descriptions = "Security Groups",
            required = True, multiple = True,
            type = descriptor.EnumeratedType(
                descriptor.ValueWithDescription(x[0], descriptions = x[1])
                for x in self._cliGetSecurityGroups()
            ))
        descr.addDataField("remoteIp",
            descriptions = "Remote IP address allowed to connect (if security group is catalog-default)",
            type = "str",
            constraints = dict(constraintName = 'length', value = 128))
        descr.addDataField("userData",
            descriptions = "User Data",
            type = "str",
            constraints = dict(constraintName = 'length', value = 256))
        return descr

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
        instanceList.extend(self._getInstances(resultSet))
        return instanceList

    def _getInstancesFromReservation(self, reservation):
        insts = instances.BaseInstances()
        insts.extend(self._getInstances(reservation.instances, reservation))
        return insts

    def _getInstances(self, instancesIterable, reservation=None):
        # Grab images first
        imageIds = set(x.image_id for x in instancesIterable
            if x.image_id is not None)
        imageIdToImageMap = dict((x.getImageId(), x)
            for x in self.drvGetImages(list(imageIds)))

        properties = {}
        if reservation:
            properties.update(ownerId=reservation.owner_id,
                              reservationId=reservation.id)
        ret = []
        for instance in instancesIterable:
            imageNode = None
            if instance.image_id is not None:
                imageNode = imageIdToImageMap[instance.image_id]
            ret.append(self._getSingleInstance(instance, imageNode,
                       properties.copy()))
        return ret

    def _getSingleInstance(self, instance, imageNode, properties):
        if hasattr(instance, 'ami_launch_index'):
            properties['launchIndex'] = int(instance.ami_launch_index)
        for attr, botoAttr in self._instanceBotoMap.items():
            properties[attr] = getattr(instance, botoAttr, None)
        # come up with a sane name

        instanceName = self._getInstanceNameFromImage(imageNode)
        instanceDescription = self._getInstanceDescriptionFromImage(imageNode) \
            or instanceName
        properties['instanceName'] = instanceName
        properties['instanceDescription'] = instanceDescription
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
        ret.extend(self._nodeFactory.newKeyPair(id = x[0], keyName = x[0],
            keyFingerprint = x[1])
            for x in self._cliGetKeyPairs(keynames))
        return ret

    def _cliGetKeyPairs(self, keynames = None):
        try:
            rs = self.client.get_all_key_pairs(keynames = keynames)
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, e.reason, e.body)
        return [ (x.name, x.fingerprint) for x in rs ]

    def _getSecurityGroups(self, groupNames = None):
        ret = securityGroups.BaseSecurityGroups()
        for sg in self._cliGetSecurityGroups(groupNames):
            sgObj = self._nodeFactory.newSecurityGroup(
                id = sg[0], groupName = sg[0], ownerId = sg[2],
                description = sg[1])
            ret.append(sgObj)
        return ret

    def _cliGetSecurityGroups(self, groupNames = None):
        try:
            rs = self.client.get_all_security_groups(groupnames = groupNames)
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, e.reason, e.body)
        ret = []
        defSecurityGroup = None
        for sg in rs:
            entry =(sg.name, sg.description, sg.owner_id)
            if sg.name == CATALOG_DEF_SECURITY_GROUP:
                # We will add this group as the first one
                defSecurityGroup = entry
                continue
            ret.append(entry)
        if defSecurityGroup is None:
            defSecurityGroup = (CATALOG_DEF_SECURITY_GROUP,
                                CATALOG_DEF_SECURITY_GROUP_DESC,
                                None)
        ret.insert(0, defSecurityGroup)
        return ret

    def _getConfigurationDataStore(self):
        path = os.path.join(self._cfg.storagePath, 'configuration',
            self._cloudType, 'aws')
        cfg = storage.StorageConfig(storagePath = path)
        return storage.DiskStorage(cfg)

