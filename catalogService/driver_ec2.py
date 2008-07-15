#
# Copyright (c) 2008 rPath, Inc.
#

import os
from boto.ec2 import connection as EC2Connection
import boto
from boto.exception import EC2ResponseError
import urllib

from catalogService import config
from catalogService import environment
from catalogService import errors
from catalogService import images
from catalogService import instances
from catalogService import newInstance
from catalogService import keypairs
from catalogService import securityGroups

class Connection_EC2(EC2Connection.EC2Connection):
    "EC2 Connection"

class Config(config.BaseConfig):
    def __init__(self, awsPublicKey, awsPrivateKey):
        config.BaseConfig.__init__(self)
        self.awsPublicKey = awsPublicKey
        self.awsPrivateKey = awsPrivateKey

class Image(images.BaseImage):
    "EC2 Image"

class Images(images.BaseImages):
    "EC2 Images"

class Instance(instances.BaseInstance):
    "EC2 Instance"

class Instances(instances.BaseInstances):
    "EC2 Instances"

class InstanceType(instances.InstanceType):
    "EC2 Instance Type"

class InstanceTypes(instances.InstanceTypes):
    "EC2 Instance Types"

    idMap = [
        ('m1.small', "Small"),
        ('m1.large', "Large"),
        ('m1.xlarge', "Extra Large"),
        ('c1.medium', "High-CPU Medium"),
        ('c1.xlarge', "High-CPU Extra Large"),
    ]

class KeyPair(keypairs.BaseKeyPair):
    "EC2 Key Pair"

class KeyPairs(keypairs.BaseKeyPairs):
    "EC2 Key Pairs"

class SecurityGroup(securityGroups.BaseSecurityGroup):
    "EC2 Security Group"

class SecurityGroups(securityGroups.BaseSecurityGroups):
    "EC2 Security Groups"

class Cloud(environment.BaseCloud):
    "EC2 Cloud"

class Environment(environment.BaseEnvironment):
    "EC2 Environment"

class Driver(object):
    __slots__ = [ 'ec2conn' ]

    def __init__(self, cfg):
        self.ec2conn = Connection_EC2(cfg.awsPublicKey, cfg.awsPrivateKey)

    def _launchInstance(self, ec2AMIId, minCount=1, maxCount=1,
            keyName=None, securityGroups=None, userData=None,
            instanceType=None, prefix = None):

        if instanceType is None:
            instanceType = "m1.small"
        try:
            ec2Reservation = self.ec2conn.run_instances(ec2AMIId,
                    min_count=minCount, max_count=maxCount,
                    key_name=keyName, security_groups=securityGroups,
                    user_data=userData, instance_type=instanceType)
            return self._getInstancesFromResultSet([ec2Reservation],
                prefix = prefix)
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, e.reason, e.body)

    def getInstanceStatus(self, ec2InstanceId):
        try:
            rs = self.ec2conn.get_all_instances(instance_ids=[ec2InstanceId])
            instance = rs[0].instances[0]
            return str(instance.state), str(instance.dns_name)
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, e.reason, e.body)

    def _terminateInstances(self, instanceIds, prefix = None):
        node = instances.BaseInstances()
        try:
            rs = self.ec2conn.terminate_instances(instance_ids=instanceIds)
            node.extend(self._genInstances(rs, prefix = prefix))
            return node
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, e.reason, e.body)

    @staticmethod
    def addPrefix(prefix, data):
        data = urllib.quote(data, safe="")
        if prefix is None:
            return data
        return os.path.join(prefix, data)

    def getAllImages(self, imageIds = None, owners = None, prefix = None):
        node = Images()
        try:
            rs = self.ec2conn.get_all_images(image_ids = imageIds, owners = owners)
            node.extend(Image(id=self.addPrefix(prefix, x.id), imageId=x.id,
                              ownerId=x.ownerId, longName=x.location,
                              state=x.state, isPublic=x.is_public) for x in rs
                              if x.id.startswith('ami-'))
            return node
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, e.reason, e.body)

    def getAllInstances(self, instanceIds = None, prefix = None):
        try:
            rs = self.ec2conn.get_all_instances(instance_ids = instanceIds)
            return self._getInstancesFromResultSet(rs, prefix = prefix)
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, e.reason, e.body)

    def getAllInstanceTypes(self, prefix=None):
        ret = InstanceTypes()
        ret.extend(InstanceType(id=self.addPrefix(prefix, x), instanceTypeId=x,
                   description=y)
                   for x, y in InstanceTypes.idMap)
        return ret

    def getAllKeyPairs(self, keynames = None, prefix = None):
        try:
            rs = self.ec2conn.get_all_key_pairs(keynames = keynames)
            ret = KeyPairs()
            ret.extend(
                KeyPair(id=self.addPrefix(prefix, x.name),
                        keyName=x.name, keyFingerprint=x.fingerprint)
                        for x in rs)
            return ret
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, e.reason, e.body)

    def getAllSecurityGroups(self, groupNames = None, prefix = None):
        try:
            rs = self.ec2conn.get_all_security_groups(groupnames = groupNames)
            ret = SecurityGroups()
            ret.extend(
                SecurityGroup(id=self.addPrefix(prefix, x.name),
                        ownerId=x.owner_id, groupName=x.name,
                        description=x.description)
                        for x in rs)
            return ret
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, e.reason, e.body)

    def getEnvironment(self, prefix=None):
        env = Environment()
        cloud = Cloud()

        instanceTypes = self.getAllInstanceTypes(
            prefix = "%s/instanceTypes/" % prefix)
        keyPairs = self.getAllKeyPairs(
            prefix = "%s/keyPairs/" % prefix)
        securityGroups = self.getAllSecurityGroups(
            prefix = "%s/securityGroups/" % prefix)

        cloud.setId(prefix)
        cloud.setCloudName('ec2')
        cloud.setInstanceTypes(instanceTypes)
        cloud.setKeyPairs(keyPairs)
        cloud.setSecurityGroups(securityGroups)

        env.append(cloud)

        return env

    def newInstance(self, launchData, prefix=None):
        hndlr = newInstance.Handler()
        node = hndlr.parseString(launchData)
        assert(isinstance(node, newInstance.BaseNewInstance))

        # Extract the real IDs
        image = node.getImage()
        imageId = image.getId()
        imageId = self._extractId(imageId)

        minCount = node.getMinCount() or 1
        maxCount = node.getMaxCount() or 1

        keyPair = node.getKeyPair()
        if not keyPair:
            raise errors.ParameterError('keyPair was not specified')
        keyName = keyPair.getId()
        keyName = self._extractId(keyName)

        securityGroups = []
        for sg in (node.getSecurityGroups() or []):
            sgId = sg.getId()
            sgId = self._extractId(sgId)
            securityGroups.append(sgId)

        userData = node.getUserData()

        instanceType = node.getInstanceType()
        if instanceType is None:
            instanceType = 'm1.small'
        else:
            instanceType = instanceType.getId() or 'm1.small'
            instanceType = self._extractId(instanceType)

        ret = self._launchInstance(imageId, minCount=minCount,
            maxCount=maxCount, keyName=keyName, securityGroups=securityGroups,
            userData=userData, instanceType=instanceType,
            prefix = prefix)
        return ret

    def terminateInstance(self, instanceId, prefix = None):
        ret = self._terminateInstances([instanceId], prefix = prefix)
        return ret[0]

    @staticmethod
    def _extractId(value):
        if value is None:
            return None
        return urllib.unquote(os.path.basename(value))

    def _genInstances(self, iList, reservation = None, prefix = None):
        for x in iList:
            ownerId = reservationId = launchIndex = None
            if reservation:
                ownerId = reservation.owner_id
                reservationId = reservation.id
            if hasattr(x, 'ami_launch_index'):
                launchIndex = int(x.ami_launch_index)
            inst = Instance(
                id=self.addPrefix(prefix, x.id), instanceId=x.id,
                dnsName=x.dns_name,
                publicDnsName=x.public_dns_name,
                privateDnsName=x.private_dns_name,
                state=x.state, stateCode=x.state_code,
                keyName=x.key_name,
                shutdownState=x.shutdown_state,
                previousState=x.previous_state,
                instanceType=x.instance_type,
                launchTime=x.launch_time,
                imageId=x.image_id,
                placement=x.placement,
                kernel=x.kernel,
                ramdisk=x.ramdisk,
                reservationId=reservationId,
                ownerId=ownerId,
                launchIndex=launchIndex)
            yield inst

    def _getInstancesFromResultSet(self, resultSet, prefix=None):
        node = Instances()
        for reserv in resultSet:
            node.extend(self._genInstances(reserv.instances, reserv,
                        prefix = prefix))
        return node
