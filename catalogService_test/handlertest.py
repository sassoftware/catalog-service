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

import boto
import os
import pickle
import tempfile

import testbase
from mint.rest.db.database import TargetManager
from catalogService.rest import baseDriver
from catalogService.restClient import ResponseError

from catalogService.rest.models import cloud_types
from catalogService.rest.models import clouds
from catalogService.rest.models import credentials
from catalogService.rest.models import images
from catalogService.rest.models import instances

import mockedData

from conary.lib import util

from catalogService_test import ec2test

class MockedRequest(ec2test.MockedRequest):
    _tmpFd, MOCKED_MAKE_REQ_DATA_PATH = tempfile.mkstemp()
    os.close(_tmpFd)
    del _tmpFd

    def mockedMakeRequest(self, action, params=None, path=None, verb='GET', **kwargs):
        resp = ec2test.MockedRequest.mockedMakeRequest(self, action,
            params = params, path = path, verb=verb, **kwargs)
        if action not in [ 'CreateSecurityGroup', 'AuthorizeSecurityGroupIngress']:
            return resp

        # Write to disk, since we need access to the data in the server
        # process
        try:
            f = open(self.MOCKED_MAKE_REQ_DATA_PATH, 'rb')
            filedata = pickle.load(f)
        finally:
            if f: f.close()

        if action == 'CreateSecurityGroup':
            filedata[params['GroupName']] = []
        elif action == 'AuthorizeSecurityGroupIngress':
            filedata[params['GroupName']].append((params['IpPermissions.1.IpProtocol'],
                params['IpPermissions.1.FromPort'],
                params['IpPermissions.1.ToPort'],
                params['IpPermissions.1.IpRanges.1.CidrIp']))
        try:
            f = open(self.MOCKED_MAKE_REQ_DATA_PATH, 'wb')
            pickle.dump(filedata, f)
        finally:
            if f: f.close()

        return resp

class SimpleHandlerTest(testbase.TestCase):
    TARGETS = ec2test.HandlerTest.TARGETS + []
    cloudType = TARGETS[0][0]
    cloudName = TARGETS[0][1]

    def testGetHTTPMethod(self):
        raise testsuite.SkipTestException("restlib: should move to restlib")
        m = testbase.RESTHandler._get_HTTP_method
        self.failUnlessEqual(m('a', 'PP'), ('a', 'PP'))
        self.failUnlessEqual(m('a?', 'PP'), ('a', 'PP'))
        self.failUnlessEqual(m('a?_method', 'PP'), ('a', 'PP'))
        self.failUnlessEqual(m('a?b=1', 'PP'), ('a', 'PP'))
        self.failUnlessEqual(m('a?_method=QQ', 'PP'), ('a', 'QQ'))

    def testGetUserInfoNoSession(self):
        srv = self.newService()
        uri = 'clouds/ec2/instances'
        client = self.newClient(srv, uri, username=None)

        resp = self.failUnlessRaises(ResponseError,
            client.request, 'GET')
        self.failUnlessEqual(resp.status, 401)

        client = self.newClient(srv, uri, username=None,
            headers = {'HTTP_X_FLASH_VERSION': '1'})
        resp = client.request('GET')
        self.assertXMLEquals(resp.read(), """\
<?xml version='1.0' encoding='UTF-8'?>
<fault>
  <code>403</code>
  <message>Forbidden</message>
</fault>
""")


class BaseTest(testbase.TestCase):
    def setUp(self):
        f = None
        try:
            f = open(MockedRequest.MOCKED_MAKE_REQ_DATA_PATH, 'wb+')
            pickle.dump(dict(), f)
        finally:
            if f: f.close()
        testbase.TestCase.setUp(self)
        self._mockRequest()
        baseDriver.CatalogJobRunner.preFork = lambda *args: None

    def _mockRequest(self, **kwargs):
        from catalogService.rest.drivers.ec2.ec2client import EC2Connection
        self.botoRequestDir = os.path.join(self.workDir, "botoRequest")
        reqobj = MockedRequest(self.botoRequestDir)
        reqobj.data = MockedRequest.data.copy()
        reqobj.data.update(kwargs)
        self.mock(EC2Connection, 'make_request',
                  reqobj.mockedMakeRequest)
        self.mock(EC2Connection, 'proxy_ssl',
                  ec2test.mockedProxySsl)

    def tearDown(self):
        testbase.TestCase.tearDown(self)
        if os.path.exists(MockedRequest.MOCKED_MAKE_REQ_DATA_PATH):
            os.unlink(MockedRequest.MOCKED_MAKE_REQ_DATA_PATH) 

    def newService(self):
        return testbase.TestCase.newService(self)

class HandlerTest(BaseTest):
    TARGETS = ec2test.HandlerTest.TARGETS
    USER_TARGETS = ec2test.HandlerTest.USER_TARGETS
    cloudType = TARGETS[0][0]
    cloudName = TARGETS[0][1]

    supportedCloudTypes = ['ec2', 'eucalyptus', 'openstack',
        'vcloud', 'vmware', 'xen-enterprise']

    def testGetCrossdomain(self):
        raise testsuite.SkipTestException("Need to provide an absolute path")
        srv = self.newService()
        client = self.newClient(srv,
            'http://localhost:%(port)s/crossdomain.xml' % dict(port=srv.port))
        response = client.request('GET')
        self.failUnlessEqual(response.read(), crossdomainXml)

    def testMalformedURI(self):
        # pass a uri that doesn't have an ID (it should) to see if the system
        # tips over or not.
        srv = self.newService()
        uri = 'clouds/ec2/instances?_method=GET'

        client = self.newClient(srv, uri)

        response = client.request('POST')
        self.failUnlessEqual(response.msg['Content-Type'], 'application/xml')
        hndlr = clouds.Handler()
        response = util.BoundedStringIO(response.read())
        nodes = hndlr.parseFile(response)
        self.failUnlessEqual(len(nodes), 1)
        expected = ['ec2/instances/aws' ]
        self.failUnlessEqual([ x.getType().getText() for x in nodes ],
            [ x.split('/')[0] for x in expected ])
        self.failUnlessEqual([ x.getCloudName() for x in nodes ],
            [ x.split('/')[2] for x in expected ])
        for exp, x in zip(expected, nodes):
            self.failUnlessEqual(x.getName(), 'cloud')
            cloudId = x.getId()
            expUrl = "http://%s/TOPLEVEL/clouds/%s" % (client.hostport, exp)
            self.failUnlessEqual(cloudId, expUrl)

    def testGetCloudTypes1(self):
        uri = 'clouds?_method=GET'
        srv = self.newService()

        client = self.newClient(srv, uri)

        response = client.request("POST")
        self.failUnlessEqual(response.msg['Content-Type'], 'application/xml')
        hndlr = cloud_types.Handler()
        response = util.BoundedStringIO(response.read())
        nodes = hndlr.parseFile(response)
        self.failUnlessEqual([x.getCloudTypeName() for x in nodes],
            self.supportedCloudTypes)

        expIds = [ "http://%s/TOPLEVEL/clouds/%s" % (client.hostport, exp)
            for exp in self.supportedCloudTypes ]
        self.failUnlessEqual([x.getId() for x in nodes], expIds)

        expRefs = [ x + '/instances' for x in expIds ]
        self.failUnlessEqual(
            [x.getCloudInstances().getHref() for x in nodes], expRefs)

        expRefs = [ x + '/descriptor/configuration' for x in expIds ]
        self.failUnlessEqual(
            [x.getDescriptorInstanceConfiguration().getHref() for x in nodes], expRefs)

        expRefs = [ x + '/descriptor/credentials' for x in expIds ]
        self.failUnlessEqual(
            [x.getDescriptorCredentials().getHref() for x in nodes], expRefs)

    def testGetCloudTypes2(self):
        uri = 'clouds?_method=GET'
        srv = self.newService()

        client = self.newClient(srv, uri)

        response = client.request("POST")
        self.failUnlessEqual(response.msg['Content-Type'], 'application/xml')
        hndlr = cloud_types.Handler()
        response = util.BoundedStringIO(response.read())
        nodes = hndlr.parseFile(response)
        self.failUnlessEqual([x.getCloudTypeName() for x in nodes],
            self.supportedCloudTypes)

    def testGetClouds1(self):
        expected = {
            'ec2' : [
                dict(cloudName = 'aws', cloudAlias = 'aws-us-east',
                    description = 'Amazon Elastic Compute Cloud - US East Region'),
            ],
        }
        for ctype, cexp in expected.items():
            uri = 'clouds/%s/instances' % ctype
            self._testGetClouds(uri, ctype, cexp, method = 'GET')
            uri = 'clouds/%s/instances?_method=GET' % ctype
            self._testGetClouds(uri, ctype, cexp, method = 'POST')

    def _testGetClouds(self, uri, cloudType, expected, method='POST'):
        srv = self.newService()

        client = self.newClient(srv, uri)

        response = client.request(method)
        self.failUnlessEqual(response.msg['Content-Type'], 'application/xml')
        hndlr = clouds.Handler()
        response = util.BoundedStringIO(response.read())
        nodes = hndlr.parseFile(response)

        self.failUnlessEqual([ x.getType().getText() for x in nodes ],
            [ cloudType ] * len(nodes))

        expTypeRefs = [ "http://%s/TOPLEVEL/clouds/%s" % (
            client.hostport, cloudType) ] * len(nodes)
        self.failUnlessEqual([ x.getType().getHref() for x in nodes ],
            expTypeRefs)

        expIds = [ "http://%s/TOPLEVEL/clouds/%s/instances/%s" % (
            client.hostport, cloudType, x['cloudName'])
                for x in expected ]
        self.failUnlessEqual([ x.getId() for x in nodes ], expIds)


        self.failUnlessEqual([ x.getCloudName() for x in nodes ],
            [ x['cloudName'] for x in expected ])
        self.failUnlessEqual([ x.getCloudAlias() for x in nodes ],
            [ x['cloudAlias'] for x in expected ])
        self.failUnlessEqual([ x.getDescription() for x in nodes ],
            [ x['description'] for x in expected ])
        self.failUnlessEqual([ x.getImages().getHref() for x in nodes ],
            [ x + '/images' for x in expIds ])
        self.failUnlessEqual([ x.getInstances().getHref() for x in nodes ],
            [ x + '/instances' for x in expIds ])
        self.failUnlessEqual([ x.getDescriptorLaunch().getHref() for x in nodes ],
            [ x + '/descriptor/launch' for x in expIds ])
        self.failUnlessEqual(
            [ x.getConfiguration().getHref() for x in nodes ],
            [ x + '/configuration' for x in expIds ])
        self.failUnlessEqual(
            [ x.getUserCredentials().getHref() for x in nodes ],
            [ x + '/users/JeanValjean/credentials' for x in expIds ])

        expHrefs = [ "http://%s/TOPLEVEL/jobs/types/instance-launch/jobs?cloudName=%s&cloudType=%s&status=Running" % (
            client.hostport, x['cloudName'], cloudType)
                for x in expected ]
        self.failUnlessEqual(
            [ x.getActiveJobs().getHref() for x in nodes ],
            expHrefs)

    def testGetOneCloud1(self):
        srv = self.newService()
        uri = 'clouds/ec2/instances/aws'

        client = self.newClient(srv, uri)

        response = client.request('GET')
        response = util.BoundedStringIO(response.read())
        hndlr = clouds.Handler()
        nodes = hndlr.parseFile(response)
        self.failUnlessEqual([ x.getCloudName() for x in nodes ],
            [ 'aws' ])

    def testIs_rBuilderImage(self):
        class MockedRequest(object):
            def getAbsoluteURI(x):
                return None

        class FakeImage(object):
            __slots__ = ['id', 'location', 'state', 'ownerId', 'is_public',
                'productDescription', 'product_codes', ]
            def __init__(slf, **kwargs):
                for slot in slf.__slots__:
                    setattr(slf, slot, kwargs.get(slot))

        def MockedGetAllImages(*args, **kwargs):
            rs = boto.resultset.ResultSet()
            rs.append(FakeImage(id = 'ami-0435d06d', product_codes = ['a']))
            rs.append(FakeImage(id = 'ami-12345678', product_codes = ['a']))
            return rs

        from catalogService.rest.drivers.ec2 import ec2client
        self.mock(ec2client.EC2Connection, 'get_all_images', MockedGetAllImages)

        uri = 'clouds/ec2/instances/aws/images'
        srv = self.newService()

        client = self.newClient(srv, uri)
        response = client.request("GET")

        hndlr = images.Handler()
        data = response.read()
        node = hndlr.parseString(data)
        self.assertEquals(sorted([x.getIs_rBuilderImage() for x in node]),
                [False, False, True])

    def testGetUserInfo(self):
        srv = self.newService()
        uri = 'userinfo?_method=GET'
        client = self.newClient(srv, uri)

        response = client.request('POST')
        self.failUnlessEqual(response.msg['Content-Type'], 'application/xml')
        data = response.read()
        self.assertXMLEquals(data, """\
<?xml version='1.0' encoding='UTF-8'?>
<userinfo id="%s">
  <displayRepositories>false</displayRepositories>
  <email>email@address.com</email>
  <fullName>Jean Valjean</fullName>
  <isAdmin>false</isAdmin>
  <preferences href="%s"/>
  <username>JeanValjean</username>
</userinfo>""" % (self.makeUri(client, "userinfo"), self.makeUri(client, "users/JeanValjean/preferences/")))

    def testGetUserInfoIsAdmin(self):
        self.setAdmin(True)

        srv = self.newService()
        uri = 'userinfo?_method=GET'
        client = self.newClient(srv, uri)

        response = client.request('POST')
        self.failUnlessEqual(response.msg['Content-Type'], 'application/xml')
        data = response.read()
        self.assertXMLEquals(data, """\
<?xml version='1.0' encoding='UTF-8'?>
<userinfo id="%s">
  <displayRepositories>false</displayRepositories>
  <email>email@address.com</email>
  <fullName>Jean Valjean</fullName>
  <isAdmin>true</isAdmin>
  <preferences href="%s"/>
  <username>JeanValjean</username>
</userinfo>""" % (self.makeUri(client, "userinfo"), self.makeUri(client, "users/JeanValjean/preferences/")))

    def testGetServiceInfo(self):
        '''
        Test fetching the service info
        '''
        srv = self.newService()
        uri = 'serviceinfo?_method=GET'
        client = self.newClient(srv, uri)

        response = client.request('POST')
        self.failUnlessEqual(response.msg['Content-Type'], 'application/xml')
        data = response.read()
        self.assertXMLEquals(data, """\
<?xml version='1.0' encoding='UTF-8'?>
<serviceinfo id="%s">
  <type>full</type>
  <version>1</version>
</serviceinfo>""" % self.makeUri(client, "serviceinfo"))
        
    def testGetServiceInfoLimited(self):
        '''
        Test fetching the service info when the type is limited
        '''
        # This should be implemented as part of RBL-4191
        pass

    def testGetNoInstances(self):
        # ensure listing instances when there are none actually returns
        def FakeGetAllInstances(*args, **kwargs):
            return boto.resultset.ResultSet()
        from catalogService.rest.drivers.ec2.ec2client import EC2Connection
        self.mock(EC2Connection, 'get_all_instances', FakeGetAllInstances)
        srv = self.newService()
        uri = 'clouds/ec2/instances/aws/instances?_method=GET'
        client = self.newClient(srv, uri)

        response = client.request('POST')
        self.failUnlessEqual(response.msg['Content-Type'], 'application/xml')
        hndlr = instances.Handler()
        response = util.BoundedStringIO(response.read())
        node = hndlr.parseFile(response)
        self.failUnless(
            isinstance(node, instances.BaseInstances),
            node)
        self.failUnlessEqual(len(node), 0)

    def testSetCredentialsEC2(self):
        srv = self.newService()
        uri = 'clouds/ec2/instances/aws/users/%(username)s/credentials?_method=PUT'

        client = self.newClient(srv, uri)
        response = client.request('POST', body = _xmlNewEC2Creds)

        hndlr = credentials.Handler()

        data = response.read()
        node = hndlr.parseString(data)

        self.failUnlessEqual(node.getValid(), True)

    def testSetCredentialsEC2Fail(self):
        # Force a failure
        oldSetTargetCredentialsForUser = TargetManager.setTargetCredentialsForUser
        def mockedSetTargetCredentialsForUser(slf, targetType, targetName,
                userName, credentials):
            # Make sure the data comes in as string, not Unicode
            strings = [ targetType, targetName, userName ]
            strings.extend(credentials.keys())
            strings.extend(credentials.values())
            for s in strings:
                if not isinstance(s, str):
                    raise Exception("Not a string")
            return oldSetTargetCredentialsForUser(slf, targetType, targetName,
                userName, credentials)
        self.mock(TargetManager, 'setTargetCredentialsForUser',
            mockedSetTargetCredentialsForUser)

        srv = self.newService()
        uri = 'clouds/ec2/instances/aws/users/%(username)s/credentials?_method=PUT'

        client = self.newClient(srv, uri)
        resp = client.request('POST', body = _xmlNewEC2Creds)

        self.assertXMLEquals(resp.read(), """\
<?xml version="1.0" encoding="UTF-8"?>
<credentials>
  <fields/>
  <valid>true</valid>
</credentials>""")


    def testNewEC2InstancesWithCatalogDefaultWithRemoteIp(self):
        # Mock the external IP determination
        def fakeOpenUrl(slf, url):
            return util.BoundedStringIO("""\
\t1.2.3.4\t\n""")
        from catalogService.rest.drivers import ec2
        self.mock(ec2.driver, '_openUrl', fakeOpenUrl)

        # We need to mock the image data
        self._mockRequest(DescribeImages = mockedData.xml_getAllImages4,
            RunInstances = mockedData.xml_runInstances3,
            )

        srv = self.newService()
        uri = 'clouds/ec2/instances/aws/instances'

        client = self.newClient(srv, uri)
        response = client.request('POST', mockedData.xml_newInstance4)
        node = self.getJobFromResponse(response)
        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        self.failUnlessEqual(node.get_id(), self.makeUri(client, jobUrlPath))

        job = self.waitForJob(srv, jobUrlPath, "Completed")
        _p =  'clouds/ec2/instances/aws/instances/'
        self.failUnlessEqual([ x.get_href() for x in job.get_resultResource() ],
            [ self.makeUri(client, _p + x)
                for x in ['i-e2df098b', 'i-e5df098c'] ])

        f = None
        try:
            f = open(MockedRequest.MOCKED_MAKE_REQ_DATA_PATH, 'rb')
            filedata = pickle.load(f)
            self.failUnless('catalog-default' in filedata)
            self.failUnlessEqual(filedata['catalog-default'],
                    [('tcp', 22, 22, '192.168.1.1/32'),
                     ('tcp', 80, 80, '192.168.1.1/32'),
                     ('tcp', 443, 443, '192.168.1.1/32'),
                     ('tcp', 8003, 8003, '192.168.1.1/32'),
                     ('tcp', 5989, 5989, '1.2.3.4/32')
                     ])
        finally:
            if f: f.close()

    def testNewInstanceFail(self):
        raise testsuite.SkipTestException("this test is probably right. we are returning a 200 when we shouldn't, for flex's sake.")
        def FakeRunInstances(*args, **kwargs):
            # note the completely bogus http status code
            raise boto.exception.EC2ResponseError(960, "Bad Request",
                    """<?xml version="1.0"?>\n<Response><Errors><Error><Code>InvalidParameterValue</Code><Message>The requested instance type's architecture (i386) does not match the architecture in the manifest for ami-a312f7ca (x86_64)</Message></Error></Errors><RequestID>76467959-d192-4314-820a-87f31d739137</RequestID></Response>""")

        from catalogService.rest.drivers.ec2.ec2client import EC2Connection
        self.mock(EC2Connection, 'run_instances', FakeRunInstances)

        srv = self.newService()
        uri = 'clouds/ec2/ec2/instances'

        client = self.newClient(srv, uri)
        err = self.assertRaises(ResponseError,
                client.request, 'POST', mockedData.xml_newInstance1)
        self.assertEquals(err.status, 400)
        self.assertEquals(err.reason, """<wrapped_fault><status>960</status><reason>Bad Request</reason><body><Response><Errors><Error><Code>InvalidParameterValue</Code><Message>The requested instance type's architecture (i386) does not match the architecture in the manifest for ami-a312f7ca (x86_64)</Message></Error></Errors><RequestID>76467959-d192-4314-820a-87f31d739137</RequestID></Response></body>""")
        self.failIf(not err.headers.dict, "Expected some headers")

    def testTerminateEC2Instance(self):
        self._mockRequest(DescribeImages = mockedData.xml_getAllImages4)

        instanceId = 'i-60f12709'

        srv = self.newService()
        uri = 'clouds/ec2/instances/aws/instances/' + instanceId
        client = self.newClient(srv, uri)
        response = client.request('DELETE', mockedData.xml_terminateInstance1)
        hndlr = instances.Handler()
        response = util.BoundedStringIO(response.read())
        node = hndlr.parseFile(response)
        self.failUnless(isinstance(node, instances.BaseInstance),
                        node)
        self.failUnlessEqual(node.getId(),
            self.makeUri(client, 'clouds/ec2/instances/aws/instances/' + instanceId))

    def testTerminateEC2Instance2(self):
        # repeat the test using POST. it's a different codepath
        instanceId = 'i-60f12709'

        srv = self.newService()
        uri = 'clouds/ec2/instances/aws/instances/%s?_method=DELETE' % instanceId
        client = self.newClient(srv, uri)
        response = client.request('POST', mockedData.xml_terminateInstance1)
        hndlr = instances.Handler()
        response = util.BoundedStringIO(response.read())
        node = hndlr.parseFile(response)
        self.failUnless(isinstance(node, instances.BaseInstance),
                        node)
        self.failUnlessEqual(node.getId(),
            self.makeUri(client, 'clouds/ec2/instances/aws/instances/' + instanceId))

    def testTerminateEC2InstanceFail(self):
        raise testsuite.SkipTestException("this test is probably right. we are returning a 200 when we shouldn't, for flex's sake.")
        def FakeTerminateEC2Instances(*args, **kwargs):
            raise boto.exception.EC2ResponseError(400, "Bad Request",
                    """<?xml version="1.0" encoding="UTF-8"?>\n<Response><Errors><Error><Code>ServerWasLazy</Code><Message>The server isn't going to respond because it wasn't listening</Message></Error></Errors><RequestID>76467959-d192-4314-820a-87f31d739137</RequestID></Response></wrapped_fault>""")

        from catalogService.rest.drivers.ec2.ec2client import EC2Connection
        self.mock(EC2Connection, 'terminate_instances',
                FakeTerminateEC2Instances)

        instanceId = 'i-60f12709'

        srv = self.newService()
        uri = 'clouds/ec2/ec2/instances/' + instanceId
        client = self.newClient(srv, uri)
        err = self.assertRaises(ResponseError,
                client.request, 'DELETE', mockedData.xml_terminateInstance1)
        self.assertEquals(err.status, 400)
        self.assertEquals(err.reason, "<wrapped_fault><status>400</status><reason>Bad Request</reason><body><Response><Errors><Error><Code>ServerWasLazy</Code><Message>The server isn't going to respond because it wasn't listening</Message></Error></Errors><RequestID>76467959-d192-4314-820a-87f31d739137</RequestID></Response></body>")
        self.failIf(not err.headers.dict, "Expected some headers")

    def testTerminateEC2InstancesPOST(self):
        instanceId = 'i-60f12709'

        srv = self.newService()
        uri = 'clouds/ec2/instances/aws/instances/%s?_method=DELETE' % instanceId
        client = self.newClient(srv, uri)
        response = client.request('POST', mockedData.xml_terminateInstance1)
        hndlr = instances.Handler()
        response = util.BoundedStringIO(response.read())
        node = hndlr.parseFile(response)
        self.failUnless(isinstance(node, instances.BaseInstance),
                        node)
        self.failUnlessEqual(node.getId(),
            self.makeUri(client, 'clouds/ec2/instances/aws/instances/' + instanceId))

    #def testStackTraces(self):
    def testBadUserName(self):
        srv = self.newService()
        uri = 'users/bADuSERnAME<xml_tag>/library'

        client = self.newClient(srv, uri)
        reqData = 'Request data'
        e = self.failUnlessRaises(ResponseError,
            client.request, 'POST', body = reqData)

        self.failUnlessEqual(e.status, 400)
        expContents = """\
<?xml version='1.0' encoding='UTF-8'?>
<fault>
  <code>400</code>
  <message>Mismatching users bADuSERnAME&lt;xml_tag&gt;, JeanValjean</message>
</fault>
"""
        self.assertXMLEquals(e.contents, expContents)

        # RBL-3818: if the Flex header is present, faults get wrapped in 200
        resp = client.request('POST', body = reqData,
            headers = {'HTTP_X_FLASH_VERSION' : '0.99fake'})
        self.failUnlessEqual(resp.status, 200)

        contents = resp.read()

crossdomainXml = """\
<?xml version="1.0"?>
<!DOCTYPE cross-domain-policy
          SYSTEM "http://www.adobe.com/xml/dtds/cross-domain-policy.dtd">
<cross-domain-policy>
  <site-control permitted-cross-domain-policies="all" />
  <allow-access-from domain="*" secure="false"/>
  <allow-http-request-headers-from domain="*" headers="*" />
</cross-domain-policy>
"""

_xmlNewCloud = """
<descriptorData>
  <alias>newbie</alias>
  <description>Brand new cloud</description>
  <factory>newbie.eng.rpath.com:8443</factory>
  <factoryIdentity>/O=rPath Inc/CN=host/newbie</factoryIdentity>
  <repository>newbie.eng.rpath.com:2811</repository>
  <repositoryIdentity>"/O=rPath Inc/CN=host/newbie</repositoryIdentity>
  <caCert>-----BEGIN CERTIFICATE-----
MIICZTCCAc6gAwIBAgIBADANBgkqhkiG9w0BAQQFADBVMQ0wCwYDVQQKEwRHcmlk
MRMwEQYDVQQLEwpHbG9idXNUZXN0MRwwGgYDVQQLExNzaW1wbGUtd29ya3NwYWNl
LWNhMREwDwYDVQQDEwhTaW1wbGVDQTAeFw0wNzAyMjYwMjE4MDBaFw0xMjAyMjUw
MjE4MDBaMFUxDTALBgNVBAoTBEdyaWQxEzARBgNVBAsTCkdsb2J1c1Rlc3QxHDAa
BgNVBAsTE3NpbXBsZS13b3Jrc3BhY2UtY2ExETAPBgNVBAMTCFNpbXBsZUNBMIGf
MA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCpFzJ+klOA7XvDs6e9T4EKFzVc5+gP
nsQPk6ARxJMBJvvEmHDVHOiGBKl4ua3KscP/LOPyhTbshtukcE4FrzG3HRrfSzJL
lbRrtmrLFp+9hIv8g2klC9/a444DnBTdrBjcAywRjiDDZwYKZucYjbmivbuzVYDs
xy7eDixbTCmWewIDAQABo0UwQzAPBgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBQ8
HTYkMIb4nykLBEPFRApQAnik/DARBglghkgBhvhCAQEEBAMCAAcwDQYJKoZIhvcN
AQEEBQADgYEAgtdSTpYug9NgtiMK+1ivN+Hug+BAYnfWoqMqbFeRN0R/l7bHI5Q5
E7/27cGZV/rkWw/XiZcY8tvq6IpSj8EO4DNHoPf1fcB456LJC1JynAakR0Um/s/O
mGHoqfb9hJbpLdxyvhdR2RjZYsOjSrF1zrqwCwuYEhVKuCav+oYyC+Q=
-----END CERTIFICATE-----</caCert>
</descriptorData>"""

_xmlNewEC2Creds = """
<descriptorData>
  <accountId>1122334455</accountId>
  <publicAccessKeyId>awsSecretAccessKey</publicAccessKeyId>
  <secretAccessKey>Supr sikrt</secretAccessKey>
</descriptorData>
"""

if __name__ == "__main__":
    testsuite.main()
