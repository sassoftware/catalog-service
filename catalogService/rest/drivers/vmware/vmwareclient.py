#!/usr/bin/python2.4
#
# Copyright (c) 2008 rPath, Inc.  All Rights Reserved.
#

import os
import signal
import time
import urllib
import datetime

from conary.lib import util, sha1helper

from catalogService import clouds
from catalogService import descriptor
from catalogService import environment
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
    "VMware Image"

    __slots__ = images.BaseImage.__slots__ + [ 'isDeployed', ]
    _slotTypeMap = images.BaseImage._slotTypeMap.copy()
    _slotTypeMap.update(dict(isDeployed = bool))

def uuidgen():
    hex = sha1helper.md5ToString(sha1helper.md5String(os.urandom(128)))
    return '-'.join((hex[:8], hex[8:12], hex[12:16], hex[16:20], hex[20:]))

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
            raise AuthenticationFailure('', '')
        # FIXME: refactor this into common code
        keyPrefix = "%s/%s" % (self._sanitizeKey(self.cloudName),
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

    def _getCloudCredentialsForUser(self):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        return self._getCredentialsForCloudName(self.cloudName)[1]

    def isValidCloudName(self, cloudName):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        cloudConfig = self._getCloudConfiguration(cloudName)
        return bool(cloudConfig)

    def drvSetUserCredentials(self, fields):
        data = dict((x.getName(), x.getValue()) for x in fields.getFields())
        store = self._getCredentialsDataStore()
        self._writeCredentialsToStore(store, self.userId, self.cloudName, data)
        try:
            self.drvCreateCloudClient(data)
            valid = True
        except:
            # FIXME: exception handler too broad
            valid = False
        node = self._nodeFactory.newCredentials(valid)
        return node

    def _createCloudNode(self, cloudConfig):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        cld = self._nodeFactory.newCloud(
            cloudName = cloudConfig['name'],
            description = cloudConfig['description'],
            cloudAlias = cloudConfig['alias'])
        return cld

    def _daemonize(self, *args, **kw):
        self._cloudClient = None
        return storage_mixin.StorageMixin._daemonize(self, *args, **kw)

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
                           constraints = dict(constraintName = 'length',
                                              value = 32))

        descr.addDataField('instanceDescription',
                           descriptions = 'Instance Description',
                           type = 'str',
                           constraints = dict(constraintName = 'length',
                                              value = 128))

        vicfg = self.vicfg
        dataCenters = vicfg.getDatacenters()
        descr.addDataField('dataCenter',
                           descriptions = 'Data Center',
                           required = True,
                           type = descriptor.EnumeratedType(
            descriptor.ValueWithDescription(x.properties['name'],
                                            descriptions=x.properties['name'])
            for x in dataCenters),
                           default = dataCenters[0].properties['name'],
                           readonly = True
                           )
        crToDc = {}
        for dc in dataCenters:
            crs = dc.getComputeResources()
            for cr in crs:
                crToDc[cr] = dc
            descr.addDataField('cr-%s' %dc.properties['name'],
                               descriptions = 'Compute Resource',
                               required = True,
                               type = descriptor.EnumeratedType(
                descriptor.ValueWithDescription(
                x.properties['name'], descriptions=x.properties['name'])
                for x in crs),
                               default = crs[0].properties['name'],
                               conditional = descriptor.Conditional(
                fieldName='dataCenter',
                operator='eq',
                value=dc.properties['name'])
                               )
        for cr in crToDc.keys():
            cfg = cr.configTarget
            dataStores = []
            def formatSize(size):
                suffixes = (' bytes', ' KiB', ' MiB', ' GiB')
                div = 1
                for suffix in suffixes:
                    if size < (div * 1024):
                        return '%d %s' %(size / div, suffix)
                    div = div * 1024
                return '%d TiB' %(size / div)

            for ds in cfg.get_element_datastore():
                name = ds.get_element_name()
                dsInfo = ds.get_element_datastore()
                free = dsInfo.get_element_freeSpace()
                dsDesc = '%s - %s free' %(name, formatSize(free))
                dataStores.append((name, dsDesc))
            dc = crToDc[cr]
            descr.addDataField('dataStore-%s' %cr.properties['name'],
                               descriptions = 'Data Store',
                               required = True,
                               type = descriptor.EnumeratedType(
                descriptor.ValueWithDescription(x[0], descriptions = x[1])
                for x in dataStores),
                               default = dataStores[0][0],
                               conditional = descriptor.Conditional(
                fieldName='cr-%s' %dc.properties['name'],
                operator='eq',
                value=cr.properties['name'])
                               )
            # FIXME: add (descriptor.Conditional(
            #fieldName='dataCenter',
            #    operator='eq',
            #    value=dc.obj),

        for cr in crToDc.keys():
            rps = [ x['name'] for x in cr.resourcePools.itervalues() ]
            descr.addDataField('resourcePool-%s' %cr.properties['name'],
                               descriptions = 'Resource Pool',
                               required = True,
                               type = descriptor.EnumeratedType(
                descriptor.ValueWithDescription(x,
                                                descriptions=x)
                for x in rps),
                               default = rps[0],
                               conditional = descriptor.Conditional(
                fieldName='cr-%s' %dc.properties['name'],
                operator='eq',
                value=cr.properties['name'])
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

    def drvGetImages(self, imageIds):
        # currently we return the templates as available images
        imageList = self._getTemplatesFromInventory()

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

    def getEnvironment(self):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        cloud = self._nodeFactory.newEnvironmentCloud(
            cloudName = self.cloudName, cloudAlias = self.getCloudAlias())
        env = self._nodeFactory.newEnvironment()
        env.append(cloud)
        return env

    def getInstanceTypes(self):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        return self._getInstanceTypes()

    def getCloudAlias(self):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        cloudConfig = self.drvGetCloudConfiguration()
        return cloudConfig['alias']

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
            # END FIXME
        instMap = self.client.getVirtualMachines([ 'name',
                                                   'config.annotation',
                                                   'config.template',
                                                   'runtime.powerState',
                                                   'runtime.bootTime',
                                                   'config.uuid',
                                                   'config.extraConfig',
                                                   'guest.ipAddress' ])
        for mor, vminfo in instMap.iteritems():
            if vminfo.get('config.template', False):
                continue
            if not 'config.uuid' in vminfo:
                continue
            launchTime = None
            if 'runtime.bootTime' in vminfo:
                dt = datetime.datetime(*vminfo['runtime.bootTime'][:7])
                launchTime = dt.strftime('%a %b %d %H:%M:%S UTC-0000 %Y')
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
            instanceList.append(inst)
        instanceList.sort(key = lambda x: (x.getState(), x.getInstanceId()))
        return instanceList

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

    def _getCredentialsForCloudName(self, cloudName):
        # FIXME: re-factor this into common code (copied from Xen Ent)
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

    def _cloneTemplate(self, imageId, instanceName, instanceDescription,
                       uuid, dataCenter, computeResource, dataStore,
                       resourcePool):
        templateUuid = os.path.basename(imageId)
        ret = self.client.cloneVM(uuid=templateUuid,
                                  name=instanceName,
                                  annotation=instanceDescription,
                                  dc=self.vicfg.getMOR(dataCenter),
                                  cr=self.vicfg.getMOR(computeResource),
                                  ds=self.vicfg.getMOR(dataStore),
                                  rp=self.vicfg.getMOR(resourcePool),
                                  newuuid=uuid)

    def _launchInstance(self, instanceId, image, dataCenter,
                        computeResource, dataStore, resourcePool,
                        instanceName, instanceDescription):
        try:
            self._instanceStore.setPid(instanceId)
            if not image.getIsDeployed():
                raise NotImplementedError
            imageId = image.getImageId()

            self._setState(instanceId, 'Cloning template')
            self._cloneTemplate(imageId, instanceName,
                                instanceDescription, instanceId,
                                dataCenter, computeResource,
                                dataStore, resourcePool)
            self._setState(instanceId, 'Launching')
            self.startVm(imageId)
        finally:
            self._instanceStore.deletePid(instanceId)

