#!/usr/bin/python2.4
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
testsuite.setup()

import os
import time

import testbase
from catalogService import jobs
from rpath_job import api1 as rpath_job

class JobStoreTest(testbase.TestCase):
    cloudName = 'vsphere.eng.rpath.com'
    cloudType = 'vmware'

    TARGETS = [
        (cloudType, cloudName, {}),
    ]

    def setUp(self):
        testbase.TestCase.setUp(self)
        self.storePath = os.path.join(self.workDir, "job-store")
        self.jobStore = jobs.LaunchJobStore(self.storePath)

    def testEnumeration(self):
        stg = self.jobStore

        now = time.time()

        ejobs = [ stg.create(created = now - 10 * x, modified = now - 10 * x,
                    cloudName = self.cloudName, cloudType = self.cloudType)
                 for x in range(3) ]
        expiredJob = ejobs[-1]
        ejobs2 = ejobs[:-1]

        ejobs.sort(key = lambda x: x.id)
        ejobs2.sort(key = lambda x: x.id)

        self.failIfEqual(stg.get(expiredJob.id), None)

        jobs = [ x for x in stg.enumerate() ]
        self.failUnlessEqual([ x.id for x in jobs ], [ x.id for x in ejobs ])
        self.failUnlessEqual([ x.status for x in jobs ],
            [ jobs[0].STATUS_QUEUED ] * len(jobs))

        # Expire the first job
        expiredJob.modified = time.time() - 1 - expiredJob.ttl
        jobs = [ x for x in stg.enumerate() ]
        self.failUnlessEqual([ x.id for x in jobs ], [ x.id for x in ejobs2 ])

        # Last job should not exist
        self.failUnlessEqual(stg.get(expiredJob.id), None)

        # Update status
        for job in ejobs2:
            job.status = job.STATUS_RUNNING

        # Make sure status change got persisted: reload jobs from disk
        jobs = [ x for x in stg.enumerate() ]
        self.failUnlessEqual([ x.status for x in jobs ],
            [ jobs[0].STATUS_RUNNING ] * len(jobs))

    def testLogs(self):
        stg = self.jobStore
        now = float("%.3f" % time.time())

        j1 = stg.create(created = now - 10, modified = now - 10,
            cloudType = self.cloudType, cloudName = self.cloudName)
        self.failUnlessEqual(j1.created, now - 10)
        self.failUnlessEqual(j1.modified, now - 10)

        j1.modified = now - 5
        self.failUnlessEqual(j1.created, now - 10)
        self.failUnlessEqual(j1.modified, now - 5)

        # Make sure adding a log entry changes the modified timestamp
        j1.addHistoryEntry(rpath_job.HistoryEntry("Created", now - 10))
        self.failUnless(j1.modified >= now)
        stg.commit()

        # Make sure the modified timestamp has changed and was persisted
        j2 = stg.get(j1.id)
        self.failUnlessEqual("%.3f" % j1.modified, "%.3f" % j2.modified)

        j1.addHistoryEntry(rpath_job.HistoryEntry("Flipsted", now - 9))
        j1.addHistoryEntry(rpath_job.HistoryEntry("Acceborated", now - 8))
        j1.addResults(["Result1", "Result2"])

        j1.restUri = "blah"
        j1.restArgs = "<some-xml/>"
        j1.restMethod = 'PUT'

        j2 = stg.get(j1.id)
        self.failUnlessEqual([x.content for x in j2.history],
            ['Created', 'Flipsted', 'Acceborated'])

        self.failUnlessEqual([ x for x in j2.result ],
            ['Result1', 'Result2'])

        self.failUnlessEqual(j2.restMethod, "PUT")
        self.failUnlessEqual(j2.restUri, "blah")
        self.failUnlessEqual(j2.restArgs, "<some-xml/>")

    def testResults(self):
        stg = self.jobStore
        now = float("%.3f" % time.time())

        j1 = stg.create(created = now - 10, modified = now - 10,
            cloudType = self.cloudType, cloudName = self.cloudName)
        results = ['a', 'b', 'c']
        j1.addResults(results)
        self.failUnlessEqual(j1.getResults(), results)

    def testDelete(self):
        stg = self.jobStore
        j1 = stg.create(cloudType = self.cloudType, cloudName = self.cloudName)
        j1.pid = 12345
        stg.commit()

        # Force the key to be a long
        try:
            j1.id = long(j1.id)
        except ValueError:
            pass
        j2 = stg.get(j1.id)
        self.failUnlessEqual(j2.pid, 12345)

        # Delete pid
        j2.pid = None

        j2 = stg.get(j1.id)
        self.failUnlessEqual(j2.pid, None)

class SQLJobStoreTest(JobStoreTest):
    def setUp(self):
        JobStoreTest.setUp(self)
        self.jobStore = jobs.LaunchJobSqlStore(self.restdb)

if __name__ == "__main__":
    testsuite.main()
