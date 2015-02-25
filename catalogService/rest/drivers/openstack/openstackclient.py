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


import os
import time

from catalogService import errors
from catalogService.rest import baseDriver
from catalogService.rest.models import images
from catalogService.rest.models import instances

try:
    from keystoneclient.auth.identity import v2 as v2_auth
    from keystoneclient.client import Client as KeystoneClient
    from keystoneclient.session import Session as KeystoneSession
    from novaclient.v1_1.client import Client as NovaClient
    from glanceclient import Client as GlanceClient
except ImportError:
    NovaClient = None #pyflakes=ignore

class OpenStack_Image(images.BaseImage):
    "OpenStack Image"

NOVA_PORT = 5000
CATALOG_NEW_FLOATING_IP = "new floating ip-"
CATALOG_NEW_FLOATING_IP_DESC = "[New floating IP in {pool}]"

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
      <type>int</type>
      <required>true</required>
      <default>%(nova_port)s</default>
      <help href='configuration/novaPortNumber.html'/>
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
      <name>project_name</name>
      <descriptions>
        <desc>Project Name</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/project_name.html'/>
    </field>
  </dataFields>
</descriptor>""" % dict(nova_port=NOVA_PORT, )

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
    def __init__(self, keystone_client, nova_client, glance_client):
        self.keystone = keystone_client
        self.nova = nova_client
        self.glance = glance_client

class OpenStackClient(baseDriver.BaseDriver):
    Image = OpenStack_Image
    cloudType = 'openstack'

    configurationDescriptorXmlData = _configurationDescriptorXmlData
    credentialsDescriptorXmlData = _credentialsDescriptorXmlData

    RBUILDER_BUILD_TYPE = 'RAW_HD_IMAGE'

    NovaClientClass = NovaClient
    KEYSTONE_API_VERSION = '2.0'
    GLANCE_CLIENT_VERSION = '1'

    @classmethod
    def isDriverFunctional(cls):
        return cls.NovaClientClass is not None

    getImageIdFromMintImage = baseDriver.BaseDriver._getImageIdFromMintImage_local

    def drvCreateCloudClient(self, credentials):
        cloudConfig = self.getTargetConfiguration()
        server = cloudConfig['name']
        port = cloudConfig['nova_port']
        authUrl = "http://%s:%s" % (server, port)
        projectName = cloudConfig['project_name']
        try:
            session = KeystoneSession()
            keystoneCli = KeystoneClient(self.KEYSTONE_API_VERSION,
                    tenant_name=projectName,
                    auth_url=authUrl,
                    username=credentials['username'],
                    password=credentials['password'],
                    session=session)
            auth = v2_auth.Password(
                    keystoneCli.auth_url,
                    username=credentials['username'],
                    password=credentials['password'])
            session.auth = auth
            keystoneCli.authenticate()
            auth.auth_ref = keystoneCli.auth_ref
            novaCli = self.NovaClientClass(auth_token=keystoneCli.auth_token,
                    project_id=projectName,
                    auth_url=keystoneCli.auth_url,
                    session=session)
            endpoint = session.get_endpoint(service_type="image")
            glanceCli = GlanceClient(self.GLANCE_CLIENT_VERSION,
                    endpoint=endpoint,
                    project_id=projectName,
                    token=keystoneCli.auth_token,
                    session=session)
            clients = ConsolidatedClient(keystoneCli, novaCli, glanceCli)
        except Exception, e:
            raise errors.PermissionDenied(message =
                    "Error initializing client: %s" % (e, ))
        return clients

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

    def drvPopulateImageDeploymentDescriptor(self, descr, extraArgs=None):
        descr.setDisplayName("OpenStack Launch Parameters")
        descr.addDescription("OpenStack Launch Parameters")
        self.drvImageDeploymentDescriptorCommonFields(descr)
        self._imageDeploymentSpecifcDescriptorFields(descr, extraArgs=extraArgs)
        return self._drvPopulateDescriptorFromTarget(descr)

    def drvPopulateLaunchDescriptor(self, descr, extraArgs=None):
        descr.setDisplayName("OpenStack Launch Parameters")
        descr.addDescription("OpenStack Launch Parameters")
        self.drvLaunchDescriptorCommonFields(descr)
        self._launchSpecificDescriptorFields(descr, extraArgs=extraArgs)
        return self._drvPopulateDescriptorFromTarget(descr)

    def _drvPopulateDescriptorFromTarget(self, descr):
        pass

    def _launchSpecificDescriptorFields(self, descr, extraArgs=None):
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
                            )
        fpList = self._cliGetFloatingIps()
        descr.addDataField('floatingIp',
            descriptions = 'Floating IP',
            required = True,
            help = [
                ('launch/floatingIp.html', None)
            ],
            type = descr.EnumeratedType(
                descr.ValueWithDescription(x['id'], descriptions = x['label'])
                for x in fpList),
            default=fpList[0]['id'],
        )
        return descr

    def _cliGetFloatingIps(self):
        cli = self.client.nova
        pools = cli.floating_ip_pools.list()
        objs = cli.floating_ips.list()
        unassigned = [
                dict(
                    id=CATALOG_NEW_FLOATING_IP + x.name,
                    label=CATALOG_NEW_FLOATING_IP_DESC.format(pool=x.name),
                    pool=x.name)
                for x in pools ]
        for obj in objs:
            if obj.instance_id:
                continue
            unassigned.append(dict(id=obj.id,
                label= "%s in pool %s" % (obj.ip, obj.pool),
                pool=obj.pool,
                ip=obj.ip))
        unassigned.sort(key=lambda x: x.get('ip'))
        return unassigned

    def _imageDeploymentSpecifcDescriptorFields(self, descr, **kwargs):
        pass

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

    def drvGetInstances(self, instanceIds, force=False):
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
            imageId = None
            imgobj = server.image
            if imgobj:
                imageRef = self._idFromRef(imgobj['id'])
                image = imagesMap.get(imageRef)
                if image:
                    imageId = image.id
            publicDnsName = privateDnsName = None
            if server.addresses.values():
                addrList = server.addresses.values()[0]
                floatingAddrs = [ x['addr'] for x in addrList if x['OS-EXT-IPS:type'] == 'floating' ]
                fixedAddrs = [ x['addr'] for x in addrList if x['OS-EXT-IPS:type'] == 'fixed' ]
                if floatingAddrs:
                    publicDnsName = floatingAddrs[0]
                if fixedAddrs:
                    privateDnsName = fixedAddrs[0]
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

    @classmethod
    def _getServerAddressByType(cls, server, addressType):
        if not server.addresses:
            return None
        addrlist = server.addresses.get(addressType)
        if not addrlist:
            return None
        return addrlist[0]['addr']

    def getLaunchInstanceParameters(self, image, descriptorData):
        params = baseDriver.BaseDriver.getLaunchInstanceParameters(self,
            image, descriptorData)
        getField = descriptorData.getField
        srUuid = getField('storageRepository')
        params['srUuid'] = srUuid
        return params

    def deployImageProcess(self, job, image, auth, **params):
        # RCE-1751: always redeploy.
        if 0 and image.getIsDeployed():
            self._msg(job, "Image is already deployed")
            return image.getImageId()

        ppop = params.pop
        imageName = ppop('imageName')

        cloudConfig = self.getTargetConfiguration()
        nameLabel = image.getLongName()
        nameDescription = image.getBuildDescription()

        self._deployImage(job, image, auth, imageName=imageName)
        self._msg(job, 'Image deployed')
        return image.getImageId()

    def launchInstanceProcess(self, job, image, auth, **launchParams):
        ppop = launchParams.pop
        instanceName = ppop('instanceName')
        instanceDescription = ppop('instanceDescription')
        flavorRef = ppop('flavor')
        floatingIp = ppop('floatingIp')
        if floatingIp.startswith(CATALOG_NEW_FLOATING_IP):
            poolName = floatingIp[len(CATALOG_NEW_FLOATING_IP):]
            floatingIp = self.client.nova.floating_ips.create(pool=poolName)
        else:
            floatingIp = self.client.nova.floating_ips.get(floatingIp)

        cloudConfig = self.getTargetConfiguration()
        nameLabel = image.getLongName()
        nameDescription = image.getBuildDescription()

        imageName = image.getBaseFileName()

        if not image.getIsDeployed():
            imageId = self._deployImage(job, image, auth, imageName=imageName)
        else:
            imageId = getattr(image, 'opaqueId')

        job.addHistoryEntry('Launching')
        instId = self._launchInstanceOnTarget(job, instanceName, imageId,
                flavorRef, floatingIp)
        return [ instId ]

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
        return self.filterImages(imageIdsFilter, ret)

    @classmethod
    def _getLinkRelFromList(cls, list, rel):
        for link in list:
            if link['rel'] == rel:
                return link['href']
        return None

    @classmethod
    def _getLinkRel(cls, obj, rel):
        return cls._getLinkRelFromList(obj.links, rel)

    def _getImageDiskFormat(self):
        return 'raw'

    def _getImageContainerFormat(self):
        return 'bare'

    def _getImagePublic(self):
        return True

    def _importImage(self, job, imageMetadata, fileObj):
        job.addHistoryEntry('Creating image')
        glanceImage = self.client.glance.images.create(**imageMetadata)
        job.addHistoryEntry('Uploading image content')
        glanceImage.update(data=fileObj)
        return str(glanceImage.id)

    def _deployImageFromFile(self, job, image, path, *args, **kwargs):
        imageName = kwargs.get('imageName', image.getShortName())
        try:
            job.addHistoryEntry('Uncompressing image')
            logger = lambda *x: self._msg(job, *x)
            archive = baseDriver.Archive(path, logger)
            archive.extract()
            archiveMembers = list(archive)
            assert len(archiveMembers) == 1
            member = archiveMembers[0]
            fobj = archive.extractfile(member)
            job.addHistoryEntry('Importing image')
            imageDiskFormat = self._getImageDiskFormat()
            imageContainerFormat = self._getImageContainerFormat()
            imagePublic = self._getImagePublic()
            imageMetadata = {'name':imageName, 'disk_format':imageDiskFormat, 
                    'container_format':imageContainerFormat, 'is_public':imagePublic}
            imageId = self._importImage(job, imageMetadata, fobj)
        finally:
            pass
        return imageId

    def _launchInstanceOnTarget(self, job, name, imageRef, flavorRef, floatingIp):
        client = self.client.nova
        server = client.servers.create(name, imageRef, flavorRef) # ipGroup, etc
        for i in range(20):
            if server.status == 'ACTIVE':
                break
            job.addHistoryEntry('Waiting for server to become active')
            time.sleep(2*i + 1)
            server = client.servers.get(server)
        server.add_floating_ip(floatingIp)
        return str(server.id)
