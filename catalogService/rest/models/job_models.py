#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import rpath_xmllib as xmllib

import xmlNode

class JobHistoryEntry(xmlNode.BaseNode):
    tag = "historyEntry"
    multiple = True
    __slots__ = [ 'timestamp', 'content']

    def __repr__(self):
        return "<%s at %x, timestamp=%s>" % (self.__class__.__name__,
            id(self), self.getTimestamp())

class JobResult(xmlNode.BaseMultiNode):
    tag = "result"
    __slots__ = [ 'href' ]
    _slotAttributes = set(['href'])

class Job(xmlNode.BaseNode):
    tag = 'job'
    __slots__ = [ 'id', 'type', 'status', 'created', 'modified', 'createdBy',
                  'expiration', 'result', 'errorResponse', 'history', 'imageId',
                  'cloudName', 'cloudType', 'instanceId', ]
    _slotAttributes = set(['id'])
    _slotTypeMap = dict(created = int, modified = int, expiration = int,
        history = JobHistoryEntry, result = JobResult, errorResponse = xmlNode.BaseNode)

class Jobs(xmlNode.BaseNodeCollection):
    tag = 'jobs'

class Handler(xmllib.DataBinder):
    jobClass = Job
    jobsClass = Jobs
    jobHistoryEntryClass = JobHistoryEntry
    jobResultClass = JobResult
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        for cls in [ self.jobClass, self.jobsClass, self.jobHistoryEntryClass,
                     self.jobResultClass ]:
            self.registerType(cls, cls.tag)
