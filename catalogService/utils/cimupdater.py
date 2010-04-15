#!/usr/bin/python2.4
#
# Copyright (c) 2009 rPath, Inc.
#

import time

import wbemlib

WBEMException = wbemlib.WBEMException

class CIMUpdater(object):
    '''
    Class for checking and applying updates to a remote appliance via CIM.
    Exposes both asynchronous and synchronous methods to check for and apply
    updates.
    '''

    DEFAULT_TIMEOUT = 3600

    def __init__(self, host, x509=None, logger=None):
        """
        Connect to the specified host.
        x509 should be a dictionary with cert_file and key_file as keys, and
        paths to the corresponding X509 components as values.
        """

        self.server = wbemlib.WBEMServer(host, debug = True, x509 = x509)
        self._jobStates = None
        self._updateCheckReturnValues = None
        self._elementSoftwareStatusValues = None
        self.logger = logger

    def _normalizeValueMap(self, values, valueMap, cimType):
        typeFunc = self._toPythonType(cimType)
        return dict(zip((typeFunc(x) for x in valueMap), values))

    class WrapType(object):
        def __init__(self, typeFunc):
            self.typeFunc = typeFunc

        def __call__(self, value):
            try:
                return self.typeFunc(value)
            except ValueError:
                return value

    @classmethod
    def _toPythonType(cls, cimType):
        if cimType.startswith('int') or cimType.startswith('uint'):
            return cls.WrapType(int)
        raise RuntimeError("Unhandled type %s" % cimType)

    def _getJobStates(self, force=False):
        '''
        Get the possible job states and format them as an easy to use
        dictionary.  Will only happen once per session and result is saved as
        a class property (unless the force parameter is used.)
        '''
        if not self._jobStates or force:
            cimClass = self.server.GetClass('VAMI_UpdateConcreteJob')
            jobStates = cimClass.properties['JobState'].qualifiers

            # Turn jobStates into key/value pairs of integers and
            # descriptions so that it's easy to work with.
            self._jobStates = self._normalizeValueMap(
                jobStates['Values'].value, jobStates['ValueMap'].value)

        return self._jobStates
    jobStates = property(_getJobStates)

    def _getSoftwareElementStatusValues(self, force = False):
        if not self._elementSoftwareStatusValues or force:
            cimClass = self.server.VAMI_ElementSoftwareIdentity.GetClass()
            prop = cimClass.properties['ElementSoftwareStatus']
            states = prop.qualifiers
            self._elementSoftwareStatusValues = self._normalizeValueMap(
                states['Values'].value, states['ValueMap'].value,
                prop.type)
        return self._elementSoftwareStatusValues
    elementSoftwareStatusValues = property(_getSoftwareElementStatusValues)

    def _unexpectedReturnCode(self, CIMClassName, methodName, returnCode, expectedReturnCode):
        returnCodes = self.server.getMethodReturnCodes(CIMClassName, methodName)
        returnMsg = returnCodes[str(returnCode)]
        raise wbemlib.WBEMUnexpectedReturnException(
            expectedReturnCode, returnCode, returnMsg)
        
    def isJobComplete(self, instance):
        jobState = instance.properties['JobState'].value
        # Any state >= 7 (Completed) is final
        return (jobState >= 7), instance

    def isJobSuccessful(self, instance):
        if instance is None:
            return False
        jobState = instance.properties['JobState'].value
        return jobState == 7

    def pollJobForCompletion(self, job, timeout = DEFAULT_TIMEOUT):
        '''
        Returns when the given job is complete, or when the specified timeout
        has passed.
        The call returns None on timeout, or the job instance otherwise.
        '''
        timeEnd = time.time() + timeout
        while time.time() < timeEnd:
            instance = self.server.GetInstance(job)
            jobCompleted, instance = self.isJobComplete(instance)
            print "jobCompleted", jobCompleted, instance.properties['JobState'].value
            if jobCompleted:
                return instance
            time.sleep(1)
        return None

    def getInstalledItemList(self):
        # Select the ones that have Installed and Available as
        # ElementSoftwareStatus. See the mof for the value mappings
        return self._filterItemList([2, 6])

    def getAvailableItemList(self):
        return self._filterItemList([8])

    def getInstalledGroups(self):
        # XXX this is fairly low-level, we should probably try to wrap some of
        # these in wbemlib
        installedGroups = self.getInstalledItemList()
        ids = [ g['Antecedent']['InstanceID'] for g in installedGroups ]
        instanceNames = [ wbemlib.pywbem.cim_obj.CIMInstanceName(
            'VAMI_SoftwareIdentity', keybindings = dict(InstanceId = i))
            for i in ids ]
        instances = [ self.server.VAMI_SoftwareIdentity.GetInstance(i)
            for i in instanceNames ]
        ret = [ "%s=%s" % (x['name'], x['VersionString'])
            for x in instances ]
        return ret

    def _filterItemList(self, states):
        insts = self.server.VAMI_ElementSoftwareIdentity.EnumerateInstances()
        targetState = set(states)
        insts = [ x for x in insts
            if targetState.issubset(x.properties['ElementSoftwareStatus'].value)]
        return insts

    def updateCheckAsync(self):
        result = self.server.VAMI_SoftwareInstallationService.CheckAvailableUpdates()

        if result[0] != 4096L:
            self._unexpectedReturnCode('VAMI_SoftwareInstallationService', 
                'CheckAvailableUpdates', result[0], 4096L)

        job = result[1]['job']
        return job

    def updateCheck(self, timeout = DEFAULT_TIMEOUT):
        job = self.updateCheckAsync()
        return self.pollJobForCompletion(job, timeout = timeout)

    def applyUpdateAsync(self):
        result = self.server.VAMI_SoftwareInstallationService.InstallFromSoftwareIdentity()
        return result[1]['job']

    def applyUpdate(self, timeout = DEFAULT_TIMEOUT):
        job = self.applyUpdateAsync()
        return self.pollJobForCompletion(job, timeout = timeout)

    def checkAndApplyUpdate(self, timeout = DEFAULT_TIMEOUT):
        job = self.updateCheck(timeout = timeout)
        if job is None:
            return
        if not self.isJobSuccessful(job):
            error = self.server.getError(job)
            self.log_error(error)
            raise RuntimeError("Error checking for available software")
        job = self.applyUpdate(timeout = timeout)
        if not self.isJobSuccessful(job):
            error = self.server.getError(job)
            self.log_error(error)
            raise RuntimeError("Error while applying updates")

    def log_error(self, error):
        if self.logger:
            self.logger.error(error)

if __name__ == '__main__':
    host = 'https://ec2-174-129-153-120.compute-1.amazonaws.com'
    x509 = dict(cert_file = "/tmp/cert.crt", key_file = "/tmp/cert.key")
    updater = CIMUpdater(host, x509 = x509)
    updater.checkAndApplyUpdate()

