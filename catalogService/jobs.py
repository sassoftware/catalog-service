#!/usr/bin/python2.4
#
# Copyright (c) 2010 rPath, Inc.

from rpath_job import api1 as rpath_job
HistoryEntry = rpath_job.HistoryEntry
ResultResource = rpath_job.ResultResource

class InstanceLaunchJob(rpath_job.HistoryBaseJob):
    _fieldTypes = rpath_job.HistoryBaseJob._fieldTypes.copy()
    _fieldTypes['cloudType'] = rpath_job.FieldString
    _fieldTypes['cloudName'] = rpath_job.FieldString
    _fieldTypes['system'] = rpath_job.FieldInteger

class VersionUpdateLaunchJob(rpath_job.HistoryBaseJob):
    _fieldTypes = rpath_job.HistoryBaseJob._fieldTypes.copy()
    _fieldTypes['instanceId'] = rpath_job.FieldString
    _fieldTypes['cloudType'] = rpath_job.FieldString
    _fieldTypes['cloudName'] = rpath_job.FieldString

class InstanceUpdateJob(rpath_job.HistoryBaseJob):
    _fieldTypes = rpath_job.HistoryBaseJob._fieldTypes.copy()
    _fieldTypes['instanceId'] = rpath_job.FieldString
    _fieldTypes['cloudType'] = rpath_job.FieldString
    _fieldTypes['cloudName'] = rpath_job.FieldString

class CatalogJobStore(rpath_job.JobStore):
    _storageSubdir = "catalog-jobs"

class LaunchJobStore(CatalogJobStore):
    jobType = "instance-launch"
    jobFactory = InstanceLaunchJob
    resultClass = ResultResource

class ApplianceVersionUpdateJobStore(CatalogJobStore):
    jobType = "software-version-refresh"
    jobFactory = VersionUpdateLaunchJob
    resultClass = unicode

class ApplianceUpdateJobStore(CatalogJobStore):
    jobType = "instance-update"
    jobFactory = InstanceUpdateJob
    resultClass = unicode

class CatalogSqlJobStore(rpath_job.SqlJobStore):
    pass

class LaunchJobSqlStore(CatalogSqlJobStore):
    jobType = LaunchJobStore.jobType
    jobFactory = InstanceLaunchJob
    resultClass = ResultResource
    BackingStore = rpath_job.TargetSqlBacking

class ApplianceVersionUpdateJobSqlStore(CatalogSqlJobStore):
    jobType = ApplianceVersionUpdateJobStore.jobType
    jobFactory = VersionUpdateLaunchJob
    resultClass = unicode
    BackingStore = rpath_job.ManagedSystemsSqlBacking

class ApplianceUpdateJobSqlStore(CatalogSqlJobStore):
    jobType = ApplianceUpdateJobStore.jobType
    jobFactory = InstanceUpdateJob
    resultClass = unicode
    BackingStore = rpath_job.ManagedSystemsSqlBacking
