#
# Copyright (C) 2009 rPath, Inc.
#

import os

from catalogService import job_models
from catalogService import job_store
from catalogService import job_types
from catalogService.rest import base
from catalogService.rest.response import XmlResponse, XmlStringResponse

class JobTypeController(base.BaseController):
    modelName = 'jobId'
    supportedJobTypes = {
        'appliance-version-update' : 'Appliance Version Update',
    }
    storagePathSuffix = 'jobs'
    def index(self, request, jobType):
        if jobType not in self.supportedJobTypes:
            raise NotImplementedError

        self._setStore()
        jobs = (self.jobModelFromJob(request, j, jobType)
            for j in sorted(self.jobStore.enumerate(),
                key = lambda x: x.created))
        ret = job_models.Jobs()
        ret.extend(jobs)
        return XmlResponse(ret)

    def jobModelFromJob(self, request, job, jobType):
        logs = [ job_models.JobLog(
                    timestamp = "%.3f" % x.timestamp, content = x.content)
                 for x in job.logs ]
        jobId = self.url(request, 'jobs', 'types', os.path.dirname(job.id),
            'jobs', os.path.basename(job.id))
        ret = job_models.Job(id = jobId, status = job.status,
            result = job.result or None,
            created = int(job.created), modified = int(job.modified),
            expiration = int(job.expiration), log = logs)
        return ret

    def _setStore(self):
        spath = self._getStorePath()
        self.jobStore = job_store.ApplianceVersionUpdateJobStore(spath)

    def _getStorePath(self):
        return os.path.join(self.cfg.storagePath, self.storagePathSuffix)

    def get(self, request, jobType, jobId):
        if jobType not in self.supportedJobTypes:
            raise NotImplementedError

        self._setStore()
        internalId = (jobType, jobId)
        job = self.jobStore.get(internalId)
        return XmlResponse(self.jobModelFromJob(request, job, jobType))


class JobTypesController(base.BaseController):
    modelName = 'jobType'
    urls = { 'jobs' : JobTypeController }
    def index(self, request):
        ret = job_types.JobTypes()
        for jtype, jtypeLabel in JobTypeController.supportedJobTypes.items():
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
