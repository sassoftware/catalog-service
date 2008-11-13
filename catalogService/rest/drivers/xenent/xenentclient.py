
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

XenAPI = None
xenprov = None
try:
    import XenAPI as XenAPI
    from XenAPI import provision as xenprov
except ImportError:
    pass

from catalogService.rest.drivers.xenent import xmlNodes

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
      <password>true</password>
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

    XenSessionClass = None

    def __init__(self, *args, **kwargs):
        baseDriver.BaseDriver.__init__(self, *args, **kwargs)
        self._instanceStore = None

    @classmethod
    def isDriverFunctional(cls):
        if not XenAPI or not xenprov:
            return False
        return True

    def drvCreateCloudClient(self, credentials):
        cloudConfig = self.drvGetCloudConfiguration()
        if self.XenSessionClass:
            klass = self.XenSessionClass
        else:
            klass = XenAPI.Session
        sess = klass("https://%s" % self._getCloudNameFromConfig(cloudConfig))
        try:
            # password is a ProtectedString, we have to convert to string
            sess.login_with_password(credentials['username'],
                                     str(credentials['password']))
        except XenAPI.Failure, e:
            raise AuthenticationFailure(e.details[1], e.details[2])
        keyPrefix = "%s/%s" % (self._sanitizeKey(self.cloudName),
                               self._sanitizeKey(self.userId))
        self._instanceStore = self._getInstanceStore(keyPrefix)
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

    def drvLaunchInstance(self, descriptorData, requestIPAddress):
        client = self.client
        getField = descriptorData.getField

        imageId = os.path.basename(getField('imageId'))

        image = self.getImages([imageId])[0]
        if not image:
            raise errors.HttpNotFound()

        instanceName = self._getInstanceNameFromImage(image)
        instanceDescription = self._getInstanceDescriptionFromImage(image) \
            or instanceName

        instanceId = self._instanceStore.newKey(imageId = imageId)

        self._daemonize(self._launchInstance,
                        instanceId, image,
                        instanceType=getField('instanceType'))
        cloudAlias = self.getCloudAlias()
        instanceList = instances.BaseInstances()
        instance = self._nodeFactory.newInstance(id=instanceId,
                                        instanceId=instanceId,
                                        imageId=imageId,
                                        instanceName=instanceName,
                                        instanceDescription=instanceDescription,
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
        descr.addDataField("instanceType", required = True,
            descriptions = "Instance Size",
            type = descriptor.EnumeratedType(
                descriptor.ValueWithDescription(x,
                    descriptions = y)
                  for (x, y) in XenEnt_InstanceTypes.idMap)
            )
        descr.addDataField("minCount", required = True,
            descriptions = "Minimum Number of Instances",
            type = "int",
            constraints = dict(constraintName = 'range',
                               min = 1, max = 100))
        descr.addDataField("maxCount", required = True,
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

        storeInstanceKeys = self._instanceStore.enumerate()
        for storeKey in storeInstanceKeys:
            instanceId = os.path.basename(storeKey)
            expiration = self._instanceStore.getExpiration(storeKey)
            if expiration is None or time.time() > float(expiration):
                # This instance exists only in the store, and expired
                self._instanceStore.delete(storeKey)
                continue
            imageId = self._instanceStore.getImageId(storeKey)
            imagesL = self.getImages([imageId])
            if not imagesL:
                # We no longer have this image. Junk the instance
                self._instanceStore.delete(storeKey)
                continue
            image = imagesL[0]

            instanceName = self._getInstanceNameFromImage(image)
            instanceDescription = self._getInstanceDescriptionFromImage(image) \
                or instanceName

            inst = self._nodeFactory.newInstance(id = instanceId,
                imageId = imageId,
                instanceId = instanceId,
                instanceName = instanceName,
                instanceDescription = instanceDescription,
                dnsName = 'UNKNOWN',
                publicDnsName = 'UNKNOWN',
                privateDnsName = 'UNKNOWN',
                state = self._instanceStore.getState(storeKey),
                launchTime = 1,
                cloudName = self.cloudName,
                cloudAlias = cloudAlias)

            instanceList.append(inst)

        for opaqueId, vm in instMap.items():
            if vm['is_a_template']:
                continue

            instanceId = vm['uuid']
            imageId = vm['other_config'].get('catalog-client-checksum')
            inst = self._nodeFactory.newInstance(id = instanceId,
                imageId = imageId or 'UNKNOWN',
                instanceId = instanceId,
                instanceName = vm['name_label'],
                instanceDescription = vm['name_description'],
                reservationId = vm['uuid'],
                dnsName = 'UNKNOWN',
                publicDnsName = 'UNKNOWN',
                privateDnsName = 'UNKNOWN',
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

    def _launchInstance(self, instanceId, image, instanceType):
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
                callback = callback)

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

        for vmRef, vm in instMap.items():
            if not vm['is_a_template']:
                continue

            imgChecksum = vm['other_config'].get('cloud-catalog-checksum')
            if imgChecksum:
                is_rBuilderImage = True
                imageId = imgChecksum
            else:
                is_rBuilderImage = False
                imageId = vm['uuid']

            image = self._nodeFactory.newImage(id = imageId,
                    imageId = imageId, isDeployed = True,
                    is_rBuilderImage = is_rBuilderImage,
                    longName = vm['name_label'],
                    buildDescription = vm['name_description'],
                    cloudName = self.cloudName,
                    cloudAlias = cloudAlias)
            imageList.append(image)
        return imageList

    def _addMintDataToImageList(self, imageList):
        cloudAlias = self.getCloudAlias()

        mintImages = self._mintClient.getAllBuildsByType('XEN_OVA')
        # Convert the list into a map keyed on the sha1
        mintImages = dict((x['sha1'], x) for x in mintImages)

        for image in imageList:
            imageId = image.getImageId()
            mintImageData = mintImages.pop(imageId, {})
            image.setIs_rBuilderImage(bool(mintImageData))
            image.setIsDeployed(True)
            if not mintImageData:
                continue
            self._addImageDataFromMintData(image, mintImageData,
                images.buildToNodeFieldMap)

        # Add the rest of the images coming from mint
        for imgChecksum, mintImageData in sorted(mintImages.iteritems()):
            image = self._nodeFactory.newImage(id = imgChecksum,
                    imageId = imgChecksum, isDeployed = False,
                    is_rBuilderImage = True,
                    cloudName = self.cloudName,
                    cloudAlias = cloudAlias)
            self._addImageDataFromMintData(image, mintImageData,
                images.buildToNodeFieldMap)
            imageList.append(image)
        return imageList

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

    def getRestClient(self):
        creds = self.credentials
        username, password = creds['username'], creds['password']
        cli = restClient.Client('http://%s:%s@%s' %
            (username, password, self.cloudName))
        cli.connect()
        return cli

    def createVirtualMachine(self, cli, checksum, name, description):
        cli.path = '/virtual-machines'

        resp = cli.request("POST",
            "<vm><label>%s</label><description>%s</description></vm>" %
            (name, description))

        respData = resp.read()
        uuid = self._extractUuid(respData)
        vmRef = self.client.xenapi.VM.get_by_uuid(uuid)

        # Mark it as a template
        self.client.xenapi.VM.set_is_a_template(vmRef, True)
        # Set state so we can filter out these images, they are not useful yet
        self._setVmState(vmRef, 'Downloading')
        self._setVmMetadata(vmRef, checksum = checksum)
        return uuid

    def downloadImage(self, cli, rbuilderUrl):
        cli.path = '/images'
        resp = cli.request("POST",
            "<image><rbuilderUrl>%s</rbuilderUrl></image>" % rbuilderUrl)

        respData = resp.read()
        return self._extractImage(respData)

    def importVirtualMachine(self, cli, imageId, srUuid):
        cli.path = '/virtual-machines-imported'
        resp = cli.request("POST", "<vm><image>%s</image><sr>%s</sr></vm>" %
            (imageId, srUuid))

        respData = resp.read()
        return self._extractUuid(respData)

    def setVDIMetadata(self, vbdRecs, label, description, metadata):
        for vbd in vbdRecs:
            vdiRef = vbd['VDI']
            if vdiRef == 'OpaqueRef:NULL':
                continue
            self.client.xenapi.VDI.set_other_config(vdiRef, metadata)
            self.client.xenapi.VDI.set_name_label(vdiRef, label)
            self.client.xenapi.VDI.set_name_description(vdiRef, description)


    def cloneDisk(self, templateVbd, vmRef, otherConfig = None):
        fields = [ 'bootable', 'device', 'empty', 'mode',
            'qos_algorithm_params', 'qos_algorithm_type', 'type',
            'userdevice', 'VDI', 'other_config']
        vbdRec = dict((x, templateVbd[x]) for x in fields)
        # Point it to the right VM
        vbdRec['VM'] = vmRef
        if otherConfig:
            vbdRec['other_config'].update(otherConfig)
        vbdRef = self.client.xenapi.VBD.create(vbdRec)
        return vbdRef

    def getVBDs(self, vmRec):
        ret = []
        for vbdRef in vmRec['VBDs']:
            ret.append(self.client.xenapi.VBD.get_record(vbdRef))
        return ret

    def _setVmState(self, vmRef, state):
        self.client.xenapi.VM.add_to_other_config(vmRef,
            'cloud-catalog-state', state)

    def _setVmMetadata(self, vmRef, checksum = None):
        self.client.xenapi.VM.add_to_other_config(vmRef,
            'cloud-catalog-checksum', checksum)

    def _deleteVirtualMachine(self, vmRef):
        # Get rid of the imported vm
        self.client.xenapi.VM.destroy(vmRef)

    @classmethod
    def _extractUuid(cls, dataString):
        hndlr = xmlNodes.UuidHandler()
        node = hndlr.parseString(dataString)
        return node.getText()

    @classmethod
    def _extractImage(cls, dataString):
        hndlr = xmlNodes.ImageHandler()
        node = hndlr.parseString(dataString)
        return node.getText()

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
