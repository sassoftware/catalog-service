
import os
import signal
import time
import urllib

from conary.lib import util

from catalogService import clouds
from catalogService import descriptor
from catalogService import environment
from catalogService import images
from catalogService import instances
from catalogService import storage
from catalogService.rest import baseDriver
from catalogService.rest.mixins import storage_mixin

import globuslib

class VWS_Cloud(clouds.BaseCloud):
    "Clobus Virtual Workspaces Cloud"

class VWS_Image(images.BaseImage):
    "Globus Virtual Workspaces Image"

    __slots__ = images.BaseImage.__slots__ + ['isDeployed', 'buildId',
                                              'downloadUrl', 'buildPageUrl',
                                              'baseFileName']
    _slotTypeMap = images.BaseImage._slotTypeMap.copy()
    _slotTypeMap.update(dict(isDeployed = bool))
    _constructorOverrides = VWS_Cloud._constructorOverrides.copy()

class VWS_Instance(instances.BaseInstance):
    "Globus Virtual Workspaces Instance"
    _constructorOverrides = VWS_Cloud._constructorOverrides.copy()

class VWS_EnvironmentCloud(environment.BaseCloud):
    "Globus Virtual Workspaces Environment Cloud"
    _constructorOverrides = VWS_Image._constructorOverrides.copy()

class VWS_InstanceTypes(instances.InstanceTypes):
    "Globus Virtual Workspaces Instance Types"

    idMap = [
        ('vws.small', "Small"),
        ('vws.medium', "Medium"),
        ('vws.large', "Large"),
        ('vws.xlarge', "Extra Large"),
    ]

class VWS_ImageHandler(images.Handler):
    imageClass = VWS_Image

_configurationDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>Globus Workspaces Cloud Configuration</displayName>
    <descriptions>
      <desc>Configure Globus Workspaces Cloud</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>alias</name>
      <descriptions>
        <desc>Cloud Alias</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
    </field>
    <field>
      <name>description</name>
      <descriptions>
        <desc>Full Description</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
    </field>
    <field>
      <name>factory</name>
      <descriptions>
        <desc>Factory Name</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
    </field>
    <field>
      <name>factoryIdentity</name>
      <descriptions>
        <desc>Factory Identity (x509 subject)</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
    </field>
    <field>
      <name>repository</name>
      <descriptions>
        <desc>GridFTP Repository Name</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
    </field>
    <field>
      <name>repositoryIdentity</name>
      <descriptions>
        <desc>GridFTP Repository Identity (x509 subject)</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
    </field>
    <field>
      <name>caCert</name>
      <descriptions>
        <desc>Certificate Authority (x509) Public Key</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Maximum Length</desc>
        </descriptions>
        <length>4096</length>
      </constraints>
      <required>true</required>
    </field>
  </dataFields>
</descriptor>"""

_credentialsDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>Globus Workspaces User Credentials</displayName>
    <descriptions>
      <desc>User Credentials for Globus Workspaces</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>userCert</name>
      <descriptions>
        <desc>X509 User Certificate</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Maximum Characters</desc>
        </descriptions>
        <length>4096</length>
      </constraints>
      <required>true</required>
    </field>
    <field>
      <name>userKey</name>
      <descriptions>
        <desc>X509 User Key</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Maximum Characters</desc>
        </descriptions>
        <length>4096</length>
      </constraints>
      <required>true</required>
    </field>
    <field>
      <name>sshPubKey</name>
      <descriptions>
        <desc>SSH Public Key</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Maximum Characters</desc>
        </descriptions>
        <length>4096</length>
      </constraints>
      <required>true</required>
    </field>
  </dataFields>
</descriptor>
"""

class VWSClient(baseDriver.BaseDriver, storage_mixin.StorageMixin):
    Cloud = VWS_Cloud
    EnvironmentCloud = VWS_EnvironmentCloud
    Image = VWS_Image
    Instance = VWS_Instance

    _cloudType = 'vws'

    _credNameMap = [
        ('userCert', 'userCert'),
        ('userKey', 'userKey'),
        ('sshPubKey', 'sshPubKey'),
    ]

    configurationDescriptorXmlData = _configurationDescriptorXmlData
    credentialsDescriptorXmlData = _credentialsDescriptorXmlData

    def __init__(self, *args, **kwargs):
        baseDriver.BaseDriver.__init__(self, *args, **kwargs)
        self._instanceStore = None

    @classmethod
    def isDriverFunctional(cls):
        return globuslib.WorkspaceCloudClient.isFunctional()

    def drvCreateCloudClient(self, credentials):
        cloudConfig = self.drvGetCloudConfiguration()
        props = globuslib.WorkspaceCloudProperties()
        userCredentials = credentials
        props.set('vws.factory', cloudConfig['factory'])
        props.set('vws.repository', cloudConfig['repository'])
        props.set('vws.factory.identity', cloudConfig['factoryIdentity'])
        props.set('vws.repository.identity', cloudConfig['repositoryIdentity'])
        cli = globuslib.WorkspaceCloudClient(props, cloudConfig['caCert'],
            userCredentials['userCert'], userCredentials['userKey'],
            userCredentials['sshPubKey'], cloudConfig['alias'])
        keyPrefix = "%s/%s" % (self._sanitizeKey(self.cloudName),
                               cli.userCertHash)
        self._instanceStore = self._getInstanceStore(keyPrefix)
        return cli

    def _enumerateConfiguredClouds(self):
        if not self.isDriverFunctional():
            return []
        store = self._getConfigurationDataStore()
        ret = []
        for cloudName in sorted(store.enumerate()):
            ret.append(self._getCloudConfiguration(cloudName))
        return ret

    def _getCloudCredentialsForUser(self):
        return self._getCredentialsForCloudName(self.cloudName)[1]

    def isValidCloudName(self, cloudName):
        cloudConfig = self._getCloudConfiguration(cloudName)
        return bool(cloudConfig)

    def _createCloudNode(self, cloudConfig):
        cld = self._nodeFactory.newCloud(cloudName = cloudConfig['factory'],
                         description = cloudConfig['description'],
                         cloudAlias = cloudConfig['alias'])
        return cld

    def launchInstance(self, xmlString, requestIPAddress):
        client = self.client
        parameters = LaunchInstanceParameters(xmlString)
        imageId = parameters.imageId

        image = self.getImage(imageId)
        if not image:
            raise errors.HttpNotFound()

        instanceId = self._instanceStore.newKey(imageId = imageId)
        self._daemonize(self._launchInstance,
                        instanceId, image,
                        duration=parameters.duration,
                        instanceType=parameters.instanceType)
        cloudAlias = client.getCloudAlias()
        instanceList = instances.BaseInstances()
        instance = self._nodeFactory.newInstance(id=instanceId,
                                        instanceId=instanceId,
                                        imageId=imageId,
                                        cloudName=self.cloudName,
                                        cloudAlias=cloudAlias)
        instanceList.append(instance)
        return instanceList

    def terminateInstances(self, instanceIds):
        client = self.client

        instIdSet = set(os.path.basename(x) for x in instanceIds)
        runningInsts = self.getInstances(instanceIds)

        # Separate the ones that really exist in globus
        nonGlobusInstIds = [ x.getInstanceId() for x in runningInsts
            if x.getReservationId() is None ]

        globusInstIds = [ x.getReservationId() for x in runningInsts
            if x.getReservationId() is not None ]

        if globusInstIds:
            client.terminateInstances(globusInstIds)
            # Don't bother to remove the instances from the store,
            # getInstances() should take care of that

        self._killRunningProcessesForInstances(nonGlobusInstIds)

        insts = instances.BaseInstances()
        insts.extend(runningInsts)
        # Set state
        for inst in insts:
            inst.setState("Terminating")
        return insts

    def terminateInstance(self, instanceId):
        return self.terminateInstances([instanceId])

    def drvGetImages(self, imageIds):
        imageList = self._getImagesFromGrid()
        imageList = self._addMintDataToImageList(imageList)

        # now that we've grabbed all the images, we can return only the one
        # we want.  This is horribly inefficient, but neither the mint call
        # nor the grid call allow us to filter by image, at least for now
        if imageIds is not None:
            imagesById = dict((x.getImageId(), x) for x in imageList )
            newImageList = images.BaseImages()
            for imageId in imageIds:
                if imageId.endswith('.gz') and imageId not in imagesById:
                    imageId = imageId[:-3]
                if imageId not in imagesById:
                    continue
                newImageList.append(imagesById[imageId])
            imageList = newImageList
        return imageList

    def drvPopulateLaunchDescriptor(self, descr):
        descr.setDisplayName("Globus Workspaces Launch Parameters")
        descr.addDescription("Globus Workspaces Launch Parameters")
        descr.addDataField("instanceType",
            descriptions = "Instance Size",
            type = descriptor.EnumeratedType(
                descriptor.ValueWithDescription(x,
                    descriptions = y)
                  for (x, y) in VWS_InstanceTypes.idMap)
            )
        descr.addDataField("minCount",
            descriptions = "Minimum Number of Instances",
            type = "int",
            constraints = dict(constraintName = 'range',
                               min = 1, max = 100))
        descr.addDataField("maxCount",
            descriptions = "Maximum Number of Instances",
            type = "int",
            constraints = dict(constraintName = 'range',
                               min = 1, max = 100))
        return descr


    def getImage(self, imageId):
        return self.getImages([imageId])[0]

    def getEnvironment(self):
        instTypeNodes = self._getInstanceTypes()

        cloud = self._nodeFactory.newEnvironmentCloud(
            instanceTypes = instTypeNodes, cloudName = self.cloudName)

        env = self._nodeFactory.newEnvironment()
        env.append(cloud)
        return env

    def getInstanceTypes(self):
        return self._getInstanceTypes()

    def drvGetInstances(self, instanceIds):
        cloudAlias = self.client.getCloudAlias()
        globusInsts  = self.client.listInstances()
        globusInstsDict = dict((x.getId(), x) for x in globusInsts)
        storeInstanceKeys = self._instanceStore.enumerate()
        reservIdHash = {}
        tmpInstanceKeys = {}
        for storeKey in storeInstanceKeys:
            instanceId = os.path.basename(storeKey)
            reservationId = self._instanceStore.getId(storeKey)
            expiration = self._instanceStore.getExpiration(storeKey)
            if reservationId is None and (expiration is None
                                     or time.time() > float(expiration)):
                # This instance exists only in the store, and expired
                self._instanceStore.delete(storeKey)
                continue
            imageId = self._instanceStore.getImageId(storeKey)

            # Did we find this instance in our store already?
            if reservationId in reservIdHash:
                # If the previously found instance already has an image ID,
                # prefer it. Also, if neither this instance nor the other one
                # have an image ID, prefer the first (i.e. not this one)
                otherInstKey, otherInstImageId = reservIdHash[reservationId]
                if otherInstImageId is not None or imageId is None:
                    self._instanceStore.delete(storeKey)
                    continue

                # We prefer this instance over the one we previously found
                del reservIdHash[reservationId]
                del tmpInstanceKeys[(otherInstKey, reservationId)]

            if reservationId is not None:
                reservIdHash[reservationId] = (storeKey, imageId)
            tmpInstanceKeys[(storeKey, reservationId)] = imageId

        # Done with the preference selection
        del reservIdHash

        gInsts = []

        # Walk through the list again
        for (storeKey, reservationId), imageId in tmpInstanceKeys.iteritems():
            if reservationId is None:
                # The child process hasn't updated the reservation id yet (or
                # it died but the instance hasn't expired yet).
                # Synthesize a globuslib.Instance with not much info in it
                state = self._instanceStore.getState(storeKey)
                inst = globuslib.Instance(_id = reservationId, _state = state)
                gInsts.append((storeKey, imageId, inst))
                continue

            reservationId = int(reservationId)
            if reservationId not in globusInstsDict:
                # We no longer have this instance, get rid of it
                self._instanceStore.delete(storeKey)
                continue
            # Instance exists both in the store and in globus
            inst = globusInstsDict.pop(reservationId)
            gInsts.append((storeKey, imageId, inst))
            # If a state file exists, get rid of it, we are getting the state
            # from globus
            self._instanceStore.setState(storeKey, None)

        # For everything else, create an instance ID
        for reservationId, inst in globusInstsDict.iteritems():
            nkey = self._instanceStore.newKey(realId = reservationId)
            gInsts.append((nkey, None, inst))

        gInsts.sort(key = lambda x: x[1])

        # Set up the filter for instances the client requested
        if instanceIds is not None:
            instanceIds = set(os.path.basename(x) for x in instanceIds)

        instanceList = instances.BaseInstances()

        for storeKey, imageId, instObj in gInsts:
            instId = str(os.path.basename(storeKey))
            if instanceIds and instId not in instanceIds:
                continue

            reservationId = instObj.getId()
            if reservationId is not None:
                reservationId = str(reservationId)
            inst = self._nodeFactory.newInstance(id = instId,
                imageId = imageId,
                instanceId = instId,
                reservationId = reservationId,
                dnsName = instObj.getName(),
                publicDnsName = instObj.getIp(), state = instObj.getState(),
                launchTime = instObj.getStartTime(),
                cloudName = self.cloudName,
                cloudAlias = cloudAlias)

            instanceList.append(inst)
        return instanceList

    def _daemonize(self, function, *args, **kw):
        pid = os.fork()
        if pid:
            os.waitpid(pid, 0)
            return
        try:
            try:
                pid = os.fork()
                if pid:
                    # The first child exits and is waited by the parent
                    # the finally part will do the os._exit
                    return
                # Redirect stdin, stdout, stderr
                fd = os.open(os.devnull, os.O_RDWR)
                os.dup2(fd, 0)
                os.dup2(fd, 1)
                os.dup2(fd, 2)
                os.close(fd)
                # Create new process group
                os.setsid()

                os.chdir('/')
                function(*args, **kw)
            except Exception:
                os._exit(1)
        finally:
            os._exit(0)

    def _setState(self, instanceId, state):
        return self._instanceStore.setState(instanceId, state)

    def _launchInstance(self, instanceId, image, duration,
                        instanceType):
        try:
            self._instanceStore.setPid(instanceId)
            if not image.getIsDeployed():
                self._setState(instanceId, 'Downloading image')
                dlImagePath = self._downloadImage(img, imageExtraData)
                self._setState(instanceId, 'Preparing image')
                imgFile = self._prepareImage(dlImagePath)
                self._setState(instanceId, 'Publishing image')
                self._publishImage(imgFile)
            imageId = image.getImageId()

            def callback(realId):
                self._instanceStore.setId(instanceId, realId)
                # We no longer manage the state ourselves
                self._setState(instanceId, None)
            self._setState(instanceId, 'Launching')

            realId = self.client.launchInstances([imageId],
                duration = duration, callback = callback)

        finally:
            self._instanceStore.deletePid(instanceId)

    def _downloadImage(self, image, imageExtraData):
        imageId = image.getImageId()
        # Get rid of the trailing .gz
        assert(imageId.endswith('.gz'))
        imageSha1 = imageId[:-3]
        build = self._mintClient.getBuild(image.getBuildId())

        downloadUrl = imageExtraData['downloadUrl']

        # XXX follow redirects
        uobj = urllib.urlopen(downloadUrl)
        # Create temp file
        downloadFilePath = os.path.join(self.cloudClient._tmpDir,
            '%s.tgz' % imageSha1)
        util.copyfileobj(uobj, file(downloadFilePath, "w"))
        return downloadFilePath

    def _prepareImage(self, downloadFilePath):
        retfile = self.client._repackageImage(downloadFilePath)
        os.unlink(downloadFilePath)
        return retfile

    def _publishImage(self, fileName):
        self.client.transferInstance(fileName)

    def _getImagesFromGrid(self):
        cloudAlias = self.client.getCloudAlias()

        imageIds = self.client.listImages()
        imageList = images.BaseImages()

        for imageId in imageIds:
            imageName = imageId
            image = self._nodeFactory.newImage(id = imageId,
                    imageId = imageId, isDeployed = True,
                    is_rBuilderImage = False,
                    shortName = os.path.basename(imageName),
                    longName = imageName,
                    cloudName = self.cloudName,
                    cloudAlias = cloudAlias)
            imageList.append(image)
        return imageList

    def _addMintDataToImageList(self, imageList):
        cloudAlias = self.client.getCloudAlias()

        imageDataLookup = self._mintClient.getAllVwsBuilds()
        # Convert the images coming from rbuilder to .gz, to match what we're
        # storing in globus
        imageDataLookup = dict((x + '.gz', y)
            for x, y in imageDataLookup.iteritems())
        for image in imageList:
            imageId = image.getImageId()
            mintImageData = imageDataLookup.pop(imageId, {})
            image.setIs_rBuilderImage(bool(mintImageData))
            image.setIsDeployed(True)
            if not mintImageData:
                continue
            self._addImageDataFromMintData(image, mintImageData)

        # Add the rest of the images coming from mint
        for imageId, mintImageData in sorted(imageDataLookup.iteritems()):
            image = self._nodeFactory.newImage(id = imageId,
                    imageId = imageId, isDeployed = False,
                    is_rBuilderImage = True,
                    cloudName = self.cloudName,
                    cloudAlias = cloudAlias)
            self._addImageDataFromMintData(image, mintImageData)
            imageList.append(image)
        return imageList

    @classmethod
    def _addImageDataFromMintData(cls, image, mintImageData):
        shortName = os.path.basename(mintImageData['baseFileName'])
        longName = "%s/%s" % (mintImageData['buildId'], shortName)
        image.setShortName(shortName)
        image.setLongName(longName)
        image.setDownloadUrl(mintImageData['downloadUrl'])
        image.setBuildPageUrl(mintImageData['buildPageUrl'])
        image.setBaseFileName(mintImageData['baseFileName'])
        image.setBuildId(mintImageData['buildId'])

        for key, methodName in images.buildToNodeFieldMap.iteritems():
            getattr(image, methodName)(mintImageData.get(key))

    @classmethod
    def _readCredentialsFromStore(cls, store, userId, cloudName):
        userId = userId.replace('/', '_')
        return dict(
            (os.path.basename(k), store.get(k))
                for k in store.enumerate("%s/%s" % (userId, cloudName)))

    @classmethod
    def _writeCredentialsToStore(cls, store, userId, cloudName, credentials):
        userId = userId.replace('/', '_')
        for k, v in credentials.iteritems():
            key = "%s/%s/%s" % (userId, cloudName, k)
            store.set(key, v)

    @classmethod
    def _sanitizeKey(cls, key):
        return key.replace('/', '_')

    @classmethod
    def _getCloudNameFromConfig(cls, config):
        return config['factory']

    @classmethod
    def _getCloudNameFromDescriptorData(cls, descriptorData):
        return descriptorData.getField('factory')

    def _getCredentialsForCloudName(self, cloudName):
        cloudConfig = self._getCloudConfiguration(cloudName)
        if not cloudConfig:
            return {}, {}

        store = self._getCredentialsDataStore()
        creds = self._readCredentialsFromStore(store, self.userId, cloudName)
        return cloudConfig, creds

    def _getInstanceTypes(self):
        ret = VWS_InstanceTypes()
        ret.extend(self._nodeFactory.newInstanceType(
                id = x, instanceTypeId = x, description = y)
            for (x, y) in VWS_InstanceTypes.idMap)
        return ret

    def _killRunningProcessesForInstances(self, nonGlobusInstIds):
        # For non-globus instances, try to kill the pid
        for instId in nonGlobusInstIds:
            pid = self._instanceStore.getPid(instId)
            if pid is not None:
                # try to kill the child process
                pid = int(pid)
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError, e:
                    if e.errno != 3: # no such process
                        raise
            # At this point the instance doesn't exist anymore
            self._instanceStore.delete(instId)


class LaunchInstanceParameters(object):
    __slots__ = [
        'duration', 'imageId', 'instanceType',
    ]

    def __init__(self, xmlString=None):
        if xmlString:
            self.load(xmlString)

    def load(self, xmlString):
        from catalogService import newInstance
        node = newInstance.Handler().parseString(xmlString)
        image = node.getImage()
        imageId = image.getId()
        self.imageId = self._extractId(imageId)
        self.duration = node.getDuration()
        if self.duration is None:
            raise errors.ParameterError('duration was not specified')

        instanceType = node.getInstanceType()
        if instanceType is None:
            instanceType = 'vws.small'
        else:
            instanceType = instanceType.getId() or 'vws.small'
            instanceType = self._extractId(instanceType)
        self.instanceType = instanceType

    @staticmethod
    def _extractId(value):
        if value is None:
            return None
        return urllib.unquote(os.path.basename(value))
