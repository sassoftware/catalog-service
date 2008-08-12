#
# Copyright (c) 2008 rPath, Inc.
#

import os
import time

import urllib

from rpath_common import xmllib

from catalogService import clouds
from catalogService import config
from catalogService import driver
from catalogService import environment
from catalogService import errors
from catalogService import globuslib
from catalogService import images
from catalogService import instances
from catalogService import newInstance
from catalogService import keypairs
from catalogService import securityGroups

from conary import versions
from conary.lib import util

class Connection_Workspaces(object):
    "Globus Virtual Workspaces Connection"

class Config(config.BaseConfig):
    def __init__(self):
        "Clobus Workspaces Config"

class Image(images.BaseImage):
    "Globus Virtual Workspaces Image"

    __slots__ = images.BaseImage.__slots__ + ['isDeployed', 'buildId']

    def __init__(self, attrs = None, nsMap = None, **kwargs):
        images.BaseImage.__init__(self, attrs = None, nsMap = None, **kwargs)
        self.setIsDeployed(kwargs.get('isDeployed'))
        self.setBuildId(kwargs.get('buildId'))

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

class InstanceTypes(instances.InstanceTypes):
    "Globus Virtual Workspaces Instance Types"

    idMap = [
        ('vws.small', "Small"),
        ('vws.medium', "Medium"),
        ('vws.large', "Large"),
        ('vws.xlarge', "Extra Large"),
    ]


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

class Driver(driver.BaseDriver):
    __slots__ = [ 'cloudClient', 'cfg', 'mintClient' ]

    def __init__(self, cloudClient, cfg, mintClient):
        driver.BaseDriver.__init__(self)
        self.cloudClient = cloudClient
        self.cfg = cfg
        self.mintClient = mintClient
        # XXX we need to fetch cloud related info from mint
        self.instancesDir = '/tmp/catalog-service-instances'
        util.mkdirChain(self.instancesDir)

    def getInstanceStatus(self, workspacesInstanceId):
        raise NotImplementedError

    def getImages(self, prefix):
        imgs = self.getImagesFromGrid(prefix = prefix)
        found = set()

        imgExtraData = {}

        imageDataLookup = self._getMintImages()
        # Convert the images coming from rbuilder to .gz, to match what we're
        # storing in globus
        imageDataLookup = dict((x + '.gz', y)
            for x, y in imageDataLookup.iteritems())
        for image in imgs:
            imageId = image.getImageId()
            mintImageData = imageDataLookup.pop(imageId, {})
            image.setIs_rBuilderImage(bool(mintImageData))
            image.setIsDeployed(True)
            if not mintImageData:
                continue
            found.add(imageId)
            # Record additional info
            imgExtraData[imageId] = dict(
                downloadUrl = mintImageData['downloadUrl'],
                buildPageUrl = mintImageData['buildPageUrl'],
                baseFileName = mintImageData['baseFileName'])

            image.setBuildId(mintImageData['buildId'])
            for key, methodName in images.buildToNodeFieldMap.iteritems():
                val = mintImageData.get(key)
                method = getattr(image, methodName)
                method(val)

            shortName = os.path.basename(mintImageData['baseFileName'])
            longName = "%s/%s" % (mintImageData['buildId'], shortName)
            image.setShortName(shortName)
            image.setLongName(longName)

        # loop over the images known by rBuilder but not known by Workspaces
        for imageId, mintImageData in imageDataLookup.iteritems():
            cloudId = "vws/%s" % self.cloudClient.getCloudId()

            shortName = os.path.basename(mintImageData['baseFileName'])
            longName = "%s/%s" % (mintImageData['buildId'], shortName)
            image = Image(id = os.path.join(prefix, imageId),
                    imageId = imageId, isDeployed = False,
                    is_rBuilderImage = True,
                    buildId = mintImageData['buildId'],
                    longName = longName,
                    cloudName = cloudId, cloudType = 'vws',
                    cloudAlias = self.cloudClient.getCloudAlias())
            for key, methodName in images.buildToNodeFieldMap.iteritems():
                val = mintImageData.get(key)
                method = getattr(image, methodName)
                method(val)
            imgs.append(image)
            # Record additional info
            imgExtraData[imageId] = dict(
                downloadUrl = mintImageData['downloadUrl'],
                buildPageUrl = mintImageData['buildPageUrl'],
                baseFileName = mintImageData['baseFileName'])
        return imgs, imgExtraData

    def getImagesFromGrid(self, imageIds = None, owners = None, prefix = None):
        imageIds = self.cloudClient.listImages()
        imgs = Images()
        cloudId = 'vws/%s' % self.cloudClient.getCloudId()
        for imageId in imageIds:
            imageName = imageId
            qimageId = self._urlquote(imageId)
            image = Image(id = os.path.join(prefix, qimageId),
                    imageId = imageId, isDeployed = True,
                    is_rBuilderImage = False,
                    shortName = os.path.basename(imageName),
                    longName = imageName,
                    cloudName = cloudId, cloudType = 'vws',
                    cloudAlias = self.cloudClient.getCloudAlias())
            imgs.append(image)
        return imgs

    def getInstances(self, store, instanceIds = None, prefix = None):
        # For the comments below, reservation ID is the ID in the globus cloud
        # (a monotonically increasing integer), while the instance ID is the
        # ID we generated ourselves.
        cloudId = 'vws/%s' % self.cloudClient.getCloudId()

        globusInsts = self.cloudClient.listInstances()
        # Hash the instances
        globusInstsHash = dict((x.getId(), x) for x in globusInsts)
        del globusInsts

        # List the instances we have in the store
        keyPrefix = self._getInstanceStorePrefix()
        instanceStore = InstanceStore(store, keyPrefix)
        storeInstKeys = instanceStore.enumerate()

        tmpInstanceKeys = dict()
        reservIdHash = dict()
        for stKey in storeInstKeys:
            instId = os.path.basename(stKey)
            reservId = instanceStore.getId(stKey)
            expiration = instanceStore.getExpiration(stKey)

            if reservId is None and (expiration is None
                                     or time.time() > float(expiration)):
                # This instance exists only in the store, and expired
                instanceStore.delete(stKey)
                continue

            imageId = instanceStore.getImageId(stKey)
            # Did we find this instance in our store already?
            if reservId in reservIdHash:
                # If the previously found instance already has an image ID,
                # prefer it. Also, if neither this instance nor the other one
                # have an image ID, prefer the first (i.e. not this one)
                otherInstKey, otherInstImageId = reservIdHash[reservId]
                if otherInstImageId is not None or imageId is None:
                    instanceStore.delete(stKey)
                    continue

                # We prefer this instance over the one we previously found
                del reservIdHash[reservId]
                del tmpInstanceKeys[(otherInstKey, reservId)]

            if reservId is not None:
                reservIdHash[reservId] = (stKey, imageId)
            tmpInstanceKeys[(stKey, reservId)] = imageId

        # Done with the preference selection
        del reservIdHash

        gInsts = []

        # Walk through the list again
        for (stKey, reservId), imageId in tmpInstanceKeys.iteritems():
            if reservId is None:
                # The child process hasn't updated the reservation id yet (or
                # it died but the instance hasn't expired yet).
                # Synthesize a globuslib.Instance with not much info in it
                inst = globuslib.Instance(_id = reservId)
                gInsts.append((stKey, imageId, inst))
                continue

            reservId = int(reservId)
            if reservId not in globusInstsHash:
                # We no longer have this instance, get rid of it
                instanceStore.delete(stKey)
                continue
            # Instance exists both in the store and in globus
            inst = globusInstsHash.pop(reservId)
            gInsts.append((stKey, imageId, inst))
            # If a state file exists, get rid of it, we are getting the state
            # from globus
            instanceStore.setState(stKey, None)

        # For everything else, create an instance ID
        for reservId, inst in globusInstsHash.iteritems():
            nkey = instanceStore.newKey(realId = reservId)
            gInsts.append((nkey, None, inst))

        gInsts.sort(key = lambda x: x[1])

        nodes = Instances()

        for stKey, imageId, instObj in gInsts:
            instId = str(os.path.basename(stKey))
            longInstId = os.path.join(prefix, instId)
            reservationId = str(instObj.getId())
            inst = Instance(id = longInstId,
                imageId = imageId,
                instanceId = instId,
                reservationId = reservId,
                dnsName = instObj.getName(),
                publicDnsName = instObj.getIp(), state = instObj.getState(),
                launchTime = instObj.getStartTime(),
                cloudName = cloudId,
                cloudType = 'vws',
                cloudAlias = self.cloudClient.getCloudAlias(),)

            nodes.append(inst)
        return nodes

    def getEnvironment(self, cloudId, prefix=None):
        env = Environment()
        cloud = EnvCloud()

        instanceTypes = self.getAllInstanceTypes(
            prefix = "%s/instanceTypes/" % prefix)

        cloud.setId(prefix)
        cloud.setCloudType('vws')
        cloud.setCloudName('vws/%s' % cloudId)
        cloud.setCloudAlias(self.cloudClient.getCloudAlias())
        cloud.setInstanceTypes(instanceTypes)

        env.append(cloud)

        return env

    def newInstance(self, store, launchData, prefix=None):
        hndlr = newInstance.Handler()
        node = hndlr.parseString(launchData)
        assert(isinstance(node, newInstance.BaseNewInstance))

        # Extract the real IDs
        image = node.getImage()
        imageId = image.getId()
        imageId = self._extractId(imageId)

        duration = node.getDuration()
        if duration is None:
            raise errors.ParameterError('duration was not specified')

        instanceType = node.getInstanceType()
        if instanceType is None:
            instanceType = 'vws.small'
        else:
            instanceType = instanceType.getId() or 'vws.small'
            instanceType = self._extractId(instanceType)

        ret = self._launchInstance(store, imageId, duration = duration,
            instanceType = instanceType, prefix = prefix)
        return ret

    def terminateInstance(self, instanceId, prefix = None):
        raise NotImplementedError

    def _getMintImages(self):
        imageDataLookup = self.mintClient.getAllVwsBuilds()
        return imageDataLookup

    def _getInstanceStorePrefix(self):
        return "%s/%s" % (self.cloudClient.getCloudId().replace('/', '_'),
            self.cloudClient._userCertHash)

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

    def getAllInstanceTypes(self, prefix=None):
        ret = InstanceTypes()
        ret.extend(InstanceType(id=self.addPrefix(prefix, x), instanceTypeId=x,
                   description=y)
                   for x, y in InstanceTypes.idMap)
        return ret

    @classmethod
    def _urlquote(cls, data):
        return urllib.quote(data, safe = "")

    def _launchInstance(self, store, imageId, duration = None,
            instanceType = None, prefix = None):
        # First, verify that the instance we're about to launch exists

        # Prefix doesn't matter here, we're just trying to match the image
        # by ID
        imgs, imgsExtraData = self.getImages(prefix = 'aaa')

        fimgs = [ x for x in imgs if x.getImageId() == imageId ]

        # Strip out .gz too
        if not fimgs and imageId.endswith('.gz'):
            imgPrefix = imageId[:-3]
            fimgs = [ x for x in imgs if x.getImageId() == imgPrefix ]

        if not fimgs:
            raise errors.HttpNotFound()

        img = fimgs[0]
        imgExtraData = imgsExtraData.get(imageId)

        keyPrefix = self._getInstanceStorePrefix()
        instanceStore = InstanceStore(store, keyPrefix)

        instId = instanceStore.newKey(imageId = imageId)

        pid = os.fork()
        if pid == 0:
            # Fork once more, so we don't have to wait for the real worker
            pid = os.fork()
            if pid:
                # The first child exits and is waited by the parent
                os._exit(0)

            instanceStore.setPid(instId)

            try:
                # Redirect stdin, stdout, stderr
                fd = os.open(os.devnull, os.O_RDWR)
                os.dup2(fd, 0)
                os.dup2(fd, 1)
                os.dup2(fd, 2)
                os.close(fd)
                # Create new process group
                os.setsid()

                os.chdir('/')
                self._doLaunchImage(instanceStore, instId, img,
                    duration = duration, instanceType = instanceType,
                    imageExtraData = imgExtraData)
            finally:
                self.cloudClient.close()
                os._exit(0)
        else:
            os.waitpid(pid, 0)

        cloudId = "vws/%s" % self.cloudClient.getCloudId()
        ret = Instances()
        inst = Instance(id = self.addPrefix(prefix, instId),
            instanceId = instId,
            imageId = imageId,
            cloudName = cloudId,
            cloudType = 'vws',
            cloudAlias = self.cloudClient.getCloudAlias(),)
        ret.append(inst)
        return ret

    def _setState(self, instanceStore, instanceId, state):
        return instanceStore.setState(instanceId, state)

    def _doLaunchImage(self, instanceStore, instanceId, img, duration = None,
            instanceType = None, imageExtraData = None):
        if not img.getIsDeployed():
            self._setState(instanceStore, instanceId, 'Downloading image')
            dlImagePath = self._downloadImage(img, imageExtraData)
            self._setState(instanceStore, instanceId, 'Preparing image')
            imgFile = self._prepareImage(dlImagePath)
            self._setState(instanceStore, instanceId, 'Publishing image')
            self._publishImage(imgFile)

        imageId = img.getImageId()

        def callback(realId):
            instanceStore.setId(instanceId, realId)
            # We no longer manage the state ourselves
            self._setState(instanceStore, instanceId, None)

        self._setState(instanceStore, instanceId, 'Launching')
        try:
            # The callback will deal with setting the real ID and the state
            realId = self.cloudClient.launchInstances([imageId],
                duration = duration, callback = callback)
        except:
            raise

    def _downloadImage(self, image, imageExtraData):
        imageId = image.getImageId()
        # Get rid of the trailing .gz
        assert(imageId.endswith('.gz'))
        imageSha1 = imageId[:-3]
        build = self.mintClient.getBuild(image.getBuildId())

        downloadUrl = imageExtraData['downloadUrl']

        # XXX follow redirects
        uobj = urllib.urlopen(downloadUrl)
        # Create temp file
        downloadFilePath = os.path.join(self.cloudClient._tmpDir,
            '%s.tgz' % imageSha1)
        util.copyfileobj(uobj, file(downloadFilePath, "w"))
        return downloadFilePath

    def _prepareImage(self, downloadFilePath):
        retfile = self.cloudClient._repackageImage(downloadFilePath)
        os.unlink(downloadFilePath)
        return retfile

    def _publishImage(self, fileName):
        self.cloudClient.transferInstance(fileName)

class InstanceStore(object):
    __slots__ = [ '_store', '_prefix' ]
    DEFAULT_EXPIRATION = 300

    def __init__(self, store, prefix):
        self._store = store
        self._prefix = prefix

    def newKey(self, realId = None, imageId = None, expiration = None,
            state = None):
        if state is None:
            state = 'Creating'
        nkey = self._store.newKey(keyPrefix = self._prefix, keyLength = 6)
        instId = os.path.basename(nkey)
        if imageId is not None:
            self.setImageId(instId, imageId)
        if realId is not None:
            self.setId(instId, realId)
        self.setState(instId, state)
        self.setExpiration(instId, expiration)
        return instId

    def enumerate(self):
        return self._store.enumerate(self._prefix)

    def getImageId(self, instanceId):
        return self._get(instanceId, 'imageId')

    def setImageId(self, instanceId, imageId):
        return self._set(instanceId, 'imageId', imageId)

    def getId(self, instanceId):
        return self._get(instanceId, 'id')

    def setId(self, instanceId, realId):
        return self._set(instanceId, 'id', realId)

    def getState(self, instanceId, default = None):
        return self._get(instanceId, 'state', default = default)

    def setState(self, instanceId, state):
        ret = self._set(instanceId, 'state', state)
        if state is not None:
            # Also set the expiration
            self.setExpiration(instanceId)
        return ret

    def getPid(self, instanceId):
        ret = self._get(instanceId, 'pid')
        if ret is None:
            return ret
        return int(ret)

    def setPid(self, instanceId, pid = None):
        if pid is None:
            pid = os.getpid()
        return self._set(instanceId, 'pid', pid)

    def getExpiration(self, instanceId):
        exp = self._get(instanceId, 'expiration')
        if exp is None:
            return None
        return int(float(exp))

    def setExpiration(self, instanceId, expiration = None):
        if expiration is None:
            expiration = self.DEFAULT_EXPIRATION
        return self._set(instanceId, 'expiration',
            int(time.time() + expiration))

    def _get(self, instanceId, key, default = None):
        instanceId = self._getInstanceId(instanceId)
        fkey = os.path.join(self._prefix, instanceId, key)
        return self._store.get(fkey, default = default)

    def _set(self, instanceId, key, value):
        instanceId = self._getInstanceId(instanceId)
        fkey = os.path.join(self._prefix, instanceId, key)
        if value is not None:
            return self._store.set(fkey, value)
        return self._store.delete(fkey)

    def _getInstanceId(self, key):
        return os.path.basename(key)

    def delete(self, key):
        instanceId = self._getInstanceId(key)
        self._store.delete(os.path.join(self._prefix, instanceId))
