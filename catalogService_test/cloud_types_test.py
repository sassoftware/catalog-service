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

from catalogService.rest.models import cloud_types

class CloudsTest(testsuite.TestCase):
    def testFreezeThaw(self):
        hndlr = cloud_types.Handler()

        cloudTypeId = "cId"
        cloudType = "ec4"

        ctype = cloud_types.CloudType(id = cloudTypeId,
            cloudTypeName = cloudType)
        ctype.setCloudInstances(cloud_types.CloudInstances(href = 'aaa'))
        ctype.setDescriptorCredentials(cloud_types.DescriptorCredentials(href = 'bbb'))
        ctype.setDescriptorInstanceConfiguration(cloud_types.DescriptorInstanceConfiguration(href = 'ccc'))

        self.failUnlessEqual(ctype.getId(), cloudTypeId)
        self.failUnlessEqual(ctype.getCloudTypeName(), cloudType)
        self.failUnlessEqual(ctype.getCloudInstances().getHref(), 'aaa')
        self.failUnlessEqual(ctype.getDescriptorCredentials().getHref(), 'bbb')
        self.failUnlessEqual(ctype.getDescriptorInstanceConfiguration().
            getHref(), 'ccc')

        xmlContents = """<cloudType id="cId"><cloudInstances href="aaa"/><cloudTypeName>ec4</cloudTypeName><descriptorCredentials href="bbb"/><descriptorInstanceConfiguration href="ccc"/></cloudType>"""

        ret = hndlr.toXml(ctype, prettyPrint = False)
        self.failUnlessEqual(ret,
            "<?xml version='1.0' encoding='UTF-8'?>\n" + xmlContents)

        ctype = hndlr.parseString(ret)

        self.failUnlessEqual(ctype.getId(), cloudTypeId)
        self.failUnlessEqual(ctype.getCloudTypeName(), cloudType)
        self.failUnlessEqual(ctype.getCloudInstances().getHref(), 'aaa')
        self.failUnlessEqual(ctype.getDescriptorCredentials().getHref(), 'bbb')
        self.failUnlessEqual(ctype.getDescriptorInstanceConfiguration().
            getHref(), 'ccc')

        # Multiple nodes
        nodes = cloud_types.CloudTypes()
        nodes.append(ctype)

        ret = hndlr.toXml(nodes, prettyPrint = False)
        self.failUnlessEqual(ret, "<?xml version='1.0' encoding='UTF-8'?>\n<cloudTypes>%s</cloudTypes>" % xmlContents)

if __name__ == "__main__":
    testsuite.main()
