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

from testutils import apache_server

import os

from catalogService import handler_apache
from catalogService.rest.models import clouds
import testbase
from conary_test import resources

class ApacheServer(apache_server.ApacheServer):
    def getServerDir(self):
        return resources.get_path('conary_test', 'server')

    def getPythonHandler(self):
        return "catalogService.handler_apache"

class ApacheRESTHandler(handler_apache.ApacheRESTHandler):
    def getAuthData(self, req):
        return ('user', 'pass')

class ApacheServerTest(testbase.TestCase):
    _basePath = '/TOP'

    cloudType = 'ec2'
    cloudName = 'aws'
    TARGETS = [ (cloudType, cloudName, {}) ]

    def newService(self):
        topDir = os.path.join(self.workDir, "service")
        a = ApacheServer(topDir)

        a.start()
        return a

    def test1(self):
        raise testsuite.SkipTestException("Apache no longer actively used")
        uri = 'clouds/ec2/instances'
        srv = self.newService()
        client = self.newClient(srv, uri)
        response = client.request("GET")

        self.failUnlessEqual(response.msg['Content-Type'], 'application/xml')
        hndlr = clouds.Handler()
        nodes = hndlr.parseString(response.read())

        raise testsuite.SkipTestException("Need to replace vws")
        expected = ['vws/instances/snaily.eng.rpath.com:8443',
                    'vws/instances/speedy.eng.rpath.com:8443',
                    'vws/instances/tp-grid3.ci.uchicago.edu:8445']
        for exp, x in zip(expected, nodes):
            self.failUnlessEqual(x.getName(), 'cloud')
            cloudId = x.getId()
            expUrl = "http://%s:%s%s/clouds/%s" % (client.host,
                client.port, self._basePath, exp)
            self.failUnlessEqual(cloudId, expUrl)


if __name__ == "__main__":
    testsuite.main()
