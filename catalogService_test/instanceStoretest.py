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

from catalogService import config
from catalogService import storage
from catalogService import instanceStore
from catalogService_test import testbase

class InstanceStoreTest(testbase.TestCase):
    cloudType = 'ec2'
    cloudName = 'aws'
    TARGETS = [ (cloudType, cloudName, {}) ]
    def testInstanceStore(self):
        path = os.path.join(self.workDir, "inststore")
        cfg = config.BaseConfig()
        cfg.storagePath = path

        store = storage.DiskStorage(cfg)
        prefix = 'some-prefix'

        instStore = instanceStore.InstanceStore(store, prefix = prefix)
        instanceId = "aabbccdd"

        nk = instStore.newKey(realId = 123, imageId = 'image id')
        self.failUnlessEqual(instStore.getId(nk), '123')
        self.failUnlessEqual(instStore.getImageId(nk), 'image id')

        instStore.setId(nk, '234')
        self.failUnlessEqual(instStore.getId(nk), '234')

        instStore.setPid(nk)
        self.failUnlessEqual(instStore.getPid(nk), os.getpid())

        instStore.setPid(nk, 98765432)
        self.failUnlessEqual(instStore.getPid(nk), 98765432)

        instStore.setState(nk, "Blah!")
        self.failUnlessEqual(instStore.getState(nk), "Blah!")

        instStore.setState(nk, None)
        self.failUnlessEqual(instStore.getState(nk), None)

        now = int(time.time())
        self.failUnless(instStore.getExpiration(nk) < now + 1800 + 1)

        instStore.setInstanceName(nk, "blah")
        self.failUnlessEqual(instStore.getInstanceName(nk), "blah")

        val = "foo=bar@baz:blip/1-2-3"
        instStore.setSoftwareVersion(nk, val)
        self.failUnlessEqual(instStore.getSoftwareVersion(nk), val)

        val = 'job-id-1'
        instStore.setSoftwareVersionJobId(nk, val)
        self.failUnlessEqual(instStore.getSoftwareVersionJobId(nk), val)

        instStore.setSoftwareVersionJobStatus(nk, val)
        self.failUnlessEqual(instStore.getSoftwareVersionJobStatus(nk), val)

        timestamp = time.time()
        instStore.setSoftwareVersionLastChecked(nk, timestamp)
        self.failUnlessEqual(instStore.getSoftwareVersionLastChecked(nk),
            int(timestamp))

        instStore.setSoftwareVersionNextCheck(nk, timestamp)
        self.failUnlessEqual(instStore.getSoftwareVersionNextCheck(nk),
            int(timestamp + 86400))

if __name__ == "__main__":
    testsuite.main()
