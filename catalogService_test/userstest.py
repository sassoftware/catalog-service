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

import testbase

import os

from conary.lib import util

from catalogService import storage
from catalogService.rest.models import userData
from catalogService.restClient import ResponseError

class UsersTest(testbase.TestCase):
    cloudType = 'ec2'
    cloudName = 'aws'
    TARGETS = [ (cloudType, cloudName, {}) ]

    def setUp(self):
        testbase.TestCase.setUp(self)

    def testSaveLoadBlobs(self):
        srv = self.newService()
        uri = 'users/%(username)s/library'

        client = self.newClient(srv, uri)
        reqData = 'Request data'
        response = client.request('POST', body = reqData)

        hndlr = userData.Handler()

        rdata = response.read()
        node = hndlr.parseString(rdata)
        self.failUnless(isinstance(node, userData.IdNode), node)
        nuri = node.getText()

        client = self.newClient(srv, nuri)
        response = client.request('GET')

        data = response.read()

        self.failUnlessEqual(data, reqData)

        newData = "New request data"
        response = client.request('PUT', body = newData)

        data = response.read()
        self.failUnlessEqual(data, rdata)

        response = client.request('GET')
        data = response.read()

        self.failUnlessEqual(data, newData)

        newData = "Even newer data"
        client = self.newClient(srv, nuri + '?_method=PUT')
        response = client.request('POST', body = newData)

        data = response.read()
        self.failUnlessEqual(data, rdata)

        client = self.newClient(srv, nuri)

        response = client.request('GET')
        data = response.read()

        self.failUnlessEqual(data, newData)

        response = client.request('DELETE')
        data = response.read()
        self.failUnlessEqual(data, rdata)

        # GET again, should fail
        e = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(e.status, 404)
        self.assertXMLEquals(e.contents,
                '<?xml version="1.0" encoding="UTF-8"?>\n<fault>\n  <code>404</code>\n  <message>Not Found</message>\n</fault>')

        # POST to a URI with a / at the end (RDST-551)
        uri += '/'
        client = self.newClient(srv, uri)
        response = client.request('POST', body = reqData)

        hndlr = userData.Handler()

        rdata = response.read()
        node = hndlr.parseString(rdata)
        self.failUnless(isinstance(node, userData.IdNode), node)

    def testLoadUninitBlobs(self):
        srv = self.newService()
        uri = 'users/%(username)s/library/'
        reqData = '<?xml version="1.0" encoding="UTF-8"?><list></list>'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        data = response.read()

        self.failUnlessEqual(data, reqData)

    def testGetBlobsMulti(self):
        srv = self.newService()
        uri = 'users/%(username)s/library'

        client = self.newClient(srv, uri)
        hndlr = userData.Handler()

        uris = []
        for i in range(3):
            reqData = 'Request data %s' % i
            response = client.request('POST', body = reqData)

            response = util.BoundedStringIO(response.read())
            node = hndlr.parseFile(response)
            self.failUnless(isinstance(node, userData.IdNode), node)
            nuri = node.getText()
            uris.append(nuri)

        uris.sort()

        # A GET on /library should get the listing
        response = client.request('GET')
        response = util.BoundedStringIO(response.read())
        node = hndlr.parseFile(response)
        self.failUnless(isinstance(node, userData.IdsNode), node)
        ruris = [ x.getText() for x in node ]
        self.failUnlessEqual(ruris, uris)

        # Grab the contents
        data = []
        for u in uris:
            client = self.newClient(srv, u)
            response = client.request('GET')
            data.append(response.read())
        data = '<?xml version="1.0" encoding="UTF-8"?><list>%s</list>' % ''.join(data)

        # A GET on /library/ should get the blob contents
        uri = uri + '/'
        client = self.newClient(srv, uri)
        response = client.request('GET')
        self.failUnlessEqual(response.read(), data)

    def testDELETEwithPOST(self):
        srv = self.newService()
        uri = 'users/%(username)s/library'

        client = self.newClient(srv, uri)
        reqData = 'Request data'
        response = client.request('POST', body = reqData)

        rdata = response.read()
        nuri = rdata[42:]
        nuri = nuri[:-5]

        client = self.newClient(srv, nuri)
        response = client.request('GET')

        data = response.read()

        self.failUnlessEqual(data, reqData)

        client = self.newClient(srv, nuri + '?_method=DELETE')
        response = client.request('POST')

        data = response.read()
        self.failUnlessEqual(data, rdata)

        client = self.newClient(srv, nuri)
        # GET again, should fail
        e = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(e.status, 404)
        self.assertXMLEquals(e.contents,
                '<?xml version="1.0" encoding="UTF-8"?>\n<fault>\n  <code>404</code>\n  <message>Not Found</message>\n</fault>')

    def testUserIdInStorePath(self):
        srv = self.newService()
        uri = 'users/%(username)s/library/some-data'

        client = self.newClient(srv, uri)
        reqData = 'Request data'
        response = client.request('PUT', body = reqData)

        path = os.path.join(self.storagePath, 'catalog', 'userData',
            'JeanValjean', 'library', 'some-data')
        self.failUnless(os.path.exists(path))

if __name__ == "__main__":
    testsuite.main()
