#!/usr/bin/python2.4
#
# Copyright (c) 2008 rPath, Inc.  All Rights Reserved.
#

import operator
import os
import signal
import time
import tempfile

from conary.lib import util, sha1helper

from catalogService import cimupdater
from catalogService import clouds
from catalogService import descriptor
from catalogService import errors
from catalogService import images
from catalogService import instances
from catalogService import storage
from catalogService.rest import baseDriver
from catalogService.rest.mixins import storage_mixin

import viclient

_configurationDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>VMware Configuration</displayName>
    <descriptions>
      <desc>Configure VMware</desc>
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
      <help href='configuration/serverName.html'/>
    </field>
    <field>
      <name>alias</name>
      <descriptions>
        <desc>Cloud Alias</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/alias.html'/>
    </field>
    <field>
      <name>description</name>
      <descriptions>
        <desc>Full Description</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/description.html'/>
    </field>
  </dataFields>
</descriptor>"""

_credentialsDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>VMware User Credentials</displayName>
    <descriptions>
      <desc>User Credentials for VMware</desc>
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

class VMwareImage(images.BaseImage):
    'VMware Image'

def _uuid(s):
    return '-'.join((s[:8], s[8:12], s[12:16], s[16:20], s[20:32]))

def uuidgen():
    hex = sha1helper.md5ToString(sha1helper.md5String(os.urandom(128)))
    return _uuid(hex)

def formatSize(size):
    suffixes = (' bytes', ' KiB', ' MiB', ' GiB')
    div = 1
    for suffix in suffixes:
        if size < (div * 1024):
            return '%d %s' %(size / div, suffix)
        div = div * 1024
    return '%d TiB' %(size / div)

class VMwareClient(baseDriver.BaseDriver, storage_mixin.StorageMixin):
    Image = VMwareImage
    cloudType = 'vmware'

    _credNameMap = [
        ('username', 'username'),
        ('password', 'password'),
    ]

    configurationDescriptorXmlData = _configurationDescriptorXmlData
    credentialsDescriptorXmlData = _credentialsDescriptorXmlData
    # transport is mocked out during testing to simulate talking to
    # an actual server
    VimServiceTransport = None

    def __init__(self, *args, **kwargs):
        baseDriver.BaseDriver.__init__(self, *args, **kwargs)
        self._vicfg = None

    @classmethod
    def isDriverFunctional(cls):
        return True

    def drvCreateCloudClient(self, credentials):
        cloudConfig = self.drvGetCloudConfiguration()
        host = self._getCloudNameFromConfig(cloudConfig)
        try:
            client = viclient.VimService(host,
                                         credentials['username'],
                                         credentials['password'],
                                         transport=self.VimServiceTransport)
        except Exception, e:
            # FIXME: better error
            raise errors.PermissionDenied(message = '')
        # FIXME: refactor this into common code
        keyPrefix = '%s/%s' % (self._sanitizeKey(self.cloudName),
                               self._sanitizeKey(self.userId))
        self._instanceStore = self._getInstanceStore(keyPrefix)
        return client

    def _getVIConfig(self):
        if self._vicfg is None:
            self._vicfg = self.client.getVIConfig()
        return self._vicfg
    vicfg = property(_getVIConfig)

    @classmethod
    def _getCloudNameFromConfig(cls, config):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        return config['name']

    @classmethod
    def _getCloudNameFromDescriptorData(cls, descriptorData):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        return descriptorData.getField('name')

    def _enumerateConfiguredClouds(self):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        if not self.isDriverFunctional():
            return []
        store = self._getConfigurationDataStore()
        ret = []
        for cloudName in sorted(store.enumerate()):
            ret.append(self._getCloudConfiguration(cloudName))
        return ret

    def isValidCloudName(self, cloudName):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        cloudConfig = self._getCloudConfiguration(cloudName)
        return bool(cloudConfig)

    def _createCloudNode(self, cloudConfig):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        cld = self._nodeFactory.newCloud(
            cloudName = cloudConfig['name'],
            description = cloudConfig['description'],
            cloudAlias = cloudConfig['alias'])
        return cld

    def _daemonize(self, *args, **kw):
        self._cloudClient = None
        return baseDriver.BaseDriver._daemonize(self, *args, **kw)

    def drvLaunchInstance(self, descriptorData, requestIPAddress):
        getField = descriptorData.getField
        imageId = os.path.basename(getField('imageId'))
        image = self.getImages([imageId])[0]
        if not image:
            raise errors.HttpNotFound()

        instanceName = getField('instanceName')
        instanceName = instanceName or self._getInstanceNameFromImage(image)
        instanceDescription = getField('instanceDescription')
        instanceDescription = (instanceDescription
                               or self._getInstanceDescriptionFromImage(image)
                               or instanceName)
        dataCenter = getField('dataCenter')
        cr = getField('cr-%s' %dataCenter)
        dataStore = getField('dataStore-%s' %cr)
        rp = getField('resourcePool-%s' %cr)

        instanceId = uuidgen()
        self._instanceStore.setImageId(instanceId, imageId)
        # FIXME - should not be using internal _set method
        self._instanceStore._set(instanceId, 'instanceName', instanceName)
        self._instanceStore.setState(instanceId, 'Creating')

        self._daemonize(self._launchInstance, instanceId, image,
                        dataCenter, cr, dataStore, rp, instanceName,
                        instanceDescription)
        cloudAlias = self.getCloudAlias()
        instanceList = instances.BaseInstances()
        instance = self._nodeFactory.newInstance(
            id=instanceId,
            instanceId=instanceId,
            imageId=imageId,
            instanceName=instanceName,
            instanceDescription=instanceDescription,
            cloudName=self.cloudName,
            cloudAlias=cloudAlias)
        instanceList.append(instance)
        return instanceList

    def drvPopulateLaunchDescriptor(self, descr):
        descr.setDisplayName('VMware Launch Parameters')
        descr.addDescription('VMware Launch Parameters')

        descr.addDataField('instanceName',
                           descriptions = 'Instance Name',
                           type = 'str',
                           required = True,
                           help = [
                               ('launch/instanceName.html', None)
                           ],
                           constraints = dict(constraintName = 'length',
                                              value = 32))

        descr.addDataField('instanceDescription',
                           descriptions = 'Instance Description',
                           type = 'str',
                           help = [
                               ('launch/instanceDescription.html', None)
                           ],
                           constraints = dict(constraintName = 'length',
                                              value = 128))

        vicfg = self.vicfg
        dataCenters = vicfg.getDatacenters()
        descr.addDataField('dataCenter',
                           descriptions = 'Data Center',
                           required = True,
                           help = [
                               ('launch/dataCenter.html', None)
                           ],
                           type = descriptor.EnumeratedType(
            descriptor.ValueWithDescription(x.obj,
                                            descriptions=x.properties['name'])
            for x in dataCenters),
                           default = dataCenters[0].obj,
                           readonly = True
                           )
        crToDc = {}
        for dc in dataCenters:
            crs = dc.getComputeResources()
            for cr in crs:
                crToDc[cr] = dc
            descr.addDataField('cr-%s' %dc.obj,
                               descriptions = 'Compute Resource',
                               required = True,
                               help = [
                                   ('launch/computeResource.html', None)
                               ],
                               type = descriptor.EnumeratedType(
                descriptor.ValueWithDescription(
                x.obj, descriptions=x.properties['name'])
                for x in crs),
                               default = crs[0].obj,
                               conditional = descriptor.Conditional(
                fieldName='dataCenter',
                operator='eq',
                value=dc.obj)
                               )
        for cr in crToDc.keys():
            cfg = cr.configTarget
            dataStores = []

            for ds in cfg.get_element_datastore():
                name = ds.get_element_name()
                dsInfo = ds.get_element_datastore()
                free = dsInfo.get_element_freeSpace()
                dsDesc = '%s - %s free' %(name, formatSize(free))
                dsMor = ds.get_element_datastore().get_element_datastore()
                dataStores.append((dsMor, dsDesc))
            dc = crToDc[cr]
            descr.addDataField('dataStore-%s' %cr.obj,
                               descriptions = 'Data Store',
                               required = True,
                               help = [
                                   ('launch/dataStore.html', None)
                               ],
                               type = descriptor.EnumeratedType(
                descriptor.ValueWithDescription(x[0], descriptions = x[1])
                for x in dataStores),
                               default = dataStores[0][0],
                               conditional = descriptor.Conditional(
                fieldName='cr-%s' %dc.obj,
                operator='eq',
                value=cr.obj)
                               )
            # FIXME: add (descriptor.Conditional(
            #fieldName='dataCenter',
            #    operator='eq',
            #    value=dc.obj),

        for cr in crToDc.keys():
            # sort a list of mor, name tuples based on name
            # and use the first tuple's mor as the default resource pool
            defaultRp = sorted(((x[0], x[1]['name'])
                                for x in cr.resourcePools.iteritems()),
                               key=operator.itemgetter(1))[0][0]
            descr.addDataField('resourcePool-%s' %cr.obj,
                               descriptions = 'Resource Pool',
                               required = True,
                               help = [
                                   ('launch/resourcePool.html', None)
                               ],
                               type = descriptor.EnumeratedType(
                descriptor.ValueWithDescription(str(x[0]),
                                                descriptions=x[1]['name'])
                for x in cr.resourcePools.iteritems()),
                               default = defaultRp,
                               conditional = descriptor.Conditional(
                fieldName='cr-%s' %dc.obj,
                operator='eq',
                value=cr.obj)
                               )

        return descr

    def terminateInstances(self, instanceIds):
        insts = self.getInstances(instanceIds)
        for instanceId in instanceIds:
            self.client.shutdownVM(uuid=instanceId)
        for inst in insts:
            inst.setState('Terminating')
        return insts

    def terminateInstance(self, instanceId):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        return self.terminateInstances([instanceId])

    def updateInstances(self, instanceIds):
        instanceList = instances.BaseInstances()
        for id in instanceIds:
            instanceList.append(self.getInstance(id))

        for instance in instanceList:
            newState = self.updateStatusStateUpdating
            newTime = int(time.time())
            self._setInstanceUpdateStatus(newState, newTime)

        instanceList.sort(key = lambda x: (x.getState(), x.getInstanceId()))
        return instanceList

    def updateInstance(self, instanceId):
        return self.updateInstances([instanceId])

    def _updateInstance(self, instance):
        host = 'https://%s' % instance.publicDnsName.getText()
        updater = cimupdater.CIMUpdater(host)
        updater.checkAndApplyUpdate()

        # Mark the update status as done.
        newState = self.updateStatusStateDone
        newTime = int(time.time())
        self._setInstanceUpdateStatus(newState, newTime)

    def _setInstanceUpdateStatus(self, newState, newTime):
        instance.getUpdateStatus().setState(newState)
        instance.getUpdateStatus().setTime(newTime)
        # Save the update status in the instance store
        self._instanceStore.setUpdateStatusState(instance.getId(), newState)
        self._instanceStore.setUpdateStatusTime(instance.getId(), newTime)
        # Set the expiration to 3 hours for now.
        self._instanceStore.setExpiration(instance.getId(), newTime+10800)
        self._daemonize(self._updateInstance, instance)

    def drvGetImages(self, imageIds):
        # currently we return the templates as available images
        imageList = self._getTemplatesFromInventory()
        imageList = self._addMintDataToImageList(imageList)

        # FIXME: duplicate code
        # now that we've grabbed all the images, we can return only the one
        # we want.  This is horribly inefficient, but neither the mint call
        # nor the grid call allow us to filter by image, at least for now
        if imageIds is None:
            # no filtering required
            return imageList

        # filter the images to those requested
        imagesById = dict((x.getImageId(), x) for x in imageList)
        newImageList = images.BaseImages()
        for imageId in imageIds:
            if imageId not in imagesById:
                continue
            newImageList.append(imagesById[imageId])
        return newImageList

    def getInstanceTypes(self):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        return self._getInstanceTypes()

    def getCloudAlias(self):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        cloudConfig = self.drvGetCloudConfiguration()
        return cloudConfig['alias']

    def _buildInstanceList(self, instMap):
        cloudAlias = self.getCloudAlias()
        instanceList = instances.BaseInstances()
        for mor, vminfo in instMap.iteritems():
            if vminfo.get('config.template', False):
                continue
            if not 'config.uuid' in vminfo:
                continue
            launchTime = None
            if 'runtime.bootTime' in vminfo:
                launchTime = int(time.mktime(vminfo['runtime.bootTime']))
            inst = self._nodeFactory.newInstance(
                id = vminfo['config.uuid'],
                instanceName = vminfo['name'],
                instanceDescription = vminfo['config.annotation'],
                instanceId = vminfo['config.uuid'],
                reservationId = vminfo['config.uuid'],
                dnsName = vminfo.get('guest.ipAddress', None),
                publicDnsName = vminfo.get('guest.ipAddress', None),
                state = vminfo['runtime.powerState'],
                launchTime = launchTime,
                cloudName = self.cloudName,
                cloudAlias = cloudAlias)

            # Check instance store for updating status, and if it's present,
            # set the data on the instance object.
            updateStatusState = self._instanceStore.getUpdateStatusState(inst.getId(), None)
            updateStatusTime = self._instanceStore.getUpdateStatusTime(inst.getId(), None)
            if updateStatusState:
                inst.getUpdateStatus().setState(updateStatusState)
            if updateStatusTime:
                inst.getUpdateStatus().setTime(updateStatusTime)

            instanceList.append(inst)
        instanceList.sort(key = lambda x: (x.getState(), x.getInstanceId()))

        return instanceList

    def drvGetInstance(self, instanceId):
        uuidRef = self.client.findVMByUUID(instanceId)
        instMap = self.client.getVirtualMachines([ 'name',
                                                   'config.annotation',
                                                   'config.template',
                                                   'runtime.powerState',
                                                   'runtime.bootTime',
                                                   'config.uuid',
                                                   'config.extraConfig',
                                                   'guest.ipAddress' ],
                                                  uuidRef)
        
        return self._buildInstanceList(instMap)[0]

    def drvGetInstances(self, instanceIds):
        cloudAlias = self.getCloudAlias()
        instanceList = instances.BaseInstances()

        # FIXME: duplicate code
        storeInstanceKeys = self._instanceStore.enumerate()
        for storeKey in storeInstanceKeys:
            instanceId = os.path.basename(storeKey)
            expiration = self._instanceStore.getExpiration(storeKey)
            if expiration is None or time.time() > float(expiration):
                # This instance exists only in the store, and expired
                self._instanceStore.delete(storeKey)
                continue
            imageId = self._instanceStore.getImageId(storeKey)
            updateData = self._instanceStore.getUpdateStatusState(storeKey)
            imagesL = self.getImages([imageId])

            # If there were no images read from the instance store, but there
            # was update data present, just continue, so that the update data
            # doesn't get deleted from the store.
            if not imagesL and updateData:
                continue
            elif not imagesL:
                # We no longer have this image. Junk the instance
                self._instanceStore.delete(storeKey)
                continue
            image = imagesL[0]

            # FIXME: should not be using internal method
            instanceName = self._instanceStore._get(storeKey, 'instanceName')
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
        # END FIXME
        instMap = self.client.getVirtualMachines([ 'name',
                                                   'config.annotation',
                                                   'config.template',
                                                   'runtime.powerState',
                                                   'runtime.bootTime',
                                                   'config.uuid',
                                                   'config.extraConfig',
                                                   'guest.ipAddress' ])
        return self._buildInstanceList(instMap)

    def _addMintDataToImageList(self, imageList):
        # FIXME: duplicate code
        cloudAlias = self.getCloudAlias()

        mintImages = self._mintClient.getAllBuildsByType('VMWARE_ESX_IMAGE')
        # Convert the list into a map keyed on the sha1 converted into
        # uuid format
        mintImages = dict((_uuid(x['sha1']), x) for x in mintImages)
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
        for uuid, mintImageData in sorted(mintImages.iteritems()):
            image = self._nodeFactory.newImage(id=uuid,
                    imageId=uuid, isDeployed=False,
                    is_rBuilderImage=True,
                    cloudName=self.cloudName,
                    cloudAlias=cloudAlias)
            self._addImageDataFromMintData(image, mintImageData,
                images.buildToNodeFieldMap)
            imageList.append(image)
        return imageList

    def _getTemplatesFromInventory(self):
        """
        returns all templates in the inventory
        """
        cloudAlias = self.getCloudAlias()
        instMap = self.client.getVirtualMachines([ 'name',
                                                   'config.annotation',
                                                   'config.template',
                                                   'runtime.powerState',
                                                   'runtime.bootTime',
                                                   'config.uuid',
                                                   'config.extraConfig',
                                                   'guest.ipAddress' ])
        imageList = images.BaseImages()
        for opaqueId, vminfo in instMap.items():
            if not vminfo.get('config.template', False):
                continue

            imageId = vminfo['config.uuid']
            image = self._nodeFactory.newImage(
                id = imageId,
                imageId = imageId,
                isDeployed = True,
                is_rBuilderImage = False,
                shortName = vminfo['name'],
                productName = vminfo['name'],
                longName = vminfo['config.annotation'],
                cloudName = self.cloudName,
                cloudAlias = cloudAlias)
            imageList.append(image)
        return imageList

    def _cloneTemplate(self, imageId, instanceName, instanceDescription,
                       uuid, dataCenter, computeResource, dataStore,
                       resourcePool, vm=None):
        templateUuid = None
        if not vm:
            templateUuid = os.path.basename(imageId)
        ret = self.client.cloneVM(mor=vm,
                                  uuid=templateUuid,
                                  name=instanceName,
                                  annotation=instanceDescription,
                                  dc=self.vicfg.getMOR(dataCenter),
                                  cr=self.vicfg.getMOR(computeResource),
                                  ds=self.vicfg.getMOR(dataStore),
                                  rp=self.vicfg.getMOR(resourcePool),
                                  newuuid=uuid)
        # FIXME: error handle on ret

    def _findUniqueName(self, inventoryPrefix, startName):
        # make sure that the vm name is not used in the inventory
        testName = startName
        x = 0
        while True:
            ret = self.client.findVMByInventoryPath(inventoryPrefix + testName)
            if not ret:
                # the name is not used in the inventory, stop looking
                break
            x += 1
            # add a suffix to make it unique
            testName = startName + '-%d' %x
        return testName

    def _deployImage(self, instanceId, image, dataCenter, dataStore,
                     computeResource, resourcePool, vmName, uuid):
        downloadUrl = image.getDownloadUrl()

        dc = self.vicfg.getDatacenter(dataCenter)
        dcName = dc.properties['name']

        cr = dc.getComputeResource(computeResource)
        ds = self.vicfg.getMOR(dataStore)
        dsInfo = self.client.getDynamicProperty(ds, 'summary')
        dsName = dsInfo.get_element_name()
        rp = self.vicfg.getMOR(resourcePool)
        props = self.vicfg.getProperties()
        # find a host that can access the datastore
        hosts = [ x for x in cr.properties['host'] if ds in props[x]['datastore'] ]
        if not hosts:
            raise RuntimeError('no host can access the requested datastore')
        host = hosts[0]

        self._setState(instanceId, 'Downloading image')
        tmpDir = tempfile.mkdtemp(prefix="vmware-download-")
        try:
            path = self._downloadImage(image, tmpDir)
        except errors.CatalogError, e:
            self._setState(instanceId, 'Error')
            raise

        vmFolder = self.vicfg.getName(dc.properties['vmFolder'])
        inventoryPrefix = '/%s/%s/' %(dcName, vmFolder)
        vmName = self._findUniqueName(inventoryPrefix, vmName)
        # FIXME: make sure that there isn't something in the way on
        # the data store

        self._setState(instanceId, 'Extracting image')
        try:
            workdir = self.extractImage(path)
            self._setState(instanceId, 'Uploading image to VMware')
            vmFiles = os.path.join(workdir, image.getBaseFileName())
            vmx = viclient.vmutils.uploadVMFiles(self.client,
                                                 vmFiles,
                                                 vmName,
                                                 dataCenter=dcName,
                                                 dataStore=dsName)
            try:
                vm = self.client.registerVM(dc.properties['vmFolder'], vmx,
                                            vmName, asTemplate=False,
                                            host=host, pool=rp)
                self.client.reconfigVM(vm, {'uuid': uuid})
            except viclient.Error, e:
                raise RuntimeError('An error occurred when registering the '
                                   'VM: %s' %str(e))
            return vm
        finally:
            # clean up our mess
            util.rmtree(tmpDir, ignore_errors=True)

    def _launchInstance(self, instanceId, image, dataCenter,
                        computeResource, dataStore, resourcePool,
                        instanceName, instanceDescription):
        vm = None
        self._instanceStore.setPid(instanceId)
        try:
            useTemplate = not self.client.isESX()
            if not image.getIsDeployed():
                if useTemplate:
                    # if we can use a template, deploy the image
                    # as a template with the imageId as the uuid
                    vmName = 'template-' + image.getBaseFileName()
                    uuid = image.getImageId()
                else:
                    # otherwise, we'll use the instance name and instace
                    # uuid for deployment
                    vmName = instanceName
                    uuid = instanceId
                vm = self._deployImage(instanceId, image, dataCenter,
                                       dataStore, computeResource,
                                       resourcePool, vmName, uuid)
                if useTemplate:
                    self.client.markAsTemplate(vm=vm)

            if useTemplate:
                # mark the VM as a template, clone, and launch it
                self._setState(instanceId, 'Cloning template')
                self._cloneTemplate(image.getImageId(), instanceName,
                                    instanceDescription, instanceId,
                                    dataCenter, computeResource,
                                    dataStore, resourcePool, vm=vm)
            else:
                self.client.startVM(uuid=instanceId)
            self._setState(instanceId, 'Launching')
        finally:
            self._instanceStore.deletePid(instanceId)

