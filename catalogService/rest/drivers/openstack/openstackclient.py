#
# Copyright (c) 2011 rPath, Inc.  All Rights Reserved.
#

import os
from operator import attrgetter

from catalogService import errors
from catalogService.rest import baseDriver
from catalogService.rest.models import images
from catalogService.rest.models import instances

try:
    from novaclient.v1_1.client import Client as NovaClient
    from glance.client import V1Client as GlanceClient
except ImportError:
    NovaClient = None #pyflakes=ignore
    GlanceClient = None #pyflakes=ignore

class OpenStack_Image(images.BaseImage):
    "OpenStack Image"

NOVA_PORT = 8774
GLANCE_PORT = 9292

# This is provided by the nova api
#class OpenStack_InstanceTypes(instances.InstanceTypes):
#    "OpenStack Instance Types"
#
#    idMap = [
#        ('xenent.small', "Small"),
#        ('xenent.medium', "Medium"),
#    ]

# Nova address
# Nova port
# Glance address (until apis are integrated)
# Glance port
_configurationDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>OpenStack Configuration</displayName>
    <descriptions>
      <desc>Configure OpenStack</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>name</name>
      <descriptions>
        <desc>Nova Server</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/novaServerName.html'/>
    </field>
    <field>
      <name>nova_port</name>
      <descriptions>
        <desc>Nova Port</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <default>%(nova_port)s</default>
      <help href='configuration/novaPortNumber.html'/>
    </field>
    <field>
      <name>glance_server</name>
      <descriptions>
        <desc>Glance Server</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/glanceServerName.html'/>
    </field>
    <field>
      <name>glance_port</name>
      <descriptions>
        <desc>Glance Port</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <default>%(glance_port)s</default>
      <help href='configuration/glancePortNumber.html'/>
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
  </dataFields>
</descriptor>""" % dict(nova_port=NOVA_PORT, glance_port=GLANCE_PORT)

# User Name
# Auth Token
_credentialsDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>OpenStack User Credentials</displayName>
    <descriptions>
      <desc>User Credentials for OpenStack</desc>
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
        <length>255</length>
      </constraints>
      <required>true</required>
    </field>
    <field>
      <name>auth_token</name>
      <descriptions>
        <desc>Auth Token</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Field must contain between 1 and 40 characters</desc>
        </descriptions>
        <length>40</length>
      </constraints>
      <required>true</required>
      <password>true</password>
    </field>
  </dataFields>
</descriptor>
"""

# http://glance.openstack.org/client.html
# http://pypi.python.org/pypi/python-novaclient
class ConsolidatedClient(object):
    def __init__(self, nova_client, glance_client):
        self.nova = nova_client
        self.glance = glance_client

class OpenStackClient(baseDriver.BaseDriver):
    Image = OpenStack_Image
    cloudType = 'openstack'

    configurationDescriptorXmlData = _configurationDescriptorXmlData
    credentialsDescriptorXmlData = _credentialsDescriptorXmlData

    RBUILDER_BUILD_TYPE = 'XEN_OVA'  # TODO: Determine appropriate rBuilder image type
    # This should probably be the KVM Raw....

    NovaClientClass = NovaClient
    GlanceClientClass = GlanceClient

    @classmethod
    def isDriverFunctional(cls):
        return (cls.NovaClientClass is not None) and (cls.GlanceClientClass is not None)

    # Right now 1.1 is the only version that is supported
    def _openstack_api_version(self):
        return 'v1.1'

    def drvCreateCloudClient(self, credentials):
        cloudConfig = self.getTargetConfiguration()
        server = cloudConfig['name']
        port = cloudConfig['nova_port']
        glanceServer = cloudConfig.get('glance_server', server)
        glancePort = int(cloudConfig.get('glance_port', GLANCE_PORT))
        api_version = self._openstack_api_version()
        authUrl = "http://%s:%s/%s/" % (server, port, api_version)
        try:
            # password is a ProtectedString, we have to convert to string
            novaClient = self.NovaClientClass(credentials['username'],
                                    credentials['auth_token'],
                                    project_id=None,
                                    auth_url=authUrl)
            glanceClient = self.GlanceClientClass(glanceServer, port=glancePort)
            clients = ConsolidatedClient(novaClient, glanceClient)
        except Exception, e:
            raise errors.PermissionDenied(message =
                    "Error initializing client: %s" % (e, ))
        return clients

    def drvVerifyCloudConfiguration(self, config):
        return

    def terminateInstances(self, instanceIds):
        running_instances = self.getInstances(instanceIds)
        for server in running_instances:
            server.delete() # there is no terminate method in novaclient

        insts = instances.BaseInstances()
        insts.extend(running_instances)
        # Set state
        for inst in insts:
            inst.setState("Terminating")
        return insts

    def terminateInstance(self, instanceId):
        return self.terminateInstances([instanceId])

    def _get_flavors(self):
        client = self.client.nova
        return sorted(client.flavors.list(), key=self.sortKey)

    # TODO: figure this out.  It is an option launch param.
    def _get_ipgroups(self):
        client = self.client.nova
        return sorted( client.ipgroup.list(), key=attrgetter('id') )

    # This also takes optional "ipgroup", "meta", and "files", 
    # see novaclient/servers.py, ignoring for now.  TODO: really ignore?
    def drvPopulateLaunchDescriptor(self, descr):
        descr.setDisplayName("OpenStack Launch Parameters")
        descr.addDescription("OpenStack Launch Parameters")
        self.drvLaunchDescriptorCommonFields(descr)

        targetFlavors = self._get_flavors()
        if not targetFlavors:
            raise errors.CatalogError("No instance flavors defined")
        flavors = [ descr.ValueWithDescription(str(f.id), descriptions = f.name) for f in targetFlavors ]
        descr.addDataField('flavor',
                            descriptions = 'Flavor',
                            required = True,
                            help = [
                                ('launch/flavor.html', None)
                            ],
                            type = descr.EnumeratedType(flavors),
                            default=flavors[0].key,
                            readonly=True,
                            )
        return descr

    # TODO: remove when novaclient has caught up to v1.1.
    # This pulls a resource id from from a resource ref url
    def _get_id_from_ref(self, resource_ref):
        return resource_ref.split('/')[-1]

    @classmethod
    def _idFromRef(cls, ref):
        if ref is None:
            return ref
        if isinstance(ref, int):
            return str(ref)
        # Grab the last part of the URL and return it
        return os.path.basename(ref)

    def drvGetInstances(self, instanceIds):
        client = self.client.nova
        cloudAlias = self.getCloudAlias()
        instanceList = instances.BaseInstances()
        images = self.getAllImages()
        # Hash images so we can quickly return a ref
        imagesMap = dict((self._idFromRef(image.opaqueId), image)
            for image in images if hasattr(image, 'opaqueId'))
        servers = sorted(client.servers.list(), key=self.sortKey)
        for server in servers:
            instanceId = str(server.id)
            imageRef = self._idFromRef(server.imageRef)
            image = imagesMap.get(imageRef)
            if image:
                imageId = image.id
            else:
                imageId = None
            publicDnsName = None # XXX FIXME
            privateDnsName = None # XXX FIXME
            inst = self._nodeFactory.newInstance(id = instanceId,
                imageId = imageId,
                instanceId = instanceId,
                instanceName = server.name,
                instanceDescription = server.name,
                dnsName = 'UNKNOWN',
                publicDnsName = publicDnsName,
                privateDnsName = privateDnsName,
                state = server.status,
                launchTime = server.created if hasattr(server, 'created') else None,
                cloudName = self.cloudName,
                cloudAlias = cloudAlias)

            instanceList.append(inst)
        instanceList.sort(key = lambda x: (x.getState(), x.getInstanceId()))
        return self.filterInstances(instanceIds, instanceList)

    def getLaunchInstanceParameters(self, image, descriptorData):
        params = baseDriver.BaseDriver.getLaunchInstanceParameters(self,
            image, descriptorData)
        getField = descriptorData.getField
        srUuid = getField('storageRepository')
        params['srUuid'] = srUuid
        return params


    def launchInstanceProcess(self, job, image, auth, **launchParams):
        ppop = launchParams.pop
        instanceName = ppop('instanceName')
        instanceDescription = ppop('instanceDescription')

        cloudConfig = self.getTargetConfiguration()
        nameLabel = image.getLongName()
        nameDescription = image.getBuildDescription()

        self._deployImage(job, image, auth)

        imageId = image.getInternalTargetId()

        job.addHistoryEntry('Cloning template')
        realId = self.cloneTemplate(job, imageId, instanceName,
            instanceDescription)
        job.addHistoryEntry('Attaching credentials')
        try:
            self._attachCredentials(realId)
        except Exception, e:
            self.log_exception("Exception attaching credentials: %s" % e)
        job.addHistoryEntry('Launching')
        self.startVm(realId)
        return self.client.xenapi.VM.get_uuid(realId)

    @classmethod
    def sortKey(cls, x):
        return x.id

    def getImagesFromTarget(self, imageIdsFilter):
        cloudAlias = self.getCloudAlias()

        client = self.client.nova
        ret = []
        images = sorted(client.images.list(detailed=True), key=self.sortKey)
        for image in images:
            # image.id is numeric
            imageId = str(image.id)
            imageName = image.name
            img = self._nodeFactory.newImage(
                id = imageId,
                imageId = imageId,
                isDeployed = True,
                is_rBuilderImage = False,
                shortName = imageName,
                productName = imageName,
                longName = imageName,
                cloudName = self.cloudName,
                cloudAlias = cloudAlias)
            img.opaqueId = self._getLinkRel(image, 'self')
            ret.append(img)
        return ret

    @classmethod
    def _getLinkRel(cls, obj, rel):
        for link in obj.links:
            if link['rel'] == rel:
                return link['href']
        return None

    def startVm(self, name, imageRef, flavorRef):
        client = self.client.nova
        server = client.create(name, imageRef, flavorRef) # ipGroup, etc
