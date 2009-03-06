
import os
import signal
import socket
import tempfile
import time
import urllib
import urllib2
import httplib

from conary.lib import util

from catalogService import clouds
from catalogService import errors
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

class StreamingRequestMixIn(object):
    def _send_request_mix_in(self, parentClass, method, url, body, headers):
        if not hasattr(body, 'read') and not hasattr(body, 'seek'):
            # Not a file-like object
            return parentClass._send_request(self, method, url, body,
                headers)
        # Compute body length
        pos = body.tell()
        body.seek(0, 2)
        contentLength = body.tell() - pos
        body.seek(pos)
        headers['Content-Length'] = str(contentLength)
        # Send the request with no body
        parentClass._send_request(self, method, url, None, headers)
        # Now stream the body
        while 1:
            buf = body.read(16384)
            if not buf:
                break
            self.send(buf)

class HTTPConnection(httplib.HTTPConnection, StreamingRequestMixIn):
    def _send_request(self, method, url, body, headers):
        return self._send_request_mix_in(httplib.HTTPConnection,
            method, url, body, headers)

class HTTPSConnection(httplib.HTTPSConnection, StreamingRequestMixIn):
    def _send_request(self, method, url, body, headers):
        return self._send_request_mix_in(httplib.HTTPSConnection,
            method, url, body, headers)

class HTTPHandler(urllib2.HTTPHandler):
    def http_open(self, req):
        return self.do_open(HTTPConnection, req)

class HTTPSHandler(urllib2.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(HTTPSConnection, req)

class Request(urllib2.Request):
    def get_method(self):
        if self.has_data():
            return "PUT"
        else:
            return "GET"

    def get_host(self):
        ret = urllib2.Request.get_host(self)
        userpass, hostport = urllib.splituser(ret)
        if userpass:
            userpass = urllib2.base64.b64encode(userpass)
            self.unredirected_hdrs['Authorization'] = 'Basic %s' % userpass

        return hostport

class UploadClient(object):
    requestClass = Request
    def __init__(self, url, headers = None):
        self.url = url
        self.headers = headers or {}

    def getOpener(self):
        return urllib2.build_opener(HTTPHandler, HTTPSHandler)

    def request(self, data, headers = None):
        headers = self.headers.copy()
        # Dummy Content-Length
        headers['Content-Length'] = '0'
        headers['Content-Type'] = 'application/octet-stream'
        # Give it a chance to override Content-Type
        headers.update(headers or {})
        req = self.requestClass(self.url, data, headers = headers)
        resp = self.getOpener().open(req)
        return resp

class XenEntClient(baseDriver.BaseDriver, storage_mixin.StorageMixin):
    Image = XenEnt_Image

    cloudType = 'xen-enterprise'

    _credNameMap = [
        ('username', 'username'),
        ('password', 'password'),
    ]

    configurationDescriptorXmlData = _configurationDescriptorXmlData
    credentialsDescriptorXmlData = _credentialsDescriptorXmlData

    XenSessionClass = None

    _XmlRpcWrapper = "<methodResponse><params><param>%s</param></params></methodResponse>"

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
            raise errors.PermissionDenied(message = "User %s: %s" % (
                e.details[1], e.details[2]))
        keyPrefix = "%s/%s" % (self._sanitizeKey(self.cloudName),
                               self._sanitizeKey(self.userId))
        self._instanceStore = self._getInstanceStore(keyPrefix)
        return sess

    def drvVerifyCloudConfiguration(self, config):
        return

    @classmethod
    def _getCloudNameFromConfig(cls, config):
        return config['name']

    @classmethod
    def _getCloudNameFromDescriptorData(cls, descriptorData):
        return descriptorData.getField('name')

    def isValidCloudName(self, cloudName):
        cloudConfig = self._getCloudConfiguration(cloudName)
        return bool(cloudConfig)

    def _createCloudNode(self, cloudConfig):
        cld = self._nodeFactory.newCloud(cloudName = cloudConfig['name'],
                         description = cloudConfig['description'],
                         cloudAlias = cloudConfig['alias'])
        return cld

    def drvLaunchInstance(self, descriptorData, requestIPAddress):
        client = self.client
        getField = descriptorData.getField

        cloudConfig = self.drvGetCloudConfiguration()

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
                        srUuid = getField('storageRepository'),
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

        synthesizedInstIds = [ x.getInstanceId() for x in runningInsts
            if len(x.getInstanceId()) != 36 ]
        realInstIds =  [ x.getInstanceId() for x in runningInsts
            if len(x.getInstanceId()) == 36 ]

        for instId in realInstIds:
            instRef = self.client.xenapi.VM.get_by_uuid(instId)
            client.xenapi.VM.clean_shutdown(instRef)

        self._killRunningProcessesForInstances(synthesizedInstIds)

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
                if imageId is None or imageId not in imagesById:
                    continue
                newImageList.append(imagesById[imageId])
            imageList = newImageList
        return imageList

    def drvPopulateLaunchDescriptor(self, descr):
        descr.setDisplayName("Xen Enterprise Launch Parameters")
        descr.addDescription("Xen Enterprise Launch Parameters")
        descr.addDataField("instanceName",
            descriptions = "Instance Name",
            type = "str",
            help = [
                ("launch/instanceName.html", None)
            ],
            constraints = dict(constraintName = 'length',
                               value = 32))
        descr.addDataField("instanceDescription",
            descriptions = "Instance Description",
            type = "str",
            help = [
                ("launch/instanceDescription.html", None)
            ],
            constraints = dict(constraintName = 'length',
                               value = 128))
        storageRepos = self._getStorageRepos()
        descr.addDataField("storageRepository",
            descriptions = "Storage Repository",
            required = True,
            help = [
                ("launch/storageRepository.html", None)
            ],
            type = descriptor.EnumeratedType(
                descriptor.ValueWithDescription(x[0], descriptions = x[1][0])
                for x in storageRepos),
            default = storageRepos[0][0],
            )

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

    def _getInstanceLaunchTime(self, vmRef, vm):
        if vm['power_state'] != 'Running' or vm['is_control_domain']:
            # Control domains always report 0
            return None
        vmMetricsRef = vm['metrics']
        metrics = self.client.xenapi.VM_metrics.get_record(vmMetricsRef)
        # Apparently the string sent back is not really XML-RPC conformant, so
        # we parse the value ourselves
        startTime = metrics['start_time'].value
        try:
            startTime = time.strptime(startTime, "%Y%m%dT%H:%M:%SZ")
        except ValueError:
            # We couldn't parse the value.
            return None
        # time.mktime will produce a local time out of a Zulu time, so we need
        # to adjust it with the local timezone offset
        return int(time.mktime(startTime) - time.timezone)

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
                launchTime = None,
                cloudName = self.cloudName,
                cloudAlias = cloudAlias)

            instanceList.append(inst)

        for opaqueId, vm in instMap.items():
            if vm['is_a_template']:
                continue

            # Try to grab the guest metrics, if available
            publicIpAddr = None
            guestMetricsRef = vm['guest_metrics']
            if guestMetricsRef != 'OpaqueRef:NULL':
                networks = self.client.xenapi.VM_guest_metrics.get_networks(
                    guestMetricsRef)
                # XXX we are assuming eth0
                publicIpAddr = networks.get('0/ip')

            instanceId = vm['uuid']
            imageId = vm['other_config'].get('catalog-client-checksum')
            inst = self._nodeFactory.newInstance(id = instanceId,
                imageId = imageId or 'UNKNOWN',
                instanceId = instanceId,
                instanceName = vm['name_label'],
                instanceDescription = vm['name_description'],
                reservationId = vm['uuid'],
                dnsName = 'UNKNOWN',
                publicDnsName = publicIpAddr,
                privateDnsName = 'UNKNOWN',
                state = vm['power_state'],
                launchTime = self._getInstanceLaunchTime(opaqueId, vm),
                cloudName = self.cloudName,
                cloudAlias = cloudAlias)

            instanceList.append(inst)
        if instanceIds:
            instanceIds = set(os.path.basename(x) for x in instanceIds)
            instanceList = [ x for x in instanceList
                if x.getInstanceId() in instanceIds ]
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

    def _putImage(self, vmFile, srUuid, taskRef):
        srRef = self.client.xenapi.SR.get_by_uuid(srUuid)
        urlTemplate = 'http://%s:%s@%s/import?task_id=%s&sr_id=%s'

        cloudConfig = self.drvGetCloudConfiguration()
        cloudName = cloudConfig['name']
        creds = self.credentials
        username, password = creds['username'], creds['password']
        client = UploadClient(urlTemplate % (username, password, cloudName,
            taskRef, srRef))
        resp = client.request(file(vmFile))
        # The server does not send any useful information back. Close the
        # request and fetch the status from the task
        resp.close()
        task = self.client.xenapi.task.get_record(taskRef)
        if task.get('status') != 'success':
            errorInfo = task.get('error_info', '')
            raise errors.CatalogError("Unable to upload image %s: %s" %
                vmFile, errorInfo)
        # Wrap the pseudo-XMLRPC response
        params = XenAPI.xmlrpclib.loads(self._XmlRpcWrapper %
            task['result'])[0]
        reflist = params[0]
        if len(reflist) < 1:
            raise errors.CatalogError("Unable to publish image, no results found")
        vmRef = reflist[0]
        # Make it a template
        self.client.xenapi.VM.set_is_a_template(vmRef, True)

        vmUuid = self.client.xenapi.VM.get_uuid(vmRef)
        return vmRef, vmUuid

    def _importImage(self, image, vmFile, srUuid):
        checksum = image.getImageId()
        taskRef = self.client.xenapi.task.create("Import of %s" % checksum,
            "Import of %s" % checksum)
        vmRef, vmUuid = self._putImage(vmFile, srUuid, taskRef)
        self._setVmMetadata(vmRef, checksum = checksum)
        return vmRef, vmUuid

    def _deployImage(self, instanceId, image, srUuid):
        tmpDir = tempfile.mkdtemp(prefix="xenent-download-")
        try:
            try:
                downloadUrl = image.getDownloadUrl()
                checksum = image.getImageId()

                self._setState(instanceId, 'Downloading image')
                path = self._downloadImage(image, tmpDir, extension = '.xva')

                self._setState(instanceId, 'Importing image')
                templRef, templUuid = self._importImage(image, path, srUuid)

                image.setImageId(templUuid)
                image.setInternalTargetId(templUuid)
            except:
                self._setState(instanceId, 'Error')
                raise
        finally:
            util.rmtree(tmpDir)

    def _launchInstance(self, instanceId, image, instanceType, srUuid,
            instanceName, instanceDescription):
        cloudConfig = self.drvGetCloudConfiguration()
        nameLabel = image.getLongName()
        nameDescription = image.getBuildDescription()
        try:
            self._instanceStore.setPid(instanceId)
            if not image.getIsDeployed():
                self._deployImage(instanceId, image, srUuid)

            imageId = image.getInternalTargetId()

            self._setState(instanceId, 'Cloning template')
            realId = self.cloneTemplate(imageId, instanceName,
                instanceDescription)
            self._setState(instanceId, 'Launching')
            self.startVm(realId)
        finally:
            self._instanceStore.delete(instanceId)

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
                    internalTargetId = vm['uuid'],
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

    def _getInstanceTypes(self):
        ret = VWS_InstanceTypes()
        ret.extend(self._nodeFactory.newInstanceType(
                id = x, instanceTypeId = x, description = y)
            for (x, y) in VWS_InstanceTypes.idMap)
        return ret

    def _killRunningProcessesForInstances(self, synthesizedInstIds):
        # For synthesized instances, try to kill the pid
        for instId in synthesizedInstIds:
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
        return vmRef

    def startVm(self, vmRef):
        self.client.xenapi.VM.provision(vmRef)
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
        try:
            self.client.xenapi.VIF.create(vifRec)
        except Exception, e:
            if e.details[0] != 'DEVICE_ALREADY_EXISTS':
                raise

    def _setVmMetadata(self, vmRef, checksum = None,
            templateUuid = None):
        if checksum:
            self._wrapper_add_to_other_config(vmRef,
                'cloud-catalog-checksum', checksum)

        if templateUuid:
            self._wrapper_add_to_other_config(vmRef,
                'cloud-catalog-template-uuid', templateUuid)

    def _wrapper_add_to_other_config(self, vmRef, key, data):
        try:
            self.client.xenapi.VM.add_to_other_config(vmRef, key, data)
        except XenAPI.Failure, e:
            if e.details[0] != 'MAP_DUPLICATE_KEY':
                raise

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

        hCache = XenEntHostCache(self.client)

        srRecs = self.client.xenapi.SR.get_all_records()
        for k, srRec in sorted(srRecs.items(), key = lambda x: x[1]['uuid']):
            uuid = srRec['uuid']
            if not srRec['PBDs']:
                # Improperly configured SR - no PBDs
                continue
            if 'vdi_create' not in srRec['allowed_operations']:
                continue
            if uuid in uuidsFound:
                continue
            ret.append(uuid)
            srRecNameLabel = srRec['name_label']
            srRecType = srRec['type']
            if srRecType == 'lvm':
                # Grab the host name from the first PBD
                hostName = hCache.getHostNameFromPbd(srRec['PBDs'][0])
                label = "%s (%s) on %s" % (srRecNameLabel, srRecType, hostName)
            else:
                label = "%s (%s)" % (srRecNameLabel, srRecType)
            uuidsFound[uuid] = (label, srRec['name_description'])
        return [ (x, uuidsFound[x]) for x in ret if uuidsFound[x] ]

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

class XenEntHostCache(object):
    __slots__ = ['client', 'hostNameMap', 'hostRefMap']
    def __init__(self, client):
        self.client = client
        self.hostRefMap = {}
        self.hostNameMap = {}

    def getHostNameFromPbd(self, pbdRef):
        hostRef = self.client.xenapi.PBD.get_host(pbdRef)
        hostRec = self.hostRefMap.get(hostRef)
        if hostRec is not None:
            return self.hostNameMap[hostRec['address']]

        hostRec = self.hostRefMap[hostRef] = self.client.xenapi.host.get_record(hostRef)
        addr = hostRec['address']
        if addr in self.hostNameMap:
            return self.hostNameMap[addr]

        hostName = self.resolveAddress(addr)
        self.hostNameMap[addr] = hostName
        return hostName

    def resolveAddress(self, addr):
        try:
            hostName = socket.gethostbyaddr(addr)[0]
        except socket.error, e:
            if e.args[0] != 1: # Unknown host
                raise
            # Negative lookup
            hostName = addr
        return hostName

