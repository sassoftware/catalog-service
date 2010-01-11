#
# Copyright (C) 2009 rPath, Inc.
#

from lxml import etree
import os

from catalogService import nodeFactory
from catalogService import job_models
from catalogService import jobs
from catalogService import job_types
from catalogService.rest import base
from catalogService.rest.response import XmlResponse, XmlStringResponse

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
        'appliance-version-update' : ('Appliance Version Update',
            jobs.ApplianceVersionUpdateJobStore),
        'instance-launch' : ('Instance Launch',
            jobs.LaunchJobStore),
    }
    storagePathSuffix = 'jobs'
    def index(self, request, jobType):
        if jobType not in self.supportedJobTypes:
            raise NotImplementedError

        self._setStore(jobType)
        # Build filter object, passing in the query arguments
        filter = JobFilter(request.GET)
        jobs = filter.matchIterator(self.jobStore.enumerate())
        jobs = (self.jobModelFromJob(request, j, jobType)
            for j in sorted(jobs, key = lambda x: x.created))
        ret = job_models.Jobs()
        ret.extend(jobs)
        return XmlResponse(ret)

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
        logs = [ job_models.JobLog(
                    timestamp = "%.3f" % x.timestamp, content = x.content)
                 for x in job.logs ]
        jobId = self.url(request, 'jobs', 'types', os.path.dirname(job.id),
            'jobs', os.path.basename(job.id))
        results = job.result
        resultIsHref = self.supportedJobTypes[jobType][1].resultIsHref
        if results:
            results = results.split('\n')
            if resultIsHref:
                results = [ job_models.JobResult().setHref(x)
                    for x in results ]
            else:
                results = [ job_models.JobResult(None, None, x)
                    for x in results ]
        else:
            results = [ ] # empty string should be None
        errorResponse = job.errorResponse
        if errorResponse:
            try:
                errorResponse = etree.fromstring(errorResponse)
                errorResponse = self.XmlPassThrough(errorResponse)
            except etree.LxmlError:
                pass
        params = dict(id = jobId, status = job.status,
            type = jobType,
            result = results,
            errorResponse = errorResponse,
            cloudName = job.cloudName, cloudType = job.cloudType,
            created = int(job.created), modified = int(job.modified),
            expiration = int(job.expiration), log = logs)
        for k in ['imageId', 'instanceId']:
            params[k] = getattr(job, k, None)
        nf = nodeFactory.NodeFactory(baseUrl = request.baseUrl,
            cloudType = job.cloudType, instanceLaunchJobFactory = job_models.Job)
        return nf.newInstanceLaunchJob(**params)

    def _setStore(self, jobType):
        jobStoreClass = self.supportedJobTypes[jobType][1]
        spath = self._getStorePath()
        self.jobStore = jobStoreClass(spath)

    def _getStorePath(self):
        return os.path.join(self.cfg.storagePath, self.storagePathSuffix)

    def get(self, request, jobType, jobId):
        if jobType not in self.supportedJobTypes:
            raise NotImplementedError

        self._setStore(jobType)
        internalId = (jobType, jobId)
        job = self.jobStore.get(internalId)
        return XmlResponse(self.jobModelFromJob(request, job, jobType))


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
