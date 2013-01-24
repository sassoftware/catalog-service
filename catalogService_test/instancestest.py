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

from catalogService.rest.models import instances

class InstancesTest(testsuite.TestCase):
    def testFreezeThaw(self):
        hndlr = instances.Handler()

        instId = "ec2-adfadf"
        instVal = "someval"

        instance = instances.BaseInstance(id = instId, state = instVal)

        self.failUnlessEqual(instance.getId(), instId)
        self.failUnlessEqual(instance.getShutdownState(), None)
        self.failUnlessEqual(instance.getState(), instVal)
        self.failUnlessRaises(AttributeError, getattr, instance, "getADFAdcadf")

        ret = hndlr.toXml(instance, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<instance id="ec2-adfadf" xmlNodeHash="1a837d8c26533d24be7184cf5ebb8a00886a85ff"><state>someval</state></instance>""")
        x = hndlr.parseString(ret)
        self.failUnlessEqual(x.getId(), instId)
        self.failUnlessEqual(x.getShutdownState(), None)
        self.failUnlessEqual(x.getState(), instVal)

        # Multiple nodes
        insts = instances.BaseInstances()
        insts.append(x)

        ret = hndlr.toXml(insts, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<instances><instance id="ec2-adfadf" xmlNodeHash="1a837d8c26533d24be7184cf5ebb8a00886a85ff"><state>someval</state></instance></instances>""")
        # XXX this has to change - we need to parse these objects
        return
        x = hndlr.parseString(ret)

        instance = instances.BaseInstance(location = instLocation)
        self.failUnlessEqual(instance.getId(), None)
        self.failUnlessEqual(instance.getLocation(), instLocation)
        ret = hndlr.toXml(instance, prettyPrint = False)
        self.failUnlessEqual(ret, "<?xml version='1.0' encoding='UTF-8'?>\n<instance><location>ec2 name</location></instance>")
        x = hndlr.parseString(ret)
        self.failUnlessEqual(x.getId(), None)
        self.failUnlessEqual(x.getLocation(), instLocation)

        instance = instances.BaseInstance(id = instId, location = instLocation)
        ret = hndlr.toXml(instance, prettyPrint = False)
        self.failUnlessEqual(ret, "<?xml version='1.0' encoding='UTF-8'?>\n<instance><id>ec2-adfadf</id><location>ec2 name</location></instance>")

        x = hndlr.parseString(ret)
        self.failUnlessEqual(x.getId(), instId)
        self.failUnlessEqual(x.getLocation(), instLocation)

        instance = instances.BaseInstance(id = instId, isPublic = False)
        ret = hndlr.toXml(instance, prettyPrint = False)
        self.failUnlessEqual(ret, "<?xml version='1.0' encoding='UTF-8'?>\n<instance><id>ec2-adfadf</id><isPublic>false</isPublic></instance>")

        x = hndlr.parseString(ret)
        self.failUnlessEqual(x.getId(), instId)
        self.failUnlessEqual(x.getIsPublic(), False)

    def testFreezeInstanceTypes(self):
        hndlr = instances.Handler()

        instTypes = instances.InstanceTypes()
        instTypes.extend(instances.InstanceType(id=x, description=y)
            for (x, y) in [('a', 'aa'), ('b', 'bb')])
        ret = hndlr.toXml(instTypes, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<instanceTypes><instanceType id="a"><description>aa</description></instanceType><instanceType id="b"><description>bb</description></instanceType></instanceTypes>""")

    def testChecksum(self):
        hndlr = instances.Handler()

        instId = "blah blah blah"
        instLocation = "Location"
        instState = "Pending"
        instance = instances.BaseInstance(id = instId, location = instLocation,
            state = instState)

        ret = hndlr.toXml(instance, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<instance id="blah blah blah" xmlNodeHash="5b37fd4919b3c3d1bf6a9295175f33f52a78111b"><state>Pending</state></instance>""")

        instState = "Running"
        instance = instances.BaseInstance(id = instId, location = instLocation,
            state = instState)

        ret = hndlr.toXml(instance, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<instance id="blah blah blah" xmlNodeHash="484471a6a17481fcfd7ecf821833928c8679b392"><state>Running</state></instance>""")


if __name__ == "__main__":
    testsuite.main()
