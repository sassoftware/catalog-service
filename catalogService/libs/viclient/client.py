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
import sys
import time
import weakref
from collections import namedtuple
from conary.lib.util import SavedException

from catalogService.libs.ovf import OVF

from VimService_client import *  # pyflakes=ignore
#from ZSI.wstools import logging
from ZSI.wstools import TimeoutSocket
from ZSI import FaultException
#logging.setLevel(logging.DEBUG)

import vmutils

def _strToMor(smor, mortype=None):
    if isinstance(smor, unicode):
        # XML parsers tend to decode information as unicode strings
        smor = smor.encode('ascii')
    if type(smor) != str:
        return smor
    # convert a string to a managed object reference
    mor = ns0.ManagedObjectReference_Def('').pyclass(smor)
    if mortype:
        mor.set_attribute_type(mortype)
    return mor

class BaseStorage(object):
    __slots__ = []

    @classmethod
    def _filterStorage(cls, iterable, filterExp=None):
        for obj in iterable:
            if filterExp is None or fnmatch.fnmatch(obj.name, filterExp):
                yield obj

    def getStorageMostFreeSpace(self, filterExp=None):
        return max(self._filterStorage(self.datastoresActive, filterExp),
                key=lambda x: x.freeSpace)

    def getStorageLeastOvercommitted(self, filterExp=None):
        return max(self._filterStorage(
            (x for x in self.datastoresActive if x.uncommitted is not None),
            filterExp),
            key=lambda x: x.freeSpace - x.uncommitted)

class ComputeResource(BaseStorage):
    __slots__ = [ 'obj', 'configTarget', 'properties', 'resourcePools', '_dc',
            '_storage', ]
    def __init__(self, obj, properties, configTarget, resourcePools, dataCenter=None):
        self.obj = obj
        self.properties = properties
        self.configTarget = configTarget
        self.resourcePools = resourcePools
        if dataCenter is None:
            self._dc = None
        else:
            self._dc = weakref.proxy(dataCenter)
        self._storage = None

    @property
    def dc(self):
        return self._dc

    def getStorageByMor(self, mor):
        for stg in self.storage:
            if stg.mor == mor:
                return stg
        return None

    @property
    def storage(self):
        """
        Return all storage available for this compute resource
        """
        if self._storage is not None:
            return self._storage
        dc = self._dc
        crDsSet = set(self.properties['datastore'])
        self._storage = storage = []
        dsMorToDsInfoMap = dict(
                (x.get_element_datastore().get_element_datastore(),
                    x)
                for x in self.configTarget.get_element_datastore())
        for dsCluster in dc.datastoreClusters.values():
            dsClusterDatastores = set(x.mor for x in dsCluster.datastores)
            common = dsClusterDatastores.intersection(crDsSet)
            if not common:
                continue
            # Fetch datastore info objects
            dsInfoList = [ dsMorToDsInfoMap[x] for x in common ]
            # Some datastores from the storage pod may not be available to
            # this compute resource. Filter only the ones that do belong here.
            newCluster = DatastoreCluster(dsCluster.mor, dsCluster.name,
                    [ self.DatastoreFromVirtualMachineDatastoreInfo(x)
                        for x in dsInfoList ])
            storage.append(newCluster)

        for dsMor in self.properties['datastore']:
            dsInfo = dsMorToDsInfoMap[dsMor]
            storage.append(self.DatastoreFromVirtualMachineDatastoreInfo(dsInfo))

        return storage

    @property
    def datastoresActive(self):
        return [ x for x in self.storage if x.isWritable ]

    @classmethod
    def DatastoreFromVirtualMachineDatastoreInfo(cls, vmdi):
        dsSummary = vmdi.get_element_datastore()
        uncommitted = None
        if hasattr(dsSummary, '_uncommitted'):
            uncommitted = dsSummary.get_element_uncommitted()
        return Datastore(vmdi.get_element_datastore().get_element_datastore(),
                name=dsSummary.get_element_name(),
                mode=vmdi.get_element_mode(),
                freeSpace=dsSummary.get_element_freeSpace(),
                capacity=dsSummary.get_element_capacity(),
                uncommitted=uncommitted,
                maintenanceMode=dsSummary.get_element_maintenanceMode())

class Datacenter(object):
    __slots__ = [ 'obj', 'crs', 'properties', '_datastores',
            '_datastoreClusters', '__weakref__', ]
    def __init__(self, obj, properties):
        self.crs = []
        self.obj = obj
        self.properties = properties
        self._datastores = {}
        self._datastoreClusters = {}

    def addComputeResource(self, cr):
        self.crs.append(cr)

    def getComputeResources(self):
        return self.crs

    def iterValidComputeResources(self):
        for cr in self.crs:
            cfg = cr.configTarget
            if cfg is None:
                continue
            if not cr.datastoresActive:
                # None of the datastores are available, so skip
                continue
            yield cr

    def getComputeResource(self, objref):
        for cr in self.crs:
            if str(cr.obj) == objref:
                return cr
        return None

    def findStorage(self, srv):
        datastores = self.properties['datastore']
        datastoreFolderMoRef = self.properties['datastoreFolder']
        self._datastores = {}
        self._datastoreClusters = {}
        propsWanted = {
                'Folder' : [
                    'name',
                    'childEntity',
                    'childType',
                    'parent',
                    ],
                }
        foldersToDatastores = srv.dataToArray(srv.getContentsRecursively(
            None, datastoreFolderMoRef, propsWanted,
            selectionSpecs=srv.buildDatastoreFolderTraversal()))
        # All datastores available to this datacenter
        for datastoreMor in datastores:
            ds = Datastore(mor=datastoreMor)
            self._datastores[datastoreMor] = ds
        # Start walking the folder, looking for storage pods
        pods = []
        foldersStack = [ datastoreFolderMoRef ]
        while foldersStack:
            folder = foldersStack.pop()
            entries = foldersToDatastores[folder]['childEntity']
            pods.extend(x for x in entries
                    if x.get_attribute_type() == 'StoragePod')
            folders = [ x for x in entries
                    if x.get_attribute_type() == 'Folder' ]
            folders.reverse()
            foldersStack.extend(folders)
        for podMor in pods:
            pod = foldersToDatastores[podMor]
            dsMors = pod['childEntity']
            dsList = [ self._datastores[x] for x in dsMors ]
            dsc = DatastoreCluster(podMor, pod['name'], dsList)
            self._datastoreClusters[podMor] = dsc

    @property
    def datastores(self):
        return self._datastores

    @property
    def datastoreClusters(self):
        return self._datastoreClusters

class _Slotted(object):
    __slots__ = []
    def _init(self, slots, args, kwargs):
        # Stuff kwargs with None when a value wasn't specified
        for propName in slots:
            kwargs.setdefault(propName, None)
        for propName, propVal in zip(slots, args):
            setattr(self, propName, propVal)
            kwargs.pop(propName, None)
        for propName, propVal in kwargs.items():
            setattr(self, propName, propVal)

class Datastore(_Slotted):
    __slots__ = [ 'mor', 'name', 'mode', 'capacity', 'freeSpace', 'uncommitted', 'maintenanceMode' ]
    def __init__(self, *args, **kwargs):
        self._init(self.__slots__, args, kwargs)

    def __repr__(self):
        return "<%s object at 0x%x; name=%s, mor=%s>" % (
                self.__class__.__name__, id(self), self.name, self.mor)

    @property
    def isWritable(self):
        return self.mode == 'readWrite' and self.maintenanceMode == 'normal'

class DatastoreCluster(_Slotted, BaseStorage):
    __slots__ = [ 'mor', 'name', 'datastores', ]
    def __init__(self, *args, **kwargs):
        self._init(self.__slots__, args, kwargs)

    @property
    def datastoresActive(self):
        return [ x for x in self.datastores if x.isWritable ]

    @property
    def isWritable(self):
        return bool(len(self.datastoresActive))

    @property
    def freeSpace(self):
        return sum(x.freeSpace for x in self.datastoresActive)

    @property
    def uncommitted(self):
        return sum(x.uncommitted for x in self.datastoresActive
                if x.uncommitted is not None)

    @property
    def capacity(self):
        dsList = self.datastoresActive
        unknown = [ x.capacity for x in dsList if x.capacity is None ]
        if unknown:
            return None
        return sum(x.capacity for x in dsList)

    def __repr__(self):
        return "<%s object at 0x%x; name=%s, mor=%s, datastores=%s>" % (
                self.__class__.__name__, id(self), self.name, self.mor,
                self.datastores)

class Network(object):
    __slots__ = [ 'mor', 'props' ]
    def __init__(self, mor, props):
        self.mor = mor
        self.props = props

    @property
    def name(self):
        return self.props['name']

class VIConfig(object):
    def __init__(self):
        self.datacenters = []
        self.namemap = {}
        self.mormap = {}
        self.props = {}
        self.networks = {}
        self.distributedVirtualSwitches = {}
        self.dcFolders = {}
        self.vmFolders = {}
        self.vmFolderTree = {}

    def addDatacenter(self, dc):
        self.datacenters.append(dc)

    def updateNamemap(self, names):
        self.namemap.update(names)
        self.mormap.update(dict((str(x), x) for x in names.iterkeys()))

    def getDatacenters(self):
        return self.datacenters

    def getDatacenter(self, objref):
        for dc in self.datacenters:
            if str(dc.obj) == objref:
                return dc
        return None

    def getName(self, mor):
        return self.namemap[mor]

    def getMOR(self, morid):
        return self.mormap.get(morid, None)

    def setProperties(self, props):
        self.props = props

    def getProperties(self):
        return self.props

    def getNetwork(self, mor):
        return self.networks.get(mor)

    def addNetwork(self, mor, props):
        self.networks[mor] = Network(mor, props)

    def addDistributedVirtualSwitch(self, dvs):
        d = self.distributedVirtualSwitches
        k = dvs.get_element_distributedVirtualSwitch()
        d[k] = dvs

    def getDistributedVirtualSwitch(self, dvs):
        return self.distributedVirtualSwitches.get(dvs)

    def getVmFolderTree(self, folder):
        return self.vmFolderTree[folder]

    def getVmFolderLabelsForTree(self, folder):
        """Return a list of labels and folders for all sub-folders of the
        specified one"""
        stack = [ ("", folder) ]
        ret = []
        while stack:
            parentPath, nodeMor = stack.pop()
            nodeProps = self.vmFolders[nodeMor]
            nodeLabel = "%s/%s" % (parentPath,
                self._escapeFolderName(nodeProps['name']))
            children = self.vmFolderTree.get(nodeMor, [])
            stack.extend((nodeLabel, x) for x in children)
            ret.append((nodeLabel, nodeMor))
        ret.sort(key=lambda x: x[0])
        return ret

    def getVmFolderLabelPath(self, folder):
        """
        Walk backwards until we reach a top-level folder
        """
        stack = []
        node = folder
        # Hash datacenters
        topFolders = dict((dc.properties['vmFolder'], dc)
            for dc in self.datacenters)
        dc = None
        while 1:
            morProps = self.vmFolders[node]
            dc = topFolders.get(node)
            if dc is not None:
                stack.append(self._escapeFolderName(morProps['name']))
                break

            childTypes = morProps['childType'].get_element_string()
            if 'VirtualMachine' not in childTypes:
                # Got to a non-VM folder
                break
            stack.append(self._escapeFolderName(morProps['name']))
            node = morProps['parent']
        stack.reverse()
        return dc, '/'.join(stack)

    @classmethod
    def _escapeFolderName(cls, folderName):
        return folderName.replace('/', '%2f')

class Error(Exception):
    pass

class LeaseProgressUpdate(object):
    def __init__(self, vmclient, httpNfcLease, callback=None):
        self.vmclient = vmclient
        self.httpNfcLease = httpNfcLease
        self.callback = callback

    def __call__(self, percent):
        req = HttpNfcLeaseProgressRequestMsg()
        req.set_element__this(self.httpNfcLease)
        req.set_element_percent(percent)

        self.vmclient._service.HttpNfcLeaseProgress(req)
        if self.callback:
            self.callback(percent)

class VimService(object):
    def __init__(self, host, username, password, locale='en_US', debug=False,
                 **kw):
        self.sdkUrl = 'https://%s/sdk' %host
        self.baseUrl = 'https://%s/' %host
        self._loggedIn = False
        loc = VimServiceLocator()
        if debug:
            tracefile=sys.stdout
        else:
            tracefile=None
        self._service = loc.getVimPort(url=self.sdkUrl, tracefile=tracefile,
                                       **kw)
        # Set the user agent
        self._service.binding.AddHeader('User-Agent', 'VMware-client')

        # get the service content
        req = RetrieveServiceContentRequestMsg()
        _this = req.new__this('ServiceInstance')
        _this.set_attribute_type('ServiceInstance')
        req.set_element__this(_this)
        ret = self._service.RetrieveServiceContent(req)

        # make some handy references
        self._sic = ret.get_element_returnval()
        self._propCol = self._sic.get_element_propertyCollector()
        self._rootFolder = self._sic.get_element_rootFolder()
        self.vmwareVersion = self.getVmwareVersion()

        # log in
        ret = self.login(self._service, username, password, locale,
            self._sic.get_element_sessionManager())
        self._loggedIn = True
        self._service = self.ServiceProxy(self._service, username, password,
            locale, self._sic.get_element_sessionManager())

    @classmethod
    def login(cls, service, username, password, locale, sessionManager):
        req = LoginRequestMsg()
        req.set_element__this(sessionManager)
        req.set_element_userName(username)
        req.set_element_password(password)
        req.set_element_locale(locale)
        ret = service.Login(req)
        return ret

    class ServiceProxy(object):
        def __init__(self, service, username, password, locale, sessionManager):
            self._service = service
            self._username = username
            self._password = password
            self._locale = locale
            self._sessionManager = sessionManager

        class ServiceProxyMethod(object):
            def __init__(self, method, serviceProxy):
                self._method = method
                self._serviceProxy = serviceProxy

            def __call__(self, *args, **kwargs):
                try:
                    return self._method(*args, **kwargs)
                except FaultException, e:
                    if e.fault.string != 'The session is not authenticated.':
                        raise
                    # Log in again
                    VimService.login(self._serviceProxy._service,
                        self._serviceProxy._username,
                        self._serviceProxy._password,
                        self._serviceProxy._locale,
                        self._serviceProxy._sessionManager)
                    return self._method(*args, **kwargs)

        def __getattr__(self, name):
            ret = getattr(self._service, name)
            if not hasattr(ret, '__call__'):
                return ret
            return self.ServiceProxyMethod(ret, self)

    def isESX(self):
        prodLine = self._sic.get_element_about().get_element_productLineId()
        return 'esx' in prodLine.lower()

    def getVmwareVersion(self):
        version =  self._sic.get_element_about().get_element_version()
        version = tuple(int(x) for x in version.split('.'))
        return version

    def getUrlBase(self):
        return self.baseUrl

    def getSessionUUID(self):
        return self._service._service.binding.cookies['vmware_soap_session'].coded_value

    def getObjectProperties(self, obj, properties, collector=None):
        if obj is None:
            return None
        if not collector:
            collector = self._propCol

        req = RetrievePropertiesRequestMsg()
        spec = req.new_specSet()

        propSpec = spec.new_propSet()
        propSpec.set_element_all(not properties)
        propSpec.set_element_pathSet(properties)
        propSpec.set_element_type(obj.get_attribute_type())
        propSet = [ propSpec ]
        spec.set_element_propSet(propSet)

        objSpec = spec.new_objectSet()
        objSpec.set_element_obj(obj)
        objSpec.set_element_skip(False)
        objSet = [ objSpec ]
        spec.set_element_objectSet(objSet)

        req.set_element__this(collector)
        req.set_element_specSet([ spec ])
        resp = self._service.RetrieveProperties(req)
        return resp.get_element_returnval()

    def getDynamicProperty(self, obj, prop):
        """
        Retrieve a single object

        @param mor Managed Object Reference to get contents for
        @param propertyName of the object to retrieve

        @return retrieved object
        """
        objContent = self.getObjectProperties(obj, [ prop ])

        if not objContent:
            return None

        objContent = objContent[0]
        if not hasattr(objContent, '_propSet'):
            return None
        dynamicProperty = objContent.get_element_propSet()
        if not dynamicProperty:
            return None

        dynamicPropertyVal = dynamicProperty[0].get_element_val()
        dynamicPropertyName = dynamicProperty[0].get_element_name()
        if dynamicPropertyName.startswith('ArrayOf'):
            # FIXME: implement this
            raise NotImplemented
        return dynamicPropertyVal

    def getMoRefProp(self, obj, prop):
        props = self.getDynamicProperty(obj, prop)
        propMor = None
        if not isinstance(props, list):
            propMor = props
        return propMor

    def getConfigTarget(self, computeRes, host=None):
        envBrowse = self.getMoRefProp(computeRes, 'environmentBrowser')
        if envBrowse is None:
            return None
        req = QueryConfigTargetRequestMsg()
        req.set_element__this(envBrowse)
        if host:
            req.set_element_host(host)
        resp = self._service.QueryConfigTarget(req)
        return resp.get_element_returnval()

    def getDefaultDevices(self, computeResMor, hostMor):
        """
        The method returns the default devices from the HostSystem

        @param computeResMor A MoRef to the ComputeResource used by
        the HostSystem
        @param hostMor A MoRef to the HostSystem
        @return Array of VirtualDevice containing the default devices for 
        the HostSystem
        """

        envBrowseMor = self.getMoRefProp(computeResMor, 'environmentBrowser')
        if envBrowseMor is None:
            return None

        req = QueryConfigOptionRequestMsg()
        req.set_element__this(envBrowseMor)
        req.set_element_host(hostMor)
        resp = self._service.QueryConfigOption(req)
        cfgOpt = resp.get_element_returnval()
        if not cfgOpt:
            raise RuntimeError('No VirtualHardwareInfo found in ComputeResource')
        defaultDevs = cfgOpt.get_element_defaultDevice()
        if not defaultDevs:
            raise RuntimeError('No Datastore found in ComputeResource')
        return defaultDevs

    def _getVolumeName(self, volName):
        if volName:
            return '[%s]' %volName
        return '[Local]'

    def createVirtualDisk(self, volName, diskCtlrKey,
                          datastoreRef, diskSizeMB):
        volumeName = self._getVolumeName(volName)
        diskSpec = ns0.VirtualDeviceConfigSpec_Def('').pyclass()

        diskSpec.set_element_fileOperation('create')
        diskSpec.set_element_operation('add')

        disk = ns0.VirtualDisk_Def('').pyclass()
        diskfileBacking = ns0.VirtualDiskFlatVer2BackingInfo_Def('').pyclass()

        diskfileBacking.set_element_fileName(volumeName)
        diskfileBacking.set_element_diskMode('persistent')

        disk.set_element_key(0)
        disk.set_element_controllerKey(diskCtlrKey)
        disk.set_element_unitNumber(0)
        disk.set_element_backing(diskfileBacking)
        disk.set_element_capacityInKB(1024)

        diskSpec.set_element_device(disk)
        return diskSpec

    def _getIdeController(self, defaultDevices):
        # Find the IDE controller
        for dev in defaultDevices:
            if isinstance(dev.typecode, ns0.VirtualIDEController_Def):
                return dev
        return None

    def createNicConfigSpec(self, networkMor, nic=None):
        # Add a NIC.
        if networkMor.get_attribute_type() == 'DistributedVirtualPortgroup':
            # We don't fetch the full config upfront, it's too large
            dvsMor = self.getMoRefProp(networkMor,
                'config.distributedVirtualSwitch')
            switchUuid = self.getMoRefProp(dvsMor, 'uuid')
            nicBacking = ns0.VirtualEthernetCardDistributedVirtualPortBackingInfo_Def('').pyclass()
            port = nicBacking.new_port()
            port.set_element_switchUuid(switchUuid)
            port.set_element_portgroupKey(str(networkMor))
            nicBacking.set_element_port(port)
        else:
            # Plain network. NIC is bound by network name (very lame)
            deviceName = self.getMoRefProp(networkMor, 'name')
            nicBacking = ns0.VirtualEthernetCardNetworkBackingInfo_Def('').pyclass()
            nicBacking.set_element_deviceName(deviceName)

        nicSpec = ns0.VirtualDeviceConfigSpec_Def('').pyclass()
        if nic is None:
            nicSpec.set_element_operation('add')

            nic = ns0.VirtualPCNet32_Def('').pyclass()
            nic.set_element_key(-1)
            nic.set_element_addressType('generated')
        else:
            nicSpec.set_element_operation('edit')
        nic.set_element_backing(nicBacking)
        nicSpec.set_element_device(nic)

        return nicSpec

    def createCdromConfigSpec_passthrough(self, vmmor, controller):
        vm = self._getVm(vmmor)
        unitNumber = self._getNextCdromUnitNumber(vm)
        cdSpec = ns0.VirtualDeviceConfigSpec_Def('').pyclass()
        cdSpec.set_element_operation('add')

        cdDeviceBacking = ns0.VirtualCdromRemotePassthroughBackingInfo_Def('').pyclass()
        cdDeviceBacking.set_element_deviceName('cdrom')
        cdDeviceBacking.set_element_exclusive(False)

        cdrom = ns0.VirtualCdrom_Def('').pyclass()
        cdrom.set_element_backing(cdDeviceBacking)
        cdrom.set_element_key(-1)
        cdrom.set_element_controllerKey(controller.get_element_key())
        cdrom.set_element_unitNumber(unitNumber)
        cdSpec.set_element_device(cdrom)
        return cdSpec

    def createCdromConfigSpec(self, filename, vmmor, controller, datastoreRef,
                datastoreVolume):
        vm = self._getVm(vmmor)
        unitNumber = self._getNextCdromUnitNumber(vm)
        vmName = vm['config.name']
        datastoreRef = _strToMor(datastoreRef, 'Datastore')

        cdSpec = ns0.VirtualDeviceConfigSpec_Def('').pyclass()
        cdSpec.set_element_operation('add')
        cdrom = ns0.VirtualCdrom_Def('').pyclass()
        cdDeviceBacking = ns0.VirtualCdromIsoBackingInfo_Def('').pyclass()
        cdDeviceBacking.set_element_datastore(datastoreRef)
        cdDeviceBacking.set_element_fileName(
            "%s%s/%s" % (datastoreVolume, vmName, filename))
        cdrom.set_element_backing(cdDeviceBacking)
        cdrom.set_element_key(-1)
        cdrom.set_element_controllerKey(controller.get_element_key())
        #cdrom.set_element_unitNumber(controller.get_element_unitNumber())
        cdrom.set_element_unitNumber(unitNumber)
        cdSpec.set_element_device(cdrom)
        return cdSpec

    def _getVm(self, vmmor):
        vmmor = _strToMor(vmmor, 'VirtualMachine')
        # Grab the VM's configuration
        vms = self.getVirtualMachines(['config.hardware.device', 'config.name'],
            root = vmmor)
        return vms[vmmor]

    def _getNextCdromUnitNumber(self, vm):
        devices = vm['config.hardware.device']
        devices = devices.get_element_VirtualDevice()
        cdromUnitNumbers = [ x.get_element_unitNumber()
                for x in devices if x.typecode.type[1] == 'VirtualCdrom' ]
        if not cdromUnitNumbers:
            unitNumber = 0
        else:
            unitNumber = max(cdromUnitNumbers) + 1
        return unitNumber

    def disconnectCdrom(self, vmmor, cdrom):
        cdrom.get_element_connectable().set_element_connected(False)
        cdSpec = ns0.VirtualDeviceConfigSpec_Def('').pyclass()
        operation = "edit"
        cdSpec.set_element_operation(operation)
        cdSpec.set_element_device(cdrom)
        self.reconfigVM(vmmor, dict(deviceChange = [ cdSpec ]))

    def browseDatastore(self, datastore):
        ftup = namedtuple("FileObject", "path size modification")
        browser = self.getDynamicProperty(datastore, 'browser')
        if browser is None:
            return []
        dsInfo = self.getDynamicProperty(datastore, 'info')
        dsPath = "[%s]" % dsInfo.get_element_name()

        queryFlags = ns0.FileQueryFlags_Def('').pyclass()
        queryFlags.set_element_fileSize(True)
        queryFlags.set_element_modification(True)
        queryFlags.set_element_fileType(False)
        queryFlags.set_element_fileOwner(False)
        specs = ns0.HostDatastoreBrowserSearchSpec_Def('').pyclass()
        specs.set_element_details(queryFlags)

        req = SearchDatastoreSubFolders_TaskRequestMsg()
        req.set_element__this(browser)
        req.set_element_datastorePath(dsPath)
        req.set_element_searchSpec(specs)

        ret = self._service.SearchDatastoreSubFolders_Task(req)
        task = ret.get_element_returnval()
        res = self.waitForTask(task)
        if res.lower() != 'success':
            raise RuntimeError(res)
        tinfo = self.getDynamicProperty(task, 'info')

        paths = []

        taskRes = tinfo.get_element_result()
        browseResults = taskRes.get_element_HostDatastoreBrowserSearchResults()
        for br in browseResults:
            dirname = br.get_element_folderPath()
            for fobj in br.get_element_file():
                paths.append(ftup(
                    "%s%s" %  (dirname, fobj.get_element_path()),
                    fobj.get_element_fileSize(), fobj.get_element_modification()))
        return paths

    def buildFullTraversal(self):
        """
        This method creates a SelectionSpec[] to traverses the entire
        inventory tree starting at a Folder
        @return list of selection specs
        """
        # Recurse through all ResourcePools
        rpToRp = self.TraversalSpec('rpToRp', 'ResourcePool', 'resourcePool',
                ['rpToRp', 'rpToVm'])
        # Recurse through all ResourcePools
        rpToVm = self.TraversalSpec('rpToVm', 'ResourcePool', 'vm', [])

        # Traversal through ResourcePool branch
        crToRp = self.TraversalSpec('crToRp', 'ComputeResource', 'resourcePool',
                ['rpToRp', 'rpToVm'])

        # Traversal through host branch
        crToH = self.TraversalSpec('crToH', 'ComputeResource', 'host', [])

        # Traversal through hostFolder branch
        dcToHf = self.TraversalSpec('dcToHf', 'Datacenter', 'hostFolder',
                ['visitFolders'])

        # Traversal through vmFolder branch
        dcToVmf = self.TraversalSpec('dcToVmf', 'Datacenter', 'vmFolder',
                ['visitFolders'])

        # Recurse through networkFolder branch
        dcToNetwork = self.TraversalSpec('dcToNetwork', 'Datacenter',
                'networkFolder', ['visitFolders'])

        # Recurse through all Hosts
        hToVm = self.TraversalSpec('HToVm', 'HostSystem', 'vm',
                ['visitFolders'])

        # Recurse through the folders
        visitFolders = self.TraversalSpec('visitFolders', 'Folder',
                'childEntity', [])
        # We set selectSet to the empty list; we'll fix it once we figure out
        # the whole set

        # XXX rpToRp may not be needed here, it's not part of
        # src/com/vmware/vim25/mo/util/PropertyCollectorUtil.java
        retSpecs = [ visitFolders, dcToHf, dcToVmf, crToH, crToRp, rpToRp,
                hToVm, rpToVm ]

        if self.vmwareVersion >= (4, 0, 0):
            retSpecs.append(dcToNetwork)

        visitFolders.set_element_selectSet(
                [ self.SelectionSpec(x.get_element_name()) for x in retSpecs ])
        return retSpecs

    def buildDatastoreFolderTraversal(self):
        specs = []
        specs.append(self.TraversalSpec('visitStoragePods', 'StoragePod',
            'childEntity', []))
        specs.append(self.TraversalSpec('visitFolders', 'Folder',
            'childEntity', ['visitFolders', 'visitStoragePods']))
        return specs

    @classmethod
    def TraversalSpec(cls, name, type, path, selectSet):
        ts = ns0.TraversalSpec_Def('').pyclass()
        ts.set_element_name(name)
        ts.set_element_type(type)
        ts.set_element_path(path)
        ts.set_element_skip(False)
        ts.set_element_selectSet([ cls.SelectionSpec(s) for s in selectSet ])
        return ts

    @classmethod
    def SelectionSpec(cls, name):
        if not isinstance(name, basestring):
            return name
        ss = ns0.SelectionSpec_Def('').pyclass()
        ss.set_element_name(name)
        return ss

    def buildPropertySpecArray(self, typeinfo):
        """
        This code takes an array of [typename, property, property, ...]
        and converts it into a PropertySpec[].
        handles case where multiple references to the same typename
        are specified.

        @param typeinfo 2D array of type and properties to retrieve
        @return Array of container filter specs
        """
        # Create PropertySpecs
        pSpecs = []
        for typeName, props in typeinfo.iteritems():
            pSpec = ns0.PropertySpec_Def('').pyclass()
            pSpec.set_element_type(typeName)
            if props:
                pSpec.set_element_all(False)
            else:
                pSpec.set_element_all(True)
            pSpec.set_element_pathSet(list(props))
            pSpecs.append(pSpec)
        return pSpecs

    def getContentsRecursively(self, collector=None, root=None,
                               typeinfo=None, recurse=False,
                               selectionSpecs=None):
        """
        Retrieve container contents from specified root recursively if
        requested.

        @param root a root folder if available, or None for default
        @param recurse retrieve contents recursively from the root down

        @return retrieved object contents
        """
        if not typeinfo:
            return None

        if not collector:
            collector = self._propCol

        if not root:
            root = self._rootFolder

        req = RetrievePropertiesRequestMsg()

        if recurse:
            if selectionSpecs:
                raise RuntimeError('programming error: both recurse and selectionSpecs provided')
            selectionSpecs = self.buildFullTraversal()
        propSpec = self.buildPropertySpecArray(typeinfo)
        spec = req.new_specSet()
        spec.set_element_propSet(propSpec)
        # select the root object
        objSpec = spec.new_objectSet()
        objSpec.set_element_obj(root)
        objSpec.set_element_skip(False)
        objSpec.set_element_selectSet(selectionSpecs)
        spec.set_element_objectSet([ objSpec ])

        # form up the request and fire it off
        req.set_element__this(collector)
        req.set_element_specSet([ spec ])
        resp = self._service.RetrieveProperties(req)
        return resp.get_element_returnval()

    def getDecendentMoRef(self, root, objtype, name):
        """
        Get the ManagedObjectReference for an item under the specified
        root folder that has the type and name specified.

        @param root a root folder if available, or None for default
        @param type type of the managed object
        @param name name to match

        @return First ManagedObjectReference of the type / name pair found
        """
        if not name:
            return None

        typeinfo = { objtype: ['name'] }
        objs = self.getContentsRecursively(None, root, typeinfo, True)
        if not objs:
            return None

        found = False
        for obj in objs:
            mor = obj.get_element_obj()
            properties = obj.get_element_propSet()
            property = properties[0]
            if property and property.get_element_val() == name:
                found = True
                break
        if not found:
            return None
        return mor

    def getFirstDecendentMoRef(self, root, objtype):
        """
        Get the first ManagedObjectReference from a root of 
        the specified type

        @param root a root folder if available, or None for default
        @param type the type of the entity - e.g. VirtualMachine
        @return managed object reference available
        """
        objs = self.getDecendentMoRefs(root, objtype)
        if objs:
            return objs[0]
        return None

    def getDecendentMoRefs(self, root, objtype, filter=None):
        """
        Retrieve all the ManagedObjectReferences of the type specified.

        @param root a root folder if available, or None for default
        @param type type of container refs to retrieve

        @return List of MORefs
        """
        typeinfo = { objtype: ['name'] }
        objs = self.getContentsRecursively(None, root, typeinfo, True)
        refs = [ x.get_element_obj() for x in objs ]
        if not refs:
            return refs
        if filter:
            raise NotImplemented
        return refs

    def _updateValues(self, props, vals, propchg):
        for idx, prop in enumerate(props):
            if prop in propchg.get_element_name():
                if propchg.get_element_op() == 'remove':
                    vals[idx] = ''
                else:
                    # FIXME: bug?
                    if hasattr(propchg, '_val'):
                        vals[idx] = propchg.get_element_val()
                    else:
                        vals[idx] = None

    def waitForValues(self, objmor, filterProps, endWaitProps, expectedVals,
            callback=None):
        """
        Handle Updates for a single object.
        waits till expected values of properties to check are reached
        Destroys the ObjectFilter when done.
        @param objmor MOR of the Object to wait for
        @param filterProps Properties list to filter
        @param endWaitProps Properties list to check for expected values
        these be properties of a property in the filter properties list
        @param expectedVals values for properties to end the wait
        @param callback A callback to be called with values of the
            properties specified in filterProps
        @return true indicating expected values were met, and false otherwise
        """

        # Sometimes we're seeing BadStatusLine messages coming from vsphere
        for i in range(10):
            try:
                return self._waitForValues(objmor, filterProps, endWaitProps,
                    expectedVals, callback=callback)
            except ZSI.client.httplib.BadStatusLine:
                time.sleep(1)
        raise

    def _waitForValues(self, objmor, filterProps, endWaitProps, expectedVals,
            callback=None):
        version = ''
        endVals = [ None ] * len(endWaitProps)
        filterVals = [ None ] * len(filterProps)

        spec = ns0.PropertyFilterSpec_Def('').pyclass()
        objSpec = ns0.ObjectSpec_Def('').pyclass()
        objSpec.set_element_obj(objmor)
        objSpec.set_element_skip(False)
        objSpec.set_element_selectSet(None)
        spec.set_element_objectSet([ objSpec ])

        propSpec = ns0.PropertySpec_Def('').pyclass()
        propSpec.set_element_pathSet(filterProps)
        propSpec.set_element_type(objmor.get_attribute_type())
        spec.set_element_propSet([ propSpec ])

        req = CreateFilterRequestMsg()
        req.set_element__this(self._propCol)
        req.set_element_spec(spec)
        req.set_element_partialUpdates(True)
        ret = self._service.CreateFilter(req)

        # wait for updates
        try:
            filterSpecRef = ret.get_element_returnval()

            done = False
            while not done:
                # wait for updates to the objects specified
                while True:
                    # retry loop
                    try:
                        req = WaitForUpdatesRequestMsg()
                        req.set_element__this(self._propCol)
                        req.set_element_version(version)
                        ret = self._service.WaitForUpdates(req)
                        updateSet = ret.get_element_returnval()
                        break
                    except TimeoutSocket.TimeoutError:
                        # FIXME: remove debugging output
                        print 'time out waiting for properties, retrying...'
                        pass
                if not updateSet.get_element_filterSet():
                    continue
                # we have an update, check to see if we have everything
                # we're looking for
                version = updateSet.get_element_version()
                updateFilterSet = updateSet.get_element_filterSet()
                for updateFilter in updateFilterSet:
                    objs = updateFilter.get_element_objectSet()
                    for objUpdate in objs:
                        kind = objUpdate.get_element_kind()
                        if kind in ('modify', 'enter', 'leave'):
                            propchgs = objUpdate.get_element_changeSet()
                            for propchg in propchgs:
                                self._updateValues(endWaitProps, endVals,
                                                   propchg)
                                self._updateValues(filterProps, filterVals,
                                                   propchg)
                for chgi, endVal in enumerate(endVals):
                    if done:
                        break
                    for expectedVal in expectedVals[chgi]:
                        if endVal == expectedVal:
                            done = True
                            break
                    else: #for; expected values not found
                        if callback:
                            callback(filterVals)
        finally:
            try:
                req = DestroyPropertyFilterRequestMsg()
                req.set_element__this(filterSpecRef)
                self._service.DestroyPropertyFilter(req)
            except:
                # Don't fail when cleaning things up
                pass

        return filterVals

    def waitForTask(self, task, callback=None):
        result = self.waitForValues(task,
                                    [ 'info.state', 'info.progress', 'info.error' ],
                                    [ 'state' ],
                                    [ [ 'success', 'error' ] ],
                                    callback=callback)
        if result[0] == 'success':
            return 'success'
        else:
            tinfo = self.getDynamicProperty(task, 'info')
            fault = tinfo.get_element_error()
            error = 'Error Occurred'
            if fault:
                error = fault.get_element_localizedMessage()
            return error
        assert('not reached')

    def getProperties(self, propsWanted, root=None):
        data = self.getContentsRecursively(None, root, propsWanted, True)
        return self.dataToArray(data)

    def dataToArray(self, data):
        ret = {}
        for datum in data:
            mor = datum.get_element_obj()
            props = {}
            ret[mor] = props
            if not hasattr(datum, '_propSet'):
                # not sure how this happens, but it does
                continue
            for prop in datum.get_element_propSet():
                name = prop.get_element_name()
                val = prop.get_element_val()
                if hasattr(val, 'typecode'):
                    typecode = val.typecode.type[1]
                    if typecode == 'ArrayOfManagedObjectReference':
                        val = val.get_element_ManagedObjectReference()
                    elif typecode == 'ArrayOfOptionValue':
                        # unroll option=value arrays into a dictionary
                        d = {}
                        for holder in val.get_element_OptionValue():
                            d[holder.get_element_key()] = holder.get_element_value()
                            val = d
                props[name] = val
        return ret

    def getDatacenters(self):
        propsWanted = {'Datacenter': ['name']}
        return self.getProperties(propsWanted)

    def getVirtualMachines(self, propertyList, root=None):
        propsWanted = {'VirtualMachine': propertyList}
        return self.getProperties(propsWanted, root)

    def findVMByUUID(self, uuid):
        searchIndex = self._sic.get_element_searchIndex()
        req = FindByUuidRequestMsg()
        req.set_element__this(searchIndex)
        req.set_element_uuid(uuid)
        req.set_element_vmSearch(True)
        ret = self._service.FindByUuid(req)
        return ret.get_element_returnval()

    def findVMByInventoryPath(self, path):
        searchIndex = self._sic.get_element_searchIndex()
        req = FindByInventoryPathRequestMsg()
        req.set_element__this(searchIndex)
        req.set_element_inventoryPath(path)
        ret = self._service.FindByInventoryPath(req)
        return ret.get_element_returnval()

    def registerVM(self, folderMor, vmxPath, vmName, asTemplate=False,
                   pool=None, host=None):
        req = RegisterVM_TaskRequestMsg()
        req.set_element__this(folderMor)
        req.set_element_path(vmxPath)
        req.set_element_name(vmName)
        req.set_element_asTemplate(asTemplate)
        if pool:
            req.set_element_pool(pool)
        if host:
            req.set_element_host(host)
        ret = self._service.RegisterVM_Task(req)
        task = ret.get_element_returnval()

        result = self.waitForValues(task,
                                    [ 'info.state', 'info.progress', 'info.error' ],
                                    [ 'state' ],
                                    [ [ 'success', 'error' ] ])
        if result[0] == 'success':
            tinfo = self.getDynamicProperty(task, 'info')
            vm = tinfo.get_element_result()
            return vm

        tinfo = self.getDynamicProperty(task, 'info')
        error = 'Error occurred while waiting for task'
        if hasattr(tinfo, '_error'):
            fault = tinfo.get_element_error()
            if fault:
                error = fault.get_element_localizedMessage()
        raise Error(error)

    def reconfigVM(self, vm, options, callback=None):
        req = ReconfigVM_TaskRequestMsg()
        spec = req.new_spec()
        for key, value in options.iteritems():
            method = 'set_element_' + key
            if not hasattr(spec, method):
                raise TypeError('no such configuration value "%s"' %key)
            setter = getattr(spec, method)
            setter(value)
        return self._reconfigVM(vm, spec, callback=callback)

    def _reconfigVM(self, vm, spec, callback=None):
        req = ReconfigVM_TaskRequestMsg()
        req.set_element__this(_strToMor(vm, 'VirtualMachine'))
        req.set_element_spec(spec)
        ret = self._service.ReconfigVM_Task(req)
        task = ret.get_element_returnval()
        return self.waitForTask(task, callback=callback)

    def leaseComplete(self, httpNfcLease):
        req = HttpNfcLeaseCompleteRequestMsg()
        req.set_element__this(httpNfcLease)

        self._service.HttpNfcLeaseComplete(req)

    def leaseAbort(self, httpNfcLease):
        req = HttpNfcLeaseAbortRequestMsg()
        req.set_element__this(httpNfcLease)
        self._service.HttpNfcLeaseAbort(req)

    def getOvfManager(self):
        return getattr(self._sic, '_ovfManager', None)

    def parseOvfDescriptor(self, ovfContents):
        ovfContents = self.sanitizeOvfDescriptor(ovfContents)
        params = ns0.OvfParseDescriptorParams_Def('').pyclass()
        params.set_element_deploymentOption('')
        params.set_element_locale('')

        req = ParseDescriptorRequestMsg()
        req.set_element__this(self.getOvfManager())
        req.set_element_ovfDescriptor(ovfContents)
        req.set_element_pdp(params)
        resp = self._service.ParseDescriptor(req)
        parseDescriptorResult = resp.get_element_returnval()

        if hasattr(parseDescriptorResult, '_error'):
            errors = []
            for f in parseDescriptorResult._error:
                if hasattr(f, '_localizedMessage'):
                    errors.append(f.LocalizedMessage)
            raise Exception("Error parsing OVF descriptor: %s" %
                '; '.join(errors))
        return parseDescriptorResult

    @classmethod
    def sanitizeOvfDescriptor(cls, ovfContents):
        # Get rid of the network specification, it breaks older vSphere 4.0
        # nodes
        ovf = OVF(ovfContents)
        return ovf.sanitize()

    def destroyVM(self, vmMor, callback=None):
        req = Destroy_TaskRequestMsg()
        req.set_element__this(vmMor)

        ret = self._service.Destroy_Task(req)
        task = ret.get_element_returnval()
        ret = self.waitForTask(task, callback=callback)
        if ret != 'success':
            raise RuntimeError("Unable to destroy virtual machine: %s" % ret)

    def createOvfDescriptor(self, vmMor, name, description, ovfFiles):
        req = CreateDescriptorRequestMsg()
        req.set_element__this(self.getOvfManager())
        req.set_element_obj(vmMor)
        req.set_element_cdp(self.createOvfCreateDescriptorParams(
            name, description, ovfFiles))

        resp = self._service.CreateDescriptor(req)
        createDescriptorResult = resp.get_element_returnval()
        return createDescriptorResult

    def createOvfCreateDescriptorParams(self, name, description, ovfFiles,
            includeImageFiles=False):
        params = ns0.OvfCreateDescriptorParams_Def('').pyclass()
        params.set_element_name(name)
        params.set_element_description(description)
        params.set_element_ovfFiles(ovfFiles)
        #params.set_element_includeImageFiles(includeImageFiles)

        return params

    def ovfImportStart(self, ovfContents, vmName,
            vmFolder, resourcePool, dataStore, network, diskProvisioning):
        ovfContents = self.sanitizeOvfDescriptor(ovfContents)
        createImportSpecResult = self.createOvfImportSpec(ovfContents, vmName,
            resourcePool, dataStore, network, diskProvisioning)

        hostErrorMessage = 'Host did not have any virtual network defined.'
        if hasattr(createImportSpecResult, '_error'):
            errors = createImportSpecResult.get_element_error()
            if errors:
                errmsg = errors[0].get_element_localizedMessage()
                if errmsg == hostErrorMessage:
                    raise Exception("Please update to vCenter update 1: "
                        "http://www.vmware.com/support/vsphere4/doc/vsp_vc40_u1_rel_notes.html")
                raise Exception("Error creating import spec: %s" % errmsg)

        fileItems = createImportSpecResult.get_element_fileItem()

        httpNfcLease = self.getOvfImportLease(resourcePool, vmFolder,
            createImportSpecResult.get_element_importSpec())
        return fileItems, httpNfcLease

    def ovfUpload(self, httpNfcLease, archive, prefix, fileItems):
        httpNfcLeaseInfo = self.getMoRefProp(httpNfcLease, 'info')
        deviceUrls = httpNfcLeaseInfo.get_element_deviceUrl()
        vmMor = httpNfcLeaseInfo.get_element_entity()

        # Figure out which files get uploaded where first and key it by archive
        # path, because the archive has to be read out in stream order.
        idToPathMap = {}
        for fileItem in fileItems:
            deviceId = fileItem.get_element_deviceId()
            filePath = fileItem.get_element_path()
            filePathInArchive = prefix + filePath
            isCreated = fileItem.get_element_create()
            method = (isCreated and 'PUT') or 'POST'
            idToPathMap[deviceId] = (method, filePathInArchive)
        pathToUrlMap = {}
        for deviceUrl in deviceUrls:
            deviceId = deviceUrl.get_element_importKey()
            method, filePathInArchive = idToPathMap[deviceId]
            url = deviceUrl.get_element_url()
            if url.startswith("https://*/"):
                url = self.baseUrl + url[10:]
            pathToUrlMap[filePathInArchive] = (method, url)

        try:
            # Now pull out files in order and upload them
            for path, tarinfo, fobj in archive.iterFileStreams():
                if path not in pathToUrlMap:
                    continue
                method, url = pathToUrlMap[path]
                vmutils._putFile(fobj, url, session=None, method=method)
                del pathToUrlMap[path]
            self.leaseComplete(httpNfcLease)
        except:
            err = SavedException()
            try:
                self.leaseAbort(httpNfcLease)
            except:
                # Ignore errors related to aborting the lease
                pass
            err.throw()

        if pathToUrlMap:
            raise Exception("File(s) missing from archive: %s"
                    % (', '.join(sorted(pathToUrlMap))))

        return vmMor


    def waitForLeaseReady(self, lease):
        ret = self.waitForValues(lease, ['state'],
            [ 'state' ], [ ['ready', 'error'] ])
        if ret[0] != 'ready':
            raise Exception("Error getting lease")

    def createOvfImportSpec(self, ovfContents, vmName, resourcePool,
                            dataStore, network, diskProvisioning):

        parseDescriptorResult = self.parseOvfDescriptor(ovfContents)
        params = self.createOvfImportParams(parseDescriptorResult, vmName,
            network, diskProvisioning)

        req = CreateImportSpecRequestMsg()
        req.set_element__this(self.getOvfManager())
        req.set_element_ovfDescriptor(ovfContents)
        req.set_element_resourcePool(resourcePool)
        req.set_element_datastore(dataStore)
        req.set_element_cisp(params)

        resp = self._service.CreateImportSpec(req)
        createImportSpecResult = resp.get_element_returnval()
        return createImportSpecResult


    def createOvfImportParams(self, parseDescriptorResult, vmName, network,
            diskProvisioning):
        params = ns0.OvfCreateImportSpecParams_Def('').pyclass()
        params.set_element_locale('')
        params.set_element_deploymentOption(
            parseDescriptorResult.get_element_defaultDeploymentOption())
        params.set_element_entityName(vmName)

        # Assign the first network
        networkLabels = [ x.get_element_name()
            for x in parseDescriptorResult.get_element_network() ]
        if networkLabels:
            nm = params.new_networkMapping()
            nm.set_element_name(networkLabels[0])
            nm.set_element_network(network)
            params.set_element_networkMapping([ nm ])
        if diskProvisioning is not None and hasattr(params, 'set_element_diskProvisioning'):
            params.set_element_diskProvisioning(diskProvisioning)
        return params


    def getOvfImportLease(self, resourcePool, vmFolder, importSpec):
        req = ImportVAppRequestMsg()
        req.set_element__this(resourcePool)
        req.set_element_spec(importSpec)
        req.set_element_folder(vmFolder)

        resp = self._service.ImportVApp(req)
        httpNfcLease = resp.get_element_returnval()
        return httpNfcLease

    def getLeaseManifest(self, lease):
        # XXX Not working yet, we need 4.1
        req = HttpNfcLeaseGetManifestRequestMsg()
        req.set_element__this(lease)
        resp = self._service.HttpNfcLeaseGetManifest(req)
        manifest = resp.get_element_returnval()
        return manifest

    def markAsTemplate(self, vm=None, uuid=None):
        mor = self._getVM(mor=vm, uuid=uuid)
        req = MarkAsTemplateRequestMsg()
        req.set_element__this(mor)
        self._service.MarkAsTemplate(req)

    def getVIConfig(self):
        # get properties for interesting objects
        propsDict = {
                                    'Datacenter': [ 'name',
                                                    'hostFolder',
                                                    'vmFolder',
                                                    'datastore',
                                                    'datastoreFolder',
                                                    'network',
                                                    'parent', ],
                                    'Folder': ['name', 'parent', 'childType', ],
                                    'HostSystem': [ 'name',
                                                    'datastore',
                                                    'network' ],
                                    'ComputeResource': [ 'name',
                                                         'datastore',
                                                         'parent',
                                                         'host',
                                                         'resourcePool',
                                                         'network'],
                                    'ResourcePool': [ 'name',
                                                      'parent' ],
                                    }
        if self.vmwareVersion >= (4, 0, 0):
            propsDict['Network'] = [ 'name', 'host', 'tag', ]
        props = self.getProperties(propsDict)

        crs = []
        hostFolderToDataCenter = {}
        rps = {}
        childRps = {}
        networks = {}
        incompleteNetworks = set()
        nameMap = dict((x[0], x[1].get('name', None))
                       for x in props.iteritems())

        networkTypes = set(['Network', 'DistributedVirtualPortgroup'])
        vmFolders = {}
        vmFolderTree = {}
        crFolders = {}
        dcFolders = {}
        for mor, morProps in props.iteritems():
            # this is ClusterComputeResource in case of DRS
            objType = mor.get_attribute_type()
            if objType.endswith('ComputeResource'):
                crs.append(mor)
            elif objType == 'Datacenter':
                # build a map from host folder -> data center
                dc = Datacenter(mor, morProps)
                hostFolderToDataCenter[morProps['hostFolder']] = dc
                for network in dc.properties.get('network', []):
                    if network not in networks:
                        networks[network] = None
            elif objType == 'ResourcePool':
                rps[mor] = morProps
                l = childRps.setdefault(morProps['parent'], [])
                l.append(mor)
            elif objType in networkTypes:
                # Ignore networks without hosts
                if not morProps['host']:
                    incompleteNetworks.add(mor)
                    continue
                tags = set([ x.get_element_key()
                    for x in morProps['tag'].get_element_Tag() ])
                if 'SYSTEM/DVS.UPLINKPG' in tags:
                    # We can't use an uplink
                    incompleteNetworks.add(mor)
                    continue
                networks[mor] = morProps
            elif objType == 'Folder':
                childTypes = morProps['childType'].get_element_string()
                if 'VirtualMachine' in childTypes:
                    vmFolders[mor] = morProps
                    parent = morProps['parent']
                    vmFolderTree.setdefault(parent, []).append(mor)
                elif 'ComputeResource' in childTypes:
                    crFolders[mor] = morProps
                elif 'Datacenter' in childTypes:
                    dcFolders[mor] = morProps

        networksNotInFolder = [ x for (x, y) in networks.items()
            if y is None and x not in incompleteNetworks ]
        # 3.5 did not have a networkFolder child for datacenters, so we could
        # not traverse the folder that way. Describe the networks
        # individually.
        if networksNotInFolder:
            propsDict = {}
            propList = [ 'name', 'host' ]
            for network in networksNotInFolder:
                propsDict.clear()
                nwtype = network.get_attribute_type()
                propsDict[nwtype] = propList
                nwprops = self.getProperties(propsDict, root = network)[network]
                if not nwprops['host']:
                    # No host attached to this network
                    del networks[network]
                    continue
                networks[network] = nwprops
            nameMap.update((mor, p['name']) for (mor, p) in networks.items())

        vicfg = VIConfig()
        vicfg.dcFolders = dcFolders
        vicfg.vmFolders = vmFolders
        vicfg.vmFolderTree = vmFolderTree
        for cr in crs:
            # grab the previously retreived properties for this
            # compute resource
            crProps = props[cr]
            nodeProps = crProps
            while 1:
                parent = nodeProps['parent']
                dataCenter = hostFolderToDataCenter.get(parent)
                if dataCenter is not None:
                    break
                # Walk to the parent folder
                nodeProps = crFolders.get(parent)
                if nodeProps is None:
                    # We should find this parent in the discovered CR
                    # folders; this is strange
                    break
            if dataCenter is None:
                # The CR's parent (host folder) is not discoverable under one
                # of the data centers, so skip this compute resource
                continue
            # for each compute resource, we need to get the config
            # target.  This lets us build up the options for deploying
            # VMs
            configTarget = self.getConfigTarget(cr)
            datastores = (configTarget is not None and
                          configTarget.get_element_datastore()) or []
            dvsList = (configTarget is not None and
                       hasattr(configTarget, '_distributedVirtualSwitch') and
                       configTarget.get_element_distributedVirtualSwitch()) or []
            for dvs in dvsList:
                vicfg.addDistributedVirtualSwitch(dvs)
            for ds in datastores:
                # first go through all the datastores and record
                # their names.
                ds = ds.get_element_datastore()
                nameMap[ds.get_element_datastore()] = ds.get_element_name()
            # get the top level resource pool for the compute resource
            crRp = crProps['resourcePool']

            # pull out the list of child resource pool objects for this
            # toplevel compute resource (if any exist)
            crRpMors = [ crRp ]
            if crRp in childRps:
                # extend the list of compute resource objects with
                # any included child objects
                crRpMors.extend(childRps[crRp])
            # now create a properties dictionary keyed off the
            # resource pool objects
            crRps = dict(x for x in props.iteritems() if x[0] in crRpMors)
            # nowe we can create some objects that are easier to deal with
            cr = ComputeResource(cr, crProps, configTarget, crRps,
                    dataCenter=dataCenter)
            dataCenter.addComputeResource(cr)

        for dc in hostFolderToDataCenter.values():
            vicfg.addDatacenter(dc)
            dc.findStorage(self)
        vicfg.updateNamemap(nameMap)
        vicfg.setProperties(props)
        for mor, props in networks.items():
            if props is None:
                continue
            vicfg.addNetwork(mor, props)
        return vicfg

    def _getVM(self, mor=None, uuid=None):
        if not mor and not uuid:
            raise TypeError('either VM object reference (mor) or uuid required')
        if mor and uuid:
            raise TypeError('either VM object reference (mor) or uuid required, but not both')

        if mor:
            mor = _strToMor(mor, 'VirtualMachine')

        if uuid:
            mor = self.findVMByUUID(uuid)
            if not mor:
                raise RuntimeError('VM matching uuid %s not found' %uuid)
        return mor

    def cloneVM(self, mor=None, uuid=None, name=None, annotation=None,
                dc=None, ds=None, rp=None, newuuid=None, template=False,
                vmFolder=None, network=None, callback=None):
        if uuid:
            # ugh, findVMByUUID does not return templates
            # See the release notes:
            # http://www.vmware.com/support/developer/vc-sdk/visdk25pubs/visdk25knownissues.html
            vms = self.getVirtualMachines([ 'config.template',
                                         'config.uuid' ])
            mor = None
            for obj, props in vms.iteritems():
                if props['config.template'] and props['config.uuid'] == uuid:
                    mor = obj
                    break
            if not mor:
                raise RuntimeError('No template with UUID %s' %uuid)
        if vmFolder is None:
            if dc is not None:
                vmFolder = self.getMoRefProp(dc, 'vmFolder')
            else:
                # Copy the parent (folder) from the source vm
                vmFolder = self.getMoRefProp(mor, 'parent')

        templateVm = self.getVirtualMachines(
            ['config.hardware.device'], root = mor)
        templateNetworkDevices = [ x
            for x in templateVm[mor]['config.hardware.device'].VirtualDevice
                if hasattr(x, '_macAddress') and x.get_element_macAddress() ]

        req = CloneVM_TaskRequestMsg()
        req.set_element__this(mor)
        req.set_element_folder(vmFolder)
        req.set_element_name(name)

        cloneSpec = req.new_spec()
        cloneSpec.set_element_template(template)
        # We do not want to power on the clone just yet, we need to attach its
        # credentials disk
        cloneSpec.set_element_powerOn(False)
        # set up the data relocation
        loc = cloneSpec.new_location()
        if ds:
            loc.set_element_datastore(ds)
        if rp:
            loc.set_element_pool(rp)
        cloneSpec.set_element_location(loc)
        # set up the vm config (uuid)
        config = cloneSpec.new_config()
        if newuuid:
            config.set_element_uuid(newuuid)
        config.set_element_annotation(annotation)
        cloneSpec.set_element_config(config)
        req.set_element_spec(cloneSpec)

        if network is not None:
            if not templateNetworkDevices:
                nicSpec = self.createNicConfigSpec(network)
            else:
                nic = templateNetworkDevices[0]
                nicSpec = self.createNicConfigSpec(network, nic)
            config.set_element_deviceChange([nicSpec])

        ret = self._service.CloneVM_Task(req)
        task = ret.get_element_returnval()
        ret = self.waitForTask(task, callback=callback)
        if ret != 'success':
            # FIXME: better exception
            raise RuntimeError("Unable to clone template: %s" % ret)
        tinfo = self.getDynamicProperty(task, 'info')
        vm = tinfo.get_element_result()
        return vm

    def shutdownVM(self, mor=None, uuid=None, callback=None):
        mor = self._getVM(mor=mor, uuid=uuid)
        req = ShutdownGuestRequestMsg()
        req.set_element__this(mor)
        try:
            ret = self._service.ShutdownGuest(req)
            # FIXME: we should probably monitor the VM for some time
            # and poweroff if it does not shut down within a resonable
            # period
        except FaultException, e:
            if isinstance(e.fault.detail[0].typecode,
                          ns0.ToolsUnavailableFault_Dec):
                # no tools (required for clean shutdown) - use poweroff
                req = PowerOffVM_TaskRequestMsg()
                req.set_element__this(mor)
                ret = self._service.PowerOffVM_Task(req)
                task = ret.get_element_returnval()
                res = self.waitForTask(task, callback=callback)
                if res.lower() != 'success':
                    raise RuntimeError(res)

    def startVM(self, mor=None, uuid=None, callback=None):
        mor = self._getVM(mor=mor, uuid=uuid)
        req = PowerOnVM_TaskRequestMsg()
        req.set_element__this(mor)
        ret = self._service.PowerOnVM_Task(req)
        task = ret.get_element_returnval()
        res = self.waitForTask(task, callback=callback)
        if res.lower() != 'success':
            raise RuntimeError(res)

    def logout(self):
        req = LogoutRequestMsg()
        req.set_element__this(self._sic.get_element_sessionManager())
        self._service.Logout(req)

    def __del__(self):
        if self._loggedIn:
            self.logout()

