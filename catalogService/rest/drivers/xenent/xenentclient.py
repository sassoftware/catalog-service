
import os
import re
import signal
import select
import socket
import tempfile
import time
import urllib
import urllib2
import httplib

from conary.lib import util

from catalogService import errors
from catalogService import instanceStore
from catalogService import storage
from catalogService.rest import baseDriver
from catalogService.rest.models import clouds
from catalogService.rest.models import images
from catalogService.rest.models import instances

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

class StreamingRequestMixIn(object):
    def _send_request_mix_in(self, parentClass, method, url, body, headers):
        if not hasattr(body, 'read') and not hasattr(body, 'seek'):
            # Not a file-like object
            return parentClass._send_request(self, method, url, body,
                headers)
        # Compute body length
        pos = 0
        body.seek(0, 2)
        contentLength = body.tell() - pos
        body.seek(pos)
        headers['Content-Length'] = str(contentLength)
        # Send the request with no body
        parentClass._send_request(self, method, url, None, headers)
        # Now stream the body
        blockSize = 16384
        pollobj = select.poll()
        pollobj.register(self.sock, select.POLLOUT)
        while 1:
            buf = body.read(blockSize)
            if not buf:
                break
            pollobj.poll()
            try:
                self.send(buf)
            except socket.error, e:
#                import traceback; traceback.print_exc()
                # Inject the response (headers may be interesting) in the
                # socket error
                e.response = self.getresponse()
                e.response.close()
                raise
        print "Done"

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

        for i in range(5):
            try:
                resp = self.getOpener().open(req)
                return resp
            except urllib2.URLError, e:
                if hasattr(e.args[0], 'errno') and e.args[0].errno == 104:
                    # Connection reset by peer. xen has the bad habit of
                    # closing the request before one had the chance to read
                    # the response
                    print "   Failure", i, e.args[0].response.status
                    continue
                raise
        else:
            raise
        return None

class XenEntClient(baseDriver.BaseDriver):
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

    RBUILDER_BUILD_TYPE = 'XEN_OVA'
    minSizeRe = re.compile(".*VDI size must be between (.*) and .*|"
        "VDI size must be a minimum of (.*)")

    @classmethod
    def isDriverFunctional(cls):
        if not XenAPI or not xenprov:
            return False
        return True

    def drvCreateCloudClient(self, credentials):
        cloudConfig = self.getTargetConfiguration()
        if self.XenSessionClass:
            klass = self.XenSessionClass
        else:
            klass = XenAPI.Session
        sess = klass("https://%s" % self.cloudName)
        try:
            # password is a ProtectedString, we have to convert to string
            sess.login_with_password(credentials['username'],
                                     str(credentials['password']))
        except XenAPI.Failure, e:
            raise errors.PermissionDenied(message = "User %s: %s" % (
                e.details[1], e.details[2]))
        self._uuidToRefMap = {}
        return sess

    def _cachedGet(self, uuid, function):
        ref = self._uuidToRefMap.get(uuid)
        if ref is not None:
            return ref
        ref = function(uuid)
        self._uuidToRefMap[uuid] = ref
        return ref

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
            instRef = self._cachedGet(instId, client.xenapi.VM.get_by_uuid)
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
            type = descr.EnumeratedType(
                descr.ValueWithDescription(x[0], descriptions = x[1][0])
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
        client = self.client
        instMap  = client.xenapi.VM.get_all_records()
        cloudAlias = self.getCloudAlias()
        instanceList = instances.BaseInstances()
        for opaqueId, vm in instMap.items():
            if vm['is_a_template']:
                continue

            # Try to grab the guest metrics, if available
            publicIpAddr = None
            guestMetricsRef = vm['guest_metrics']
            if guestMetricsRef != 'OpaqueRef:NULL':
                networks = client.xenapi.VM_guest_metrics.get_networks(
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

    def _pollTask(self, taskRef, loopCount = 100, timeout = 0.5):
        client = self.client
        for i in range(loopCount):
            status = client.xenapi.task.get_status(taskRef)
            # http://docs.vmd.citrix.com/XenServer/4.0.1/api/docs/html/browser.html
            # Valid status: pending, success, failure, cancelling, cancelled
            if status == 'pending':
                time.sleep(timeout)
                continue
            return client.xenapi.task.get_record(taskRef)
        return None

    def _putVmImage(self, vmFile, srUuid, taskRef):
        client = self.client
        srRef = self._cachedGet(srUuid, client.xenapi.SR.get_by_uuid)
        task = self._xePutFile('import', file(vmFile), taskRef,
            loopCount = 10000, sr_id = srRef)
        # Wrap the pseudo-XMLRPC response
        params = XenAPI.xmlrpclib.loads(self._XmlRpcWrapper %
            task['result'])[0]
        reflist = params[0]
        if len(reflist) < 1:
            raise errors.CatalogError("Unable to publish image, no results found")
        vmRef = reflist[0]
        # Make it a template
        client.xenapi.VM.set_is_a_template(vmRef, True)

        vmUuid = client.xenapi.VM.get_uuid(vmRef)
        return vmRef, vmUuid

    def _newVdi(self, vmUuid, fileObj, srRef):
        client = self.client
        fileObj.seek(0, 2)
        fileSize = fileObj.tell()
        fileObj.seek(0)

        nameLabel = "Credentials image for %s" % vmUuid
        vdiRef = self._createVdi(srRef, vmUuid, fileSize)

        for i in range(10):
            try:
                taskRef = client.xenapi.task.create(nameLabel, nameLabel)
                task = self._xePutFile('import_raw_vdi', fileObj,
                    taskRef = taskRef, vdi = vdiRef)
                break
            except urllib2.URLError, e:
                if hasattr(e.args[0], 'errno') and e.args[0].errno == 104:
                    # Connection reset by peer. xen has the bad habit of
                    # closing the request before one had the chance to read
                    # the response
                    print "Failure", i
                    time.sleep(1)
                    continue
                raise
        else: # for
            raise

        if task.get('status') != 'success':
            errorInfo = task.get('error_info', '')
            # Get rid of the vdi, it's not useful anymore
            client.xenapi.VDI.destroy(vdiRef)
            raise errors.CatalogError(
                "Unable to upload initial credentials for %s: %s" %
                    vmUuid, errorInfo)
        return vdiRef

    def _createVdi(self, srRef, vmUuid, fileSize):
        client = self.client
        vdiRec = {
            'SR' : srRef,
            'type' : 'system',
            'virtual_size' : str(fileSize),
            'name_label' : 'Credentials for %s' % vmUuid,
            'name_description' : 'Credentials for %s' % vmUuid,
            'sharable' : False,
            'read_only' : True,
            'other_config' : {},
        }
        try:
            vdiRef = client.xenapi.VDI.create(vdiRec)
        except XenAPI.Failure, e:
            # This is disgusting. I could not find a minimal size for the SR,
            # so for now we're parsing the error.
            if e.details[0] != 'SR_BACKEND_FAILURE_79':
                raise
            m = self.minSizeRe.match(e.details[2])
            if not m:
                raise
            matchedGroups = m.groups()
            matched = matchedGroups[0]
            if matched is None:
                matched = matchedGroups[1]
            arr = matched.split()
            dsize = int(arr[0])
            if len(arr) >= 2:
                # Is there a multiplier?
                mult = arr[1].upper()
                if mult == 'MB':
                    multiplier = 1024 * 1024
                elif mult == 'KB':
                    multiplier = 1024
                elif mult == 'GB':
                    multiplier = 1024 * 1024 * 1024
                else:
                    multiplier = 1
                dsize = multiplier * dsize
            vdiRec['virtual_size'] = str(dsize)
            vdiRef = client.xenapi.VDI.create(vdiRec)
        return vdiRef

    def _xePutFile(self, urlSelector, fileObj, taskRef, loopCount = 1000,
            loopTimeout = 0.5, **kwargs):
        urlTemplate = 'http://%s:%s@%s/%s?%s'
        cloudConfig = self.getTargetConfiguration()
        cloudName = cloudConfig['name']
        creds = self.credentials
        username, password = creds['username'], creds['password']
        kwargs['task_id'] = taskRef

        query = '&'.join("%s=%s" % (k, kwargs[k]) for k in sorted(kwargs))

        #print ("curl -T /tmp/foo.iso '%s'" % (urlTemplate % (username, password, cloudName, urlSelector, query)))
        client = UploadClient(urlTemplate % (username, password, cloudName,
            urlSelector, query))
        resp = client.request(fileObj)
        # The server does not send any useful information back. Close the
        # request and fetch the status from the task
        if resp:
            resp.close()
        rec = self._pollTask(taskRef, loopCount, timeout = loopTimeout)
        if not rec:
            # timeout
            raise errors.CatalogError("Failure uploading file")
        status = rec.get('status')
        if status == 'success':
            return rec
        if status == 'failure':
            errorInfo = rec['error_info']
            raise errors.CatalogError("Unable to upload file: %s" %
                    (errorInfo, ))
        # Canceled
        raise errors.CatalogError("Task has finished unexpectedly: %s" % status)

    def _importImage(self, image, vmFile, srUuid):
        checksum = image.getImageId()
        taskRef = self.client.xenapi.task.create("Import of %s" % checksum,
            "Import of %s" % checksum)
        vmRef, vmUuid = self._putVmImage(vmFile, srUuid, taskRef)
        self._setVmMetadata(vmRef, checksum = checksum)
        return vmRef, vmUuid

    def _deployImage(self, job, image, auth, srUuid):
        tmpDir = tempfile.mkdtemp(prefix="xenent-download-")
        try:
            job.addHistoryEntry('Downloading image')
            path = self._downloadImage(image, tmpDir, auth = auth, extension = '.xva')

            job.addHistoryEntry('Importing image')
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

        cloudConfig = self.getTargetConfiguration()
        nameLabel = image.getLongName()
        nameDescription = image.getBuildDescription()

        if not image.getIsDeployed():
            self._deployImage(job, image, auth, srUuid)

        imageId = image.getInternalTargetId()

        job.addHistoryEntry('Cloning template')
        realId = self.cloneTemplate(job, imageId, instanceName,
            instanceDescription)
        job.addHistoryEntry('Attaching credentials')
        try:
            self._attachCredentials(realId, srUuid)
        except Exception, e:
            self.log_exception("Exception attaching credentials: %s" % e)
        job.addHistoryEntry('Launching')
        self.startVm(realId)
        return self.client.xenapi.VM.get_uuid(realId)

    def getImagesFromTarget(self, imageIdsFilter):
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

            if imageIdsFilter is not None and imageId not in imageIdsFilter:
                continue

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
        client = self.client
        vmTemplateRef = self._cachedGet(imageId, client.xenapi.VM.get_by_uuid)
        imageId = os.path.basename(imageId)

        vmRef = client.xenapi.VM.clone(vmTemplateRef,
            instanceName)
        client.xenapi.VM.set_name_description(vmRef, instanceDescription)
        self._setVmMetadata(vmRef, templateUuid = imageId)

        # Get all physical interfaces
        pifs = client.xenapi.PIF.get_all_records()
        # Grab the lowest device (eth0)
        lowest = min((v['device'], k) for k, v in pifs.items())[1]

        networkRef = client.xenapi.PIF.get_network(lowest)

        self.addVIFtoVM(vmRef, networkRef)

        # Generate credentials image here
        return vmRef

    def _attachCredentials(self, vmRef, srUuid):
        client = self.client
        srRef = self._cachedGet(srUuid, client.xenapi.SR.get_by_uuid)
        filename = self.getCredentialsIsoFile()
        fileObj = file(filename)
        os.unlink(filename)
        self._attachCredentialsDisk(vmRef, fileObj, srRef)

    def _attachCredentialsDisk(self, vmRef, fileObj, srRef = None):
        client = self.client
        if srRef is None:
            srRef = self._getSrFromVmRef(vmRef)
        vmUuid = client.xenapi.VM.get_uuid(vmRef)
        vdiRef = self._newVdi(vmUuid, fileObj, srRef)
        try:
            self._newVbd(vmRef, vdiRef)
        except:
            client.xenapi.VDI.destroy(vdiRef)
            raise
        #try:
        #    self._plugVbd(vbdRef)
        #except:
        #    exc_info = sys.exc_info()
        #    try:
        #        client.xenapi.VDI.destroy(vdiRef)
        #        client.xenapi.VBD.destroy(vbdRef)
        #    except:
        #        pass
        #    raise exc_info[0], exc_info[1], exc_info[2]

    def _newVbd(self, vmRef, vdiRef, vbdType="disk"):
        client = self.client
        # Determine available devices
        allowedVbds = client.xenapi.VM.get_allowed_VBD_devices(vmRef)
        # Grab the first one
        vbdDevNo = allowedVbds[0]
        # Create the vbd
        vbdRec = dict(
            userdevice = vbdDevNo,
            VM = vmRef,
            VDI = vdiRef,
            type = vbdType,
            mode = "RO",
            bootable = False,
            empty = False,
            other_config = {},
            qos_algorithm_type = '',
            qos_algorithm_params = {},
        )
        vbdRef = client.xenapi.VBD.create(vbdRec)
        return vbdRef

    def _plugVbd(self, vbdRef):
        ret = self.client.xenapi.VBD.plug(vbdRef)
        return ret

    def _getSrFromVmRef(self, vmRef):
        # For VMs that we just pushed, we should not do this, we already know
        # the SR
        client = self.client
        # Grab the VBDs first
        for vbdRef in client.xenapi.VM.get_VBDs(vmRef):
            # Grab VDIs for this vbd
            vdiRef = client.xenapi.VBD.get_VDI(vbdRef)
            srRef = client.xenapi.VDI.get_SR(vdiRef)
            return srRef
        return None

    def startVm(self, vmRef):
        client = self.client
        client.xenapi.VM.provision(vmRef)
        startPaused = False
        force = False
        client.xenapi.VM.start(vmRef, startPaused, force)

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
        client = self.client
        pools = client.xenapi.pool.get_all_records()
        srList = [ x['default_SR'] for x in pools.values() ]
        # Validate the sr list
        uuidsFound = dict()
        ret = []
        for srRef in srList:
            try:
                uuid = client.xenapi.SR.get_uuid(srRef)
                if uuid in uuidsFound:
                    continue
                ret.append(uuid)
                uuidsFound[uuid] = None
            except XenAPI.Failure, e:
                if e.details[0] != 'HANDLE_INVALID':
                    raise

        hCache = XenEntHostCache(self.client)

        srRecs = client.xenapi.SR.get_all_records()
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

