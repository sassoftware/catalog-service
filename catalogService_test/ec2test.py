#!/usr/bin/python
# vim: set fileencoding=utf-8 :
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

from testrunner.output import SkipTestException

import base64
import os
import pickle
import StringIO
import tempfile

from conary.lib import util

import testbase

from catalogService.restClient import ResponseError

from catalogService.rest import baseDriver
from catalogService.rest.drivers import ec2 as dec2
from catalogService.rest.models import clouds
from catalogService.rest.models import descriptor
from catalogService.rest.models import images
from catalogService.rest.models import instances
from catalogService.rest.models import jobs as jobmodels
from catalogService.utils import x509

from catalogService_test import mockedData


class HandlerTest(testbase.TestCase):
    TARGETS = [
        ('ec2', 'aws', dict(
            alias = 'aws-us-east',
            region = 'us-east-1',
            description = 'Amazon Elastic Compute Cloud - US East Region',
            ec2PublicKey = 'Public Key',
            ec2PrivateKey = 'Private Key',
            ec2AccountId = '867530900000',
            # Keep bucket name uppercase to test RCE-1354
            ec2S3Bucket = 'Bucket',
            ec2Certificate = mockedData.tmp_userCert,
            ec2CertificateKey = mockedData.tmp_userKey,
            ec2LaunchUsers = ['user1', 'user2'],
            ec2LaunchGroups = ['group1', 'group2'],
        )),
    ]
    MINT_CFG = testbase.TestCase.MINT_CFG + [
        ('proxy', 'http http://user:pass@host:3129'),
        ('proxy', 'https https://user:pass@host:3129'),
    ]

    USER_TARGETS = [
        ('JeanValjean', 'ec2', 'aws', dict(
                accountId = '8675309jv',
                publicAccessKeyId = 'User public key',
                secretAccessKey = 'User private key',
            )),
    ]
    cloudType = 'ec2'
    cloudName = 'aws'
    _baseCloudUrl = 'clouds/%s/instances/%s' % (cloudType, cloudName)

    SecurityGroupHandler = dec2.ec2client.EC2Client.SecurityGroupHandler

    def setUp(self):
        testbase.TestCase.setUp(self)

        self._mockRequest()
        baseDriver.CatalogJobRunner.preFork = lambda *args: None

    def _mockRequest(self, **kwargs):
        from catalogService.rest.drivers.ec2.ec2client import EC2Connection, S3Connection
        s3kwargs = kwargs.pop('s3kwargs', {})

        self.botoRequestDir = os.path.join(self.workDir, "botoRequest")

        class DummyEC2Req(object):
            reqobj = MockedRequest(self.botoRequestDir)
            reqobj.data = MockedRequest.data.copy()
            reqobj.data.update(kwargs)

            @staticmethod
            def mockedMakeRequest(slf, *args, **kwargs):
                # Here we force getting an http connection, so we can trigger
                # proxy_ssl. We need to make this method static, so it gets
                # the real Connection object passed into it as slf
                slf._pool.clean()
                slf.get_http_connection(slf.host, slf.is_secure)
                return DummyEC2Req.reqobj.mockedMakeRequest(*args, **kwargs)

        self.mock(EC2Connection, 'make_request',
                  DummyEC2Req.mockedMakeRequest)
        self.mock(EC2Connection, 'proxy_ssl', mockedProxySsl)

        class DummyS3Req(object):
            reqobj = MockedS3Request(self.botoRequestDir + 'S3')
            reqobj.data = MockedS3Request.data.copy()
            reqobj.data.update(s3kwargs)

            @staticmethod
            def mockedMakeRequest(slf, *args, **kwargs):
                # Here we force getting an http connection, so we can trigger
                # proxy_ssl. We need to make this method static, so it gets
                # the real Connection object passed into it as slf
                slf._pool.clean()
                slf.get_http_connection(slf.host, slf.is_secure)
                return DummyS3Req.reqobj.mockedMakeRequest(*args, **kwargs)

        self.mock(S3Connection, 'make_request',
                  DummyS3Req.mockedMakeRequest)
        self.mock(S3Connection, 'proxy_ssl', mockedProxySsl)

        # Create a new attribute for the connection, a file where we store the
        # proxy config. This should validate that we properly tried to contact
        # the proxy
        proxyFile = os.path.join(self.workDir, "proxySettings")
        proxyFileS3 = os.path.join(self.workDir, "proxySettingsS3")
        for fname in [ proxyFile, proxyFileS3 ]:
            try:
                os.unlink(fname)
            except OSError, e:
                if e.errno != 2:
                    raise
        self.mock(EC2Connection, '_proxyFile', proxyFile)
        self.mock(S3Connection, '_proxyFile', proxyFileS3)

    def testGetClouds1(self):
        srv = self.newService()
        uri = 'clouds/ec2/instances'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = clouds.Handler()
        response = util.BoundedStringIO(response.read())
        nodes = hndlr.parseFile(response)

        self.failUnlessEqual([x.getCloudName() for x in nodes],
            ['aws'])

        self.failUnlessEqual([x.getCloudAlias() for x in nodes],
            ['aws-us-east'])

        self.failUnlessEqual([x.getDescription() for x in nodes],
            ['Amazon Elastic Compute Cloud - US East Region'])

    def testRemoveCloud(self):
        srv = self.newService()
        uri = self._baseCloudUrl
        client = self.newClient(srv, uri)

        response = client.request('DELETE')
        hndlr = clouds.Handler()

        self.assertXMLEquals(response.read(), "<?xml version='1.0' encoding='UTF-8'?>\n<clouds/>")

        # Removing a second time should give a 404
        response = self.failUnlessRaises(ResponseError, client.request, 'DELETE')
        self.failUnlessEqual(response.status, 404)

        # Cloud enumeration should no loger reveal aws
        uri = 'clouds/ec2/instances'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        self.assertXMLEquals(response.read(), "<?xml version='1.0' encoding='UTF-8'?>\n<clouds/>")

        # Instance enumeration should fail with 404 (bad cloud name)
        uri = self._baseCloudUrl + '/instances'
        client = self.newClient(srv, uri)

        response = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(response.status, 404)

    def testGetImages1(self):
        srv = self.newService()
        uri = "%s/images?_method=GET" % self._baseCloudUrl
        correctedUri = "%s/images" % self._baseCloudUrl
        client = self.newClient(srv, uri)

        response = client.request('POST')
        self.failUnlessEqual(response.msg['Content-Type'], 'application/xml')
        self.failUnlessEqual(response.msg['Cache-Control'], 'no-store')
        hndlr = images.Handler()
        response = util.BoundedStringIO(response.read())
        node = hndlr.parseFile(response)
        self.failUnless(isinstance(node, images.BaseImages),
                        node)
        self.failUnlessEqual([x.getImageId() for x in node],
            ['aaaaaabbbbbbbbbcccccccccccddddddddeeeeee', 'ami-0435d06d'])
        # make sure the ?_method=GET portion of the URI didn't persist
        self.failUnlessEqual([x.getId() for x in node],
            [ self.makeUri(client, "%s/%s" % (correctedUri, x)) \
                    for x in ['aaaaaabbbbbbbbbcccccccccccddddddddeeeeee', 'ami-0435d06d'] ])

        # this data comes from the mockModule for mint. we're just testing
        # that it gets integrated
        self.assertEquals([x.getProductDescription() for x in node],
                ['words words SPARKY words', None])
        self.assertEquals([x.getBuildDescription() for x in node],
                ['just words and stuff', None])
        self.assertEquals([x.getIsPrivate_rBuilder() for x in node], [False, None])
        self.assertEquals([x.getProductName() for x in node], ['foo project', None])
        self.assertEquals([x.getRole() for x in node], ['developer', None ])
        self.assertEquals([x.getPublisher() for x in node],
            ['Bob Loblaw', None])
        self.assertEquals([x.getAwsAccountNumber() for x in node],
                [None, None])
        self.assertEquals([x.getBuildName() for x in node],
                ['foo project', None])
        self.assertEquals([x.getIs_rBuilderImage() for x in node],
                [True, False])
        self.assertEquals([x.getBuildPageUrl() for x in node],
                ['http://test.rpath.local2/project/foo/build?id=7', None])
        urlTemplate = 'https://aws-portal.amazon.com/gp/aws/user/subscription/index.html?productCode=%s'

    def testGetImage1(self):
        srv = self.newService()
        imageId = 'ami-0435d06d'
        uri = "%s/images/%s" % (self._baseCloudUrl, imageId)
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = images.Handler()
        response = util.BoundedStringIO(response.read())
        node = hndlr.parseFile(response)
        self.failUnless(isinstance(node, images.BaseImages),
                        node)
        self.failUnlessEqual(len(node), 1)
        self.failUnlessEqual([x.getImageId() for x in node],
            [imageId])

    def testGetInstances1(self):
        # We need to mock the image data
        self._mockRequest(DescribeImages = mockedData.xml_getAllImages3)

        srv = self.newService()
        uri = "%s/instances" % (self._baseCloudUrl, )
        client = self.newClient(srv, uri)

        response = client.request('GET')
        self.failUnlessEqual(response.msg['Content-Type'], 'application/xml')
        self.failUnlessEqual(response.msg['Cache-Control'], 'no-store')
        hndlr = self.InstancesHandler()
        response = util.BoundedStringIO(response.read())
        node = hndlr.parseFile(response)
        self.failUnless(
            isinstance(node, instances.BaseInstances),
            node)
        self.failUnlessEqual(len(node), 2)
        expId = ['i-1639fe7f', 'i-805f98e9', ]
        self.failUnlessEqual([x.getInstanceId() for x in node],
            expId)
        self.failUnlessEqual([x.getId() for x in node],
            [ self.makeUri(client, "%s/%s" % (uri, x)) for x in expId ])
        self.failUnlessEqual([x.getCloudName() for x in node],
            [ 'aws' ] * len(node))
        self.failUnlessEqual([x.getCloudType() for x in node],
            [ 'ec2' ] * len(node))
        self.failUnlessEqual([x.getCloudAlias() for x in node],
            [ 'aws-us-east' ] * len(node))

        self.failUnlessEqual([x.getInstanceName() for x in node],
            ['reviewboard-1.0-x86_13964.img (ami-3675905f)',
             'reviewboard-1.0-x86_13965.img (ami-957590fc)',])
        self.failUnlessEqual([x.getInstanceDescription() for x in node],
            ['reviewboard-1.0-x86_13964.img (ami-3675905f)',
             'reviewboard-1.0-x86_13965.img (ami-957590fc)',])

        self.failUnlessEqual([x.getLaunchTime() for x in node],
            ['1207592569', '1207665151'])
        
        self.failUnlessEqual([x.getPlacement() for x in node],
            ['us-east-1c', 'imperial-russia'])

        urlTemplate = 'https://aws-portal.amazon.com/gp/aws/user/subscription/index.html?productCode=%s'
        self.assertEquals([
            [(y.code.getText(), y.url.getText()) for y in x.getProductCode()]
            for x in node],
            [ [ (x, urlTemplate % x) for x in [ '8ED157F9', '8675309' ] ],
              [ (x, urlTemplate % x) for x in [ '8675309', '8ED157F9' ] ] ])

        self.failUnlessEqual(
            [[ x.getId() for x in n.getSecurityGroup() ] for n in node ],
            [ [ 'BEA Demo' ], [ 'BEA Demo' ]])

    def testGetInstance1(self):
        srv = self.newService()
        uri = "%s/instances/%s" % (self._baseCloudUrl, 'AABBCC')
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = self.InstancesHandler()
        node = hndlr.parseString(response.read())

        # Normally we should only get one instance, but the call is mocked
        self.failUnlessEqual(node.getInstanceId(),
            'i-1639fe7f')
        self.failUnlessEqual( [ x.getId() for x in node.getSecurityGroup() ],
            ['BEA Demo'])

    def testGetInstance2(self):
        self._mockRequest(DescribeInstances = mockedData.xml_getAllInstances2)
        srv = self.newService()
        uri = "%s/instances/%s" % (self._baseCloudUrl, 'AABBCC')
        client = self.newClient(srv, uri)

        response = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(response.status, 404)

    def testGetSecurityGroups(self):
        srv = self.newService()
        uri = "%s/instances/%s" % (self._baseCloudUrl, 'AABBCC/securityGroups')
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = self.SecurityGroupHandler()
        data = response.read()
        nodes = hndlr.parseString(data)
        self.failUnlessEqual([x.getId() for x in nodes],
            [ self.makeUri(client, uri + '/' + x)
                for x in ['SAS%%20Demo', 'build-cluster']])
        self.failUnlessEqual([x.getGroupName() for x in nodes],
            ['SAS Demo', 'build-cluster'])
        self.failUnlessEqual([x.getDescription() for x in nodes],
            ['Permissions for SAS demo', 'private group for rMake build cluster in ec2'])
        self.failUnlessEqual(
            [ [ ([z.getText() for z in y.getIpRange()], y.getIpProtocol(), y.getFromPort(), y.getToPort())
                for y in x.getPermission() ] for x in nodes ],
            [
                [
                    (['149.173.12.1/24', '149.173.13.1/24', '149.173.8.1/24',
                        '24.163.70.1/24', '66.192.95.1/24'], 'tcp', '0', '65535'),
                    (['149.173.12.1/24', '149.173.13.1/24', '149.173.8.1/24',
                        '24.163.70.1/24', '66.192.95.1/24'], 'udp', '0', '65535')
                ],
                [
                    (['build-cluster-941766519978'], 'tcp', '1', '65535'),
                    (['build-cluster-941766519978'], 'udp', '1', '65535'),
                    (['build-cluster-941766519978'], 'icmp', '-1', '-1'),
                    (['66.192.95.194/32'], 'tcp', '0', '65535'),
                    (['66.192.95.194/32'], 'udp', '0', '65535')
                ],
            ])

    def testGetSecurityGroup(self):
        self._mockRequest(DescribeSecurityGroups =
            mockedData.xml_getAllSecurityGroups1.replace("SAS", "BEA"))
        srv = self.newService()
        uri = "%s/instances/%s" % (self._baseCloudUrl, 'AABBCC/securityGroups/BEA%%20Demo')
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = self.SecurityGroupHandler()
        data = response.read()
        node = hndlr.parseString(data)
        self.failUnlessEqual(node.getId(),
            self.makeUri(client, uri))
        self.failUnlessEqual(node.getGroupName(), 'BEA Demo')
        self.failUnlessEqual(node.getDescription(),
            'Permissions for BEA demo')
        self.failUnlessEqual(
            [ ([z.getText() for z in y.getIpRange()], y.getIpProtocol(), y.getFromPort(), y.getToPort())
                for y in node.getPermission() ],
            [
                (['149.173.12.1/24', '149.173.13.1/24', '149.173.8.1/24',
                    '24.163.70.1/24', '66.192.95.1/24'], 'tcp', '0', '65535'),
                (['149.173.12.1/24', '149.173.13.1/24', '149.173.8.1/24',
                    '24.163.70.1/24', '66.192.95.1/24'], 'udp', '0', '65535')
            ])

    def testUpdateSecurityGroup(self):
        self._mockRequest(DescribeSecurityGroups =
            mockedData.xml_getAllSecurityGroups1.replace("SAS", "BEA"))
        srv = self.newService()
        uri = "%s/instances/%s" % (self._baseCloudUrl, 'AABBCC/securityGroups/BEA%%20Demo')
        client = self.newClient(srv, uri)

        body = """\
<securityGroup>
  <permission>
    <fromPort>0</fromPort>
    <ipProtocol>tcp</ipProtocol>
    <ipRange>149.173.12.1/24</ipRange>
    <ipRange>149.173.13.1/24</ipRange>
    <ipRange>149.173.8.1/24</ipRange>
    <ipRange>24.163.70.1/24</ipRange>
    <ipRange>88.192.95.1/24</ipRange>
    <toPort>65535</toPort>
  </permission>
  <permission>
    <fromPort>0</fromPort>
    <ipProtocol>udp</ipProtocol>
    <ipRange>149.173.12.1/24</ipRange>
    <ipRange>149.173.13.1/24</ipRange>
    <ipRange>149.173.8.1/24</ipRange>
    <ipRange>24.163.70.1/24</ipRange>
    <ipRange>88.192.95.1/24</ipRange>
    <toPort>65535</toPort>
  </permission>
  <permission>
    <fromPort>22</fromPort>
    <ipProtocol>tcp</ipProtocol>
    <ipRange>1.2.3.4/24</ipRange>
    <toPort>22</toPort>
  </permission>
</securityGroup>
"""

        response = client.request('PUT', body)
        hndlr = self.SecurityGroupHandler()
        data = response.read()
        node = hndlr.parseString(data)
        self.failUnlessEqual(node.getId(),
            self.makeUri(client, uri))
        self.failUnlessEqual(node.getGroupName(), 'BEA Demo')
        self.failUnlessEqual(node.getDescription(),
            'Permissions for BEA demo')
        self.failUnlessEqual(
            [ ([z.getText() for z in y.getIpRange()], y.getIpProtocol(), y.getFromPort(), y.getToPort())
                for y in node.getPermission() ],
            [
                (['149.173.12.1/24', '149.173.13.1/24', '149.173.8.1/24',
                    '24.163.70.1/24', '66.192.95.1/24'], 'tcp', '0', '65535'),
                (['149.173.12.1/24', '149.173.13.1/24', '149.173.8.1/24',
                    '24.163.70.1/24', '66.192.95.1/24'], 'udp', '0', '65535')
            ])

    def testNewCloud(self):
        self.deleteTarget('ec2', 'aws')

        srv = self.newService()
        uri = 'clouds/ec2/instances'
        client = self.newClient(srv, uri)
        reqData = _xmlNewCloud
        response = client.request('POST', reqData)

        # Fetch the proxy file
        from catalogService.rest.drivers.ec2.ec2client import S3Connection
        proxySettings = open(S3Connection._proxyFile).read()
        self.failUnlessEqual(proxySettings, """\
proxy = host
proxy_port = 3129
proxy_user = user
proxy_pass = pass
""")

        hndl = clouds.Handler()
        node = hndl.parseString(response.read())

        cloudName = 'newbie.eng.rpath.com'
        cloudAlias = 'newbie'
        cloudId = "http://%s/TOPLEVEL/clouds/%s/instances/%s" % (
            client.hostport, self.cloudType, cloudName)
        self.failUnlessEqual(node.getId(), cloudId)
        self.failUnlessEqual(node.getCloudAlias(), cloudAlias)
        self.failUnlessEqual(node.getCloudName(), cloudName)
        self.failUnlessEqual(node.getType().getText(), self.cloudType)

        dataDict = self.getTargetData(self.cloudType, cloudName)
        dataDict['ec2Certificate'] = _normalizeCert(dataDict['ec2Certificate'])
        dataDict['ec2CertificateKey'] = _normalizeCert(dataDict['ec2CertificateKey'])

        self.failUnlessEqual(dataDict, {
            'alias': cloudAlias,
            'description': 'Brand new cloud',
            'ec2AccountId': '867530900000',
            'ec2Certificate': _normalizeCert(mockedData.tmp_userCert),
            'ec2CertificateKey': _normalizeCert(mockedData.tmp_userKey),
            'ec2PrivateKey': 'Secret key',
            'ec2PublicKey': 'Public key',
            'ec2S3Bucket': 'S3 Bucket',
            'name': cloudName,
            'region' : 'us-east-1',
        })

        # Adding it again should fail
        response = self.failUnlessRaises(ResponseError,
            client.request, 'POST', reqData)
        self.failUnlessEqual(response.status, 409)
        self.assertXMLEquals(response.contents, """
<?xml version='1.0' encoding='UTF-8'?>
<fault>
  <code>409</code>
  <message>Target already exists</message>
</fault>""")

        # Enumerate clouds
        uri = 'clouds/ec2/instances'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndl = clouds.Handler()
        nodes = hndl.parseString(response.read())
        self.failUnlessEqual(len(nodes), 1)
        node = nodes[0]
        self.failUnlessEqual(node.getCloudAlias(), cloudAlias)

    def testNewCloud2(self):
        # RBL-4060 - force cred validation errors
        self._mockRequest(DescribeRegions = mockedData.xml_getAllRegions2)

        self.deleteTarget('ec2', 'aws')

        srv = self.newService()
        uri = 'clouds/ec2/instances'
        client = self.newClient(srv, uri)

        reqData = _xmlNewCloud

        resp = self.failUnlessRaises(ResponseError,
            client.request, 'POST', reqData)
        self.failUnlessEqual(resp.status, 403)
        self.assertXMLEquals(resp.contents, """
<?xml version="1.0" encoding="UTF-8"?>
<fault>
  <code>403</code>
  <message>The AWS Access Key Id you provided does not exist in our records.</message>
  <traceback>&lt;Response&gt;&lt;Errors&gt;&lt;Error&gt;&lt;Code&gt;InvalidClientTokenId&lt;/Code&gt;&lt;Message&gt;The AWS Access Key Id you provided does not exist in our records.&lt;/Message&gt;&lt;/Error&gt;&lt;/Errors&gt;&lt;RequestID&gt;10f59dc7-1053-4cc5-9e8b-20cdef2428d3&lt;/RequestID&gt;&lt;/Response&gt;</traceback>
</fault>""")

    def testNewCloudValidS3Bucket1(self):
        self.deleteTarget('ec2', 'aws')

        self._mockRequest(s3kwargs = dict(
            PUT = {
                None : (409, '<?xml version="1.0" encoding="UTF-8"?>\n<Error><Code>BucketAlreadyExists</Code><Message>The requested bucket name is not available. The bucket namespace is shared by all users of the system. Please select a different name and try again.</Message><BucketName>foonly</BucketName><RequestId>9475636DFF559A9B</RequestId><HostId>a7paJwA7n8i+tMHAW0WwbQfN85Ss7NNOGtA/A0xGHmMsmGajE8fWdYOCMza9WJQs</HostId></Error>'),
            },
            GET = {
                None : (403, '<?xml version="1.0" encoding="UTF-8"?>\n<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Name>foonly</Name><Prefix></Prefix><Marker></Marker><MaxKeys>1000</MaxKeys><IsTruncated>false</IsTruncated></ListBucketResult>')
            }))

        srv = self.newService()
        uri = 'clouds/ec2/instances'
        client = self.newClient(srv, uri)

        reqData = _xmlNewCloud
        response = self.failUnlessRaises(ResponseError,
            client.request, 'POST', reqData)
        self.failUnlessEqual(response.status, 409)

    def testNewCloudValidS3Bucket2(self):
        self.deleteTarget('ec2', 'aws')

        self.mock(dec2.driver, '_createRandomKey', lambda x: '99999')

        self._mockRequest(s3kwargs = dict(
            PUT = {
                None : (409, '<?xml version="1.0" encoding="UTF-8"?>\n<Error><Code>BucketAlreadyExists</Code><Message>The requested bucket name is not available. The bucket namespace is shared by all users of the system. Please select a different name and try again.</Message><BucketName>foonly</BucketName><RequestId>9475636DFF559A9B</RequestId><HostId>a7paJwA7n8i+tMHAW0WwbQfN85Ss7NNOGtA/A0xGHmMsmGajE8fWdYOCMza9WJQs</HostId></Error>'),
                '99999' : (403, ''),
            },
            GET = {
                None : '<?xml version="1.0" encoding="UTF-8"?>\n<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Name>foonly</Name><Prefix></Prefix><Marker></Marker><MaxKeys>1000</MaxKeys><IsTruncated>false</IsTruncated></ListBucketResult>'
            },
            DELETE = {
                '99999' : (204, ''),
            },))

        srv = self.newService()
        uri = 'clouds/ec2/instances'
        client = self.newClient(srv, uri)

        reqData = _xmlNewCloud
        response = self.failUnlessRaises(ResponseError,
            client.request, 'POST', reqData)
        self.failUnlessEqual(response.status, 409)


    def testNewCloudValidS3Bucket3(self):
        # Remove the cloud
        self.deleteTarget('ec2', 'aws')

        self.mock(dec2.driver, '_createRandomKey', lambda x: '99999')

        self._mockRequest(s3kwargs = dict(
            PUT = {
                None : (409, '<?xml version="1.0" encoding="UTF-8"?>\n<Error><Code>BucketAlreadyExists</Code><Message>The requested bucket name is not available. The bucket namespace is shared by all users of the system. Please select a different name and try again.</Message><BucketName>foonly</BucketName><RequestId>9475636DFF559A9B</RequestId><HostId>a7paJwA7n8i+tMHAW0WwbQfN85Ss7NNOGtA/A0xGHmMsmGajE8fWdYOCMza9WJQs</HostId></Error>'),
                '99999' : (204, ''),
            },
            GET = {
                None : '<?xml version="1.0" encoding="UTF-8"?>\n<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Name>foonly</Name><Prefix></Prefix><Marker></Marker><MaxKeys>1000</MaxKeys><IsTruncated>false</IsTruncated></ListBucketResult>'
            },
            DELETE = {
                '99999' : (204, ''),
            },))

        srv = self.newService()
        uri = 'clouds/ec2/instances'
        client = self.newClient(srv, uri)

        reqData = _xmlNewCloud
        client.request('POST', reqData)

    def testGetImageDeploymentDescriptor(self):
        srv = self.newService()
        uri = "%s/descriptor/deployImage" % (self._baseCloudUrl, )

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getRootElement(), "newImage")
        self.failUnlessEqual(dsc.getDisplayName(), "Amazon EC2 Image Deployment Parameters")
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'Amazon EC2 Image Deployment Parameters'})
        self.failUnlessEqual([ df.name for df in dsc.getDataFields() ],
            ['imageId', 'imageName', 'imageDescription', 'tags', ])

    def testGetLaunchDescriptor(self):
        srv = self.newService()
        uri = "%s/descriptor/launch" % (self._baseCloudUrl, )

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getDisplayName(), "Amazon EC2 System Launch Parameters")
        self.failUnlessEqual(dsc.getDescriptions(), {None : "Amazon EC2 System Launch Parameters"})
        self.failUnlessEqual([ df.name for df in dsc.getDataFields() ],
            ['imageId', 'instanceName', 'instanceDescription', 'instanceType',
             'availabilityZone',
             'minCount', 'maxCount', 'keyName',
             'securityGroups', 'remoteIp', 'userData', 'tags'])
        ftypes = [ df.type for df in dsc.getDataFields() ]
        self.failUnlessEqual([ ftypes[0], ftypes[1], ftypes[2], ftypes[5],
            ftypes[6], ftypes[9], ftypes[10] ],
            ['str', 'str', 'str', 'int', 'int', 'str', 'str'])
        self.failUnlessEqual([ [ (x.key, x.descriptions.asDict()) for x in ftype ]
            for ftype in [ ftypes[3], ftypes[4], ftypes[7], ftypes[8] ] ],
            [
                [
                    ('m3.medium', {None: 'M3 Medium'}),
                    ('m3.large', {None: 'M3 Large'}),
                    ('m3.xlarge', {None: 'M3 Extra Large'}),
                    ('m3.2xlarge', {None: 'M3 Double Extra Large'}),
                    ('c3.large', {None: 'C3 Compute Optimized Large'}),
                    ('c3.xlarge', {None: 'C3 Compute Optimized Extra Large'}),
                    ('c3.2xlarge', {None: 'C3 Compute Optimized Double Extra Large'}),
                    ('c3.4xlarge', {None: 'C3 Compute Optimized Quadruple Extra Large'}),
                    ('c3.8xlarge', {None: 'C3 Compute Optimized Eight Extra Large'}),
                    ('g2.2xlarge', {None: 'G2 GPU-Optimized Double Extra Large'}),
                    ('r3.xlarge', {None: 'R3 Memory Optimized Extra Large'}),
                    ('r3.2xlarge', {None: 'R3 Memory Optimized Double Extra Large'}),
                    ('r3.4xlarge', {None: 'R3 Memory Optimized Quadruple Extra Large'}),
                    ('r3.8xlarge', {None: 'R3 Memory Optimized Eight Extra Large'}),
                    ('i2.xlarge', {None: 'I2 Storage Optimized Extra Large'}),
                    ('i2.2xlarge', {None: 'I2 Storage Optimized Double Extra Large'}),
                    ('i2.4xlarge', {None: 'I2 Storage Optimized Quadruple Extra Large'}),
                    ('i2.8xlarge', {None: 'I2 Storage Optimized Eight Extra Large'}),
                    ('hs1.8xlarge', {None: 'High Storage Eight Extra Large'}),
                    ('m1.small', {None: '(OLD) M1 Small'}),
                    ('m1.medium', {None: '(OLD) M1 Medium'}),
                    ('m1.large', {None: '(OLD) M1 Large'}),
                    ('m1.xlarge', {None: '(OLD) M1 Extra Large'}),
                    ('m2.xlarge', {None: '(OLD) M2 High Memory Extra Large'}),
                    ('m2.2xlarge', {None: '(OLD) M2 High Memory Double Extra Large'}),
                    ('m2.4xlarge', {None: '(OLD) M2 High Memory Quadruple Extra Large'}),
                    ('c1.medium', {None: '(OLD) C1 High-CPU Medium'}),
                    ('c1.xlarge', {None: '(OLD) C1 High-CPU Extra Large'}),
                    ('hi1.4xlarge', {None: '(OLD) High I/O Quadruple Extra Large'})
                ],
                [
                    ('us-east-1a', {None: 'us-east-1a'}),
                    ('us-east-1b', {None: 'us-east-1b'}),
                    ('us-east-1c', {None: 'us-east-1c'}),
                    ('us-east-1d', {None: 'us-east-1d'}),
                ],
                [
                    ('tgerla', {None: 'tgerla'}),
                    ('gxti', {None: 'gxti'}),
                    ('bpja', {None: 'bpja'})
                ],
                [
                    ('catalog-default', {None: 'Default EC2 Catalog Security Group'}),
                    (u'dynamic', {None: u'Generated Security Group'}),
                    ('SAS Demo', {None: 'Permissions for SAS demo'}),
                    ('build-cluster', {None: 'private group for rMake build cluster in ec2'})
                ]
            ])
        self.assertEquals(ftypes[11], 'listType')
        expMultiple = [None, None, None, None, None, None, None, None, True, None, None, None]
        self.failUnlessEqual([ df.multiple for df in dsc.getDataFields() ],
            expMultiple)
        self.failUnlessEqual([ df.required for df in dsc.getDataFields() ],
            [ True, True, None, True, None, True, True, None, True, None, None, None] )
        self.failUnlessEqual([ df.hidden for df in dsc.getDataFields() ],
            [ True, None, None, None, None, None, None, None, None, True, None, None] )
        prefix = self.makeUri(client, "help/targets/drivers/%s/launch/" % self.cloudType)
        self.failUnlessEqual([ df.helpAsDict for df in dsc.getDataFields() ],
            [
                {},
                {None: prefix + 'instanceName.html'},
                {None: prefix + 'instanceDescription.html'},
                {None: prefix + 'instanceTypes.html'},
                {None: prefix + 'availabilityZones.html'},
                {None: prefix + 'minInstances.html'},
                {None: prefix + 'maxInstances.html'},
                {None: prefix + 'keyPair.html'},
                {None: prefix + 'securityGroups.html'},
                {},
                {None: prefix + 'userData.html'},
                {},
            ])
        self.failUnlessEqual([ df.getDefault() for df in dsc.getDataFields() ],
            [None, None, None, 'm3.medium', None, 1, 1, None, ['catalog-default'], None, None, None])

        self.failUnlessEqual([ df.descriptions.asDict() for df in dsc.getDataFields() ],
            [
                {None: 'Image ID'},
                {None: 'Instance Name'},
                {None: 'Instance Description'},
                {None: 'Instance Type', 'fr_FR': "Type de l'instance"},
                {None: 'Availability Zone', 'fr_FR': u"Zone de disponibilit\u00e9"},
                {None: 'Minimum Number of Instances',
                    'fr_FR': "Nombre minimal d'instances"},
                {None: 'Maximum Number of Instances',
                    'fr_FR': "Nombre maximal d'instances"},
                {None: 'SSH Key Pair', 'fr_FR' : 'Paire de clefs' },
                {None: 'Security Groups', 'fr_FR' : u"Groupes de sécurité"},
                {None: 'Remote IP address allowed to connect (if security group is catalog-default)'},
                {None: 'User Data', 'fr_FR' : 'Data utilisateur'},
                {None: 'Additional tags'},
                ])
        self.failUnlessEqual([ df.constraintsPresentation for df in dsc.getDataFields() ],
            [
                [{'max': 32, 'constraintName': 'range', 'min': 1}],
                [{'constraintName': 'length', 'value': 32}],
                [{'constraintName': 'length', 'value': 128}],
                [],
                [],
                [{'max': 100, 'constraintName': 'range', 'min': 1}],
                [{'max': 100, 'constraintName': 'range', 'min': 1}],
                [], [],
                [{'constraintName': 'length', 'value': 128}],
                [{'constraintName': 'length', 'value': 256}],
                [{'constraintName': 'maxLength', 'value': 9}],
            ])
        tagsField = dsc.getDataFields()[11]
        tagsFieldFields = tagsField._descriptor.getDataFields()
        self.assertEquals([ df.name for df in tagsFieldFields ],
                ['name', 'value', ])
        self.assertEquals([ df.type for df in tagsFieldFields ],
                [ 'str', 'str', ])
        self.assertEquals([ df.multiple for df in tagsFieldFields ],
                [ None, None, ])
        self.assertEquals([ df.required for df in tagsFieldFields ],
                [ True, True, ])
        self.assertEquals([ df.constraintsPresentation for df in tagsFieldFields ],
                [
                    [{'constraintName': 'length', 'value': 127}],
                    [{'constraintName': 'length', 'value': 255}],
                    ])

    class InstancesHandler(instances.Handler):
        instanceClass = dec2.driver.Instance

    def _mockFunctions(self):
        def fakeDaemonize(slf, *args, **kwargs):
            slf.postFork()
            return slf.function(*args, **kwargs)
        self.mock(baseDriver.CatalogJobRunner, 'backgroundRun', fakeDaemonize)

        def fakeOpenUrl(slf, url, headers):
            return StringIO.StringIO(url)
        self.mock(dec2.driver, "openUrl", fakeOpenUrl)

        def getFilesystemImageFunc(slf, job, image, stream):
            f = tempfile.NamedTemporaryFile(delete=False)
            f.seek(1024 * 1024 - 1)
            f.write('\0')
            f.close()
            return f.name
        self.mock(dec2.driver, '_getFilesystemImage', getFilesystemImageFunc)

    def _setUpNewImageTest(self, cloudName=None, imageName=None, imageId=None):
        if cloudName is None:
            cloudName = self.cloudName

        self._mockFunctions()
        if not imageId:
            imageId = 'aaaaaabbbbbbbbbcccccccccccddddddddeeeeee'

        srv = self.newService()
        uri = 'clouds/%s/instances/%s/images' % (self.cloudType, cloudName)

        requestXml = mockedData.xml_newImageVMware1 % imageId
        client = self.newClient(srv, uri)
        response = client.request('POST', requestXml)

        job = self.getJobFromResponse(response)
        return srv, client, job, response

    def testDeployImage1(self):
        # We need to mock the image data
        getAclXml = """
<AccessControlPolicy><Owner><ID>eddc7475f4f0dd333f7724f3edcc77b281e0150690f02eac96cb1d5f382ca8ec</ID><DisplayName>awsrpath</DisplayName></Owner><AccessControlList><Grant><Grantee xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="CanonicalUser"><ID>eddc7475f4f0dd333f7724f3edcc77b281e0150690f02eac96cb1d5f382ca8ec</ID><DisplayName>awsrpath</DisplayName></Grantee><Permission>FULL_CONTROL</Permission></Grant><Grant><Grantee xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="CanonicalUser"><ID>6aa5a366c34c1cbe25dc49211496e913e0351eb0e8c37aa3477e40942ec6b97c</ID><DisplayName>za-team</DisplayName></Grantee><Permission>READ</Permission></Grant></AccessControlList></AccessControlPolicy>"""
        self._mockRequest(DescribeImages = mockedData.xml_getAllImages2,
            RegisterImage=mockedData.xml_registerImage1,
            s3kwargs = dict(
                PUT = {
                    None: 200,
                    'some-file-6-1-x86_6.part.0' : 200,
                    'some-file-6-1-x86_6.manifest.xml' : 200,
                },
                HEAD = {
                    'some-file-6-1-x86_6.part.0' : 200,
                    'some-file-6-1-x86_6.manifest.xml' : 200,
                },
                GET = {
                    'some-file-6-1-x86_6.part.0' : getAclXml,
                    'some-file-6-1-x86_6.manifest.xml' : getAclXml,
                },
        ))

        imageId = 'aaaaaabbbbbbbbbcccccccccccddddddddeeeeee'
        srv, client, job, response = self._setUpNewImageTest(
            imageId=imageId, imageName='blabbedy')

        jobUrlPath = 'jobs/types/image-deployment/jobs/1'
        imageUrlPath = 'clouds/%s/instances/%s/images/%s' % (
            self.cloudType, self.cloudName, imageId)

        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))
        self.failUnlessEqual(job.get_imageId(), self.makeUri(client, imageUrlPath))

        job = self.waitForJob(srv, jobUrlPath, "Completed")

        self.failUnlessEqual([ x.get_content() for x in job.history ], [
            'Running',
            'Bundling image',
            'Uploading bundle',
            'Registering image',
            'Registered ami-00112233',
            'Done',
        ])
        self.failUnlessEqual(job.get_statusMessage(), 'Done')
        self.failUnlessEqual([ x.href for x in job.get_resultResource() ],
            [ self.makeUri(client, self._baseCloudUrl + '/images/ami-00112233') ])

        # RCE-1354 - verify we're attempting to register the image with
        # the lowercase bucket name
        fname = os.path.join(self.botoRequestDir, 'RegisterImage')
        args = pickle.load(file(fname))
        self.assertEquals(args, {'ImageLocation': 'bucket/some-file-6-1-x86_6.manifest.xml'})

    def testNewInstances(self):
        # We need to mock the image data
        self._mockRequest(DescribeImages = mockedData.xml_getAllImages2)

        srv = self.newService()
        uri = "%s/instances" % (self._baseCloudUrl, )

        client = self.newClient(srv, uri)
        response = client.request('POST', mockedData.xml_newInstance6)

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        imageUrlPath = "%s/images/ami-afa642c6" % (self._baseCloudUrl, )

        node = jobmodels.Job()
        node.parseStream(response)
        self.failUnlessEqual(node.get_id(), self.makeUri(client, jobUrlPath))
        self.failUnlessEqual(node.get_imageId(), self.makeUri(client, imageUrlPath))

        node = self.waitForJob(srv, jobUrlPath, "Completed")
        #self.failUnlessEqual(node.getImageId(), self.makeUri(client, imageUrlPath))

        instanceIds = ['i-e2df098b', 'i-e5df098c']

        results = node.get_resultResource()
        _p = "%s/instances/" % (self._baseCloudUrl, )
        self.failUnlessEqual([ x.get_href() for x in results ],
            [ self.makeUri(client, _p + x) for x in instanceIds ])

        jobId = os.path.basename(node.id)
        cu = self.restdb.db.cursor()
        cu.execute("SELECT job_uuid FROM jobs WHERE job_id = ?", jobId)
        bootUuid, = cu.fetchone()

        # RBL-3998 - verify the user data is sent to boto
        fpath = os.path.join(self.botoRequestDir, "RunInstances")
        params = pickle.load(file(fpath))

        for instanceId in instanceIds:
            # Grab SSL cert
            certFile = os.path.join(self.workDir, "data", "x509.crt")
            certContents = file(certFile).read()
            certHash = x509.X509.computeHash(certFile)
            zoneAddresses = "1.2.3.4:5678 2.3.4.5:6789"
            conaryProxies = "1.2.3.4 2.3.4.5"
            userData = """\
my user data
[amiconfig]
plugins = rpath sfcb-client-setup
[sfcb-client-setup]
x509-cert-hash=%s
x509-cert(base64)=%s
[rpath-tools]
boot-uuid=%s
zone-addresses=%s
conary-proxies=%s
""" % (certHash, base64.b64encode(certContents), bootUuid, zoneAddresses,
            conaryProxies)

        self.failUnlessEqual(params['UserData'], base64.b64encode(userData))
        self.failUnlessEqual(params['Placement.AvailabilityZone'], 'us-east-1c')

    def testNewInstancesWithCatalogDefaultWithoutRemoteIp(self):
        # We need to mock the image data
        self._mockRequest(DescribeImages = mockedData.xml_getAllImages2)

        srv = self.newService()
        uri = "%s/instances" % (self._baseCloudUrl, )

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'

        client = self.newClient(srv, uri)
        response = client.request('POST', mockedData.xml_newInstance5)
        job = self.getJobFromResponse(response)
        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))

        job = self.waitForJob(srv, jobUrlPath, "Completed")
        results = job.get_resultResource()
        _p = "%s/instances/" % (self._baseCloudUrl, )
        self.failUnlessEqual([ x.get_href() for x in results ],
            [ self.makeUri(client, _p + x)
                for x in ['i-e2df098b', 'i-e5df098c'] ])

    def testNewInstancesNoRemoteIP(self):
        self._mockRequest(DescribeImages = mockedData.xml_getAllImages2)

        srv = self.newService()
        uri = "%s/instances" % (self._baseCloudUrl, )

        client = self.newClient(srv, uri)
        # No longer expect a ResponseError if bad data is supplied for the
        # remote IP (RBL-4148)
        #response = self.failUnlessRaises(ResponseError,
        #    client.request, 'POST', mockedData.xml_newInstance5)
        #self.failUnlessEqual(response.status, 400)

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'

        response = client.request('POST', mockedData.xml_newInstance5)

        job = self.getJobFromResponse(response)
        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))

        job = self.waitForJob(srv, jobUrlPath, "Completed")

        data = pickle.load(file(os.path.join(
            self.botoRequestDir, 'AuthorizeSecurityGroupIngress')))
        self.failUnlessEqual(data, {
                'IpPermissions.1.ToPort': 5989,
                'GroupName': 'catalog-default',
                'IpPermissions.1.IpRanges.1.CidrIp': u'0.0.0.0/0',
                'IpPermissions.1.IpProtocol': 'tcp',
                'IpPermissions.1.FromPort': 5989,
                })

    def testNewInstancesProductCodeError(self):
        def FakeRunInstances(*args, **kwargs):
            from catalogService.rest.drivers.ec2.ec2client import EC2ResponseError
            raise EC2ResponseError(400, "Bad Request", mockedData.ec2ProductCodeErrorXML) 
                                   
        from catalogService.rest.drivers.ec2.ec2client import EC2Connection
        self.mock(EC2Connection, 'run_instances', FakeRunInstances)

        srv = self.newService()
        uri = "%s/instances" % (self._baseCloudUrl, )

        client = self.newClient(srv, uri)
        resp = client.request('POST', mockedData.xml_newInstance1)

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        job = self.getJobFromResponse(resp)
        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))

        job = self.waitForJob(srv, jobUrlPath, 'Failed')
        errorResponse = job.get_errorResponse()
        sio = util.BoundedStringIO()
        errorResponse.export(sio, 0, '')
        sio.seek(0)
        self.assertXMLEquals(sio.read(), '''<errorResponse><fault><code>400</code><message>Subscription to ProductCode 8675309 required.</message><traceback>&lt;Response&gt;&lt;Errors&gt;&lt;Error&gt;&lt;Code&gt;AuthFailure&lt;/Code&gt;&lt;Message&gt;Subscription to ProductCode 8675309 required.&lt;/Message&gt;&lt;/Error&gt;&lt;/Errors&gt;&lt;RequestID&gt;76467959-d192-4314-820a-87f31d739137&lt;/RequestID&gt;&lt;/Response&gt;
</traceback><productCode url="https://aws-portal.amazon.com/gp/aws/user/subscription/index.html?productCode=8675309" code="8675309"/></fault></errorResponse>''')

    def testHelp(self):
        raise SkipTestException("Temporarily skipping -- misa")
        srv = self.newService()
        uri = 'clouds/ec2/help/demo/about.html'

        client = self.newClient(srv, uri)
        resp = client.request('GET')
        self.failUnlessEqual(resp.status, 200)
        self.failUnlessEqual(resp.msg['Content-Type'], 'text/html')
        self.failUnlessEqual(resp.read()[:14], "<html>\n<head>\n")

    def testGetConfiguration(self):
        self.setAdmin(1)
        srv = self.newService()
        uri = "%s/configuration" % (self._baseCloudUrl, )

        client = self.newClient(srv, uri)
        response = client.request('GET')

        self.assertXMLEquals(response.read(), """\
<?xml version='1.0' encoding='UTF-8'?>
<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/ec2/instances/aws/configuration">
  <accountId>867530900000</accountId>
  <alias>aws-us-east</alias>
  <certificateData>%s</certificateData>
  <certificateKeyData>%s</certificateKeyData>
  <description>Amazon Elastic Compute Cloud - US East Region</description>
  <name>aws</name>
  <publicAccessKeyId>Public Key</publicAccessKeyId>
  <region>us-east-1</region>
  <s3Bucket>Bucket</s3Bucket>
  <secretAccessKey>Private Key</secretAccessKey>
</descriptorData>""" % (client.hostport, mockedData.tmp_userCert, mockedData.tmp_userKey))

    def testGetConfigurationStrangeTargetData(self):
        self.setAdmin(True)
        self.deleteTarget('ec2', 'aws')
        dataDict = dict(accountId = '',
            ec2Certificate = '-----BEGIN BLAH-----\n' +
                             'certHere\n' +
                             '-----END BLAH-----\n',
            ec2CertificateKey = '-----BEGIN BLAH-----\n' +
                             'certKeyHere\n' +
                             '-----END BLAH-----\n',
            alias = 'newbie',
            description = 'Some fake data here',
            ec2PublicKey = 'public key ID',
            ec2PrivateKey = 'secret key data',
            ec2S3Bucket = 'my-bucket',
            )
        self.setTargetData('ec2', 'aws', dataDict)

        srv = self.newService()
        uri = "%s/configuration" % (self._baseCloudUrl, )

        client = self.newClient(srv, uri)
        response = client.request('GET')

        self.assertXMLEquals(response.read(), """\
<?xml version='1.0' encoding='UTF-8'?>
<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/ec2/instances/aws/configuration">
  <accountId></accountId>
  <alias>%s</alias>
  <certificateData>%s</certificateData>
  <certificateKeyData>%s</certificateKeyData>
  <description>%s</description>
  <name>aws</name>
  <publicAccessKeyId>%s</publicAccessKeyId>
  <s3Bucket>my-bucket</s3Bucket>
  <secretAccessKey>%s</secretAccessKey>
</descriptorData>""" % (client.hostport, dataDict['alias'],
            dataDict['ec2Certificate'], dataDict['ec2CertificateKey'],
            dataDict['description'], dataDict['ec2PublicKey'],
            dataDict['ec2PrivateKey']))

    def testGetConfigurationMissingTarget(self):
        self.deleteTarget('ec2', 'aws')

        srv = self.newService()
        uri = "%s/configuration" % (self._baseCloudUrl, )

        client = self.newClient(srv, uri)
        e = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(e.status, 404)

    def testGetConfigurationPermissionDenied(self):
        srv = self.newService()
        uri = "%s/configuration" % (self._baseCloudUrl, )

        client = self.newClient(srv, uri)
        response = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(response.status, 403)
        self.assertXMLEquals(response.contents, '<?xml version="1.0" encoding="UTF-8"?>\n<fault>\n  <code>403</code>\n  <message>Permission Denied - user is not adminstrator</message>\n</fault>')

    def testSetCredentialsEC2Fail(self):
        # Force a failure
        self.mock(dec2.ec2client.EC2Client, 'drvValidateCredentials',
            lambda *args: False)

        srv = self.newService()
        uri = self._baseCloudUrl + '/users/%(username)s/credentials?_method=PUT'

        client = self.newClient(srv, uri)
        resp = self.failUnlessRaises(ResponseError,
               client.request, 'POST', body = _xmlNewEC2Creds)

        self.failUnlessEqual(resp.status, 403)
        self.failUnlessEqual(resp.headers['Content-Type'], 'application/xml')
        self.assertXMLEquals(resp.contents, '<?xml version="1.0" encoding="UTF-8"?>\n<fault>\n  <code>403</code>\n  <message>The supplied credentials are invalid</message>\n</fault>')

    def testGetConfigurationDescriptor(self):
        srv = self.newService()
        uri = 'clouds/ec2/descriptor/configuration'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getDisplayName(), "EC2 Cloud Configuration")
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'Configure Amazon EC2'})
        dataFields = dsc.getDataFields()
        self.failUnlessEqual([ df.name for df in dataFields ],
            ['name', 'alias', 'description', 'region', 'accountId',
             'publicAccessKeyId', 'secretAccessKey', 'certificateData',
             'certificateKeyData', 's3Bucket'])
        self.failUnlessEqual([ df.type for df in dataFields[:3] ],
            ['str'] * len(dataFields[:3]))
        self.failUnlessEqual([ df.type for df in dataFields[4:] ],
            ['str'] * len(dataFields[4:]))
        self.assertEquals([ df.multiline for df in dataFields ],
                [None, None, None, None, None, None, None, True, True, None])
        self.failUnlessEqual(
            [ (x.key, x.descriptions.asDict()) for x in  dataFields[3].type ],
            [
                ('us-east-1', {None: 'US East 1 (Northern Virginia) Region'}),
                ('us-west-1', {None: 'US West 1 (Northern California)'}),
                ('us-west-2', {None: 'US West 2 (Oregon)'}),
                ('eu-west-1', {None: 'EU (Ireland)'}),
                ('sa-east-1', {None: 'South America (Sao Paulo)'}),
                ('ap-northeast-1', {None: 'Asia Pacific NorthEast (Tokyo)'}),
                ('ap-southeast-1', {None: 'Asia Pacific 1 (Singapore)'}),
                ('ap-southeast-2', {None: 'Asia Pacific 2 (Sydney)'}),
            ])
        self.failUnlessEqual([ df.multiple for df in dataFields ],
            [None] * len(dataFields))
        self.failUnlessEqual([ df.descriptions.asDict() for df in dataFields ],
            [{None : 'Name'}, {None : 'Alias'},
              {None : 'Description'},  {None: 'Region'},
              {None: 'AWS Account Number'},
              {None: 'Access Key ID'}, {None: 'Secret Access Key'},
              {None: 'X.509 Certificate'},
              {None: 'X.509 Private Key'},
              {None: 'S3 Bucket'}])
        pref = self.makeUri(client,
            "help/targets/drivers/%s/configuration/" % self.cloudType)
        helpData = [ {}, {}, {}, {} ] + [ { None : pref + x } for x in [
            'accountNumber.html', 'accessKey.html', 'secretAccessKey.html',
            'certificateData.html', 'certificateKeyData.html',
            's3Bucket.html'] ]
        self.failUnlessEqual([ df.helpAsDict for df in dataFields ],
            helpData)

    def testProxyAccess(self):
        srv = self.newService()
        uri = 'clouds/ec2/instances/aws/images'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = images.Handler()
        nodes = hndlr.parseString(response.read())
        self.failUnlessEqual([x.getImageId() for x in nodes],
            ['aaaaaabbbbbbbbbcccccccccccddddddddeeeeee', 'ami-0435d06d'])

        # Fetch the proxy file
        from catalogService.rest.drivers.ec2.ec2client import EC2Connection
        proxySettings = open(EC2Connection._proxyFile).read()
        self.failUnlessEqual(proxySettings, """\
proxy = host
proxy_port = 3129
proxy_user = user
proxy_pass = pass
""")

    def testGetCredentials(self):
        srv = self.newService()
        uri = 'clouds/ec2/instances/aws/users/%(username)s/credentials'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        data = response.read()
        self.failUnlessEqual(data, """\
<?xml version='1.0' encoding='UTF-8'?>
<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/ec2/instances/aws/users/JeanValjean/credentials">
  <accountId>8675309jv</accountId>
  <publicAccessKeyId>User public key</publicAccessKeyId>
  <secretAccessKey>User private key</secretAccessKey>
</descriptorData>
""" % client.hostport)

        # Wrong user name
        uri = 'clouds/ec2/instances/aws/users/NOSUCHUSER/credentials'
        client = self.newClient(srv, uri)
        e = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(e.status, 401)

        # bad cloud name (this should probably be moved to the instances test)
        uri = 'clouds/vmware/instances/badcloud.eng.rpath.com/users/NOSUCHUSER/credentials'
        client = self.newClient(srv, uri)
        e = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(e.status, 404)

    def testGetCredentials2(self):
        srv = self.newService()
        uri = 'clouds/ec2/instances/aws/users/%(username)s/credentials?_method=GET'

        client = self.newClient(srv, uri)
        response = client.request('POST')
        data = response.read()
        self.assertXMLEquals(data, """<?xml version='1.0' encoding='UTF-8'?>\n<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/ec2/instances/aws/users/JeanValjean/credentials">\n  <accountId>8675309jv</accountId>\n  <publicAccessKeyId>User public key</publicAccessKeyId>\n  <secretAccessKey>User private key</secretAccessKey>\n</descriptorData>\n""" % client.hostport)

        # Wrong user name
        uri = 'clouds/ec2/instances/aws/users/NOSUCHUSER/credentials'
        client = self.newClient(srv, uri)
        e = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(e.status, 401)


    def testGetUserCredentialsNoCredentials(self):
        self.restdb.targetMgr.setTargetCredentialsForUser(
            'ec2', 'aws', 'JeanValjean', dict())
        self.restdb.commit()

        srv = self.newService()
        uri = 'clouds/ec2/instances/aws/users/%(username)s/credentials'
        client = self.newClient(srv, uri)

        response = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(response.status, 404)
        self.assertXMLEquals(response.contents, """
<?xml version='1.0' encoding='UTF-8'?>
<fault>
  <code>404</code>
  <message>User credentials not configured</message>
</fault>""")

    def testFixPEM(self):
        expectedPem =  """\
-----BEGIN SOMETHING-----
VGhlIHF1aWNrIGJyb3duIGZveCBqdW1wZWQgb3ZlciB0aGUgbGF6eSBkb2csIHdheSBmYXN0ZXIg
dGhhbiB5b3UgZXhwZWN0ZWQK
-----END SOMETHING-----
"""
        pem = """
This is really of no relevance.
""" + expectedPem + """

And this is even less relevant
"""
        ret = dec2.ec2client.fixPEM(expectedPem)
        self.failUnlessEqual(ret, expectedPem)

        ret = dec2.ec2client.fixPEM(pem)
        self.failUnlessEqual(ret, expectedPem)

class MockedRequest(object):
    data = dict(
        DescribeImages = mockedData.xml_getAllImages1,
        DescribeInstances = mockedData.xml_getAllInstances1,
        DescribeKeyPairs = mockedData.xml_getAllKeyPairs1,
        DescribeRegions = mockedData.xml_getAllRegions1,
        DescribeAvailabilityZones = mockedData.xml_getAllZones1,
        DescribeSecurityGroups = mockedData.xml_getAllSecurityGroups1,
        RunInstances = mockedData.xml_runInstances1,
        TerminateInstances = mockedData.xml_awsTerminateInstances1,
        CreateSecurityGroup = mockedData.xml_createSecurityGroupSuccess,
        AuthorizeSecurityGroupIngress = mockedData.xml_authorizeSecurityGroupIngressSuccess,
        RevokeSecurityGroupIngress = mockedData.xml_revokeSecurityGroupIngressSuccess,
        CreateTags = mockedData.xml_ec2CreateTags,
    )

    def _get_response(self, action, params, path, verb, kwargs):
        if action not in self.data:
            raise Exception("Shouldn't have tried this method", action)
        data = self.data[action]
        if isinstance(data, tuple):
            status, data = data
        else:
            status = 200
        return status, data

    def mockedMakeRequest(self, action, params=None, path=None, verb='GET', **kwargs):
        # Dump the request
        util.mkdirChain(self.snapshotDir)
        pickle.dump(params, file(os.path.join(self.snapshotDir, action), "w"))

        dirName = os.path.join(self.snapshotDir, action)
        status, data = self._get_response(action, params, path, verb, kwargs)
        resp = mockedData.MockedResponse(data)
        resp.status = status
        resp.reason = "Foo"
        return resp

    def __init__(self, snapshotDir):
        # Directory where we will store the request objects
        self.snapshotDir = snapshotDir

class MockedS3Request(MockedRequest):
    data = dict(
        PUT = { None : 200 },
    )

    def _get_response(self, action, params, path, args, kwargs):
        if action not in self.data or path not in self.data[action]:
            raise Exception("Shouldn't have tried this method", action)
        data = self.data[action][path]
        if isinstance(data, tuple):
            status, data = data
        else:
            status = 200
        if status >= 300 and 'sender' in kwargs:
            # Pushing a file
            from boto.exception import S3ResponseError
            raise S3ResponseError(status, 'Foo', data)
        return status, data

class MockedHttpConnection(object):
    def set_debuglevel(self, level):
        pass

def mockedProxySsl(slf):
    fout = file(slf._proxyFile, "w")
    fout.write("%s = %s\n" % ("proxy", slf.proxy))
    fout.write("%s = %s\n" % ("proxy_port", slf.proxy_port))
    fout.write("%s = %s\n" % ("proxy_user", slf.proxy_user))
    fout.write("%s = %s\n" % ("proxy_pass", slf.proxy_pass))
    fout.close()
    return MockedHttpConnection()

def _normalizeCert(cert):
    return cert.replace('\n', '')

_xmlNewCloud = """
<descriptorData>
  <alias>newbie</alias>
  <description>Brand new cloud</description>
  <name>newbie.eng.rpath.com</name>
  <accountId>867530900000</accountId>
  <publicAccessKeyId>Public key    </publicAccessKeyId>
  <secretAccessKey>\tSecret key</secretAccessKey>
  <certificateData>%s</certificateData>
  <certificateKeyData>%s</certificateKeyData>
  <launchUsers>a,b,c</launchUsers>
  <launchGroups>d,e,f</launchGroups>
  <s3Bucket>S3 Bucket</s3Bucket>
</descriptorData>""" % (mockedData.tmp_userCert, mockedData.tmp_userKey)

_xmlNewEC2Creds = """
<descriptorData>
  <accountId>1122334455</accountId>
  <publicAccessKeyId>awsSecretAccessKey</publicAccessKeyId>
  <secretAccessKey>Supr sikrt</secretAccessKey>
</descriptorData>
"""

if __name__ == "__main__":
    testsuite.main()
