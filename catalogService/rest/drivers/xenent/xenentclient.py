
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
from catalogService import instanceStore
from catalogService import storage
from catalogService.rest import baseDriver
from catalogService.rest.mixins import storage_mixin

import XenAPI
from XenAPI import provision as xenprov

class XenEnt_Image(images.BaseImage):
    "Xen Enterprise Image"

    __slots__ = images.BaseImage.__slots__ + ['isDeployed', 'buildId',
                                              'downloadUrl', 'buildPageUrl',
                                              'baseFileName']
    _slotTypeMap = images.BaseImage._slotTypeMap.copy()
    _slotTypeMap.update(dict(isDeployed = bool))

class XenEnt_InstanceTypes(instances.InstanceTypes):
    "Xen Enterprise Instance Types"

    idMap = [
        ('xenent.small', "Small"),
        ('xenent.medium', "Medium"),
    ]

_configurationDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>Xen Enterprise Cloud Configuration</displayName>
    <descriptions>
      <desc>Configure Xen Enterprise Cloud</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>name</name>
      <descriptions>
        <desc>Server Name</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
    </field>
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
  </dataFields>
</descriptor>"""

_credentialsDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>Xen Enterprise User Credentials</displayName>
    <descriptions>
      <desc>User Credentials for Xen Enterprise</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>username</name>
      <descriptions>
        <desc>User Name</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Maximum Characters</desc>
        </descriptions>
        <length>64</length>
      </constraints>
      <required>true</required>
    </field>
    <field>
      <name>password</name>
      <descriptions>
        <desc>Password</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Maximum Characters</desc>
        </descriptions>
        <length>64</length>
      </constraints>
      <required>true</required>
    </field>
  </dataFields>
</descriptor>
"""

class XenEntClient(baseDriver.BaseDriver, storage_mixin.StorageMixin):
    Image = XenEnt_Image

    _cloudType = 'xen-enterprise'

    _credNameMap = [
        ('username', 'username'),
        ('password', 'password'),
    ]

    configurationDescriptorXmlData = _configurationDescriptorXmlData
    credentialsDescriptorXmlData = _credentialsDescriptorXmlData

    XenSessionClass = XenAPI.Session

    def __init__(self, *args, **kwargs):
        baseDriver.BaseDriver.__init__(self, *args, **kwargs)
        self._instanceStore = None

    @classmethod
    def isDriverFunctional(cls):
        return True

    def drvCreateCloudClient(self, credentials):
        cloudConfig = self.drvGetCloudConfiguration()
        sess = self.XenSessionClass("https://%s" %
                                    self._getCloudNameFromConfig(cloudConfig))
        try:
            # password is a ProtectedString, we have to convert to string
            sess.login_with_password(credentials['username'],
                                     str(credentials['password']))
        except XenAPI.Failure, e:
            raise AuthenticationFailure(e.details[1], e.details[2])
        return sess

    @classmethod
    def _getCloudNameFromConfig(cls, config):
        return config['name']

    @classmethod
    def _getCloudNameFromDescriptorData(cls, descriptorData):
        return descriptorData.getField('name')

    def _getCloudCredentialsForUser(self):
        return self._getCredentialsForCloudName(self.cloudName)[1]

    def isValidCloudName(self, cloudName):
        cloudConfig = self._getCloudConfiguration(cloudName)
        return bool(cloudConfig)

    def drvSetUserCredentials(self, fields):
        data = dict((x.getName(), x.getValue()) for x in fields.getFields())
        store = self._getCredentialsDataStore()
        self._writeCredentialsToStore(store, self.userId, self.cloudName, data)
        # XXX validate
        valid = True
        node = self._nodeFactory.newCredentials(valid)
        return node

    def _createCloudNode(self, cloudConfig):
        cld = self._nodeFactory.newCloud(cloudName = cloudConfig['name'],
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
        descr.setDisplayName("Xen Enterprise Launch Parameters")
        descr.addDescription("Xen Enterprise Launch Parameters")
        descr.addDataField("instanceType",
            descriptions = "Instance Size",
            type = descriptor.EnumeratedType(
                descriptor.ValueWithDescription(x,
                    descriptions = y)
                  for (x, y) in XenEnt_InstanceTypes.idMap)
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

    def getEnvironment(self):
        cloud = self._nodeFactory.newEnvironmentCloud(
            cloudName = self.cloudName, cloudAlias = self.getCloudAlias())
        env = self._nodeFactory.newEnvironment()
        env.append(cloud)
        return env

    def getInstanceTypes(self):
        return self._getInstanceTypes()

    def getCloudAlias(self):
        cloudConfig = self.drvGetCloudConfiguration()
        return cloudConfig['alias']

    def drvGetInstances(self, instanceIds):
        instMap  = self.client.xenapi.VM.get_all_records()
        cloudAlias = self.getCloudAlias()
        instanceList = instances.BaseInstances()
        for opaqueId, vm in instMap.items():
            if vm['is_a_template']:
                continue
            inst = self._nodeFactory.newInstance(id = vm['uuid'],
                imageId = 'AAA',
                instanceId = vm['uuid'],
                reservationId = vm['uuid'],
                dnsName = 'AAA',
                publicDnsName = 'AAA',
                privateDnsName = 'AAA',
                state = vm['power_state'],
                launchTime = 1,
                cloudName = self.cloudName,
                cloudAlias = cloudAlias)

            instanceList.append(inst)
        instanceList.sort(key = lambda x: (x.getState(), x.getInstanceId()))
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
        cloudAlias = self.getCloudAlias()
        instMap  = self.client.xenapi.VM.get_all_records()

        imageList = images.BaseImages()
        for opaqueId, vm in instMap.items():
            if not vm['is_a_template']:
                continue

            imageId = vm['uuid']
            image = self._nodeFactory.newImage(id = imageId,
                    imageId = imageId, isDeployed = True,
                    is_rBuilderImage = False,
                    shortName = vm['name_label'],
                    longName = vm['name_description'],
                    cloudName = self.cloudName,
                    cloudAlias = cloudAlias)
            imageList.append(image)
        return imageList

    def _addMintDataToImageList(self, imageList):
        # XXX
        return imageList
        cloudAlias = self.getCloudAlias()

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

    def _getCredentialsForCloudName(self, cloudName):
        cloudConfig = self._getCloudConfiguration(cloudName)
        if not cloudConfig:
            return {}, {}

        store = self._getCredentialsDataStore()
        creds = self._readCredentialsFromStore(store, self.userId, cloudName)
        if not creds:
            return cloudConfig, creds
        # Protect the password
        creds['password'] = util.ProtectedString(creds['password'])
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
