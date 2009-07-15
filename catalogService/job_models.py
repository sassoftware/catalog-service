#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

from catalogService import xmlNode

class JobLog(xmlNode.BaseNode):
    tag = "log"
    multiple = True
    __slots__ = [ 'timestamp', 'type', 'content']

    def __repr__(self):
        return "<%s at %x, timestamp=%s>" % (self.__class__.__name__,
            id(self), self.getTimestamp())

class Job(xmlNode.BaseNode):
    tag = 'job'
    __slots__ = [ 'id', 'type', 'status', 'created', 'modified', 'createdBy',
                  'expiration', 'result', 'log']
    _slotAttributes = set(['id'])
    _slotTypeMap = dict(created = int, modified = int, expiration = int,
        log = JobLog)

class Jobs(xmlNode.BaseNodeCollection):
    tag = 'jobs'

class Handler(xmllib.DataBinder):
    jobClass = Job
    jobsClass = Jobs
    jobLogClass = JobLog
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        for cls in [ self.jobClass, self.jobsClass, self.jobLogClass ]:
            self.registerType(cls, cls.tag)
