#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

from lxml import etree
import os

from catalogService import nodeFactory
from catalogService.rest.api import base
from catalogService.rest.middleware.response import (XmlResponse,
    XmlStringResponse, XmlSerializableObjectResponse)
from catalogService.rest.models import jobs as jobmodels
from catalogService.rest.models import job_types
from catalogService import jobs

class BaseFilter(object):
    _filterFields = set()

    def __init__(self, filterCriteria):
        self._filterCriteria = [(k, v)
            for (k, v) in filterCriteria.items() if k in self._filterFields]

    def match(self, obj):
        if not self._filterCriteria:
            return obj
        for (k, v) in self._filterCriteria:
            if v is None:
                continue
            if getattr(obj, k, None) != v:
                return None
        return obj

    def matchIterator(self, iterobj):
        for obj in iterobj:
            if self.match(obj) is not None:
                yield obj

class JobFilter(BaseFilter):
    _filterFields = set(['cloudName', 'cloudType', 'status'])

class JobTypeController(base.BaseController):
    modelName = 'jobId'
    supportedJobTypes = {
        'software-version-refresh' : ('Software Version Refresh',
            jobs.ApplianceVersionUpdateJobSqlStore),
        'instance-launch' : ('Instance Launch',
            jobs.LaunchJobSqlStore),
        'instance-update' : ('Instance Update',
            jobs.ApplianceUpdateJobSqlStore),
    }
    storagePathSuffix = 'jobs'
    def index(self, request, jobType):
        if jobType not in self.supportedJobTypes:
            raise NotImplementedError

        self._setStore(jobType)
        # Build filter object, passing in the query arguments
        filter = JobFilter(request.GET)
        storedJobs = filter.matchIterator(
            self.jobStore.enumerate(readOnly=True))
        storedJobs = (self.jobModelFromJob(request, j, jobType)
            for j in sorted(storedJobs, key = lambda x: x.created))
        ret = jobmodels.Jobs()
        ret.addJobs(storedJobs)
        return XmlSerializableObjectResponse(ret)

    class XmlPassThrough(object):
        def __init__(self, doc):
            self.doc = doc
        def getElementTree(self, parent = None):
            if parent is not None:
                parent.append(self.doc)
            return self.doc
        def _getName(self):
            return 'error'

    def jobModelFromJob(self, request, job, jobType):
        jobm = jobmodels.Job()
        jobm.set_type(job.type)
        jobm.set_id(job.id)
        jobm.set_created(job.created)
        jobm.set_modified(job.modified)
        jobm.set_status(job.status)
        jobm.set_cloudType(job.cloudType)
        jobm.set_cloudName(job.cloudName)
        if hasattr(job, 'instanceId'):
            jobm.set_instanceId(job.instanceId)
        hist = job.history
        jobm.history.extend(hist)
        if hist:
            # Until statusMessage is a real field, we set it to be the
            # contents of the last history entry (RBL-6643)
            jobm.set_statusMessage(hist[-1].content)
        jobId = self.url(request, 'jobs', 'types', jobType,
            'jobs', str(job.id))
        results = job.result
        resultClass = self.supportedJobTypes[jobType][1].resultClass
        if results:
            if resultClass is unicode:
                jobm.set_result([ unicode(x) for x in results ])
            else:
                jobm.set_resultResource(
                    [ resultClass(href=x) for x in results ])
        self._fillErrorResponse(jobm, job.errorResponse)
        nf = nodeFactory.NodeFactory(baseUrl = request.baseUrl,
            cloudType = job.cloudType)
        return nf.newInstanceLaunchJob(jobm)

    def _fillErrorResponse(self, job, errorResponse):
        if not errorResponse:
            return
        try:
            errorResponse = etree.fromstring(errorResponse)
        except etree.LxmlError:
            return
        if errorResponse.tag != 'fault':
            return
        code = errorResponse.find('code')
        if code is None:
            return
        message = errorResponse.find('message')
        if message is None:
            return
        tracebackData = errorResponse.find('traceback')
        if tracebackData is not None:
            tracebackData = tracebackData.text
        productCodeData = errorResponse.find('productCode')
        if productCodeData is not None:
            productCodeData = productCodeData.attrib
        job.setErrorResponse(int(code.text), message.text,
            tracebackData = tracebackData, productCodeData = productCodeData)

    def _setStore(self, jobType):
        jobStoreClass = self.supportedJobTypes[jobType][1]
        self.jobStore = jobStoreClass(self.db)

    def get(self, request, jobType, jobId):
        if jobType not in self.supportedJobTypes:
            raise NotImplementedError

        self._setStore(jobType)
        job = self.jobStore.get(jobId, readOnly=True)
        if job is None:
            raise NotImplementedError
        ret = self.jobModelFromJob(request, job, jobType)
        return XmlSerializableObjectResponse(ret)


class JobTypesController(base.BaseController):
    modelName = 'jobType'
    urls = { 'jobs' : JobTypeController }
    def index(self, request):
        ret = job_types.JobTypes()
        for jtype, (jtypeLabel, _) in JobTypeController.supportedJobTypes.items():
            ret.append(job_types.JobType(
                id = self.url(request, 'jobs', 'types', jtype),
                type = jtypeLabel))
        return XmlResponse(ret)

    def get(self, request, jobType):
        # XXX There might be a better way to handle this
        if jobType not in JobTypeController.supportedJobTypes:
            raise NotImplementedError

        return XmlStringResponse("<foo />")

class JobsController(base.BaseController):
    urls = dict(types = JobTypesController)
    def index(self, request):
        # XXX we need to enumerate available methods here
        pass
