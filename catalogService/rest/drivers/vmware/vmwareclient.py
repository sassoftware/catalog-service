#
# Copyright (c) SAS Institute Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


import fnmatch
import httplib
import operator
import os
import StringIO
import tempfile
import time
from conary.lib import util

from catalogService import errors
from catalogService import storage
from catalogService.rest import baseDriver
from catalogService.rest.models import images
from catalogService.rest.models import instances
from catalogService.libs.viclient.VimService_client import *  # pyflakes=ignore
from catalogService.utils.stream_archive import TarStreamExtractor

diskProvisioningOptions = [
    ('sparse', 'Monolithic Sparse or Thin'),
    ('flat', 'Monolithic Flat or Thick'),
    ('thin', 'Thin (Allocated on demand)'),
    ('thick', 'Thick (Preallocated)'),
    ('monolithicSparse', 'Monolithic Sparse (Allocated on demand)'),
    ('monolithicFlat', 'Monolithic Flat (Preallocated)'),
    ('twoGbMaxExtentSparse', 'Sparse 2G Maximum Extent'),
    ('twoGbMaxExtentFlat', 'Flat 2G Maximum Extent'),
]

_diskProvisioningOptionTemplate = """\
        <describedValue>
          <descriptions>
            <desc>%s</desc>
          </descriptions>
          <key>%s</key>
        </describedValue>
"""

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
        <desc>Server Address</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/serverName.html'/>
    </field>
    <field>
      <name>alias</name>
      <descriptions>
        <desc>Name</desc>
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
    <field>
      <name>defaultDiskProvisioning</name>
      <descriptions>
        <desc>Default Disk Provisioning (ESX 5.x+)</desc>
      </descriptions>
      <enumeratedType>
        %s
      </enumeratedType>
      <default>flat</default>
      <required>true</required>
      <help href='configuration/defaultDiskProvisioning.html'/>
    </field>
  </dataFields>
</descriptor>""" % '\n'.join(_diskProvisioningOptionTemplate % (y, x)
    for (x, y) in diskProvisioningOptions)

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
          <desc>Field must contain between 1 and 32 characters</desc>
        </descriptions>
        <length>32</length>
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
          <desc>Field must contain between 1 and 32 characters</desc>
        </descriptions>
        <length>32</length>
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
        if abs(size) < (div * 1024):
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

class CustomVimServiceTransport(httplib.HTTPSConnection):
    def send(self, buf):
        df = getattr(self, '_dumpFile', None)
        if df is None:
            dumpDir = os.getenv('CATALOG_SERVICE_VMWARE_DUMP_DIR')
            util.mkdirChain(dumpDir)
            df = self._dumpFile = tempfile.NamedTemporaryFile(
                    dir=dumpDir,
                    prefix="%.3f-" % time.time(),
                    delete=False)
        df.write(buf)
        return httplib.HTTPSConnection.send(self, buf)


class VMwareClient(baseDriver.BaseDriver):
    Image = VMwareImage
    cloudType = 'vmware'
    instanceStorageClass = InstanceStorage

    configurationDescriptorXmlData = _configurationDescriptorXmlData
    credentialsDescriptorXmlData = _credentialsDescriptorXmlData
    # transport is mocked out during testing to simulate talking to
    # an actual server
    dumpDir = os.getenv('CATALOG_SERVICE_VMWARE_DUMP_DIR')
    if dumpDir is None:
        VimServiceTransport = None
    else:
        VimServiceTransport = CustomVimServiceTransport

    RBUILDER_BUILD_TYPE = 'VMWARE_ESX_IMAGE'
    # We should prefer OVA over OVF, but vcenter gets upset with
    # gzip-compressed vmdk images inside ova
    #OVF_PREFERRENCE_LIST = [ '.ova', 'ovf.tar.gz', ]
    OVF_PREFERRENCE_LIST = [ 'ovf.tar.gz', 'ova', ]

    class ImageData(baseDriver.BaseDriver.ImageData):
        __slots__ = [ 'vmCPUs', 'vmMemory', ]


    def __init__(self, *args, **kwargs):
        baseDriver.BaseDriver.__init__(self, *args, **kwargs)
        self._vicfg = None
        self._virtualMachines = None

    def drvCreateCloudClient(self, credentials):
        cloudConfig = self.getTargetConfiguration()
        host = self.cloudName
        # This import is expensive!!! Delay it until it is actually needed
        from catalogService.libs import viclient
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

    def getDeployImageParameters(self, image, descriptorData):
        params = baseDriver.BaseDriver.getDeployImageParameters(self,
            image, descriptorData)
        self._paramsFromDescriptorData(params, descriptorData)
        return params

    def getLaunchInstanceParameters(self, image, descriptorData):
        params = baseDriver.BaseDriver.getLaunchInstanceParameters(self,
            image, descriptorData)
        self._paramsFromDescriptorData(params, descriptorData)
        return params

    def _filterDataStore_cond(self, cr, filterExp):
        """
        Filter out read-only datastores and the ones not matching filterExp
        """

        cfg = cr.configTarget
        for ds in cfg.get_element_datastore():
            if hasattr(ds, '_mode') and ds.get_element_mode() == 'readOnly':
                # Read-only datastore. Can't launch on it
                continue
            name = ds.get_element_name()
            if not fnmatch.fnmatch(name, filterExp):
                continue
            yield ds

    def _filterDataStore_mostFreeSpace(self, cr, filterExp):
        return max(self._filterDataStore_cond(cr, filterExp),
            key = lambda x: x.get_element_datastore().get_element_freeSpace())

    def _filterDataStore_leastOvercommitted(self, cr, filterExp):
        return max(self._filterDataStore_cond(cr, filterExp),
            key = lambda x: (x.get_element_datastore().get_element_freeSpace()
                - x.get_element_datastore().get_element_uncommitted()))

    def _paramsFromDescriptorData(self, params, descriptorData):
        getField = descriptorData.getField
        dataCenter = getField('dataCenter')
        cr = getField('cr-%s' % dataCenter)
        rp = getField('resourcePool-%s' % cr)
        network = getField('network-%s' % dataCenter)
        folder = getField('vmfolder-%s' % dataCenter)
        vicfg = self.vicfg
        dc = vicfg.getDatacenter(dataCenter)
        crObj = dc.getComputeResource(cr)
        dataStoreSelection = getField('dataStoreSelection-%s' % cr)
        if dataStoreSelection == ('dataStoreManual-%s' % cr):
            dataStore = getField('dataStore-%s' % cr)
        elif dataStoreSelection == ('dataStoreFreeSpace-%s' % cr):
            filterExp = getField('%s-filter' % dataStoreSelection)
            ds = self._filterDataStore_mostFreeSpace(crObj, filterExp)
            dataStore = ds.get_element_datastore().get_element_datastore()
        elif dataStoreSelection == ('dataStoreLeastOvercommitted-%s' % cr):
            filterExp = getField('%s-filter' % dataStoreSelection)
            ds = self._filterDataStore_leastOvercommitted(crObj, filterExp)
            dataStore = ds.get_element_datastore().get_element_datastore()
        params.update(dict(
            dataCenter = dataCenter,
            dataStore = dataStore,
            computeResource = cr,
            resourcePool = rp,
            network = network,
            vmFolder=folder,
        ))
        return params

    def drvPopulateImageDeploymentDescriptor(self, descr, extraArgs=None):
        descr.setDisplayName('VMware Image Upload Parameters')
        descr.addDescription('VMware Image Upload Parameters')
        self.drvImageDeploymentDescriptorCommonFields(descr)
        return self._drvPopulateDescriptorFromTarget(descr)

    def drvPopulateLaunchDescriptor(self, descr, extraArgs=None):
        descr.setDisplayName('VMware Launch Parameters')
        descr.addDescription('VMware Launch Parameters')
        self.drvLaunchDescriptorCommonFields(descr)
        self._launchSpecificDescriptorFields(descr, extraArgs=extraArgs)
        return self._drvPopulateDescriptorFromTarget(descr)

    def _launchSpecificDescriptorFields(self, descr, extraArgs=None):
        imageData = self._getImageData(extraArgs)
        vmCPUs = imageData.vmCPUs or 1
        vmMemory = imageData.vmMemory or 1024
        descr.addDataField(
            'vmCPUs',
            descriptions = 'Number of Virtual CPUs',
            required = True,
            help = [
                ('launch/vmCPUs.html', None)
            ],
            type = 'int',
            constraints = dict(constraintName = 'range',
                               min = 1, max = 32),
            default = vmCPUs)
        descr.addDataField(
            'vmMemory',
            descriptions = 'RAM (Megabytes)',
            required = True,
            help = [
                ('launch/vmMemory.html', None)
            ],
            type = 'int',
            constraints = dict(constraintName = 'range',
                               min = 256, max = 128*1024),
            default = vmMemory)
        descr.addDataField(
            'rootSshKeys',
            descriptions = 'Root SSH keys',
            help = [
                ('launch/rootSshKeys.html', None)
            ],
            type = 'str',
            constraints = dict(constraintName = 'length', value = 4096))

    def _drvPopulateDescriptorFromTarget(self, descr):
        targetConfig = self.getTargetConfiguration()
        if self.client.vmwareVersion >= (5, 0, 0):
            # Default to flat if the target was not configured
            defaultDiskProvisioning = targetConfig.get(
                'defaultDiskProvisioning', 'flat')

            descr.addDataField(
                'diskProvisioning',
                descriptions = 'Disk Provisioning',
                required = True,
                help = [
                    ('launch/diskProvisioning.html', None)
                ],
                type = descr.EnumeratedType(
                    descr.ValueWithDescription(x[0], descriptions=x[1])
                    for x in diskProvisioningOptions),
                default = defaultDiskProvisioning)

        vicfg = self.vicfg
        dataCenters = [ x for x in vicfg.getDatacenters()
            if x.getComputeResources() ]
        descr.addDataField('dataCenter',
                           descriptions = 'Data Center',
                           required = True,
                           help = [
                               ('launch/dataCenter.html', None)
                           ],
                           type = descr.EnumeratedType(
            descr.ValueWithDescription(x.obj,
                                            descriptions=x.properties['name'])
            for x in dataCenters),
                           default = dataCenters[0].obj,
                           )
        crToDc = {}
        validDatacenters = []
        for dc in dataCenters:
            dcNetworks = dc.properties.get('network')
            if not dcNetworks:
                # SUP-4625
                continue
            crs = dc.getComputeResources()
            validCrs = {}
            for cr in crs:
                cfg = cr.configTarget
                if cfg is None:
                    continue
                validCrs[cr] = dc
            if not validCrs:
                continue
            crToDc.update(validCrs)
            validDatacenters.append(dc)

            folders = vicfg.getVmFolderLabelsForTree(dc.properties['vmFolder'])

            descr.addDataField('vmfolder-%s' % dc.obj,
                descriptions = "VM Folder",
                required = True,
                help = [ ('launch/vmfolder.html', None) ],
                type = descr.EnumeratedType(
                    descr.ValueWithDescription(
                        x[1], descriptions=x[0])
                    for x in folders),
                   default = folders[0][1],
                   conditional = descr.Conditional(
                        fieldName='dataCenter',
                        operator='eq',
                        fieldValue=dc.obj)
                    )

            descr.addDataField('cr-%s' %dc.obj,
                               descriptions = 'Compute Resource',
                               required = True,
                               help = [
                                   ('launch/computeResource.html', None)
                               ],
                               type = descr.EnumeratedType(
                descr.ValueWithDescription(
                x.obj, descriptions=x.properties['name'])
                for x in crs),
                               default = crs[0].obj,
                               conditional = descr.Conditional(
                                    fieldName='dataCenter',
                                    operator='eq',
                                    fieldValue=dc.obj)
                               )

        for dc in validDatacenters:
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
                    type = descr.EnumeratedType(
                        descr.ValueWithDescription(x.mor,
                            descriptions=x.name) for x in networks),
                    default = networks[0].mor,
                    conditional = descr.Conditional(
                        fieldName='dataCenter',
                        operator='eq',
                        fieldValue=dc.obj))

        for cr, dc in crToDc.items():
            cfg = cr.configTarget
            dataStores = []

            dsSelection = [
                ("dataStoreFreeSpace-%s" % cr.obj, "Most free space"),
                ("dataStoreLeastOvercommitted-%s" % cr.obj, "Least Overcommitted"),
                ("dataStoreManual-%s" % cr.obj, "Manual"),
            ]

            dsSelectionFieldName = 'dataStoreSelection-%s' % cr.obj
            descr.addDataField(dsSelectionFieldName,
                    descriptions = 'Data Store Selection',
                    required = True,
                    help = [ ('launch/dataStoreSelection.html', None) ],
                    type = descr.EnumeratedType(
                        descr.ValueWithDescription(x[0], descriptions = x[1])
                        for x in dsSelection),
                    conditional = descr.Conditional(
                        fieldName='cr-%s' %dc.obj,
                        operator='eq',
                        fieldValue=cr.obj),
                    default = dsSelection[0][0],
                    )
            # First two options allow for a glob filter
            for opt in dsSelection[:2]:
                parentFieldName = opt[0]
                descr.addDataField('%s-filter' % parentFieldName,
                        descriptions = 'Filter',
                        required = True,
                        type = "str",
                        default = "*",
                            conditional = descr.Conditional(
                                fieldName=dsSelectionFieldName,
                                operator='eq',
                                fieldValue=parentFieldName)
                        )

            parentFieldName = dsSelection[-1][0]
            for ds in cfg.get_element_datastore():
                if hasattr(ds, '_mode') and ds.get_element_mode() == 'readOnly':
                    # Read-only datastore. Can't launch on it
                    continue
                name = ds.get_element_name()
                dsSummary = ds.get_element_datastore()
                free = dsSummary.get_element_freeSpace()
                dsDesc = '%s - %s free' %(name, formatSize(free))
                dsMor = ds.get_element_datastore().get_element_datastore()
                dataStores.append((dsMor, dsDesc))
            descr.addDataField('dataStore-%s' %cr.obj,
                               descriptions = 'Data Store',
                               required = True,
                               help = [
                                   ('launch/dataStore.html', None)
                               ],
                               type = descr.EnumeratedType(
                descr.ValueWithDescription(x[0], descriptions = x[1])
                for x in dataStores),
                               default = dataStores[0][0],
                               conditional = descr.Conditional(
                                    fieldName=dsSelectionFieldName,
                                    operator='eq',
                                    fieldValue=parentFieldName)
                               )
            # FIXME: add (descr.Conditional(
            #fieldName='dataCenter',
            #    operator='eq',
            #    fieldValue=dc.obj),

        for cr, dc in crToDc.items():
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
                               type = descr.EnumeratedType(
                descr.ValueWithDescription(str(x[0]),
                                                descriptions=x[1]['name'])
                for x in cr.resourcePools.iteritems()),
                               default = defaultRp,
                               conditional = descr.Conditional(
                                    fieldName='cr-%s' %dc.obj,
                                    operator='eq',
                                    fieldValue=cr.obj)
                               )

        return descr

    def postFork(self):
        if self._cloudClient is not None:
            # Pretend that we're not logged in, otherwise the __del__ method
            # will log out the parent
            self._cloudClient._loggedIn = False
        return baseDriver.BaseDriver.postFork(self)

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
        mintImages = self.db.imageMgr.getAllImagesByType(imageType)
        if self.client.vmwareVersion < (4, 0, 0):
            # We don't support OVF deployments, so don't even bother
            return mintImages
        # Prefer ova (ovf 1.0) over ovf 0.9 over plain esx
        mintImagesByBuildId = {}
        for mintImage in mintImages:
            files = self._getPreferredOvfImage(mintImage['files'])
            if files:
                mintImage['files'] = files
            mintImagesByBuildId[mintImage['buildId']] = mintImage
        # Finally, prefer OVF 1.0 images (unused at the moment)
        imageType = 'VMWARE_OVF_IMAGE'
        for mintImage in self.db.imageMgr.getAllImagesByType(imageType):
            mintImagesByBuildId[mintImage['buildId']] = mintImage
        # Sort data by build id
        return [ x[1] for x in sorted(mintImagesByBuildId.items()) ]

    @classmethod
    def _getPreferredOvfImage(cls, files):
        for suffix in cls.OVF_PREFERRENCE_LIST:
            for fdict in files:
                fname = fdict.get('fileName', '')
                if fname.endswith(suffix):
                    return [ fdict ]
        return None

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

            inst._opaqueId = mor

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

    def drvGetInstances(self, instanceIds, force=False):
        cloudAlias = self.getCloudAlias()
        instanceList = instances.BaseInstances()
        instMap = self.getVirtualMachines(force=force)
        return self.filterInstances(instanceIds,
            self._buildInstanceList(instanceList, instMap))

    def getVirtualMachines(self, force=False):
        if self._virtualMachines is not None and not force:
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
    def getImageIdFromMintImage(cls, image, targetImageIds):
        imageSha1 = baseDriver.BaseDriver.getImageIdFromMintImage(image,
            targetImageIds)
        if imageSha1 is None:
            return imageSha1
        if isinstance(imageSha1, int):
            # fake the image sha1
            imageSha1 = "%032x" % imageSha1
        return cls._uuid(imageSha1)

    def getImagesFromTarget(self, imageIds):
        """
        returns all templates in the inventory
        currently we return the templates as available images
        """
        useTemplate = not self.client.isESX()
        imageList = images.BaseImages()
        if not useTemplate:
            # ESX does not support templates, so don't bother to search
            # for them
            return imageList
        cloudAlias = self.getCloudAlias()
        instMap = self.getVirtualMachines()
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
                internalTargetId = vminfo['config.uuid'],
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
                       resourcePool, vm=None, vmFolder=None,
                       network=None, callback=None):
        templateUuid = None
        if not vm:
            templateUuid = os.path.basename(imageId)
        try:
            vmMor = self.client.cloneVM(mor=vm,
                                        uuid=templateUuid,
                                        name=instanceName,
                                        annotation=instanceDescription,
                                        dc=self.vicfg.getMOR(dataCenter),
                                        ds=self.vicfg.getMOR(dataStore),
                                        rp=self.vicfg.getMOR(resourcePool),
                                        vmFolder=self.vicfg.getMOR(vmFolder),
                                        network=self.vicfg.getMOR(network),
                                        callback=callback)
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

    def _deployOvf(self, job, vmName, uuid, stream, dataCenter,
                     dataStore, host, resourcePool, network, diskProvisioning,
                     vmFolder=None,
                     asTemplate = False):
        ovfFileName = None
        ovfContents = None
        found = 0
        stream = self.streamProgressWrapper(job, stream, "Importing OVF")
        archive = TarStreamExtractor(stream)
        for name, contents in archive.getSmallFiles().iteritems():
            if name.endswith('.ovf'):
                ovfFileName = name
                ovfContents = contents
                found += 1
        if not found:
            raise RuntimeError("No ovf file found")
        if found != 1:
            raise RuntimeError("More than one .ovf file found")
        idx = ovfFileName.rfind('/')
        if idx == -1:
            prefix = ''
        else:
            prefix = ovfFileName[:idx+1]
        baseDir = os.path.dirname(ovfFileName)

        if vmFolder is None:
            vmFolder = dataCenter.properties['vmFolder']
        self._msg(job, 'Importing OVF descriptor')

        fileItems, httpNfcLease = self.client.ovfImportStart(
                ovfContents=ovfContents,
                vmName=vmName,
                vmFolder=vmFolder,
                resourcePool=resourcePool,
                dataStore=dataStore,
                network=network,
                diskProvisioning=diskProvisioning,
                )
        self.client.waitForLeaseReady(httpNfcLease)

        # Also send progress info to vmware
        percenter = stream.callback
        percenter.callback = self.LeaseProgressUpdate(
                httpNfcLease, percenter.callback)

        vmMor = self.client.ovfUpload(httpNfcLease, archive, prefix, fileItems)
        return vmMor

    def getImageIdFromTargetImageRef(self, vmRef):
        return self._getVmUuid(vmRef)

    def _deployImageFromStream(self, job, image, stream, dataCenter,
                             dataStore, computeResource, resourcePool, vmName,
                             uuid, network, diskProvisioning,
                             vmFolder=None, asTemplate=False):

        logger = lambda *x: self._msg(job, *x)
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

        if vmFolder is None:
            vmFolderMor = dc.properties['vmFolder']
        else:
            vmFolderMor = self.vicfg.getMOR(vmFolder)
        dcName_, vmFolderPath = self.vicfg.getVmFolderLabelPath(vmFolderMor)
        if dcName_ is None:
            # Requested a folder with no path to the top level
            raise errors.ParameterError()
        inventoryPrefix = '/%s/%s/' %(dcName_, vmFolderPath)
        vmName = self._findUniqueName(inventoryPrefix, vmName)
        # FIXME: make sure that there isn't something in the way on
        # the data store

        vmMor = self._deployOvf(job, vmName, uuid,
            stream, dc, dataStore=ds,
            host = host, resourcePool=rp, network = network,
            diskProvisioning = diskProvisioning,
            vmFolder=vmFolderMor,
            asTemplate = asTemplate)

        nwobj = self.client.getMoRefProp(vmMor, 'network')
        reconfigVmParams = dict()
        if not nwobj.get_element_ManagedObjectReference():
            # add NIC
            nicSpec = self.client.createNicConfigSpec(network)
            deviceChange = [ nicSpec ]
            reconfigVmParams['deviceChange'] = deviceChange

        if asTemplate:
            # Reconfiguring the uuid is unreliable, we're using the
            # annotation field for now
            reconfigVmParams['annotation'] = "rba-uuid: %s" % uuid

        if reconfigVmParams:
            self._msg(job, 'Reconfiguring VM')
            self.client.reconfigVM(vmMor, reconfigVmParams)

        if asTemplate:
            self._msg(job, 'Converting VM to template')
            self.client.markAsTemplate(vm=vmMor)
        image.setShortName(vmName)
        return vmMor

    def _getVmUuid(self, vmMor):
        # Grab the real uuid
        instMap = self.client.getVirtualMachines(['config.uuid' ], root = vmMor)

        uuid = instMap[vmMor]['config.uuid']
        return uuid

    def deployImageProcess(self, job, image, auth, **params):
        # RCE-1751: always redeploy.
        if 0 and image.getIsDeployed():
            self._msg(job, "Image is already deployed")
            return image.getImageId()

        ppop = params.pop
        dataCenter = ppop('dataCenter')
        computeResource = ppop('computeResource')
        dataStore = ppop('dataStore')
        resourcePool= ppop('resourcePool')
        imageName = ppop('imageName')
        network = ppop('network')
        vmFolder = ppop('vmFolder')
        diskProvisioning = ppop('diskProvisioning', None)

        newImageId = self.instanceStorageClass._generateString(32)
        useTemplate = not self.client.isESX()

        # RCE-796
        vmName = imageName
        if useTemplate:
            # if we can use a template, deploy the image
            # as a template with the imageId as the uuid
            uuid = image.getImageId()
        else:
            # otherwise, we'll use
            # a random instance uuid for deployment
            uuid = newImageId

        vm = self._deployImage(job, image, auth, dataCenter,
                               dataStore, computeResource,
                               resourcePool, vmName, uuid, network,
                               diskProvisioning,
                               vmFolder=vmFolder, asTemplate = useTemplate)
        self._msg(job, 'Image deployed')
        return image.getImageId()

    def taskCallbackFactory(self, job, message):
        def callback(values):
            status, progress, error = values
            if status != "running" or not isinstance(progress, int):
                return
            self._msg(job, message % progress)
        return callback

    def LeaseProgressUpdate(self, lease, origCallback):
        """
        Returns a progress callback that sends a percentage completion to
        vmware before invoking the original callback
        """
        from catalogService.libs.viclient import client
        return client.LeaseProgressUpdate(self.client, lease, origCallback)

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
        vmFolder = ppop('vmFolder')
        diskProvisioning = ppop('diskProvisioning', None)
        vmCPUs = ppop('vmCPUs')
        vmMemory = ppop('vmMemory')
        self._rootSshKeys = ppop('rootSshKeys', None)

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
                                   network, vmFolder=vmFolder,
                                   diskProvisioning=diskProvisioning,
                                   asTemplate = useTemplate)
        else:
            # Since we're bypassing _getTemplatesFromInventory, none of the
            # images should be marked as deployed for ESX targets
            assert useTemplate
            vm = getattr(image, 'opaqueId')

        if useTemplate:
            self._msg(job, 'Cloning template')
            cloneCallback = self.taskCallbackFactory(job, "Cloning: %d%%")

            vmMor = self._cloneTemplate(job, image.getImageId(), instanceName,
                                        instanceDescription,
                                        dataCenter, computeResource,
                                        dataStore, resourcePool, vm=vm,
                                        vmFolder=vmFolder,
                                        network=network,
                                        callback=cloneCallback)
        else:
            vmMor = self.client._getVM(mor=vm)

        try:
            self._attachCredentials(job, instanceName, vmMor, dataCenter,
                    dataStore, computeResource,
                    numCPUs=vmCPUs, memoryMB=vmMemory)
        except Exception, e:
            self.log_exception("Exception attaching credentials: %s" % e)
        self._msg(job, 'Launching')
        self.client.startVM(mor = vmMor)
        uuid = self._getVmUuid(vmMor)
        self._msg(job, 'Instance launched')
        return uuid

    def _attachCredentials(self, job, vmName, vmMor, dataCenterMor, dataStoreMor,
            computeResourceMor, numCPUs=1, memoryMB=256):
        from catalogService.libs.viclient import client
        bootUuid = self.getBootUuid()

        dc = self.vicfg.getMOR(dataCenterMor)
        hostFolder = self.client.getMoRefProp(dc, 'hostFolder')
        hostMor = self.client.getFirstDecendentMoRef(hostFolder, 'HostSystem')
        cr = self.vicfg.getMOR(computeResourceMor)
        defaultDevices = self.client.getDefaultDevices(cr, hostMor)
        controllerMor = self.client._getIdeController(defaultDevices)


        conaryProxies = ' '.join(x.partition(':')[0]
                for x in self.zoneAddresses)
        zoneAddresses = ' '.join(self.zoneAddresses)
        certFile = self.getWbemClientCert()
        # Load the cert, we need the hash
        certHash = self.computeX509CertHash(certFile)

        vAppConfigSpec = ns0.VmConfigSpec_Def('').pyclass()
        vAppConfigSpec.set_element_ovfEnvironmentTransport(['iso', 'com.vmware.guestInfo'])
        properties = []
        vAppConfigSpec.set_element_property(properties)
        propValues = [
                ('com.sas.app-engine.boot-uuid', bootUuid),
                ('com.sas.app-engine.conary.proxy', conaryProxies),
                ('com.sas.app-engine.zone-addresses', zoneAddresses),
                ('com.sas.app-engine.wbem.cert.hash.0', certHash),
                ('com.sas.app-engine.wbem.cert.data.0', file(certFile).read()),
        ]
        if self._rootSshKeys:
            propValues.append(('com.sas.app-engine.ssh-keys.root', self._rootSshKeys))

        for idx, (propLabel, propValue) in enumerate(propValues):
            propSpec = vAppConfigSpec.new_property()
            properties.append(propSpec)
            propInfo = propSpec.new_info()
            propSpec.set_element_info(propInfo)
            propSpec.set_element_operation('add')
            propInfo.set_element_id(propLabel)
            propInfo.set_element_key(idx)
            propInfo.set_element_label(propLabel)
            propInfo.set_element_value(propValue)
            propInfo.set_element_type('string')

        try:
            self._msg(job, 'Setting initial configuration')
            cdromSpec = self.client.createCdromConfigSpec_passthrough(vmMor,
                    controllerMor)
            self.client.reconfigVM(vmMor, dict(deviceChange = [ cdromSpec ],
                vAppConfig=vAppConfigSpec,
                numCPUs=numCPUs, memoryMB=memoryMB))
        except client.FaultException, e:
            # We will not fail the request if we could not attach credentials
            # to the instance
            self.log_exception("Exception trying to set initial configuration: %s", e)
