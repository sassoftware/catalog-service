#!/usr/bin/python2.4
#
# Copyright (c) 2009 rPath, Inc.
#

import os
import time

from catalogService import storage

class BaseJob(object):
    __slots__ = [ 'created', 'modified', 'id', '_store', '_state' ]

    def __init__(self, store, jobId, created = None, modified = None):
        self._store = store
        self.id = jobId
        if created is not None:
            created = float(created)
        if modified is not None:
            modified = float(modified)
        self.created = created
        self.modified = modified
        self.state = "Created"

    def _getState(self):
        return self._state

    def _setState(self, state):
        self._state = state
        return self

    state = property(_getState, _setState)

    def _updateTimestamp(self, fname, timestamp = None):
        if timestamp is None:
            timestamp = time.time()
        timestamp =  "%.3f" % timestamp
        self._store.set((self.id, fname), timestamp)
        return float(timestamp)

    def updateModified(self, timestamp = None):
        self.modified = self._updateTimestamp("modified", timestamp = timestamp)
        return self

    def updateCreated(self, timestamp = None):
        self.created = self._updateTimestamp("created", timestamp = timestamp)
        return self

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
        self.updateModified()

    def _readLogs(self):
        del self._logs[:]
        self._logs.extend(self.logEntryClass(self._store.get(ts),
                                             os.path.basename(ts))
            for ts in self._store.enumerate((self.id, "logs")))

class JobStore(object):
    __slots__ = [ '_store' ]

    storageFactory = storage.DiskStorage
    jobFactory = BaseJob
    jobType = None
    # Job expires in 2 hours
    jobTTL = 7200

    _storageSubdir = "catalog-jobs"

    def __init__(self, storePath):
        self._store = self.storageFactory(storage.StorageConfig(
            os.path.join(storePath, self._storageSubdir)))

    def create(self, created = None, modified = None):
        """Create a new job"""
        if modified is None:
            modified = time.time()
        if created is None:
            created = modified
        store = self._store
        jobId = store.newCollection(keyPrefix = self.jobType)
        job = self.jobFactory(store, jobId, created, modified)
        job.updateCreated(created)
        job.updateModified(modified)
        return job

    def get(self, jobId):
        store = self._store
        if not store.exists(jobId):
            return None
        return self.jobFactory(self._store, jobId,
            store.get((jobId, "created")),
            store.get((jobId, "modified")))

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
            if job.modified + self.jobTTL < now:
                store.delete(jobId)
                continue
            yield job

class LaunchJobStore(JobStore):
    jobType = "launch"
    jobFactory = LogBaseJob

def createStore(storagePath):
    storePath = os.path.join(storagePath, "catalog-jobs")
    return JobStore(storePath)
