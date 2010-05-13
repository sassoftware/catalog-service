#!/usr/bin/python2.4
#
# Copyright (c) 2008 rPath, Inc.  All Rights Reserved.
#

import errno
import glob
import os
import select
import struct
import sys
import time
from lxml import etree

from VimService_client import *
from ZSI.wstools import logging
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

class ComputeResource(object):
    __slots__ = [ 'obj', 'configTarget', 'properties', 'resourcePools' ]
    def __init__(self, obj, properties, configTarget, resourcePools):
        self.obj = obj
        self.properties = properties
        self.configTarget = configTarget
        self.resourcePools = resourcePools

class Datacenter(object):
    __slots__ = [ 'obj', 'crs', 'properties' ]
    def __init__(self, obj, properties):
        self.crs = []
        self.obj = obj
        self.properties = properties

    def addComputeResource(self, cr):
        self.crs.append(cr)

    def getComputeResources(self):
        return self.crs

    def getComputeResource(self, objref):
        for cr in self.crs:
            if str(cr.obj) == objref:
                return cr
        return None

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
        return self.mormap[morid]

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

class Error(Exception):
    pass

class ProgressUpdate(object):
    def __init__(self, vmclient, httpNfcLease):
        self.vmclient = vmclient
        self.httpNfcLease = httpNfcLease
        self.totalSize = 0
        self.prevFilesSize = 0

    def progress(self, bytes, rate=0):
        pct = int((self.prevFilesSize + bytes) * 100.0 / self.totalSize)
        req = HttpNfcLeaseProgressRequestMsg()
        req.set_element__this(self.httpNfcLease)
        req.set_element_percent(pct)

        self.vmclient._service.HttpNfcLeaseProgress(req)

    def updateSize(self, size):
        self.prevFilesSize = size

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

    def _getDatastoreRef(self, configTarget, datastoreName):
        # determine the data store to use
        datastoreRef = None
        found = False
        for vdsInfo in configTarget.get_element_datastore():
            dsSummary = vdsInfo.get_element_datastore()
            if (dsSummary.get_element_name() == datastoreName
                or not datastoreName):
                found = True
                if dsSummary.get_element_accessible():
                    datastoreName = dsSummary.get_element_name()
                    datastoreRef = dsSummary.get_element_datastore()
                    return datastoreRef, datastoreName
                if datastoreName:
                    raise RuntimeError('Specified Datastore is not accessible')
        raise RuntimeError('No Datastore found on host')

    def _getIdeController(self, defaultDevices):
        # Find the IDE controller
        for dev in defaultDevices:
            if isinstance(dev.typecode, ns0.VirtualIDEController_Def):
                return dev
        return None

    def createNicConfigSpec(self, networkMor, vicfg):
        # Add a NIC.
        nwProps = vicfg.getNetwork(networkMor).props
        if networkMor.get_attribute_type() == 'DistributedVirtualPortgroup':
            # We don't fetch the full config upfront, it's too large
            dvsMor = self.getMoRefProp(networkMor,
                'config.distributedVirtualSwitch')
            dvs = vicfg.getDistributedVirtualSwitch(dvsMor)
            switchUuid = dvs.get_element_switchUuid()
            nicBacking = ns0.VirtualEthernetCardDistributedVirtualPortBackingInfo_Def('').pyclass()
            port = nicBacking.new_port()
            port.set_element_switchUuid(switchUuid)
            port.set_element_portgroupKey(str(networkMor))
            nicBacking.set_element_port(port)
        else:
            # Plain network. NIC is bound by network name (very lame)
            deviceName = nwProps['name']
            nicBacking = ns0.VirtualEthernetCardNetworkBackingInfo_Def('').pyclass()
            nicBacking.set_element_deviceName(deviceName)

        nicSpec = ns0.VirtualDeviceConfigSpec_Def('').pyclass()
        nicSpec.set_element_operation('add')

        nic = ns0.VirtualPCNet32_Def('').pyclass()

        nic.set_element_addressType('generated')
        nic.set_element_backing(nicBacking)
        nic.set_element_key(-1)
        nicSpec.set_element_device(nic)
        return nicSpec

    def createCdromConfigSpec(self, filename, vmmor, controller, datastoreRef,
                datastoreVolume):
        vmmor = _strToMor(vmmor, 'VirtualMachine')
        datastoreRef = _strToMor(datastoreRef, 'Datastore')
        # Grab the VM's configuration
        vm = self.getVirtualMachines(['config.hardware.device', 'config.name'],
            root = vmmor)
        vmName = vm[vmmor]['config.name']
        devices = vm[vmmor]['config.hardware.device']
        devices = devices.get_element_VirtualDevice()
        cdromUnitNumbers = [ x.get_element_unitNumber()
                for x in devices if x.typecode.type[1] == 'VirtualCdrom' ]
        if not cdromUnitNumbers:
            unitNumber = 0
        else:
            unitNumber = max(cdromUnitNumbers) + 1

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

    def disconnectCdrom(self, vmmor, cdrom):
        cdrom.get_element_connectable().set_element_connected(False)
        cdSpec = ns0.VirtualDeviceConfigSpec_Def('').pyclass()
        operation = "edit"
        cdSpec.set_element_operation(operation)
        cdSpec.set_element_device(cdrom)
        self.reconfigVM(vmmor, dict(deviceChange = [ cdSpec ]))

    def buildFullTraversal(self):
        """
        This method creates a SelectionSpec[] to traverses the entire
        inventory tree starting at a Folder
        @return list of selection specs
        """
        # Recurse through all ResourcePools
        rpToRp = ns0.TraversalSpec_Def('').pyclass()
        rpToRp.set_element_type('ResourcePool')
        rpToRp.set_element_path('resourcePool')
        rpToRp.set_element_skip(False)
        rpToRpSpec = rpToRp.new_selectSet()
        rpToRpSpec.set_element_name('rpToRp')
        rpToVmSpec = rpToRp.new_selectSet()
        rpToVmSpec.set_element_name('rpToVm')
        rpToRp.set_element_selectSet([ rpToRpSpec, rpToVmSpec ])
        rpToRp.set_element_name('rpToRp')

        # Recurse through all ResourcePools
        rpToVm = ns0.TraversalSpec_Def('').pyclass()
        rpToVm.set_element_type('ResourcePool')
        rpToVm.set_element_path('vm')
        rpToVm.set_element_skip(False)
        rpToVm.set_element_selectSet([])
        rpToVm.set_element_name('rpToVm')

        # Traversal through ResourcePool branch
        crToRp = ns0.TraversalSpec_Def('').pyclass()
        crToRp.set_element_type('ComputeResource')
        crToRp.set_element_path('resourcePool')
        crToRp.set_element_skip(False)
        crToRpSpec = crToRp.new_selectSet()
        crToRpSpec.set_element_name('rpToRp')
        crToVmSpec = crToRp.new_selectSet()
        crToVmSpec.set_element_name('rpToVm')
        crToRp.set_element_selectSet([ crToRpSpec, crToVmSpec ])
        crToRp.set_element_name('crToRp')

        # Traversal through host branch
        crToH = ns0.TraversalSpec_Def('').pyclass()
        crToH.set_element_type('ComputeResource')
        crToH.set_element_path('host')
        crToH.set_element_skip(False)
        crToH.set_element_selectSet([])
        crToH.set_element_name('crToH')

        # Traversal through hostFolder branch
        dcToHf = ns0.TraversalSpec_Def('').pyclass()
        dcToHf.set_element_type('Datacenter')
        dcToHf.set_element_path('hostFolder')
        dcToHf.set_element_skip(False)
        dcToHfSpec = dcToHf.new_selectSet()
        dcToHfSpec.set_element_name('visitFolders')
        dcToHf.set_element_selectSet([ dcToHfSpec ])
        dcToHf.set_element_name('dcToHf')

        # Traversal through vmFolder branch
        dcToVmf = ns0.TraversalSpec_Def('').pyclass()
        dcToVmf.set_element_type('Datacenter')
        dcToVmf.set_element_path('vmFolder')
        dcToVmf.set_element_skip(False)
        dcToVmfSpec = dcToVmf.new_selectSet()
        dcToVmfSpec.set_element_name('visitFolders')
        dcToVmf.set_element_selectSet([ dcToVmfSpec ])
        dcToVmf.set_element_name('dcToVmf')

        # Recurse through networkFolder branch
        dcToNetwork = ns0.TraversalSpec_Def('').pyclass()
        dcToNetwork.set_element_type('Datacenter')
        dcToNetwork.set_element_path('networkFolder')
        dcToNetwork.set_element_skip(False)
        dcToNetworkSpec = dcToNetwork.new_selectSet()
        dcToNetworkSpec.set_element_name('visitFolders')
        dcToNetwork.set_element_selectSet([ dcToNetworkSpec ])
        dcToNetwork.set_element_name('dcToNetwork')

        # Recurse through all Hosts
        hToVm = ns0.TraversalSpec_Def('').pyclass()
        hToVm.set_element_type('HostSystem')
        hToVm.set_element_path('vm')
        hToVm.set_element_skip(False)
        hToVmSpec = hToVm.new_selectSet()
        hToVmSpec.set_element_name('visitFolders')
        hToVm.set_element_selectSet([ hToVmSpec ])
        hToVm.set_element_name('HToVm')

        # Recurse through the folders
        visitFolders = ns0.TraversalSpec_Def('').pyclass()
        visitFolders.set_element_type('Folder')
        visitFolders.set_element_path('childEntity')
        visitFolders.set_element_skip(False)
        specNames =  ['visitFolders', 'dcToHf', 'dcToVmf', 'crToH',
                     'crToRp', 'HToVm', 'rpToVm' ]
        specs = [ visitFolders, dcToVmf, dcToHf, crToH, crToRp,
                  rpToRp, hToVm, rpToVm ]
        if self.vmwareVersion >= (4, 0, 0):
            specNames.append('dcToNetwork')
            specs.append(dcToNetwork)

        l = []
        for specName in specNames:
            spec = visitFolders.new_selectSet()
            spec.set_element_name(specName)
            l.append(spec)
        visitFolders.set_element_selectSet(l)
        visitFolders.set_element_name('visitFolders')
        return specs

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

    def waitForValues(self, objmor, filterProps, endWaitProps, expectedVals):
        """
        Handle Updates for a single object.
        waits till expected values of properties to check are reached
        Destroys the ObjectFilter when done.
        @param objmor MOR of the Object to wait for
        @param filterProps Properties list to filter
        @param endWaitProps Properties list to check for expected values
        these be properties of a property in the filter properties list
        @param expectedVals values for properties to end the wait
        @return true indicating expected values were met, and false otherwise
        """

        # Sometimes we're seeing BadStatusLine messages coming from vsphere
        import time
        for i in range(10):
            try:
                return self._waitForValues(objmor, filterProps, endWaitProps,
                    expectedVals)
            except ZSI.client.httplib.BadStatusLine:
                time.sleep(1)
        raise

    def _waitForValues(self, objmor, filterProps, endWaitProps, expectedVals):
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
        finally:
            try:
                req = DestroyPropertyFilterRequestMsg()
                req.set_element__this(filterSpecRef)
                self._service.DestroyPropertyFilter(req)
            except:
                # Don't fail when cleaning things up
                pass

        return filterVals

    def waitForTask(self, task):
        result = self.waitForValues(task,
                                    [ 'info.state', 'info.error' ],
                                    [ 'state' ],
                                    [ [ 'success', 'error' ] ])
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
                                    [ 'info.state', 'info.error' ],
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

    def reconfigVM(self, vm, options):
        req = ReconfigVM_TaskRequestMsg()
        spec = req.new_spec()
        for key, value in options.iteritems():
            method = 'set_element_' + key
            if not hasattr(spec, method):
                raise TypeError('no such configuration value "%s"' %key)
            setter = getattr(spec, method)
            setter(value)
        return self._reconfigVM(vm, spec)

    def _reconfigVM(self, vm, spec):
        req = ReconfigVM_TaskRequestMsg()
        req.set_element__this(_strToMor(vm, 'VirtualMachine'))
        req.set_element_spec(spec)
        ret = self._service.ReconfigVM_Task(req)
        task = ret.get_element_returnval()
        return self.waitForTask(task)

    def leaseComplete(self, httpNfcLease):
        req = HttpNfcLeaseCompleteRequestMsg()
        req.set_element__this(httpNfcLease)

        self._service.HttpNfcLeaseComplete(req)

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
            raise Exception("Error parsing OVF descriptor")
        return parseDescriptorResult

    @classmethod
    def sanitizeOvfDescriptor(cls, ovfContents):
        # Get rid of the network specification, it breaks older vSphere 4.0
        # nodes
        xsiNs = 'http://www.w3.org/2001/XMLSchema-instance'
        rasdNs = 'http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData'
        doc = etree.fromstring(ovfContents)
        contentNode = doc.find('Content')
        sections = contentNode.findall('Section')
        typeAttrib = "{%s}%s" % (xsiNs, "type")
        hardwareSection = [ x for x in sections
            if x.get(typeAttrib) == 'ovf:VirtualHardwareSection_Type' ]
        if not hardwareSection:
            return ovfContents
        hardwareSection = hardwareSection[0]
        # Iterate through all items
        captionTag = "{%s}%s" % (rasdNs, "Caption")
        for i, node in enumerate(hardwareSection.iterchildren()):
            if node.tag != 'Item':
                continue
            caption = node.find(captionTag)
            if caption is None:
                continue
            if caption.text == 'ethernet0':
                del hardwareSection[i]
                break
        return etree.tostring(doc, encoding = "UTF-8")

    def ovfImportStart(self, ovfFilePath, vmName,
            vmFolder, resourcePool, dataStore, network):
        ovfContents = file(ovfFilePath).read()
        ovfContents = self.sanitizeOvfDescriptor(ovfContents)
        createImportSpecResult = self.createOvfImportSpec(ovfContents, vmName,
            resourcePool, dataStore, network)

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

    def ovfUpload(self, httpNfcLease, downloadDir, fileItems, progressUpdate):
        httpNfcLeaseInfo = self.getMoRefProp(httpNfcLease, 'info')
        deviceUrls = httpNfcLeaseInfo.get_element_deviceUrl()
        vmMor = httpNfcLeaseInfo.get_element_entity()

        fileMap = {}
        # Compute total size
        totalSize = 0
        for fileItem in fileItems:
            filePath = fileItem.get_element_path()
            filePath = os.path.join(downloadDir, filePath)
            isCreated = fileItem.get_element_create()
            method = (isCreated and 'PUT') or 'POST'
            fileSize = os.stat(filePath).st_size
            fileMap[fileItem.get_element_deviceId()] = (method, filePath, fileSize)
            totalSize += fileSize

        progressUpdate.totalSize = totalSize
        progressUpdate.progress(0, 0)

        for deviceUrl in deviceUrls:
            method, filePath, fileSize = fileMap[deviceUrl.get_element_importKey()]
            vmutils._putFile(filePath, deviceUrl.get_element_url(),
                session=None, method=method, callback = progressUpdate)
            progressUpdate.updateSize(fileSize)
        progressUpdate.progress(100, 0)
        self.leaseComplete(httpNfcLease)

        return vmMor

    def waitForLeaseReady(self, lease):
        ret = self.waitForValues(lease, ['state'],
            [ 'state' ], [ ['ready', 'error'] ])
        if ret[0] != 'ready':
            raise Exception("Error getting lease")

    def createOvfImportSpec(self, ovfContents, vmName, resourcePool,
                            dataStore, network):

        parseDescriptorResult = self.parseOvfDescriptor(ovfContents)
        params = self.createOvfImportParams(parseDescriptorResult, vmName,
            network)

        req = CreateImportSpecRequestMsg()
        req.set_element__this(self.getOvfManager())
        req.set_element_ovfDescriptor(ovfContents)
        req.set_element_resourcePool(resourcePool)
        req.set_element_datastore(dataStore)
        req.set_element_cisp(params)

        resp = self._service.CreateImportSpec(req)
        createImportSpecResult = resp.get_element_returnval()
        return createImportSpecResult

    def createOvfImportParams(self, parseDescriptorResult, vmName, network):
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
        return params

    def getOvfImportLease(self, resourcePool, vmFolder, importSpec):
        req = ImportVAppRequestMsg()
        req.set_element__this(resourcePool)
        req.set_element_spec(importSpec)
        req.set_element_folder(vmFolder)

        resp = self._service.ImportVApp(req)
        httpNfcLease = resp.get_element_returnval()
        return httpNfcLease


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
                                                    'network' ],
                                    'Folder': ['name'],
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
        for mor, morProps in props.iteritems():
            # this is ClusterComputeResource in case of DRS
            objType = mor.get_attribute_type()
            if objType.endswith('ComputeResource'):
                crs.append(mor)
            elif objType == 'Datacenter':
                # build a map from host folder -> data center
                dc = Datacenter(mor, morProps)
                hostFolderToDataCenter[morProps['hostFolder']] = dc
                for network in dc.properties['network']:
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

        ret = []

        vicfg = VIConfig()
        for cr in crs:
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
            # grab the previously retreived properties for this
            # compute resource
            crProps = props[cr]
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
            cr = ComputeResource(cr, crProps, configTarget, crRps)
            dc = hostFolderToDataCenter[crProps['parent']]
            dc.addComputeResource(cr)

        for dc in hostFolderToDataCenter.values():
            vicfg.addDatacenter(dc)
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
                dc=None, cr=None, ds=None, rp=None, newuuid=None):
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
        hostFolder = self.getMoRefProp(dc, 'hostFolder')
        vmFolder = self.getMoRefProp(dc, 'vmFolder')

        req = CloneVM_TaskRequestMsg()
        req.set_element__this(mor)
        req.set_element_folder(vmFolder)
        req.set_element_name(name)

        cloneSpec = req.new_spec()
        cloneSpec.set_element_template(False)
        # We do not want to power on the clone just yet, we need to attach its
        # credentials disk
        cloneSpec.set_element_powerOn(False)
        # set up the data relocation
        loc = cloneSpec.new_location()
        #loc.set_element_datastore(ds)
        loc.set_element_pool(rp)
        cloneSpec.set_element_location(loc)
        # set up the vm config (uuid)
        config = cloneSpec.new_config()
        if newuuid:
            config.set_element_uuid(newuuid)
        config.set_element_annotation(annotation)
        cloneSpec.set_element_config(config)
        req.set_element_spec(cloneSpec)

        ret = self._service.CloneVM_Task(req)
        task = ret.get_element_returnval()
        ret = self.waitForTask(task)
        if ret != 'success':
            # FIXME: better exception
            raise RuntimeError("Unable to clone template: %s" % ret)
        tinfo = self.getDynamicProperty(task, 'info')
        vm = tinfo.get_element_result()
        return vm

    def shutdownVM(self, mor=None, uuid=None):
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
                res = self.waitForTask(task)
                if res.lower() != 'success':
                    raise RuntimeError(res)

    def startVM(self, mor=None, uuid=None):
        mor = self._getVM(mor=mor, uuid=uuid)
        req = PowerOnVM_TaskRequestMsg()
        req.set_element__this(mor)
        ret = self._service.PowerOnVM_Task(req)
        task = ret.get_element_returnval()
        res = self.waitForTask(task)
        if res.lower() != 'success':
            raise RuntimeError(res)

    def logout(self):
        req = LogoutRequestMsg()
        req.set_element__this(self._sic.get_element_sessionManager())
        self._service.Logout(req)

    def __del__(self):
        if self._loggedIn:
            self.logout()
