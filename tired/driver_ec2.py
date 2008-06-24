#
# Copyright (c) 2008 rPath, Inc.
#

import boto
from boto.exception import EC2ResponseError

import config
import images
import instances

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

class Driver(object):
    __slots__ = [ 'ec2conn' ]

    def __init__(self, cfg):
        self.ec2conn = boto.connect_ec2(cfg.awsPublicKey, cfg.awsPrivateKey)

    def launchInstance(self, ec2AMIId, userData=None, useNATAddressing=False):

        # Get the appropriate addressing type to pass into the
        # Amazon API; 'public' uses NAT, 'direct' is bridged.
        # The latter method is deprecated and may go away in the
        # future.
        addressingType = useNATAddressing and 'public' or 'direct'
        try:
            ec2Reservation = self.ec2conn.run_instances(ec2AMIId,
                    user_data=userData, addressing_type=addressingType)
            ec2Instance = ec2Reservation.instances[0]
            return str(ec2Instance.id)
        except EC2ResponseError:
            return None

    def getInstanceStatus(self, ec2InstanceId):
        try:
            rs = self.ec2conn.get_all_instances(instance_ids=[ec2InstanceId])
            instance = rs[0].instances[0]
            return str(instance.state), str(instance.dns_name)
        except EC2ResponseError:
            return "unknown", ""

    def terminateInstance(self, ec2InstanceId):
        try:
            self.ec2conn.terminate_instances(instance_ids=[ec2InstanceId])
            return True
        except EC2ResponseError:
            return False

    @staticmethod
    def addPrefix(prefix, data):
        if prefix is None:
            return data
        return prefix + data

    def getAllImages(self, imageIds = None, owners = None, prefix = None):
        node = Images()
        try:
            rs = self.ec2conn.get_all_images(image_ids = imageIds, owners = owners)
            node.extend(Image(id=self.addPrefix(prefix, x.id), imageId=x.id,
                              ownerId=x.ownerId, location=x.location,
                              state=x.state, isPublic=x.is_public) for x in rs
                              if x.id.startswith('ami-'))
            return node
        except EC2ResponseError:
            return None

    def getAllInstances(self, instanceIds = None, prefix = None):
        try:
            rs = self.ec2conn.get_all_instances(instance_ids = instanceIds)
            ret = []
            for reserv in rs:
                for x in reserv.instances:
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
                        reservationId=reserv.id,
                        ownerId=reserv.owner_id)
                    ret.append(inst)
            node = Instances()
            node.extend(ret)
            return node
        except EC2ResponseError:
            return None

    def getAllInstanceTypes(self, prefix=None):
        ret = InstanceTypes()
        ret.extend(InstanceType(id=self.addPrefix(prefix, x), imageTypeId=x,
                   description=y)
                   for x, y in InstanceTypes.idMap)
        return ret
