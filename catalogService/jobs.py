#!/usr/bin/python2.4
#
# Copyright (c) 2010 rPath, Inc.

from rpath_job import api1 as rpath_job

class InstanceLaunchJob(rpath_job.LogBaseJob):
    _fieldTypes = rpath_job.LogBaseJob._fieldTypes.copy()
    _fieldTypes['imageId'] = rpath_job.FieldString
    _fieldTypes['cloudType'] = rpath_job.FieldString
    _fieldTypes['cloudName'] = rpath_job.FieldString
    _fieldTypes['launchData'] = rpath_job.FieldString

class VersionUpdateLaunchJob(rpath_job.LogBaseJob):
    _fieldTypes = rpath_job.LogBaseJob._fieldTypes.copy()
    _fieldTypes = rpath_job.LogBaseJob._fieldTypes.copy()
    _fieldTypes['instanceId'] = rpath_job.FieldString
    _fieldTypes['cloudType'] = rpath_job.FieldString
    _fieldTypes['cloudName'] = rpath_job.FieldString

class CatalogJobStore(rpath_job.JobStore):
    _storageSubdir = "catalog-jobs"

class LaunchJobStore(CatalogJobStore):
    jobType = "instance-launch"
    jobFactory = InstanceLaunchJob
    # XXX this is not the proper place to indicate the conversion to href
    resultIsHref = True

class ApplianceVersionUpdateJobStore(CatalogJobStore):
    jobType = "appliance-version-update"
    jobFactory = VersionUpdateLaunchJob
    # XXX this is not the proper place to indicate the conversion to href
    resultIsHref = False
