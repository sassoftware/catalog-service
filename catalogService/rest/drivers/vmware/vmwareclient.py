#!/usr/bin/python2.4
#
# Copyright (c) 2008 rPath, Inc.  All Rights Reserved.
#

import operator
import os
import signal
import time
import tempfile
import StringIO

from conary.lib import util

from catalogService import clouds
from catalogService import descriptor
from catalogService import errors
from catalogService import images
from catalogService import instances
from catalogService import storage
from catalogService.rest import baseDriver
from catalogService.rest.mixins import storage_mixin


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

def formatSize(size):
    suffixes = (' bytes', ' KiB', ' MiB', ' GiB')
    div = 1
    for suffix in suffixes:
        if size < (div * 1024):
            return '%d %s' %(size / div, suffix)
        div = div * 1024
    return '%d TiB' %(size / div)

class InstanceStorage(storage.DiskStorage):
    """
    VMware instance ids should look like a UUID
    """
    @classmethod
    def _generateString(cls, length):
        return baseDriver.BaseDriver.uuidgen()

class VMwareClient(storage_mixin.StorageMixin, baseDriver.BaseDriver):
    Image = VMwareImage
    cloudType = 'vmware'
    instanceStorageClass = InstanceStorage

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
        self._instanceStore = None
        self._virtualMachines = None

    @classmethod
    def isDriverFunctional(cls):
        return True

    def drvCreateCloudClient(self, credentials):
        cloudConfig = self.drvGetCloudConfiguration()
        host = self._getCloudNameFromConfig(cloudConfig)
        # This import is expensive!!! Delay it until it is actually needed
        import viclient
        debug = False
        #debug = True
        try:
            client = viclient.VimService(host,
                                         credentials['username'],
                                         credentials['password'],
                                         transport=self.VimServiceTransport,
                                         debug = debug)
        except Exception, e:
            # FIXME: better error
            raise errors.PermissionDenied(message = '')
        return client

    def _getVIConfig(self):
        if self._vicfg is None:
            self._vicfg = self.client.getVIConfig()
        return self._vicfg
    vicfg = property(_getVIConfig)

    def getLaunchInstanceParameters(self, image, descriptorData):
        params = baseDriver.BaseDriver.getLaunchInstanceParameters(self,
            image, descriptorData)
        getField = descriptorData.getField
        dataCenter = getField('dataCenter')
        cr = getField('cr-%s' % dataCenter)
        rp = getField('resourcePool-%s' % cr)
        network = getField('network-%s' % dataCenter)
        params.update(dict(
            dataCenter = dataCenter,
            dataStore = getField('dataStore-%s' % cr),
            computeResource = cr,
            resourcePool = rp,
            network = network,
        ))
        return params

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
        networkToDc = {}
        for dc in dataCenters:
            crs = dc.getComputeResources()
            for cr in crs:
                crToDc[cr] = dc
            for network in dc.properties['network']:
                networkToDc.setdefault(network, []).append(dc)
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
                value=dc.obj))
        for cr, dc in crToDc.items():
            cfg = cr.configTarget
            if cfg is None:
                continue
            # We may have references to invalid networks, skip those
            networks = dc.properties['network']
            networks = [ vicfg.getNetwork(x) for x in networks ]
            networks = [ x for x in networks if x is not None ]
            descr.addDataField('network-%s' % dc.obj,
                descriptions = 'Network',
                required = True,
                    help = [
                        ('launch/network.html', None)
                    ],
                    type = descriptor.EnumeratedType(
                        descriptor.ValueWithDescription(x.mor,
                            descriptions=x.name) for x in networks),
                    default = networks[0].mor,
                    conditional = descriptor.Conditional(
                        fieldName='dataCenter',
                        operator='eq',
                        value=dc.obj))

        for cr, dc in crToDc.items():
            cfg = cr.configTarget
            if cfg is None:
                continue
            dataStores = []

            for ds in cfg.get_element_datastore():
                name = ds.get_element_name()
                dsInfo = ds.get_element_datastore()
                free = dsInfo.get_element_freeSpace()
                dsDesc = '%s - %s free' %(name, formatSize(free))
                dsMor = ds.get_element_datastore().get_element_datastore()
                dataStores.append((dsMor, dsDesc))
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

    def _getMintImagesByType(self, imageType):
        # start with the most general build type
        imageType = 'VMWARE_ESX_IMAGE'
        mintImages = self._mintClient.getAllBuildsByType(imageType)
        if self.client.vmwareVersion < (4, 0, 0):
            # We don't support OVF deployments, so don't even bother
            return mintImages
        # Prefer ovf 0.9 over plain esx
        mintImagesByBuildId = {}
        for mintImage in mintImages:
            for fdict in mintImage['files']:
                # This is a rather lame way to detect ovf builds
                if fdict.get('filename', '').endswith('ovf.tar.gz'):
                    mintImage['sha1'] = fdict['sha1']
                    mintImage['downloadUrl'] = fdict['downloadUrl']
                    break
            mintImagesByBuildId[mintImage['buildId']] = mintImage
        # Finally, prefer OVF 1.0 images
        imageType = 'VMWARE_OVF_IMAGE'
        for mintImage in self._mintClient.getAllBuildsByType(imageType):
            mintImagesByBuildId[mintImage['buildId']] = mintImage
        # Sort data by build id
        return [ x[1] for x in sorted(mintImagesByBuildId.items()) ]

    def drvGetImages(self, imageIds):
        # currently we return the templates as available images
        imageList = self._getTemplatesFromInventory(imageIds)
        # The image format does not matter here, we're overriding
        # _getMintImagesByType from parent class
        imageFormat = 'VMWARE_ESX_IMAGE'
        imageList = self.addMintDataToImageList(imageList, imageFormat)

        # FIXME: duplicate code
        # now that we've grabbed all the images, we can return only the one
        # we want.  This is horribly inefficient, but neither the mint call
        # nor the grid call allow us to filter by image, at least for now
        if imageIds is None:
            # no filtering required
            newImageList = images.BaseImages()
            newImageList.extend(imageList)
            return newImageList

        # filter the images to those requested
        imagesById = dict((x.getImageId(), x) for x in imageList)
        newImageList = images.BaseImages()
        for imageId in imageIds:
            if imageId not in imagesById:
                continue
            newImageList.append(imagesById[imageId])
        return newImageList

    def getCloudAlias(self):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        cloudConfig = self.drvGetCloudConfiguration()
        return cloudConfig['alias']

    def _buildInstanceList(self, instanceList, instMap):
        instIdSet = set()
        newInstanceList = []
        cloudAlias = self.getCloudAlias()
        for mor, vminfo in instMap.iteritems():
            if vminfo.get('config.template', False):
                continue
            if not 'config.uuid' in vminfo:
                continue
            launchTime = None
            if 'runtime.bootTime' in vminfo:
                launchTime = self.utctime(vminfo['runtime.bootTime'])
            instanceId = vminfo['config.uuid']
            longName = vminfo.get('config.annotation', '').decode('utf-8', 'replace')
            inst = self._nodeFactory.newInstance(
                id = instanceId,
                instanceName = vminfo['name'],
                instanceDescription = longName,
                instanceId = instanceId,
                reservationId = instanceId,
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

            instIdSet.add(instanceId)
            newInstanceList.append(inst)
        # Add back the original instances, unless we have them already
        for inst in instanceList:
            instanceId = inst.getInstanceId()
            if instanceId in instIdSet:
                continue
            instIdSet.add(instanceId)
            newInstanceList.append(inst)

        del instanceList[:]
        instanceList.extend(newInstanceList)
        instanceList.sort(key = lambda x: (x.getState(), x.getInstanceId()))

        return instanceList

    def drvGetInstance(self, instanceId):
        uuidRef = self.client.findVMByUUID(instanceId)
        if not uuidRef:
            raise errors.HttpNotFound()

        instMap = self._getVirtualMachines(root = uuidRef)
        instanceList = instances.BaseInstances()

        ret = self._buildInstanceList(instanceList, instMap)
        if ret:
            return ret[0]
        raise errors.HttpNotFound()

    def drvGetInstances(self, instanceIds):
        cloudAlias = self.getCloudAlias()
        instanceList = instances.BaseInstances()
        instMap = self.getVirtualMachines()
        return self.filterInstances(instanceIds,
            self._buildInstanceList(instanceList, instMap))

    def getVirtualMachines(self):
        if self._virtualMachines is not None:
            # NOTE: we cache this, but only per catalog-service request.
            # Each request generates a new Client instance.
            return self._virtualMachines

        instMap = self._getVirtualMachines()
        self._virtualMachines = instMap
        return instMap

    def _getVirtualMachines(self, root = None):
        instMap = self.client.getVirtualMachines([ 'name',
                                                   'config.annotation',
                                                   'config.template',
                                                   'runtime.powerState',
                                                   'runtime.bootTime',
                                                   'config.uuid',
                                  # NOTE: grabbing extra
                                  # config multiplies the
                                  # size of the XML being
                                  # returned by 5 and should
                                  # not be done without
                                  # some sort of delayed parsing scheme.
                                                   #'config.extraConfig',
                                                   'guest.ipAddress' ],
                                                   root = root)
        return instMap

    @classmethod
    def getImageIdFromMintImage(cls, image):
        return cls._uuid(image.get('sha1'))

    def _getTemplatesFromInventory(self, imageIds = None):
        """
        returns all templates in the inventory
        """
        useTemplate = not self.client.isESX()
        if not useTemplate:
            # ESX does not support templates, so don't bother to search
            # for them
            return []
        cloudAlias = self.getCloudAlias()
        instMap = self.getVirtualMachines()
        imageList = images.BaseImages()
        for opaqueId, vminfo in instMap.items():
            if not vminfo.get('config.template', False):
                continue

            imageId = vminfo['config.uuid']
            templateId = self._extractRbaUUID(vminfo.get('config.annotation'))
            if imageIds is not None and not (
                    imageId in imageIds or templateId in imageIds):
                continue
            if templateId:
                longName = vminfo['name']
                imageId = templateId
            else:
                longName = vminfo.get('config.annotation', '').decode('utf-8', 'replace')

            image = self._nodeFactory.newImage(
                id = imageId,
                imageId = imageId,
                isDeployed = True,
                is_rBuilderImage = False,
                shortName = vminfo['name'],
                productName = vminfo['name'],
                longName = longName,
                cloudName = self.cloudName,
                cloudAlias = cloudAlias)
            # This is a bit nasty, but we need the opaque ID later when
            # launching, so we clone the proper image (instead of the one with
            # the image ID possibly coming from the rbuilder)
            image.opaqueId = opaqueId
            imageList.append(image)
        return imageList

    def _extractRbaUUID(self, annotation):
        # Extract the rbuilder uuid from the annotation field
        if not annotation:
            return None
        sio = StringIO.StringIO(annotation)
        for r in sio:
            arr = r.strip().split(':', 1)
            if len(arr) != 2:
                continue
            if arr[0].strip().lower() == 'rba-uuid':
                return arr[1].strip().lower()
        return None

    def _cloneTemplate(self, job, imageId, instanceName, instanceDescription,
                       dataCenter, computeResource, dataStore,
                       resourcePool, vm=None):
        templateUuid = None
        if not vm:
            templateUuid = os.path.basename(imageId)
        try:
            vmMor = self.client.cloneVM(mor=vm,
                                        uuid=templateUuid,
                                        name=instanceName,
                                        annotation=instanceDescription,
                                        dc=self.vicfg.getMOR(dataCenter),
                                        cr=self.vicfg.getMOR(computeResource),
                                        ds=self.vicfg.getMOR(dataStore),
                                        rp=self.vicfg.getMOR(resourcePool))
            return vmMor
        except Exception, e:
            self.log_exception("Exception cloning template: %s" % e)
            raise

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

    def _deployOvf(self, job, vmName, uuid, vmFilesPath, dataCenter,
                     dataStore, host, resourcePool, network,
                     asTemplate = False):
        dataCenterName = dataCenter.properties['name']
        # Grab ovf file
        ovfFiles = [ x for x in os.listdir(vmFilesPath) if x.endswith('.ovf') ]
        if not ovfFiles:
            raise RuntimeError("No ovf file found")
        if len(ovfFiles) != 1:
            raise RuntimeError("More than one .ovf file found in %s" %
                vmFilesPath)
        ovfFilePath = os.path.join(vmFilesPath, ovfFiles[0])
        vmFolder = dataCenter.properties['vmFolder']
        fileItems, httpNfcLease = self.client.ovfImportStart(ovfFilePath,
            vmName = vmName, vmFolder = vmFolder, resourcePool = resourcePool,
            dataStore = dataStore, network = network)
        self.client.waitForLeaseReady(httpNfcLease)
        import viclient
        progressUpdate = viclient.client.ProgressUpdate(self.client, httpNfcLease)
        vmMor = self.client.ovfUpload(httpNfcLease, vmFilesPath, fileItems,
            progressUpdate)
        return vmMor

    def _deployByVmx(self, job, vmName, uuid, vmFiles, dataCenter,
                     dataStoreName, host, resourcePool, network,
                     asTemplate = False):
        dataCenterName = dataCenter.properties['name']
        import viclient
        vmx = viclient.vmutils.uploadVMFiles(self.client,
                                             vmFiles,
                                             vmName,
                                             dataCenter=dataCenterName,
                                             dataStore=dataStoreName)
        try:
            vm = self.client.registerVM(dataCenter.properties['vmFolder'], vmx,
                                        vmName, asTemplate=False,
                                        host=host, pool=resourcePool)
            return vm
        except viclient.Error, e:
            self.log_exception("Exception registering VM: %s", e)
            raise RuntimeError('An error occurred when registering the '
                               'VM: %s' %str(e))

    def _deployImage(self, job, image, auth, dataCenter, dataStore,
                     computeResource, resourcePool, vmName, uuid,
                     network, asTemplate=False):

        dc = self.vicfg.getDatacenter(dataCenter)
        dcName = dc.properties['name']

        cr = dc.getComputeResource(computeResource)
        ds = self.vicfg.getMOR(dataStore)
        dsInfo = self.client.getDynamicProperty(ds, 'summary')
        dsName = dsInfo.get_element_name()
        rp = self.vicfg.getMOR(resourcePool)
        network = self.vicfg.getMOR(network)
        props = self.vicfg.getProperties()
        # find a host that can access the datastore
        hosts = [ x for x in cr.properties['host'] if ds in props[x]['datastore'] ]
        if not hosts:
            raise RuntimeError('no host can access the requested datastore')
        host = hosts[0]

        job.addLog(self.LogEntry('Downloading image'))
        tmpDir = tempfile.mkdtemp(prefix="vmware-download-")
        try:
            path = self._downloadImage(image, tmpDir, auth = auth)
        except errors.CatalogError, e:
            util.rmtree(tmpDir, ignore_errors=True)
            raise

        vmFolder = self.vicfg.getName(dc.properties['vmFolder'])
        inventoryPrefix = '/%s/%s/' %(dcName, vmFolder)
        vmName = self._findUniqueName(inventoryPrefix, vmName)
        # FIXME: make sure that there isn't something in the way on
        # the data store

        job.addLog(self.LogEntry('Extracting image'))
        try:
            workdir = self.extractImage(path)
            job.addLog(self.LogEntry('Uploading image to VMware'))
            vmFiles = os.path.join(workdir, image.getBaseFileName())
            # This import is expensive!!! Delay it until it is actually needed
            import viclient
            if self.client.vmwareVersion >= (4, 0, 0):
                vmMor = self._deployOvf(job, vmName, uuid,
                    vmFiles, dc, dataStore=ds,
                    host = host, resourcePool=rp, network = network,
                    asTemplate = asTemplate)
            else:
                vmMor = self._deployByVmx(job, vmName, uuid,
                    vmFiles, dc, dataStoreName=dsName,
                    host = host, resourcePool=rp, network = network,
                    asTemplate = asTemplate)

            nwobj = self.client.getMoRefProp(vmMor, 'network')
            reconfigVmParams = dict()
            if not nwobj.get_element_ManagedObjectReference():
                # add NIC
                nicSpec = self.client.createNicConfigSpec(network, self._vicfg)
                deviceChange = [ nicSpec ]
                reconfigVmParams['deviceChange'] = deviceChange

            if asTemplate:
                # Reconfiguring the uuid is unreliable, we're using the
                # annotation field for now
                reconfigVmParams['annotation'] = "rba-uuid: %s" % uuid

            if reconfigVmParams:
                self.client.reconfigVM(vmMor, reconfigVmParams)

            if asTemplate:
                self.client.markAsTemplate(vm=vmMor)
            return vmMor
        finally:
            # clean up our mess
            util.rmtree(tmpDir, ignore_errors=True)

    def launchInstanceProcess(self, job, image, auth, **launchParams):
        ppop = launchParams.pop
        imageId = ppop('imageId')
        dataCenter = ppop('dataCenter')
        computeResource = ppop('computeResource')
        dataStore = ppop('dataStore')
        resourcePool= ppop('resourcePool')
        instanceName = ppop('instanceName')
        instanceDescription = ppop('instanceDescription')
        network = ppop('network')

        vm = None

        instanceId = self.instanceStorageClass._generateString(32)
        useTemplate = not self.client.isESX()
        if not image.getIsDeployed():
            if useTemplate:
                # if we can use a template, deploy the image
                # as a template with the imageId as the uuid
                vmName = 'template-' + image.getBaseFileName()
                uuid = image.getImageId()
            else:
                # otherwise, we'll use the instance name and
                # a random instance uuid for deployment
                vmName = instanceName
                uuid = instanceId
            vm = self._deployImage(job, image, auth, dataCenter,
                                   dataStore, computeResource,
                                   resourcePool, vmName, uuid,
                                   network, asTemplate = useTemplate)
        else:
            # Since we're bypassing _getTemplatesFromInventory, none of the
            # images should be marked as deployed for ESX targets
            assert useTemplate
            vm = getattr(image, 'opaqueId')

        if useTemplate:
            job.addLog(self.LogEntry('Cloning template'))
            vmMor = self._cloneTemplate(job, image.getImageId(), instanceName,
                                        instanceDescription,
                                        dataCenter, computeResource,
                                        dataStore, resourcePool, vm=vm)
        else:
            vmMor = self.client._getVM(mor=vm)

        try:
            self._attachCredentials(instanceName, vmMor, dataCenter, dataStore,
                                    computeResource)
        except Exception, e:
            self.log_exception("Exception attaching credentials: %s" % e)
        self.client.startVM(mor = vmMor)
        job.addLog(self.LogEntry('Launching'))
        # Grab the real uuid
        instMap = self.client.getVirtualMachines(['config.uuid' ], root = vmMor)
        uuid = instMap[vmMor]['config.uuid']
        return uuid


    def _attachCredentials(self, vmName, vmMor, dataCenterMor, dataStoreMor,
            computeResourceMor):
        filename = self.getCredentialsIsoFile()
        dataCenter = self.vicfg.getDatacenter(dataCenterMor).properties['name']
        dsInfo = self.vicfg.getMOR(dataStoreMor)
        dataStore = self.client.getDynamicProperty(dsInfo, 'summary').get_element_name()
        import viclient
        try:
            viclient.vmutils._uploadVMFiles(self.client, [ filename ], vmName,
                dataCenter = dataCenter, dataStore = dataStore)
        finally:
            # We use filename below only for the actual name; no need to keep
            # this file around now
            os.unlink(filename)

        dc = self.vicfg.getMOR(dataCenterMor)
        hostFolder = self.client.getMoRefProp(dc, 'hostFolder')
        hostMor = self.client.getFirstDecendentMoRef(hostFolder, 'HostSystem')
        cr = self.vicfg.getMOR(computeResourceMor)
        defaultDevices = self.client.getDefaultDevices(cr, hostMor)

        datastoreVolume = self.client._getVolumeName(dataStore)
        controllerMor = self.client._getIdeController(defaultDevices)
        try:
            cdromSpec = self.client.createCdromConfigSpec(
                os.path.basename(filename), vmMor, controllerMor,
                dataStoreMor, datastoreVolume)
            self.client.reconfigVM(vmMor, dict(deviceChange = [ cdromSpec ]))
        except viclient.client.FaultException, e:
            # We will not fail the request if we could not attach credentials
            # to the instance
            self.log_exception("Exception trying to attach credentials: %s", e)
