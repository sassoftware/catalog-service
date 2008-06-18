#
# Copyright (c) 2008 rPath, Inc.
#

import boto
from boto.exception import EC2ResponseError

import config
import images

class Config(config.BaseConfig):
    def __init__(self, awsPublicKey, awsPrivateKey):
        config.BaseConfig.__init__(self)
        self.awsPublicKey = awsPublicKey
        self.awsPrivateKey = awsPrivateKey

class Image(images.BaseImage):
    "EC2 Image"

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

    def getAllImages(self, imageIds = None, owners = None):
        try:
            rs = self.ec2conn.get_all_images(image_ids = imageIds, owners = owners)
            return [ Image(id=x.id, location=x.location, state=x.state,
                isPublic=x.is_public) for x in rs ]
        except EC2ResponseError:
            return None
