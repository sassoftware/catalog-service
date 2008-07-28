#
# Copyright (c) 2008 rPath, Inc.
#

import os

import urllib

from rpath_common import xmllib

from catalogService import clouds
from catalogService import config
from catalogService import environment
from catalogService import globuslib
from catalogService import images
from catalogService import instances
from catalogService import newInstance
from catalogService import keypairs
from catalogService import securityGroups

from conary import versions

class Connection_Workspaces(object):
    "Globus Virtual Workspaces Connection"

class Config(config.BaseConfig):
    def __init__(self):
        "Clobus Workspaces Config"

class Image(images.BaseImage):
    "Globus Virtual Workspaces Image"

    __slots__ = images.BaseImage.__slots__ + ['isDeployed']

    def __init__(self, attrs = None, nsMap = None, **kwargs):
        images.BaseImage.__init__(self, attrs = None, nsMap = None, **kwargs)
        self.setIsDeployed(kwargs.get('isDeployed'))

    def setIsDeployed(self, data):
        self.isDeployed = None
        if data is None:
            return self
        data = xmllib.BooleanNode.toString(data)
        self.isDeployed = xmllib.GenericNode().setName('isDeployed').characters(data)
        return self

    def getIsDeployed(self):
        if self.isDeployed is None:
            return None
        return xmllib.BooleanNode.fromString(self.isDeployed.getText())

class Images(images.BaseImages):
    "Globus Virtual Workspaces Images"

class Instance(instances.BaseInstance):
    "Globus Virtual Workspaces Instance"

class Instances(instances.BaseInstances):
    "Globus Virtual Workspaces Instances"

class Handler(images.Handler):
    imageClass = Image
    imagesClass = Images

class HandlerInstances(instances.Handler):
    instanceClass = Instance
    instancesClass = Instances

class InstanceType(instances.InstanceType):
    "Globus Virtual Workspaces Instance Type"

class KeyPair(keypairs.BaseKeyPair):
    "Globus Virtual Workspaces Key Pair"

class KeyPairs(keypairs.BaseKeyPairs):
    "Globus Virtual Workspaces Key Pairs"

class SecurityGroup(securityGroups.BaseSecurityGroup):
    "Globus Virtual Workspaces Security Group"

class SecurityGroups(securityGroups.BaseSecurityGroups):
    "Globus Virtual Workspaces Security Groups"

class EnvCloud(environment.BaseCloud):
    "Globus Virtual Workspaces Cloud"

class Environment(environment.BaseEnvironment):
    "Globus Virtual Workspaces Environment"

class Cloud(clouds.BaseCloud):
    "Globus Virtual Workspaces Cloud"
    def __init__(self, **kwargs):
        kwargs['cloudType'] = 'vws'
        clouds.BaseCloud.__init__(self, **kwargs)

class Driver(object):
    __slots__ = [ 'cloudClient', 'cfg', 'mintClient' ]

    def __init__(self, cloudClient, cfg, mintClient):
        self.cloudClient = cloudClient
        self.cfg = cfg
        self.mintClient = mintClient
        # XXX we need to fetch cloud related info from mint

    def getInstanceStatus(self, workspacesInstanceId):
        raise NotImplementedError

    def getImages(self, prefix):
        imgs = self.getImagesFromGrid(prefix = prefix)
        found = set()

        imageDataLookup = self.mintClient.getAllWorkspacesBuilds()
        for image in imgs:
            imageId = image.getImageId()
            imgData = imageDataLookup.get(imageId, {})
            if imgData:
                found.add(imageId)
            image.setIs_rBuilderImage(bool(imgData))
            image.setIsDeployed(True)
            for key, methodName in images.buildToNodeFieldMap.iteritems():
                val = imgData.get(key)
                method = getattr(image, methodName)
                method(val)

        # loop over the images known by rBuilder but not known by Workspaces
        for imageId, imgData in [x for x in imageDataLookup.iteritems()
                if x[0] not in found]:
            cloudId = "vws/%s" % self.cloudClient.getCloudId()
            image = Image(id = os.path.join(prefix, imageId),
                    imageId = imageId, cloud = cloudId, isDeployed = False,
                    is_rBuilderImage = True)
            for key, methodName in images.buildToNodeFieldMap.iteritems():
                val = imgData.get(key)
                method = getattr(image, methodName)
                method(val)
            imgs.append(image)
        return imgs

    def getImagesFromGrid(self, imageIds = None, owners = None, prefix = None):
        imageIds = self.cloudClient.listImages()
        imgs = Images()
        cloudId = 'vws/%s' % self.cloudClient.getCloudId()
        for imageId in imageIds:
            qimageId = urllib.quote(imageId, safe = "")
            image = Image(id = os.path.join(prefix, qimageId),
                    imageId = imageId, cloud = cloudId, isDeployed = True,
                    is_rBuilderImage = False)
            imgs.append(image)
        return imgs

    def getInstances(self, instanceIds = None, prefix = None):
        instObjs = self.cloudClient.listInstances()
        nodes = Instances()

        cloudId = 'vws/%s' % self.cloudClient.getCloudId()
        for instObj in instObjs:
            instId = str(instObj.getId())
            inst = Instance(id = os.path.join(prefix, instId),
                instanceId = instId, dnsName = instObj.getName(),
                privateDnsName = instObj.getIp(), state = instObj.getState(),
                launchTime = instObj.getStartTime())

            nodes.append(inst)
        return nodes

    def getEnvironment(self, prefix=None):
        env = Environment()
        cloud = EnvCloud()

        cloud.setId(prefix)
        cloud.setCloudName('workspaces')

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
        raise NotImplementedError

    def _getManifest(self, buildId):
        template = """<?xml version="1.0" encoding="UTF-8"?>
<VirtualWorkspace
    xmlns="http://www.globus.org/2008/06/workspace/metadata"
    xmlns:def="http://www.globus.org/2008/06/workspace/metadata/definition"
    xmlns:log="http://www.globus.org/2008/06/workspace/metadata/logistics"
    xmlns:jsdl="http://schemas.ggf.org/jsdl/2005/11/jsdl"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<name>%(IMAGEURI)s</name>
  <log:logistics>
    <log:networking>
      <log:nic>
        <log:name>eth0</log:name>
        <log:ipConfig>
        <log:acquisitionMethod>AllocateAndConfigure</log:acquisitionMethod>
        </log:ipConfig>
        <log:association>public</log:association>
      </log:nic>
    </log:networking>
  </log:logistics>
  <def:definition>
    <def:requirements>
      <jsdl:CPUArchitecture>
        <jsdl:CPUArchitectureName>%(ARCHTECTURE)s</jsdl:CPUArchitectureName>
      </jsdl:CPUArchitecture>
      <def:VMM>
        <def:version>3</def:version>
      </def:VMM>
    </def:requirements>
    <def:diskCollection>
      <def:rootVBD>
        <def:location>file://%(IMAGEFILENAME)s</def:location>
        <def:mountAs>sda1</def:mountAs>
        <def:permissions>ReadWrite</def:permissions>
      </def:rootVBD>
    </def:diskCollection>
  </def:definition>
</VirtualWorkspace>"""
        build = self.mintClient.getBuild(buildId)
        project = self.mintClient.getProject(build.getProjectId())
        macros = {}
        arch = build.getArch()
        ver = versions.ThawVersion(build.troveVersion)

        projectUrl = project.getUrl()
        if not projectUrl.endswith('/'):
            projectUrl += '/'
        macros['IMAGEURI'] = projectUrl + "build?%d" % build.getId()
        macros['ARCHTECTURE'] = arch

        # XXX this code mimics the rules the jobslave uses. perhaps this needs
        # to be moved into a more common location
        baseFileName = build.getDataValue('baseFileName') or ''
        baseFileName = ''.join([(x.isalnum() or x in ('-', '.')) and x or '_' \
                for x in baseFileName])
        baseFileName = baseFileName or \
                "%(name)s-%(version)s-%(arch)s" % {
                'name': project.hostname,
                'version': ver.trailingRevision().version,
                'arch': arch}

        # there's no build mount dict for now, so there's only one file
        macros['IMAGEFILENAME'] = os.path.join(baseFileName,
                baseFileName + '-root.ext3')
        return template % macros

