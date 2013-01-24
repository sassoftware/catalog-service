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

from catalogService.rest.models import clouds

class CloudsTest(testsuite.TestCase):
    def testFreezeThaw(self):
        hndlr = clouds.Handler()

        cloudId = "cId"
        cloudName = "cName"

        cloud = clouds.BaseCloud(id = cloudId, cloudName = cloudName)

        self.failUnlessEqual(cloud.getId(), cloudId)
        self.failUnlessEqual(cloud.getCloudName(), cloudName)
        self.failUnlessEqual(cloud.getType(), None)
        self.failUnlessRaises(AttributeError, getattr, cloud, "getADFAdcadf")

        ret = hndlr.toXml(cloud, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<cloud id="cId"><cloudName>cName</cloudName></cloud>""")
        x = hndlr.parseString(ret)
        self.failUnlessEqual(x.getId(), cloudId)
        self.failUnlessEqual(x.getCloudName(), cloudName)
        self.failUnlessEqual(x.getType(), None)

        # Multiple nodes
        nodes = clouds.BaseClouds()
        nodes.append(x)

        ret = hndlr.toXml(nodes, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<clouds><cloud id="cId"><cloudName>cName</cloudName></cloud></clouds>""")

if __name__ == "__main__":
    testsuite.main()
