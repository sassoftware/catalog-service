#
# Copyright (c) 2008 rPath, Inc.
#

import os

import urllib

from catalogService import config
from catalogService import environment
from catalogService import images
from catalogService import instances
from catalogService import newInstance
from catalogService import keypairs
from catalogService import securityGroups

class Connection_Globus(object):
    "Globus Workspaces Connection"

class Config(config.BaseConfig):
    def __init__(self):
        "Clobus Workspaces Config"

class Image(images.BaseImage):
    "Globus Workspaces Image"

class Images(images.BaseImages):
    "Globus Workspaces Images"

class Instance(instances.BaseInstance):
    "Globus Workspaces Instance"

class Instances(instances.BaseInstances):
    "Globus Workspaces Instances"

class InstanceType(instances.InstanceType):
    "Globus Workspaces Instance Type"

class KeyPair(keypairs.BaseKeyPair):
    "Globus Workspaces Key Pair"

class KeyPairs(keypairs.BaseKeyPairs):
    "Globus Workspaces Key Pairs"

class SecurityGroup(securityGroups.BaseSecurityGroup):
    "Globus Workspaces Security Group"

class SecurityGroups(securityGroups.BaseSecurityGroups):
    "Globus Workspaces Security Groups"

class Cloud(environment.BaseCloud):
    "Globus Workspaces Cloud"

class Environment(environment.BaseEnvironment):
    "Globus Workspaces Environment"

class Driver(object):
    __slots__ = [ 'globusconn' ]

    def __init__(self, cfg):
        self.globusconn = Connection_Globus(cfg.awsPublicKey, cfg.awsPrivateKey)

    def getInstanceStatus(self, globusInstanceId):
        raise NotImplementedError

    def getAllImages(self, imageIds = None, owners = None, prefix = None):
        raise NotImplementedError

    def getAllInstances(self, instanceIds = None, prefix = None):
        raise NotImplementedError

    def getEnvironment(self, prefix=None):
        env = Environment()
        cloud = Cloud()

        cloud.setId(prefix)
        cloud.setCloudName('globus')

        env.append(cloud)

        return env

    def newInstance(self, launchData, prefix=None):
        raise NotImplementedError

    def terminateInstance(self, instanceId, prefix = None):
        raise NotImplementedError

