#!/usr/bin/python2.4
#
# Copyright (c) 2008 rPath, Inc.  All Rights Reserved.
#

import sys
import errno
import select
import struct
import glob

from VimService_client import *
from ZSI.wstools import logging
from ZSI.wstools import TimeoutSocket
from ZSI import FaultException
#logging.setLevel(logging.DEBUG)

def _strToMor(smor, mortype=None):
    # convert a string to a managed object reference
    mor = ns0.ManagedObjectReference_Def('').pyclass(smor)
    if mortype:
        mor.set_attribute_type(mortype)
    return mor

class ComputeResource:
    def __init__(self, obj, properties, configTarget, resourcePools):
        self.obj = obj
        self.properties = properties
        self.configTarget = configTarget
        self.resourcePools = resourcePools

class Datacenter:
    def __init__(self, obj, properties):
        self.crs = []
        self.obj = obj
        self.properties = properties

    def addComputeResource(self, cr):
        self.crs.append(cr)

    def getComputeResources(self):
        return self.crs

class VIConfig:
    def __init__(self):
        self.datacenters = []
        self.namemap = {}
        self.mormap = {}

    def addDatacenter(self, dc):
        self.datacenters.append(dc)

    def updateNamemap(self, names):
        self.namemap.update(names)
        self.mormap.update(dict((x[1], x[0]) for x in names.iteritems()))

    def getDatacenters(self):
        return self.datacenters

    def getName(self, mor):
        return self.namemap[mor]

    def getMOR(self, name):
        return self.mormap[name]

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

        # log in
        req = LoginRequestMsg()
        req.set_element__this(self._sic.get_element_sessionManager())
        req.set_element_userName(username)
        req.set_element_password(password)
        req.set_element_locale(locale)
        ret = self._service.Login(req)
        self._loggedIn = True

    def getUrlBase(self):
        return self.baseUrl

    def getSessionUUID(self):
        return self._service.binding.cookies['vmware_soap_session'].coded_value

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

        dynamicProperty = objContent[0].get_element_propSet()
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

    def createVmConfigSpec(self, vmName, datastoreName, diskSizeMB,
                           computeResMor, hostMor):
        configTarget = self.getConfigTarget(computeResMor, hostMor)
        defaultDevices = self.getDefaultDevices(computeResMor, hostMor)

        configSpec = ns0.VirtualMachineConfigSpec_Def('').pyclass()

        # determine the default network name
        networkName = None
        network = configTarget.get_element_network()
        if network:
            for netInfo in network:
                netSummary = netInfo.get_element_network()
                if netSummary.get_element_accessible():
                    networkName = netSummary.get_element_name()
                    break

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
                else:
                    if datastoreName:
                        raise RuntimeError('Specified Datastore is not accessible')
                break
        if not found:
            raise RuntimeError('No Datastore found on host')

        datastoreVolume = self._getVolumeName(datastoreName)
        vmfi = ns0.VirtualMachineFileInfo_Def('').pyclass()
        vmfi.set_element_vmPathName(datastoreVolume)
        configSpec.set_element_files(vmfi)

        # Add a scsi controller
        diskCtlrKey = 1
        scsiCtrlSpec = ns0.VirtualDeviceConfigSpec_Def('').pyclass()
        scsiCtrlSpec.set_element_operation('add')

        scsiCtrl = ns0.VirtualLsiLogicController_Def('').pyclass()
        scsiCtrl.set_element_busNumber(0)
        scsiCtrlSpec.set_element_device(scsiCtrl)
        scsiCtrl.set_element_key(diskCtlrKey)
        scsiCtrl.set_element_sharedBus('noSharing')

        # Find the IDE controller
        ideCtlr = None
        for dev in defaultDevices:
            if dev.typecode == ns0.VirtualIDEController_Def:
                ideCtrl = dev
                break

        # add a floppy
        floppySpec = ns0.VirtualDeviceConfigSpec_Def('').pyclass()
        floppySpec.set_element_operation('add')
        floppy = ns0.VirtualFloppy_Def('').pyclass()
        flpBacking = ns0.VirtualFloppyDeviceBackingInfo_Def('').pyclass()
        flpBacking.set_element_deviceName('/dev/fd0')
        floppy.set_element_backing(flpBacking)
        floppy.set_element_key(3)
        floppySpec.set_element_device(floppy)

        # Add a cdrom based on a physical device
        cdSpec = None

        if ideCtlr:
            cdSpec = ns0.VirtualDeviceConfigSpec_Def('').pyclass()
            cdSpec.set_element_operation('add')
            cdrom = ns0.VirtualCdrom_Def('').pyclass()
            cdDeviceBacking = ns0.VirtualCdromIsoBackingInfo_Def('').pyclass()
            cdDeviceBacking.set_element_datastore(datastoreRef)
            cdDeviceBacking.set_element_fileName(datastoreVolume+'testcd.iso')
            cdrom.set_element_backing(cdDeviceBacking)
            cdrom.set_element_key(20)
            cdrom.set_element_controllerKey(ideCtlr.get_element_key())
            cdrom.set_element_unitNumber(0)
            cdSpec.set_element_device(cdrom)

        # Create a new disk - file based - for the vm
        diskSpec = None
        diskSpec = self.createVirtualDisk(datastoreName, diskCtlrKey,
                                          datastoreRef, diskSizeMB)


        # Add a NIC. the network Name must be set as the device name
        # to create the NIC.
        nicSpec = ns0.VirtualDeviceConfigSpec_Def('').pyclass()
        if networkName:
            nicSpec.set_element_operation('add')
            nic = ns0.VirtualPCNet32_Def('').pyclass()
            nicBacking = ns0.VirtualEthernetCardNetworkBackingInfo_Def('').pyclass()
            nicBacking.set_element_deviceName(networkName)
            nic.set_element_addressType('generated')
            nic.set_element_backing(nicBacking)
            nic.set_element_key(4)
            nicSpec.set_element_device(nic)

        deviceConfigSpec = [ scsiCtrlSpec, diskSpec ]
        if ideCtlr:
            deviceConfigSpec.append(cdSpec)
        deviceConfigSpec.append(nicSpec)

        configSpec.set_element_deviceChange(deviceConfigSpec)
        configSpec.set_element_name(vmName)
        return configSpec

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
        l = []
        for specName in ('visitFolders', 'dcToHf', 'dcToVmf', 'crToH',
                         'crToRp', 'HToVm', 'rpToVm'):
            spec = visitFolders.new_selectSet()
            spec.set_element_name(specName)
            l.append(spec)
        visitFolders.set_element_selectSet(l)
        visitFolders.set_element_name('visitFolders')
        specs = [ visitFolders, dcToVmf, dcToHf, crToH, crToRp,
                  rpToRp, hToVm, rpToVm ]
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
            req = DestroyPropertyFilterRequestMsg()
            req.set_element__this(filterSpecRef)
            self._service.DestroyPropertyFilter(req)

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
            ret[mor] = props
        return ret

    def getDatacenters(self):
        propsWanted = {'Datacenter': ['name']}
        return self.getProperties(propsWanted)

    def getVirtualMachines(self, propertyList):
        propsWanted = {'VirtualMachine': propertyList}
        return self.getProperties(propsWanted)

    def createVM(self, dcName, vmName, dataStore=None,
                 annotation=None, memory=512, cpus=1,
                 guestOsId='winXPProGuest'):
        dc = self.getDecendentMoRef(None, 'Datacenter', dcName)
        if not dc:
            raise RuntimeError('Datacenter ' + dc + ' not found')

        hostFolder = self.getMoRefProp(dc, 'hostFolder')
        computeResources = self.getDecendentMoRefs(hostFolder, 'ComputeResource')
        hostName = None
        if hostName:
            hostmor = self.getDecendentMoRef(hostFolder, 'HostSystem', hostName)
            if not host:
                raise RuntimeError('Host ' + hostName + ' not found')
        else:
            # pick the first host we find
            # FIXME: this was supposed to look up in dataCenter, but that
            # is not working
            hostmor = self.getFirstDecendentMoRef(hostFolder, 'HostSystem')

        # find the compute resource for the host we're going to use
        crmor = None
        nodeHostName = self.getDynamicProperty(hostmor, 'name')
        for cr in computeResources:
            crHosts = self.getDynamicProperty(cr, 'host')
            for crHost in crHosts.get_element_ManagedObjectReference():
                hostName = self.getDynamicProperty(crHost, 'name')
                if hostName.lower() == nodeHostName.lower():
                    crmor = cr
                    break
        if not crmor:
            raise RuntimeError('No Compute Resource Found On Specified Host')

        # now get the resourcePool for the compute resource
        resourcePool = self.getMoRefProp(crmor, 'resourcePool')
        # and vmFolder for the datacenter
        vmFolder = self.getMoRefProp(dc, 'vmFolder')
        vmConfigSpec = self.createVmConfigSpec(vmName, dataStore, 100, crmor,
                                               hostmor)
        if annotation:
            vmConfigSpec.set_element_annotation(annotation)
        vmConfigSpec.set_element_memoryMB(memory)
        vmConfigSpec.set_element_numCPUs(cpus)
        vmConfigSpec.set_element_guestId(guestOsId)

        req = CreateVM_TaskRequestMsg()
        req.set_element__this(vmFolder)
        req.set_element_config(vmConfigSpec)
        req.set_element_pool(resourcePool)
        req.set_element_host(hostmor)
        ret = self._service.CreateVM_Task(req)
        task = ret.get_element_returnval()
        return task

    def findVMByUUID(self, uuid):
        searchIndex = self._sic.get_element_searchIndex()
        req = FindByUuidRequestMsg()
        req.set_element__this(searchIndex)
        req.set_element_uuid(uuid)
        req.set_element_vmSearch(True)
        ret = self._service.FindByUuid(req)
        return ret.get_element_returnval()

    def setExtraConfig(self, vm, options):
        req = ReconfigVM_TaskRequestMsg()
        spec = req.new_spec()
        l = []
        for key, value in options.iteritems():
            option = ns0.OptionValue_Def('').pyclass()
            option.set_element_key(key)
            option.set_element_value(value)
            l.append(option)
        spec.set_element_extraConfig(l)
        return self._reconfigVM(vm, spec)

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

    def getVIConfig(self):
        props = self.getProperties({'Datacenter': [ 'name',
                                                    'hostFolder',
                                                    'datastore',
                                                    'network'],
                                    'HostSystem': [ 'name',
                                                    'datastore',
                                                    'network' ],
                                    'ComputeResource': [ 'name',
                                                         'datastore',
                                                         'parent',
                                                         'host',
                                                         'resourcePool',
                                                         'network' ],
                                    'ResourcePool': [ 'name',
                                                      'parent' ],
                                    })
        crs = []
        hostFolderToDataCenter = {}
        rps = {}
        childRps = {}
        nameMap = dict((x[0], x[1]['name']) for x in props.iteritems())

        for mor, morProps in props.iteritems():
            # this is ClusterComputeResource in case of DRS
            objType = mor.get_attribute_type()
            if objType.endswith('ComputeResource'):
                crs.append(mor)
            elif objType == 'Datacenter':
                # build a map from host folder -> data center
                dc = Datacenter(mor, morProps)
                hostFolderToDataCenter[morProps['hostFolder']] = dc
            elif objType == 'ResourcePool':
                rps[mor] = morProps
                l = childRps.setdefault(morProps['parent'], [])
                l.append(mor)

        ret = []

        vicfg = VIConfig()
        for cr in crs:
            configTarget = self.getConfigTarget(cr)
            for ds in configTarget.get_element_datastore():
                ds = ds.get_element_datastore()
                nameMap[ds.get_element_datastore()] = ds.get_element_name()
            crProps = props[cr]
            crRp = crProps['resourcePool']
            crRpsMors = childRps[crRp]
            crRps = dict(x for x in props.iteritems() if x[0] in rps)
            crRps[crRp] = props[crRp]
            cr = ComputeResource(cr, crProps, configTarget, crRps)
            dc = hostFolderToDataCenter[crProps['parent']]
            dc.addComputeResource(cr)

        for dc in hostFolderToDataCenter.values():
            vicfg.addDatacenter(dc)
        vicfg.updateNamemap(nameMap)
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
        cloneSpec.set_element_powerOn(True)
        # set up the data relocation
        loc = cloneSpec.new_location()
        #loc.set_element_datastore(ds)
        loc.set_element_pool(rp)
        import epdb;epdb.st()
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
        return self.waitForTask(task)

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

    def logout(self):
        req = LogoutRequestMsg()
        req.set_element__this(self._sic.get_element_sessionManager())
        self._service.Logout(req)

    def __del__(self):
        if self._loggedIn:
            self.logout()
