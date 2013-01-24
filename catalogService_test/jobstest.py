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


import testsuite
# Bootstrap the testsuite
testsuite.setup()

import os
import time

from conary.lib import util

import testbase
from catalogService.restClient import ResponseError
from catalogService.rest.models import job_types
from catalogService.rest.models import jobs as jobmodels
from catalogService import jobs
from rpath_job import api1 as rpath_job

class ApplianceVersionUpdateJobsTest(testbase.TestCase):
    cloudName = 'vsphere.eng.rpath.com'
    cloudType = 'vmware'

    TARGETS = [
        (cloudType, cloudName, {}),
    ]

    def setUp(self):
        testbase.TestCase.setUp(self)
        self.store = jobs.ApplianceVersionUpdateJobSqlStore(self.restdb)

    def testGetJobsTypes(self):
        job1 = self.store.create(cloudType = self.cloudType,
            cloudName = self.cloudName, instanceId = self.targetSystemIds[0])
        self.restdb.commit()

        srv = self.newService()
        uri = 'jobs/types'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = job_types.Handler()
        response = util.BoundedStringIO(response.read())
        nodes = hndlr.parseFile(response)
        prefix = self.makeUri(client, 'jobs/types')
        self.failUnlessEqual([ x.id for x in nodes],
            [ "%s/%s" % (prefix, x) for x in ['instance-launch',
                                              'software-version-refresh',
                                              'image-deployment',
                                              'instance-update']])

        uri = 'jobs/types/software-version-refresh'
        client = self.newClient(srv, uri)
        response = client.request('GET')
        response.read()

        uri = 'jobs/types/no-such-job-type'
        client = self.newClient(srv, uri)
        resp = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(resp.status, 404)

        uri = 'jobs/types/software-version-refresh/jobs'
        client = self.newClient(srv, uri)
        response = client.request('GET')
        data = response.read()

        storedJobs = jobmodels.Jobs()
        storedJobs.parseStream(data)
        self.failUnlessEqual(len(storedJobs.job), 1)
        self.failUnlessEqual(storedJobs.job[0].get_id(),
            self.makeUri(client, "%s/%s" % (uri, job1.jobId)))

        uri = 'jobs/types/no-such-job-type/jobs'
        client = self.newClient(srv, uri)
        resp = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(resp.status, 404)

    def testGetJobs(self):
        now = time.time()
        job1 = self.store.create(created = now, cloudType = self.cloudType,
            cloudName = self.cloudName, instanceId = self.targetSystemIds[0])
        job1.addHistoryEntry(rpath_job.HistoryEntry("Log entry 11", now + 1))
        job1.addHistoryEntry(rpath_job.HistoryEntry("Log entry 12", now + 2))

        job2 = self.store.create(created = now + 0.1, cloudType = self.cloudType,
            cloudName = self.cloudName, instanceId = self.targetSystemIds[0])
        job2.addResults(["Result1", "Result2"])

        job2.addHistoryEntry(rpath_job.HistoryEntry("Log entry 21", now + 1))
        job2.addHistoryEntry(rpath_job.HistoryEntry("Log entry 22", now + 2))
        self.restdb.commit()
        jlist = [ job1, job2 ]

        srv = self.newService()
        uri = 'jobs/types/software-version-refresh/jobs'

        client = self.newClient(srv, uri)
        response = client.request('GET')
        data = response.read()

        storedJobs = jobmodels.Jobs()
        storedJobs.parseStream(data)
        self.failUnlessEqual([ x.get_id() for x in storedJobs ],
            [ self.makeUri(client, "%s/%s" % (uri, x.jobId)) for x in jlist  ])
        self.failUnlessEqual([ x.get_created() for x in storedJobs ],
            [ str(x.created) for x in jlist  ])
        self.failUnlessEqual([ x.get_modified() for x in storedJobs ],
            [ str(x.modified) for x in jlist  ])
        self.failUnlessEqual([ x.get_type() for x in storedJobs ],
            ['software-version-refresh'] * len(storedJobs.job))
        self.failUnlessEqual(
            [[ (y.get_timestamp(), y.get_content()) for y in x.get_history() ]
                for x in storedJobs],
            [[ (y.timestamp, y.content) for y in x.history] for x in jlist])
        job0 = storedJobs.job[0]
        job1 = storedJobs.job[1]
        self.failUnlessEqual(
            [ job0.get_result(), job1.get_result() ],
            [ [], ['Result1', 'Result2'] ])

    def testGetOneJob(self):
        now = time.time()
        job1 = self.store.create(created = now, cloudType = self.cloudType,
            cloudName = self.cloudName, instanceId = self.targetSystemIds[0])
        job1.addHistoryEntry(rpath_job.HistoryEntry("Log entry 11", now + 1))
        job1.addHistoryEntry(rpath_job.HistoryEntry("Log entry 12", now + 2))
        self.restdb.commit()

        srv = self.newService()
        uri = 'jobs/types/software-version-refresh/jobs/%s' % job1.jobId

        client = self.newClient(srv, uri)
        response = client.request('GET')
        data = response.read()

        job = jobmodels.Job()
        job.parseStream(data)
        self.failUnlessEqual(job.get_id(), self.makeUri(client, uri))

class InstanceLaunchJobsTest(testbase.TestCase):
    cloudName = 'vsphere.eng.rpath.com'
    cloudType = 'vmware'

    TARGETS = [
        (cloudType, cloudName, {}),
        ('xen-enterprise', '32degN', {}),
    ]

    def setUp(self):
        testbase.TestCase.setUp(self)
        self.store = jobs.LaunchJobSqlStore(self.restdb)

    def testGetJobs(self):
        now = time.time()
        job1 = self.store.create(created = now, cloudName = self.cloudName,
            cloudType = self.cloudType, instanceId = self.targetSystemIds[0])
        job1.addHistoryEntry(rpath_job.HistoryEntry("Log entry 11", now + 1))
        job1.addHistoryEntry(rpath_job.HistoryEntry("Log entry 12", now + 2))
        job1.status = job1.STATUS_COMPLETED
        job1.addResults(["some-href"])

        job2 = self.store.create(created = now + 0.1,
            cloudName = self.cloudName, cloudType = self.cloudType,
            instanceId = self.targetSystemIds[0])
        job2.addResults(["Result1", "Result2"])
        job2.addHistoryEntry(rpath_job.HistoryEntry("Log entry 21", now + 1))
        job2.addHistoryEntry(rpath_job.HistoryEntry("Log entry 22", now + 2))
        job2.status = job2.STATUS_COMPLETED
        self.restdb.commit()
        jlist = [ job1, job2 ]

        srv = self.newService()
        uri = 'jobs/types/instance-launch/jobs'

        client = self.newClient(srv, uri)
        response = client.request('GET')
        data = response.read()

        storedJobs = jobmodels.Jobs()
        storedJobs.parseStream(data)

        _p = 'clouds/vmware/instances/vsphere.eng.rpath.com/instances/'
        self.failUnlessEqual([ [ y.get_href() for y in x.get_resultResource() ]
                                for x in storedJobs ],
            [ [ self.makeUri(client, _p + x) for x in y]
                for y in [['some-href'], ['Result1', 'Result2']]])

    def testSearchJobs(self):
        now = time.time()
        job1 = self.store.create(created = now, cloudName = self.cloudName,
            cloudType = self.cloudType, status = 'Running',
            instanceId = self.targetSystemIds[0])
        job2 = self.store.create(created = now, cloudName = self.cloudName,
            cloudType = self.cloudType, status = 'Failed',
            instanceId = self.targetSystemIds[0])
        job3 = self.store.create(created = now, cloudName = self.TARGETS[1][1],
            cloudType = self.TARGETS[1][0], status = 'Running',
            instanceId = self.targetSystemIds[0])
        self.restdb.commit()

        srv = self.newService()
        uri = 'jobs/types/instance-launch/jobs?cloudName=%s&cloudType=%s&status=Running' % (self.cloudName, self.cloudType)

        client = self.newClient(srv, uri)
        response = client.request('GET')
        data = response.read()

        storedJobs = jobmodels.Jobs()
        storedJobs.parseStream(data)

        self.failUnlessEqual([ j.get_id() for j in storedJobs ],
            [ self.makeUri(
                client, 'jobs/types/instance-launch/jobs/%s' % job1.jobId)
            ])

if __name__ == "__main__":
    testsuite.main()
