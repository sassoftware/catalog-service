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
from catalogService.rest.models import keypairs

class KeyPairsTest(testsuite.TestCase):
    def testFreezeThaw(self):
        hndlr = keypairs.Handler()

        seedData = ['a', 'b', 'c']

        node = keypairs.BaseKeyPairs()
        node.extend(keypairs.BaseKeyPair(id=x, keyName=x*2, keyFingerprint=x*3)
            for x in seedData)

        seedData.append('d')
        n = keypairs.BaseKeyPair()
        n.setId('d')
        n.setKeyName('dd')
        n.setKeyFingerprint('ddd')
        node.append(n)

        for sd, n in zip(seedData, node):
            self.failUnlessEqual(n.getId(), sd)
            self.failUnlessEqual(n.getKeyName(), sd*2)
            self.failUnlessEqual(n.getKeyFingerprint(), sd*3)

        self.failUnlessRaises(AttributeError, getattr, node[0], "getADFAdcadf")

        ret = hndlr.toXml(node, prettyPrint = False)
        self.failUnlessEqual(ret, "<?xml version='1.0' encoding='UTF-8'?>\n<keyPairs><keyPair><id>a</id><keyFingerprint>aaa</keyFingerprint><keyName>aa</keyName></keyPair><keyPair><id>b</id><keyFingerprint>bbb</keyFingerprint><keyName>bb</keyName></keyPair><keyPair><id>c</id><keyFingerprint>ccc</keyFingerprint><keyName>cc</keyName></keyPair><keyPair><id>d</id><keyFingerprint>ddd</keyFingerprint><keyName>dd</keyName></keyPair></keyPairs>")
        rlist = hndlr.parseString(ret)
        self.failUnlessEqual(len(rlist), 4)
        for sd, n in zip(seedData, rlist):
            self.failUnlessEqual(n.getId(), sd)
            self.failUnlessEqual(n.getKeyName(), sd*2)
            self.failUnlessEqual(n.getKeyFingerprint(), sd*3)

if __name__ == "__main__":
    testsuite.main()
