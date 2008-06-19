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

    def getAllImages(self, imageIds = None, owners = None, prefix = None):
        def addPrefix(data):
            if prefix is None:
                return data
            return prefix + data
        try:
            rs = self.ec2conn.get_all_images(image_ids = imageIds, owners = owners)
            return [ Image(id=addPrefix(x.id), imageId=x.id,
                           ownerId=x.ownerId, location=x.location,
                           state=x.state, isPublic=x.is_public) for x in rs ]
        except EC2ResponseError:
            return None

    def getAllInstances(self, instanceIds = None, prefix = None):
        def addPrefix(data):
            if prefix is None:
                return data
            return prefix + data
        try:
            rs = self.ec2conn.get_all_instances(instance_ids = instanceIds)
            ret = []
            for reserv in rs:
                for x in reserv.instances:
                    inst = Instance(
                        id=addPrefix(x.id), instanceId=x.id,
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
            return ret
        except EC2ResponseError:
            return None
