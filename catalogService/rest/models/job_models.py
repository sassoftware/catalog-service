#!/usr/bin/python
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
