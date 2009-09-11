#!/usr/bin/python2.4
#
# Copyright (c) 2009 rPath, Inc.
#

import os
import time

from catalogService import storage

class Field(object):
    @classmethod
    def fromString(cls, value):
        if value is None:
            return ''
        return value

    @classmethod
    def toString(cls, value):
        if value is None:
            return None
        return str(value)

class FieldString(Field):
    pass

class FieldTimestamp(Field):
    @classmethod
    def fromString(cls, value):
        if value is None or value == '':
            return None
        return float(value)

    @classmethod
    def toString(cls, value):
        if value is None:
            return None
        return "%.3f" % value

class FieldInteger(Field):
    @classmethod
    def fromString(cls, value):
        if value is None or value == '':
            return None
        return int(value)

    @classmethod
    def toString(cls, value):
        if value is None:
            return None
        return "%d" % value

class BaseJob(object):
    __slots__ = [ 'id', 'jobId', '_store', '_fields' ]
    _fieldTypes = dict(
        createdBy = FieldString,
        type = FieldString,
        status = FieldString,
        created = FieldTimestamp,
        modified = FieldTimestamp,
        expiration = FieldTimestamp,
        ttl = FieldInteger,
        # Result, if the job's status is COMPLETED. Multiple results may be
        # supported, they are saved newline-separated.
        result = FieldString,
        # Error response, if the job's status is FAILED.
        errorResponse = FieldString,
        pid = FieldInteger,
    )
    _defaultTTL = 7200
    _DEFAULT = object()
    STATUS_STARTED = "Started"
    STATUS_RUNNING = "Running"
    STATUS_FAILED = "Failed"
    STATUS_COMPLETED = "Completed"

    def __init__(self, store, jobId, **kwargs):
        self._store = store
        self._fields = dict()
        self.id = store._sanitizeKey(jobId)
        self.jobId = os.path.basename(self.id)
        self._load(**kwargs)
        self._setFieldsDefaults()

    def _setFieldsDefaults(self):
        if not self._get('ttl'):
            self._set('ttl', self._defaultTTL, updateModified = False)
        if not self._get('modified', None):
            self._set('modified', time.time())
        if not self.expiration:
            self._set('expiration', self.modified + self.ttl,
                updateModified = False)
        if not self.status:
            self._set('status', self.STATUS_STARTED, updateModified = False)

    def setStatus(self, status):
        self._set('status', status)

    def _load(self, **kwargs):
        for fname, ftype in self._fieldTypes.items():
            kwval = kwargs.get(fname, None)
            fval = self._getField(fname, ftype)
            if kwval is not None:
                kwval = ftype.fromString(kwval)
                if kwval != fval:
                    self._setField(fname, ftype, kwval)
                continue
            self._fields[fname] = fval

    def _getField(self, field, fieldType, default = _DEFAULT):
        if default is self._DEFAULT:
            default = None
        value = self._store.get((self.id, field), default = default)
        return fieldType.fromString(value)

    def _deleteField(self, field):
        return self._store.delete((self.id, field))

    def _setFieldRaw(self, field, value):
        if value is None:
            self._deleteField(field)
            return None
        self._store.set((self.id, field), value)
        return value

    def _setField(self, field, ftype, value):
        self._fields[field] = value
        value = ftype.toString(value)
        return self._setFieldRaw(field, value)

    def _set(self, field, value, updateModified = True):
        ftype = self._fieldTypes.get(field)
        value = self._setField(field, ftype, value)
        if field != 'modified' and updateModified:
            self._setField('modified', FieldTimestamp,
                           self._getCurrentTimestamp())
        return value

    @classmethod
    def _getCurrentTimestamp(cls):
        return time.time()

    def _get(self, field, default = _DEFAULT):
        ftype = self._fieldTypes.get(field)
        if ftype is None:
            if default is self._DEFAULT:
                raise AttributeError(field)
            return default
        if default is self._DEFAULT:
            default = None
        return self._fields.get(field, default)

    def __getattr__(self, field):
        return self._get(field)

    def __setattr__(self, field, value):
        if field in self._fieldTypes:
            return self._set(field, value)
        return object.__setattr__(self, field, value)

class LogEntry(object):
    __slots__ = [ 'timestamp', 'content', 'type' ]
    def __init__(self, content, timestamp = None):
        if timestamp is None:
            timestamp = time.time()
        else:
            timestamp = float(timestamp)
        self.timestamp = timestamp
        self.content = content

class LogBaseJob(BaseJob):
    __slots__ = [ '_logs' ]
    logEntryClass = LogEntry

    def __init__(self, *args, **kwargs):
        BaseJob.__init__(self, *args, **kwargs)
        self._logs = []
        self._readLogs()

    def _getLogs(self):
        return sorted(self._logs, key = lambda x: x.timestamp)

    def addLog(self, logObj):
        if isinstance(logObj, str):
            logObj = self.logEntryClass(logObj)
        self._writeLog(logObj)
        self._logs.append(logObj)

    logs = property(_getLogs)

    def _writeLog(self, logObj):
        timestamp = "%.3f" % logObj.timestamp
        self._store.set((self.id, "logs", timestamp), logObj.content)
        self.modified = time.time()

    def _readLogs(self):
        del self._logs[:]
        self._logs.extend(self.logEntryClass(self._store.get(ts),
                                             os.path.basename(ts))
            for ts in self._store.enumerate((self.id, "logs")))

class InstanceLaunchJob(LogBaseJob):
    _fieldTypes = LogBaseJob._fieldTypes.copy()
    _fieldTypes['imageId'] = FieldString
    _fieldTypes['cloudType'] = FieldString
    _fieldTypes['cloudName'] = FieldString
    _fieldTypes['launchData'] = FieldString

class VersionUpdateLaunchJob(LogBaseJob):
    _fieldTypes = LogBaseJob._fieldTypes.copy()
    _fieldTypes = LogBaseJob._fieldTypes.copy()
    _fieldTypes['instanceId'] = FieldString
    _fieldTypes['cloudType'] = FieldString
    _fieldTypes['cloudName'] = FieldString

class JobStore(object):
    __slots__ = [ '_store' ]

    storageFactory = storage.DiskStorage
    jobFactory = BaseJob
    jobType = None

    _storageSubdir = "catalog-jobs"

    def __init__(self, storePath):
        self._store = self.storageFactory(storage.StorageConfig(
            os.path.join(storePath, self._storageSubdir)))

    def create(self, jobType = None, **kwargs):
        """Create a new job"""
        if kwargs.get('modified') is None:
            modified = kwargs['modified'] = time.time()
        if kwargs.get('created') is None:
            kwargs['created'] = modified
        store = self._store
        if jobType is None:
            jobType = self.jobType
        kwargs['type'] = jobType
        jobId = store.newCollection(keyPrefix = jobType)
        job = self.jobFactory(store, jobId, **kwargs)
        return job

    def get(self, jobId):
        store = self._store
        if not store.exists(jobId):
            return None
        job = self.jobFactory(store, jobId)
        return job

    def enumerate(self):
        """Emumerate available jobs"""
        now = time.time()
        store = self._store
        for jobId in store.enumerate(keyPrefix = self.jobType):
            job = self.get(jobId)
            if job is None:
                # Race condition, the job went away after we enumerated it
                continue
            # Is the job expired?
            if job.expiration < now:
                store.delete(jobId)
                continue
            yield job

class LaunchJobStore(JobStore):
    jobType = "instance-launch"
    jobFactory = InstanceLaunchJob
    # XXX this is not the proper place to indicate the conversion to href
    resultIsHref = True

class ApplianceVersionUpdateJobStore(JobStore):
    jobType = "appliance-version-update"
    jobFactory = VersionUpdateLaunchJob
    # XXX this is not the proper place to indicate the conversion to href
    resultIsHref = False

def createStore(storagePath):
    storePath = os.path.join(storagePath, "catalog-jobs")
    return JobStore(storePath)
