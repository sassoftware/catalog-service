#
# Copyright (c) 2011 rPath, Inc.  All Rights Reserved.
#

import os
import socket
import tempfile
import time

from lxml import etree

from conary.lib import util
from restlib import client as restclient

from catalogService import errors
from catalogService.rest import baseDriver
from catalogService.rest.models import instances

import vcmodels as Models

class VCloudClient(baseDriver.BaseDriver):
    cloudType = 'vcloud'
    configurationDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>vCloud Configuration</displayName>
    <descriptions>
      <desc>Configure VMware vCloud</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>serverName</name>
      <descriptions>
        <desc>Server Address</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/serverName.html'/>
    </field>
    <field>
      <name>port</name>
      <descriptions>
        <desc>Server Port</desc>
      </descriptions>
      <type>int</type>
      <required>true</required>
      <default>443</default>
      <help href='configuration/serverPort.html'/>
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
      <name>organization</name>
      <descriptions>
        <desc>Organization</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/organization.html'/>
    </field>
  </dataFields>
</descriptor>"""

    credentialsDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>vCloud User Credentials</displayName>
    <descriptions>
      <desc>User Credentials for vCloud</desc>
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
    RBUILDER_BUILD_TYPE = 'VMWARE_ESX_IMAGE'
    OVF_PREFERRENCE_LIST = [ '.ova', ]

    @classmethod
    def getCloudNameFromDescriptorData(cls, descriptorData):
        serverName = descriptorData.getField('serverName')
        organization = descriptorData.getField('organization')
        return "%s-%s" % (serverName, organization)

    def _getVCloudClient(self, cloudConfig):
        port = cloudConfig.get('port', 443)
        serverName = cloudConfig['serverName']
        if port == 443:
            url = "https://%s/api/v1.0/login" % serverName
        else:
            url = "https://%s:%s/api/1.0/login" % (serverName, port)
        rcli = RestClient(url)
        return rcli

    def drvVerifyCloudConfiguration(self, config):
        rcli = self._getVCloudClient(config)
        return rcli.verify()

    def drvCreateCloudClient(self, credentials):
        cloudConfig = self.getTargetConfiguration()
        rcli = self._getVCloudClient(cloudConfig)
        rcli.setCredentials(cloudConfig['organization'],
            credentials['username'], credentials['password'])
        # Do the actual login
        rcli.login()
        return rcli

    @classmethod
    def _id(cls, href, prefix):
        return "%s-%s" % (prefix, os.path.basename(href))

    def drvPopulateLaunchDescriptor(self, descr):
        descr.setDisplayName("VMware vCloud Launch Parameters")
        descr.addDescription("VMware vCloud Launch Parameters")
        self.drvLaunchDescriptorCommonFields(descr)

        client = self.client
        vdcs = list(client.iterVdcs())
        dataCenters = []
        networksMap = {}
        # self._id makes the resulting reference a bit more explicit,
        # but we need to map networks based on it too
        for vdc in vdcs:
            vdcKey = self._id(vdc.href, 'vdc')
            dataCenters.append(
                descr.ValueWithDescription(vdcKey, descriptions=vdc.name))
            nm = networksMap[vdcKey] = []
            for network in client.iterNetworksForVdc(vdc):
                nwKey = self._id(network.href, 'network')
                nm.append(descr.ValueWithDescription(nwKey,
                    descriptions=network.name))
        catalogs = [
            descr.ValueWithDescription(item[1], descriptions=item[0])
                for item in sorted((x.name, self._id(x.href, 'catalog'))
                    for x in client.iterCatalogs()) ]
        descr.addDataField('catalog',
                           descriptions = 'Catalog',
                           required = True,
                           help = [
                               ('launch/catalog.html', None)
                           ],
                           type = descr.EnumeratedType(catalogs),
                           default=catalogs[0].key,
                           readonly=True,
                           )
        descr.addDataField('dataCenter',
                           descriptions = 'Data Center',
                           required = True,
                           help = [
                               ('launch/dataCenter.html', None)
                           ],
                           type = descr.EnumeratedType(dataCenters),
                           default=dataCenters[0].key,
                           readonly=True,
                           )
        for vdcKey, networks in networksMap.items():
            networkKey = 'network-' + vdcKey
            descr.addDataField(networkKey,
                               descriptions = 'Network',
                               required = True,
                               help = [
                                   ('launch/network.html', None)
                               ],
                               type = descr.EnumeratedType(networks),
                               default=networks[0].key,
                               readonly=True,
                               conditional = descr.Conditional(
                                    fieldName='dataCenter',
                                    operator='eq',
                                    fieldValue=vdcKey)
                               )
        return descr

    def getImagesFromTarget(self, imageIds):
        cloudAlias = self.getCloudAlias()
        imagesMap = dict(
            self._iterResourceEntities(RestClient.TYPES.vAppTemplate))
        ret = []
        for imageId, image in imagesMap.iteritems():
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
            img.opaqueId = image.href
            ret.append(img)
        return ret

    def drvGetInstance(self, instanceId):
        ret = self.drvGetInstances([instanceId])
        if not ret:
            raise errors.HttpNotFound()
        return ret[0]

    def drvGetInstances(self, instanceIds):
        cloudAlias = self.getCloudAlias()
        if instanceIds:
            idFilter = set(instanceIds)
        else:
            idFilter = None
        uqInstList = sorted(set(self._iterVms(idFilter=idFilter)))
        instanceList = instances.BaseInstances()
        for instanceId, (vapp, vm) in uqInstList:
            inst = self._newInstance(instanceId, vm, cloudAlias)
            instanceList.append(inst)
        return instanceList

    def launchInstanceProcess(self, job, image, auth, **launchParams):
        ppop = launchParams.pop
        imageId = ppop('imageId')
        instanceName = ppop('instanceName')
        instanceDescription = ppop('instanceDescription')
        dataCenterRef = ppop('dataCenter')
        catalogRef = ppop('catalog')
        networkRef = ppop('network-%s' % dataCenterRef)

        vappTemplateName = 'vapp-template-' + image.getBaseFileName()
        vappTemplateDescription = vappTemplateName

        dataCenter = self._getVdc(dataCenterRef)
        catalog = self._getCatalog(catalogRef)
        network = self._getNetworkFromVdc(dataCenter, networkRef)

        if not image.getIsDeployed():
            vappTemplateRef = self._deployImage(job, image, auth,
                vappTemplateName, vappTemplateDescription, dataCenter, catalog)
        else:
            # Since we're bypassing _getTemplatesFromInventory, none of the
            # images should be marked as deployed for ESX targets
            vappTemplateRef = getattr(image, 'opaqueId')

        vapp = self._instantiateVAppTemplate(job, instanceName,
            instanceDescription, dataCenter, vappTemplateRef, network)

        vapp = self._renameVms(job, vapp, instanceName, instanceDescription)

        try:
            self._attachCredentials(job, instanceName, vapp, dataCenter,
                catalog)
        except Exception, e:
            self.log_exception("Exception attaching credentials: %s" % e)
        self._msg(job, 'Launching')
        vapp = self._startVApp(vapp)
        self._msg(job, 'Instance launched')
        vmList = [ x[0] for x in self._iterVmsInVapp(vapp) ]
        return vmList

    getImageIdFromMintImage = baseDriver.BaseDriver._getImageIdFromMintImage_local

    def _renameVms(self, job, vapp, instanceName, instanceDescription):
        """
        If the vapp has only one vm, we want to change its nmae to match the
        name of the vapp, as specified by the user
        """
        if not vapp.Children or not vapp.Children.Vm:
            return vapp
        vmList = vapp.Children.Vm
        if len(vmList) != 1:
            return vapp
        vm = vmList[0]
        self._msg(job, 'Renaming vm: %s -> %s' % (vm.name, instanceName))
        self.client.renameVm(vm, instanceName, instanceDescription)
        return vapp

    def _getMintImagesByType(self, imageType):
        # start with the most general build type
        mintImages = self.db.imageMgr.getAllImagesByType(self.RBUILDER_BUILD_TYPE)
        # Prefer ova (ovf 1.0)
        mintImagesByBuildId = {}
        for mintImage in mintImages:
            files = self._getPreferredOvfImage(mintImage['files'])
            if not files:
                # Could not find an ova file. Ignore this image
                continue
            mintImage['files'] = files
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

    def _getVdc(self, ref):
        return self._getResourceRef(ref, self.client._vdcs)

    def _getCatalog(self, ref):
        return self._getResourceRef(ref, self.client._catalogs)

    def _getNetworkFromVdc(self, vdc, ref):
        networks = self.client.iterNetworksForVdc(vdc)
        return self._getResourceRef(ref, networks)

    def _getResourceRef(self, longRef, resourceIter):
        # Take out the leading vdc- or catalog- part
        ref = longRef.split('-', 1)[1]
        for res in resourceIter:
            if os.path.basename(res.href) == ref:
                return res
        raise RuntimeError("Unable to find resource %s" % longRef)


    def _deployImage(self, job, image, auth, vappTemplateName,
            vappTemplateDescription, dataCenter, catalog):

        logger = lambda *x: self._msg(job, *x)

        self._msg(job, 'Downloading image')
        tmpDir = tempfile.mkdtemp(prefix="vcloud-download-")
        try:
            path = self._downloadImage(image, tmpDir, auth = auth)
        except errors.CatalogError:
            util.rmtree(tmpDir, ignore_errors=True)
            raise

        vappTemplateName = self._findUniqueName(catalog, vappTemplateName)
        # FIXME: make sure that there isn't something in the way on
        # the data store

        archive = self.Archive(path, logger)
        archive.extract()
        self._msg(job, 'Uploading image to VMware')
        try:
            vapp = self.uploadVAppTemplate(job, vappTemplateName,
                vappTemplateDescription, archive, dataCenter, catalog)

            self.db.targetMgr.linkTargetImageToImage(self.cloudType,
                self.cloudName, image._fileId, self._idFromHref(vapp.href))
            return vapp.href
        finally:
            # clean up our mess
            util.rmtree(tmpDir, ignore_errors=True)

        pass

    def _findUniqueName(self, catalog, vappTemplateName):
        return vappTemplateName

    def _instantiateVAppTemplate(self, job, vappName, vappDescription,
            vdc, vappTemplateRef, network, callback=None):
        if callback is None:
            callback = lambda: self._msg(job, "Waiting for task to finish")
        cli = self.client
        vappRef = cli.instantiateVAppTemplate(self._loggerFactory(job),
            vappName, vappDescription,
            vdc.href, vappTemplateRef, network.href, callback=callback)
        return vappRef

    def _startVApp(self, vappRef):
        vapp = self.client.refreshResource(vappRef)
        return vapp

    def _attachCredentials(self, job, instanceName, vapp, dataCenter, catalog):
        return vapp

    def _iterResourceEntities(self, resourceEntityType):
        cli = self.client
        for link in cli.iterVdcs():
            vdc = cli.browseVdc(link)
            for entity in vdc.ResourceEntities:
                if entity.type != resourceEntityType:
                    continue
                id_ = self._idFromHref(entity.href)
                yield id_, entity

    def _iterVms(self, idFilter=None):
        cli = self.client
        for _, vapp in self._iterResourceEntities(RestClient.TYPES.vApp):
            vapp = cli.refreshResource(vapp)
            for id_, vm in self._iterVmsInVapp(vapp, idFilter=idFilter):
                yield id_, (vapp, vm)

    def _iterVmsInVapp(self, vapp, idFilter=None):
        if vapp.Children is None:
            vmList = []
        else:
            vmList = vapp.Children.Vm
        for vm in vmList:
            id_ = self._idFromHref(vm.href)
            if idFilter is None or id_ in idFilter:
                yield id_, vm

    def _newInstance(self, instanceId, instance, cloudAlias):
        instanceName = instance.name
        instanceDescription = instance.getDescription()
        state = Models.Status.Text.state[instance.getStatus()]
        return self._nodeFactory.newInstance(
                id = instanceId,
                instanceName = instanceName,
                instanceDescription = instanceDescription,
                instanceId = instanceId,
                reservationId = instanceId,
                cloudName = self.cloudName,
                cloudAlias = cloudAlias,
                state = state,)

    @classmethod
    def _idFromHref(cls, href):
        # We take the last part of the URL only. This works well in
        # general where IDs look like http://.../api/v1.0/vApp/vapp-1836764865
        id_ = os.path.basename(href)
        return id_

    def uploadVAppTemplate(self, job, name, description, archive, vdc, catalog):
        cli = self.client

        fileExtensions = [ '.ovf' ]
        vmFiles = list(archive.iterFileWithExtensions(fileExtensions))
        if not vmFiles:
            raise RuntimeError("No file(s) found: %s" %
                ', '.join("*%s" % x for x in fileExtensions))
        ovfFileMember = vmFiles[0]
        archive.baseDir = os.path.dirname(ovfFileMember.name)
        ovfFileObj = archive.extractfile(ovfFileMember)

        self._msg(job, 'Creating vApp template')
        vapp = cli.uploadVAppTemplate(name, description, vdc.href)
        # Find the path for the OVF descriptor
        cli.uploadOvfDescriptor(vapp, ovfFileObj)
        cli.waitForOvfDescriptorUpload(job, vapp, self._msg)

        # Refresh vapp, to notice that the ovf file was already uploaded
        vapp = cli.refreshResource(vapp)
        # Upload the rest of files
        self._refreshLastCalled = 0
        cli.uploadVAppFiles(job, vapp, archive,
            callbackFactory=self._callbackFactory,
            statusCallback=self._statusCallback)
        while 1:
            vapp = cli.refreshResource(vapp)
            if vapp.getStatus() == Models.Status.Code.POWERED_OFF:
                break
            self._msg(job, "Waiting for powered off status")
            time.sleep(cli.TIMEOUT_VAPP_INSTANTIATED)
        catalogItemsHref = catalog.href + '/catalogItems'
        cli.addVappTemplateToCatalog(self._loggerFactory(job),
            name, description, vapp.href, catalogItemsHref)
        return vapp

    def _loggerFactory(self, job):
        return lambda *args: self._msg(job, *args)

    def _callbackFactory(self, vapp, job, url, fileSize):
        fileName = os.path.basename(url)
        def cb(total, rate):
            self._msg(job, "%s: transferred %4.1f%% (%d/%d)" % (
                fileName, total * 100.0 / fileSize, total, fileSize))
            now = time.time()
            if self._refreshLastCalled + 10 < now:
                vcTransferred, vcTot = self._statusCallback(vapp, job, url)
                if vcTransferred is None or vcTot is None:
                    return
                self._msg(job, "%s: vCloud status: %4.1f%% (%d/%d)" % (
                    fileName, vcTransferred * 100.0 / vcTot,
                    vcTransferred, vcTot))
                self._refreshLastCalled = now
        return cb

    def _statusCallback(self, vapp, job, url):
        vcTransferred, vcTot = self._getUpstreamUploadStatus(vapp, url)
        if vcTransferred is None or vcTot is None:
            return None, None
        return vcTransferred, vcTot

    def _getUpstreamUploadStatus(self, vapp, url):
        vapp = self.client.refreshResource(vapp)
        if not vapp.Files:
            return None, None
        for fobj in vapp.Files:
            if fobj.Link[0].href != url:
                continue
            return fobj.getBytesTransferred(), fobj.getSize()
        return None, None


class RestClient(restclient.Client):
    _nsmap = dict(vc='http://www.vmware.com/vcloud/v1')
    class TYPES(object):
        vdc = "application/vnd.vmware.vcloud.vdc+xml"
        catalog = "application/vnd.vmware.vcloud.catalog+xml"
        vApp = "application/vnd.vmware.vcloud.vApp+xml"
        vAppTemplate = "application/vnd.vmware.vcloud.vAppTemplate+xml"
        catalogItem = "application/vnd.vmware.vcloud.catalogItem+xml"
        uploadVAppTemplateParams = "application/vnd.vmware.vcloud.uploadVAppTemplateParams+xml"
        instantiateVAppTemplateParams = "application/vnd.vmware.vcloud.instantiateVAppTemplateParams+xml"
        network = "application/vnd.vmware.vcloud.network+xml"

    TIMEOUT_VAPP_INSTANTIATED = 2
    TIMEOUT_OVF_DESCRIPTOR_PROCESSED = 2


    def connect(self):
        try:
            return restclient.Client.connect(self)
        except socket.error:
            # XXX need to raise a meaningful exception
            raise

    def verify(self):
        self.path = '/api/versions'
        try:
            self.connect()
        except restclient.ConnectionError:
            return False
        resp = self.request("GET")
        tree = etree.parse(resp)
        paths = tree.xpath('/v:SupportedVersions/v:VersionInfo/v:LoginUrl',
            namespaces=dict(v="http://www.vmware.com/vcloud/versions"))
        if not paths:
            return False
        return self._pathFromUrl(paths[0].text)

    def login(self):
        # We only support 1.0
        self.path = '/api/v1.0/login'
        self.connect()
        self.setUserPassword("%s@%s" % (self._username, self._organization),
            self._password)
        resp = self.request("POST")
        auth = resp.getheader('x-vcloud-authorization')
        self.headers.update({'x-vcloud-authorization' : auth})
        self.setUserPassword(None, None)

        tree = etree.parse(resp)
        # Find href for this org
        paths = tree.xpath('/vc:OrgList/vc:Org/@href',
            namespaces = self._nsmap)
        self._orgPath = self._pathFromUrl(paths)
        # Browse the org
        self.path = self._orgPath
        resp = self.request("GET")
        data = resp.read()
        org = Models.handler.parseString(data)
        self._catalogs = set(x for x in org.Link
            if x.getType() == self.TYPES.catalog)
        # Some of the VDCs may be disabled, so we ignore those
        self._vdcs = []
        vdcLinks = [ x for x in org.Link if x.getType() == self.TYPES.vdc ]
        self._networkMap = {}
        for vdcLink in vdcLinks:
            vdc = self.browseVdc(vdcLink)
            if not vdc.getIsEnabled():
                continue
            self._vdcs.append(vdcLink)
            self._networkMap[vdcLink] = [ x for x in vdc.AvailableNetworks ]

    @classmethod
    def _buildXpath(cls, tree, path, attribute, **conditions):
        # Start building the xpath tree
        nsprefix = cls._nsmap.keys()[0]
        nodepaths = '/'.join('%s:%s' % (nsprefix, x) for x in path.split('.'))
        conditions = ' and '.join('@%s="%s"' % (x, y)
            for (x, y) in conditions.items())
        if conditions:
            xp = "/%s[%s]/@%s" % (nodepaths, conditions, attribute)
        else:
            xp = "/%s/@%s" % (nodepaths, attribute)
        paths = tree.xpath(xp, namespaces=cls._nsmap)
        return paths

    @classmethod
    def _pathFromUrl(cls, pathList):
        if not pathList:
            return None
        if isinstance(pathList, list):
            path = pathList[0]
        else:
            path = pathList
        return util.urlSplit(path)[5]

    def setCredentials(self, organization, username, password):
        self._organization = organization
        self._username = username
        self._password = password

    def logout(self):
        if 'x-vcloud-authorization' not in self.headers:
            return
        self.path = '/api/v1.0/logout'
        self.connect()
        try:
            self.request("POST")
        except restclient.ResponseError:
            pass
        self.headers.pop('x-vcloud-authorization', None)

    def iterCatalogs(self):
        return iter(self._catalogs)

    def iterVdcs(self):
        return iter(self._vdcs)

    def iterNetworksForVdc(self, vdc):
        return iter(self._networkMap[vdc])

    def getNetworkByName(self, name):
        for vdc, networks in self._networkMap.items():
            for network in networks:
                if network.name == name:
                    return network
        return None

    def getVdcByName(self, name):
        for vdc in self._vdcs:
            if vdc.name == name:
                return vdc
        return None

    def getCatalogByName(self, name):
        for catalog in self._catalogs:
            if catalog.name == name:
                return catalog
        return None

    def browseCatalog(self, link):
        self.path = self._pathFromUrl(link.href)
        self.connect()
        resp = self.request("GET")
        data = resp.read()
        return Models.handler.parseString(data)

    def browseVdc(self, link):
        self.path = self._pathFromUrl(link.href)
        self.connect()
        resp = self.request("GET")
        data = resp.read()
        return Models.handler.parseString(data)

    def uploadVAppTemplate(self, name, description, vdcHref):
        m = Models.VAppTemplateParams()
        m.name = name
        m.setDescription(description)
        m.setManifestRequired(False)
        body = Models.handler.toXml(m)
        self.path = "%s/action/uploadVAppTemplate" % self._pathFromUrl(vdcHref)
        self.connect()
        headers = { 'Content-Type' : self.TYPES.uploadVAppTemplateParams }

        try:
            self.request("POST", body=body, headers=headers)
        except restclient.ResponseError, e:
            if e.status != 201:
                raise
        vapp = Models.handler.parseString(e.contents)
        return vapp

    def uploadOvfDescriptor(self, vapp, ovfFileObj):
        self.path = self._pathFromUrl(vapp.Files[0].Link[0].href)
        self.connect()
        self.request("PUT", body=ovfFileObj.read())

    def waitForOvfDescriptorUpload(self, job, vapp, _msg):
        for i in range(10):
            vapp = self.refreshResource(vapp)
            if vapp.Tasks and vapp.Tasks[0].status == "error":
                _msg(job, "Error uploading vApp template: %s" %
                    vapp.Tasks[0].Error.message)
                raise RuntimeError(vapp.Tasks[0].Error.message)
            if vapp.getOvfDescriptorUploaded():
                _msg(job, 'OVF descriptor uploaded')
                break
            _msg(job, 'Waiting for OVF descriptor to be processed')
            time.sleep(self.TIMEOUT_OVF_DESCRIPTOR_PROCESSED)
        else:
            raise RuntimeError("Timeout waiting for OVF descriptor to be processed")

    def refreshResource(self, vapp):
        self.path = self._pathFromUrl(vapp.href)
        self.connect()
        resp = self.request("GET")
        data = resp.read()
        return Models.handler.parseString(data)

    def uploadVAppFiles(self, job, vapp, archive, callbackFactory,
            statusCallback):
        archiveNameMap = dict((x.name, x) for x in archive)
        for fobj in vapp.Files:
            if fobj.getSize() == fobj.getBytesTransferred():
                # This is uploaded already
                continue
            fileName = os.path.basename(fobj.Link[0].href)

            filePathInArchive = os.path.join(archive.baseDir, fileName)
            member = archiveNameMap[filePathInArchive]
            fileObj = archive.extractfile(member)
            url = fobj.Link[0].href
            self.uploadVAppFile(vapp, job, url, fileObj,
                callback=callbackFactory(vapp, job, url, fobj.getSize()),
                statusCallback=statusCallback)

    def renameVm(self, vm, vmName, vmDescription):
        # Find upload link
        links = [ x for x in vm.Link if x.rel == 'edit' ]
        if not links:
            return
        url = links[0].href
        self.path = self._pathFromUrl(url)
        self.connect()
        resource = Models.Vm(description=vmDescription)
        resource.name = vmName

        body = Models.handler.toXml(resource)
        headers = { 'Content-Type' : links[0].type}
        try:
            self.request("PUT", body=body, headers=headers)
        except restclient.ResponseError, e:
            if e.status != 202:
                raise

    def uploadVAppFile(self, vapp, job, url, fobj, callback, statusCallback):
        while 1:
            try:
                self._uploadVAppFile(job, url, fobj, callback)
            except restclient.httplib.ResponseNotReady:
                # vcloud doesn't seem capable of returning a status
                # code.
                # Wait for a few seconds, then make sure the upload
                # finished successfully
                time.sleep(2)
            vcTransferred, vcTotal = statusCallback(vapp, job, url)
            if vcTransferred == vcTotal:
                # This covers the case of both being None
                return
            # XXX FIXME: range PUT here


    def _uploadVAppFile(self, job, url, fobj, callback):
        self.path = self._pathFromUrl(url)
        self.connect()
        self.request("PUT", body=fobj, callback=callback)

    def _retryForUniqueness(self, logger, suggestedName, function, *args, **kwargs):
        """
        To avoid race conditions, we need to sometimes retry if someone else
        used the same name.
        We're running 'function' with resourceName as the first argument until
        we no longer get a duplicate.
        """
        suffix = None
        # Look for a unique name
        while 1:
            if suffix is None:
                resourceName = suggestedName
                suffix = 0
            else:
                resourceName = "%s-%s" % (suggestedName, suffix)
                suffix += 1
            try:
                ret = function(resourceName, *args, **kwargs)
                logger("Resource name: %s" % resourceName)
                return ret
            except restclient.ResponseError, e:
                if e.status == 400:
                    error = Models.handler.parseString(e.contents)
                    if error.minorErrorCode == 'DUPLICATE_NAME':
                        # Naming conflict. Try again with a different name
                        logger("Duplicate name %s" % resourceName)
                        continue
                raise

    def addVappTemplateToCatalog(self, logger, name, description,
            vappTemplateHref, catalogItemsHref):
        return self._retryForUniqueness(logger, name,
            self._addVappTemplateToCatalog, description,
            vappTemplateHref, catalogItemsHref)

    def _addVappTemplateToCatalog(self, name, description,
            vappTemplateHref, catalogItemsHref):
        ent = Models.Entity()
        ent.href = vappTemplateHref
        m = Models.CatalogItem()
        m.name = name
        m.setDescription(description)
        m.Entity = ent
        body = Models.handler.toXml(m)
        self.path = self._pathFromUrl(catalogItemsHref)
        self.connect()
        headers = { 'Content-Type' : self.TYPES.catalogItem }

        try:
            self.request("POST", body=body, headers=headers)
        except restclient.ResponseError, e:
            if e.status != 201:
                raise
        catalogItem = Models.handler.parseString(e.contents)
        return catalogItem

    def instantiateVAppTemplate(self, logger, name, description,
            vdcRef, vappTemplateRef, networkRef, callback=None):
        return self._retryForUniqueness(logger, name,
            self._instantiateVAppTemplate, description,
            vdcRef, vappTemplateRef, networkRef, callback=callback)

    def _instantiateVAppTemplate(self, name, description,
            vdcRef, vappTemplateRef, networkRef, callback=None):
        m = Models.InstantiateVAppTemplateParams(Description=description)
        m.name = name
        m.setDeploy(True)
        m.setPowerOn(False)

        source = Models.Source(href=vappTemplateRef)
        m.setSource(source)

        iparams = Models.InstantiationParams()
        m.setInstantiationParams(iparams)

        nwsect = Models.NetworkConfigSection()
        iparams.setNetworkConfigSection(nwsect)

        info = Models.OVFInfo("Configuration parameters for logical networks")
        nwsect.setInfo(info)

        nwconf = Models.NetworkConfig(networkName='Network Name')
        nwsect.setNetworkConfig(nwconf)

        nwc = Models.NetworkConfiguration()
        nwconf.setConfiguration(nwc)

        pnet = Models.ParentNetwork(href=networkRef)
        nwc.setParentNetwork(pnet)
        nwc.setFenceMode('bridged')

        body = Models.handler.toXml(m)
        self.path = "%s/action/instantiateVAppTemplate" % self._pathFromUrl(vdcRef)
        self.connect()
        headers = { 'Content-Type' : self.TYPES.instantiateVAppTemplateParams}

        try:
            self.request("POST", body=body, headers=headers)
        except restclient.ResponseError, e:
            if e.status != 201:
                raise
        vapp = Models.handler.parseString(e.contents)
        vapp = self.waitForTask(vapp, [ 'queued', 'running' ], callback=callback)
        return vapp

    def waitForTask(self, vapp, inProgressStates, callback=None):
        while 1:
            tasks = vapp.getTasks()
            if not tasks or tasks[0].status not in inProgressStates:
                return vapp
            if callback:
                callback()
            time.sleep(2)
            vapp = self.refreshResource(vapp)

    def deleteEntity(self, entity):
        self.path = self._pathFromUrl(entity.href)
        try:
            self.request("DELETE")
        except restclient.ResponseError, e:
            if e.status != 202:
                raise
