
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
from catalogService import restClient
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

        instanceName = getField('instanceName')
        instanceDescription = getField('instanceDescription')

        instanceName = instanceName or self._getInstanceNameFromImage(image)
        instanceDescription = instanceDescription or \
            self._getInstanceDescriptionFromImage(image) or instanceName

        instanceId = self._instanceStore.newKey(imageId = imageId)

        self._daemonize(self._launchInstance,
                        instanceId, image,
                        instanceType = getField('instanceType'),
                        srUuid = getField('srUuid'),
                        instanceName = instanceName,
                        instanceDescription = instanceDescription)
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
        storageRepos = self._getStorageRepos()
        descr.addDataField("storageRepository",
            descriptions = "Storage Repository",
            required = True,
            type = descriptor.EnumeratedType(
                descriptor.ValueWithDescription(x[0], descriptions = x[1][0])
                for x in storageRepos),
            default = storageRepos[0][0],
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

    def _launchInstance(self, instanceId, image, instanceType, srUuid,
            instanceName, instanceDescription):
        cli = self.getRestClient()
        nameLabel = image.getLongName()
        nameDescription = image.getBuildDescription()
        try:
            self._instanceStore.setPid(instanceId)
            if not image.getIsDeployed():
                downloadUrl = image.getDownloadUrl()
                checksum = image.getImageId()
                self._setState(instanceId, 'Creating template')
                vmRef, uuid = self.createVirtualMachineTemplate(cli, checksum,
                    nameLabel, nameDescription)

                self._setState(instanceId, 'Downloading image')
                imageHandle = self.downloadImage(cli, downloadUrl)
                self._setState(instanceId, 'Importing image')
                templRef = self.importVirtualMachineTemplate(cli, imageHandle,
                    srUuid)
                # These calls should be fast, no reason to update the state
                # for them
                templRec = self.client.xenapi.VM.get_record(templRef)
                # Copy some of the params from the imported template into the
                # one we just created
                self.copyVmParams(templRec, vmRef)
                vbdRecs = self.getVBDs(templRec)
                self.setVDIMetadata(vbdRecs, nameLabel, nameDescription,
                    metadata = {'cloud-catalog-checksum' : checksum})

                self._setState(instanceId, 'Publishing image')
                for vbdRec in vbdRecs:
                    self.cloneDisk(vbdRec, vmRef)
                self._deleteVirtualMachine(templRef)
                image.setImageId(uuid)

            imageId = image.getImageId()

            self._setState(instanceId, 'Launching')
            realId = self.cloneTemplate(imageId, instanceName,
                instanceDescription)
            self.startVm(realId)

        finally:
            self._instanceStore.deletePid(instanceId)

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
        cli = RestClient('http://%s:%s@%s' %
            (username, password, self.cloudName))
        cli.connect()
        return cli

    def createVirtualMachineTemplate(self, cli, checksum, name, description):
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
        return vmRef, uuid

    def downloadImage(self, cli, rbuilderUrl):
        cli.path = '/images'
        resp = cli.request("POST",
            "<image><rbuilderUrl>%s</rbuilderUrl></image>" % rbuilderUrl)

        respData = resp.read()
        return self._extractImage(respData)

    def importVirtualMachineTemplate(self, cli, imageId, srUuid):
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


    def copyVmParams(self, srcVmRec, vmRef):
        params = ['PV_bootloader', 'PV_kernel', 'PV_ramdisk', 'PV_args',
            'PV_bootloader_args', 'PV_legacy_args',
            'HVM_boot_policy', 'HVM_boot_params']
        for param in params:
            method = getattr(self.client.xenapi.VM, "set_" + param)
            method(vmRef, srcVmRec[param])

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

    def cloneTemplate(self, imageId, instanceName, instanceDescription):
        vmTemplateRef = self.client.xenapi.VM.get_by_uuid(imageId)
        imageId = os.path.basename(imageId)

        vmRef = self.client.xenapi.VM.clone(vmTemplateRef,
            instanceName)
        self.client.xenapi.VM.set_name_description(vmRef, instanceDescription)
        self._setVmMetadata(vmRef, templateUuid = imageId)

        # Get all physical interfaces
        pifs = self.client.xenapi.PIF.get_all_records()
        # Grab the lowest device (eth0)
        lowest = min((v['device'], k) for k, v in pifs.items())[1]

        networkRef = self.client.xenapi.PIF.get_network(lowest)

        self.addVIFtoVM(vmRef, networkRef)

    def startVm(self, vmRef):
        startPaused = False
        force = False
        self.client.xenapi.VM.start(vmRef, startPaused, force)

    def addVIFtoVM(self, vmRef, networkRef):
        vifRec = {
            'device' : '0',
            'network' : networkRef,
            'VM' : vmRef,
            'MAC' : '',
            'MTU' : '1500',
            'qos_algorithm_type' : '',
            'qos_algorithm_params' : {},
            'other_config' : {},
        }
        self.client.xenapi.VIF.create(vifRec)

    def _setVmState(self, vmRef, state):
        self.client.xenapi.VM.add_to_other_config(vmRef,
            'cloud-catalog-state', state)

    def _setVmMetadata(self, vmRef, checksum = None,
            templateUuid = None):
        if checksum:
            self.client.xenapi.VM.add_to_other_config(vmRef,
                'cloud-catalog-checksum', checksum)
        if templateUuid:
            self.client.xenapi.VM.add_to_other_config(vmRef,
                'cloud-catalog-template-uuid', templateUuid)

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

    def _getStorageRepos(self):
        # Get all pools
        pools = self.client.xenapi.pool.get_all_records()
        srList = [ x['default_SR'] for x in pools.values() ]
        # Validate the sr list
        uuidsFound = dict()
        ret = []
        for srRef in srList:
            try:
                uuid = self.client.xenapi.SR.get_uuid(srRef)
                if uuid in uuidsFound:
                    continue
                ret.append(uuid)
                uuidsFound[uuid] = None
            except XenAPI.Failure, e:
                if e.details[0] != 'HANDLE_INVALID':
                    raise

        srRecs = self.client.xenapi.SR.get_all_records()
        for k, srRec in sorted(srRecs.items(), key = lambda x: x[1]['uuid']):
            uuid = srRec['uuid']
            if 'vdi_create' not in srRec['allowed_operations']:
                continue
            if uuid not in uuidsFound:
                ret.append(uuid)
            uuidsFound[uuid] = (
                "%s (%s)" % (srRec['name_label'], srRec['type']),
                srRec['name_description'])
        return [ (x, uuidsFound[x]) for x in ret if uuidsFound[x] ]

class RestClient(restClient.Client):
    pass

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
