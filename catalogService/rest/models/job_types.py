#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import rpath_xmllib as xmllib

import xmlNode

class JobType(xmlNode.BaseNode):
    tag = 'jobType'
    __slots__ = [ 'id', 'type' ]
    _slotAttributes = set(['id'])

class JobTypes(xmlNode.BaseNodeCollection):
    tag = 'jobTypes'

class Handler(xmllib.DataBinder):
    jobTypeClass = JobType
    jobTypesClass = JobTypes
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        for cls in [ self.jobTypeClass, self.jobTypesClass, ]:
            self.registerType(cls, cls.tag)
