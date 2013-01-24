#!/usr/bin/python2.4
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


from rpath_job import api1 as rpath_job
HistoryEntry = rpath_job.HistoryEntry
ResultResource = rpath_job.ResultResource

class InstanceLaunchJob(rpath_job.HistoryBaseJob):
    _fieldTypes = rpath_job.HistoryBaseJob._fieldTypes.copy()
    _fieldTypes['cloudType'] = rpath_job.FieldString
    _fieldTypes['cloudName'] = rpath_job.FieldString
    _fieldTypes['system'] = rpath_job.FieldInteger

class DeployImageJob(InstanceLaunchJob):
    pass

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

class DeployImageJobStore(CatalogJobStore):
    jobType = "image-deployment"
    jobFactory = DeployImageJob
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

class DeployImageJobSqlStore(LaunchJobSqlStore):
    jobType = DeployImageJobStore.jobType
    jobFactory = LaunchJobSqlStore.jobFactory

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
