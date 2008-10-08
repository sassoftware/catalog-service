import os
import urllib
from boto.ec2.connection import EC2Connection
from boto.exception import EC2ResponseError

from catalogService import clouds
from catalogService import environment
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

class EC2_Image(images.BaseImage):
    "EC2 Image"

    _constructorOverrides = dict(cloudName = 'aws', cloudType = 'ec2',
        cloudAlias = 'ec2')

class EC2_Instance(instances.BaseInstance):
    "EC2 Instance"

    _constructorOverrides = EC2_Image._constructorOverrides.copy()

class EC2_Cloud(clouds.BaseCloud):
    "EC2 Cloud"

    _constructorOverrides = EC2_Image._constructorOverrides.copy()
    _constructorOverrides['description'] = 'Amazon Elastic Compute Cloud'

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


class EC2Client(baseDriver.BaseDriver):
    Cloud = EC2_Cloud
    EnvironmentCloud = EC2_EnvironmentCloud
    Image = EC2_Image
    Instance = EC2_Instance

    def _getClient(self):
        if not self._client:
            self._mintAuth = self._mintClient.checkAuth()
            if not self._mintAuth.authorized:
                raise PermissionDenied
            cred = self._mintClient.getEC2CredentialsForUser(
                                                 self._mintAuth.userId)
            self._client = EC2Connection(cred['awsPublicAccessKeyId'],
                                         cred['awsSecretAccessKey'])
        return self._client

    client = property(_getClient)

    def isValidCloudName(self, cloudName):
        return cloudName == 'aws'

    def listClouds(self):
        ret = clouds.BaseClouds()
        ret.append(self._nodeFactory.newCloud())
        return ret

    def updateCloud(self, cloudId, parameters):
        parameters = CloudParameters(parameters)
        pass

    def launchInstance(self, cloudId, xmlString, requestIPAddress):
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

    def terminateInstances(self, cloudId, instanceIds):
        resultSet = self.client.terminate_instances(instance_ids=instanceIds)
        return self._getInstancesFromResult(resultSet)

    def terminateInstance(self, cloudId, instanceId):
        return self.terminateInstances(cloudId, [instanceId])[0]

    def getAllInstances(self, cloudId):
        return self.getInstances(cloudId, None)

    def getInstances(self, cloudId, instanceIds):
        resultSet = self.client.get_all_instances(instance_ids = instanceIds)
        insts = instances.BaseInstances()
        for reservation in resultSet:
            insts.extend(self._getInstancesFromReservation(reservation))
        return insts

    def getAllImages(self, cloudId):
        return self.getImages(cloudId, None)

    def getImages(self, cloudId, imageIds):
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
        properties = {'placement' : instance.placement,
                      'kernel'    : instance.kernel,
                      'ramdisk'   : instance.ramdisk}
        if reservation:
            properties.update(ownerId=reservation.owner_id,
                              resevationId=reservation.id)
        if hasattr(instance, 'ami_launch_index'):
            properties.update(launchIndex=instance.ami_launch_index)
        i = self._nodeFactory.newInstance(id=instance.id,
                                          instanceId=instance.id,
                                          launchTime=instance.launch_time,
                                          imageId=instance.image_id,
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
