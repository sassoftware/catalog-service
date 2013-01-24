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

import StringIO
from catalogService.rest.models import securityGroups

from catalogService_test import testbase

class SecurityGrooupTest(testbase.TestCase):
    cloudType = 'ec2'
    cloudName = 'aws'
    TARGETS = [(cloudType, cloudName, {})]

    def testFreezeThaw(self):
        hndlr = securityGroups.Handler()

        seedData = ['a', ]

        node = securityGroups.BaseSecurityGroups()
        node.extend(securityGroups.BaseSecurityGroup(id=x,
            ownerId=x*2, groupName=x*3, description=x*4)
            for x in seedData)

        seedData.append('b')
        n = securityGroups.BaseSecurityGroup()
        n.setId('b')
        n.setOwnerId('bb')
        n.setGroupName('bbb')
        n.setDescription('bbbb')
        node.append(n)

        for sd, n in zip(seedData, node):
            self.failUnlessEqual(n.getId(), sd)
            self.failUnlessEqual(n.getOwnerId(), sd*2)
            self.failUnlessEqual(n.getGroupName(), sd*3)
            self.failUnlessEqual(n.getDescription(), sd*4)

        self.failUnlessRaises(AttributeError, getattr, node[0], "getADFAdcadf")

        ret = hndlr.toXml(node, prettyPrint = False)
        self.assertXMLEquals(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<securityGroups><securityGroup id="a"><description>aaaa</description><groupName>aaa</groupName><ownerId>aa</ownerId></securityGroup><securityGroup id="b"><description>bbbb</description><groupName>bbb</groupName><ownerId>bb</ownerId></securityGroup></securityGroups>""")
        rlist = hndlr.parseString(ret)
        self.failUnlessEqual(len(rlist), 2)
        for sd, n in zip(seedData, rlist):
            self.failUnlessEqual(n.getId(), sd)
            self.failUnlessEqual(n.getOwnerId(), sd*2)
            self.failUnlessEqual(n.getGroupName(), sd*3)
            self.failUnlessEqual(n.getDescription(), sd*4)

if __name__ == "__main__":
    testsuite.main()
