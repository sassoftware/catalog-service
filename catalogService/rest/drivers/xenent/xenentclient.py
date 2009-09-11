
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

class XenEntClient(storage_mixin.StorageMixin, baseDriver.BaseDriver):
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
        return sess

    def drvVerifyCloudConfiguration(self, config):
        return

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
        imageList = self.addMintDataToImageList(imageList, 'XEN_OVA')

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
        if not storageRepos:
            # No storage repositories defined; fail
            raise errors.CatalogError("No Storage Repositories defined")
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
            startTime = self.utctime(startTime, "%Y%m%dT%H:%M:%SZ")
        except ValueError:
            # We couldn't parse the value.
            return None
        return startTime

    def drvGetInstances(self, instanceIds):
        instMap  = self.client.xenapi.VM.get_all_records()
        cloudAlias = self.getCloudAlias()
        instanceList = instances.BaseInstances()
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
        instanceList.sort(key = lambda x: (x.getState(), x.getInstanceId()))
        return self.filterInstances(instanceIds, instanceList)

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
        for i in range(60):
            task = self.client.xenapi.task.get_record(taskRef)
            if task.get('status') == 'pending':
                time.sleep(1)
                continue
            if task.get('status') != 'success':
                errorInfo = task.get('error_info', '')
                raise errors.CatalogError("Unable to upload image %s: %s" %
                    (vmFile, errorInfo))
            break
        else:
            raise errors.CatalogError("Task is pending for too long")
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

    def _deployImage(self, job, image, auth, srUuid):
        tmpDir = tempfile.mkdtemp(prefix="xenent-download-")
        try:
            downloadUrl = image.getDownloadUrl()
            checksum = image.getImageId()

            job.addLog(self.LogEntry('Downloading image'))
            path = self._downloadImage(image, tmpDir, auth = auth, extension = '.xva')

            job.addLog(self.LogEntry('Importing image'))
            templRef, templUuid = self._importImage(image, path, srUuid)

            image.setImageId(templUuid)
            image.setInternalTargetId(templUuid)
        finally:
            util.rmtree(tmpDir, ignore_errors = True)

    def getLaunchInstanceParameters(self, image, descriptorData):
        params = baseDriver.BaseDriver.getLaunchInstanceParameters(self,
            image, descriptorData)
        getField = descriptorData.getField
        srUuid = getField('storageRepository')
        params['srUuid'] = srUuid
        return params

    def launchInstanceProcess(self, job, image, auth, **launchParams):
        ppop = launchParams.pop
        srUuid = ppop('srUuid')
        instanceName = ppop('instanceName')
        instanceDescription = ppop('instanceDescription')

        cloudConfig = self.drvGetCloudConfiguration()
        nameLabel = image.getLongName()
        nameDescription = image.getBuildDescription()

        if not image.getIsDeployed():
            self._deployImage(job, image, auth, srUuid)

        imageId = image.getInternalTargetId()

        job.addLog(self.LogEntry('Cloning template'))
        realId = self.cloneTemplate(job, imageId, instanceName,
            instanceDescription)
        job.addLog(self.LogEntry('Launching'))
        self.startVm(realId)
        return realId

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

    @classmethod
    def getImageIdFromMintImage(cls, image):
        return image.get('sha1')

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

    def cloneTemplate(self, job, imageId, instanceName, instanceDescription):
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
            if uuidsFound.get(uuid) is not None:
                continue
            if uuid not in uuidsFound:
                # SR not coming from the default pool
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

