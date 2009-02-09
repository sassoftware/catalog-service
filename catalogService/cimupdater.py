#!/usr/bin/python2.4
#
# Copyright (c) 2009 rPath, Inc.
#

import time

import wbemlib

class CIMUpdater(object):
    '''
    Class for checking and applying updates to a remote appliance via CIM.
    Exposes both asynchronous and synchronous methods to check for and apply
    updates.
    '''
    
    def __init__(self, host):
        self.server = wbemlib.WBEMServer(host, debug = True)
        self._jobStates = None
        self._updateCheckReturnValues = None

    def _normalizeValueMap(self, values, valueMap):
        valuesDict = {}
        valuePairs = [(valueMap.pop(), values.pop()) for x in xrange(len(values))]
        for k, v in valuePairs:
            valuesDict[k] = v
        return valuesDict            
        
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

    def _unexpectedReturnCode(self, CIMClassName, methodName, returnCode, expectedReturnCode):
        returnCodes = self.server.getMethodReturnCodes(CIMClassName, methodName)
        returnMsg = returnCodes[str(returnCode)]
        raise wbemlib.WBEMUnexpectedReturnException(
            expectedReturnCode, returnCode, returnMsg)
        
    def isJobComplete(self, job):
        instance = self.server.GetInstance(job)
        jobState = str(instance.properties['JobState'].value)
        if self.jobStates[jobState] == 'Completed':
            return 1
        else:
            return 0

    def pollJobForCompletion(self, job):
        '''
        Returns when the given job is complete.
        '''
        while(not self.isJobComplete(job)):
            print "job is not complete"
            time.sleep(1)
        print "job is complete"            

    def updateCheckAsync(self):
        result = self.server.VAMI_SoftwareInstallationService.CheckAvailableUpdates()

        if result[0] != 4096L:
            self._unexpectedReturnCode('VAMI_SoftwareInstallationService', 
                'CheckAvailableUpdates', result[0], 4096L)

        job = result[1]['job']
        return job

    def updateCheck(self):
        job = self.updateCheckAsync()
        return self.pollJobForCompletion(job)

    def applyUpdateAsync(self):
        result = self.server.VAMI_SoftwareInstallationService.InstallFromSoftwareIdentity()
        return result[1]['job']

    def applyUpdate(self):
        job = self.applyUpdateAsync()
        return self.pollJobForCompletion(job)

    def checkAndApplyUpdate(self):
        self.updateCheck()
        self.applyUpdate()


if __name__ == '__main__':
    host = 'https://172.16.175.134'
    updater = CIMUpdater(host)
    updater.updateCheck()

