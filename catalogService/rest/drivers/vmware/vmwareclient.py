#!/usr/bin/python2.4
#
# Copyright (c) 2008 rPath, Inc.  All Rights Reserved.
#

import os
import signal
import time
import urllib

from conary.lib import util

from catalogService import clouds
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
    </field>
  </dataFields>
</descriptor>
"""

class VMwareInstance(instances.BaseInstance):
    "VMware Instance"
    __slots__ = instances.BaseInstance.__slots__ + [ 'instanceName',
                                                     'annotation' ]

class VMwareClient(baseDriver.BaseDriver, storage_mixin.StorageMixin):
    Instance = VMwareInstance

    _cloudType = 'vmware'

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
        return client

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

    def launchInstance(self, xmlString, requestIPAddress):
        raise NotImplementedError

    def terminateInstances(self, instanceIds):
        insts = self.getInstances(instanceIds)
        for instanceId in instanceIds:
            self.client.shutdownVM(uuid=instanceId)
        for inst in insts:
            inst.setState("Terminating")
        return insts

    def terminateInstance(self, instanceId):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        return self.terminateInstances([instanceId])

    def drvGetImages(self, imageIds):
        # currently we return the templates as available images
        imageList = self._getTemplatesFromInventory()
        return imageList

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
        instMap = self.client.getVirtualMachines([ 'name',
                                                   'config.annotation',
                                                   'config.template',
                                                   'runtime.powerState',
                                                   'config.uuid',
                                                   'guest.ipAddress' ])
        cloudAlias = self.getCloudAlias()
        instanceList = instances.BaseInstances()
        for mor, vminfo in instMap.iteritems():
            if vminfo.get('config.template', False):
                continue
            inst = self._nodeFactory.newInstance(
                id = vminfo['config.uuid'],
                instanceName = vminfo['name'],
                annotation = vminfo['config.annotation'],
                instanceId = vminfo['config.uuid'],
                reservationId = vminfo['config.uuid'],
                dnsName = vminfo.get('guest.ipAddress', None),
                publicDnsName = vminfo.get('guest.ipAddress', None),
                state = vminfo['runtime.powerState'],
                # FIXME: we haven't requested bootTime
                launchTime = vminfo.get('runtime.bootTime', 0),
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
                                                   'config.uuid',
                                                   'guest.ipAddress' ])
        imageList = images.BaseImages()
        for opaqueId, vminfo in instMap.items():
            if not vminfo.get('config.template', False):
                continue

            imageId = vminfo['config.uuid']
            image = self._nodeFactory.newImage(
                id = imageId,
                imageId = imageId, isDeployed = True,
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
