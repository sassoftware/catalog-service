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

import base64
import os
import pickle
import StringIO

from conary.lib import util

import testbase

from catalogService.restClient import ResponseError

from catalogService.rest import baseDriver
from catalogService.rest.drivers import eucalyptus as deuca
from catalogService.rest.models import clouds
from catalogService.rest.models import credentials
from catalogService.rest.models import descriptor
from catalogService.rest.models import images
from catalogService.rest.models import instances
from catalogService.rest.models import jobs as jobmodels
from catalogService.utils import x509

from catalogService_test import mockedData
from catalogService_test.mockedData import DUMMY_CERT, DUMMY_KEY


class HandlerTest(testbase.TestCase):
    cloudType = 'eucalyptus'
    cloudName = 'euca1.eng.rpath.com'

    TARGETS = [
        (cloudType, cloudName, dict(
            port = 8443,
            alias = 'euca1',
            description = 'Eucalyptus server',
            publicAccessKeyId = 'Public Key',
            secretAccessKey = 'Private Key',
            s3Bucket = 'Bukkit',
            certificateData = mockedData.DUMMY_CERT,
            certificateKeyData = mockedData.DUMMY_KEY,
            cloudX509Cert = mockedData.DUMMY_CERT,
        )),
    ]
    MINT_CFG = testbase.TestCase.MINT_CFG + [
        ('proxy', 'http http://user:pass@host:3129'),
        ('proxy', 'https https://user:pass@host:3129'),
    ]

    USER_TARGETS = [
        ('JeanValjean', cloudType, cloudName, dict(
                publicAccessKeyId = 'User public key',
                secretAccessKey = 'User private key',
            )),
    ]

    _baseCloudUrl = 'clouds/%s/instances/%s' % (cloudType, cloudName)

    class InstancesHandler(instances.Handler):
        instanceClass = deuca.driver.Instance


    def setUp(self):
        testbase.TestCase.setUp(self)

        self._mockRequest()

        # Mock the external IP determination
        def fakeOpenUrl(slf, url):
            return util.BoundedStringIO("""\
<clientInfo><remoteIp>1.2.3.4</remoteIp><hostName>rdu-wireless.rpath.com</hostName></clientInfo>""")
        self.mock(deuca.driver, '_openUrl', fakeOpenUrl)
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
                slf.get_http_connection(slf.host, slf.port, slf.is_secure)
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
                slf.get_http_connection(slf.host, slf.port, slf.is_secure)
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
        uri = 'clouds/%s/instances' % self.cloudType
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = clouds.Handler()
        response = util.BoundedStringIO(response.read())
        nodes = hndlr.parseFile(response)

        self.failUnlessEqual([x.getCloudName() for x in nodes],
            [self.cloudName])

        self.failUnlessEqual([x.getCloudAlias() for x in nodes],
            [ 'euca1' ])

        self.failUnlessEqual([x.getDescription() for x in nodes],
            ['Eucalyptus server'])

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
        uri = 'clouds/%s/instances' % self.cloudType
        client = self.newClient(srv, uri)

        response = client.request('GET')
        self.assertXMLEquals(response.read(), "<?xml version='1.0' encoding='UTF-8'?>\n<clouds/>")

        # Instance enumeration should fail with 404 (bad cloud name)
        uri = self._baseCloudUrl
        client = self.newClient(srv, uri)

        response = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(response.status, 404)

    def testGetImages1(self):
        srv = self.newService()
        uri = '%s/images?_method=GET' % (self._baseCloudUrl, )
        correctedUri = '%s/images' % (self._baseCloudUrl, )
        client = self.newClient(srv, uri)

        response = client.request('POST')
        self.failUnlessEqual(response.msg['Content-Type'], 'application/xml')
        self.failUnlessEqual(response.msg['Cache-Control'], 'no-store')
        hndlr = images.Handler()
        response = util.BoundedStringIO(response.read())
        node = hndlr.parseFile(response)
        self.failUnless(isinstance(node, images.BaseImages),
                        node)
        imageIds = [
            '0000000000000000000000000000000000000001',
            '361d7fa1d99431e16a3a438c8d4ebaa79aea075a',]
        self.failUnlessEqual([x.getImageId() for x in node], imageIds)
        # make sure the ?_method=GET portion of the URI didn't persist
        self.failUnlessEqual([x.getId() for x in node],
            [ self.makeUri(client, "%s/%s" % (correctedUri, x)) \
                    for x in imageIds ])

        # this data comes from the mockModule for mint. we're just testing
        # that it gets integrated
        self.assertEquals([x.getProductDescription() for x in node],
                ['product description for bar', 'words words SPARKY words'])
        self.assertEquals([x.getBuildDescription() for x in node],
                ['build description for bar 8', 'just words and stuff'])
        self.assertEquals([x.getIsPrivate_rBuilder() for x in node],
            [False, False])
        self.assertEquals([x.getProductName() for x in node],
            ['bar project', 'foo project'])
        self.assertEquals([x.getRole() for x in node],
            ['developer', 'developer'])
        self.assertEquals([x.getPublisher() for x in node],
            ['Bob Loblaw', 'Bob Loblaw'])
        self.assertEquals([x.getAwsAccountNumber() for x in node],
                [None, None])
        self.assertEquals([x.getBuildName() for x in node],
            ['bar project', 'foo project'])
        self.assertEquals([x.getIs_rBuilderImage() for x in node],
            [True, True])
        self.assertEquals([x.getBuildPageUrl() for x in node],
            ['http://test.rpath.local2/project/bar/build?id=8',
             'http://test.rpath.local2/project/foo/build?id=6'])
        self.assertEquals([ x.getProductCode() for x in node],
            [None, None])

    def testGetImage1(self):
        srv = self.newService()
        imageId = '0000000000000000000000000000000000000001'
        uri = '%s/images/%s' % (self._baseCloudUrl, imageId)
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
        self.failUnlessEqual([ x.getLongName() for x in node],
            ['8/some-file-8-1-x86 (emi-0435d06d)'])

        # Should be able to fetch the image with the target image id too
        targetImageId = 'emi-0435d06d'
        uri = '%s/images/%s' % (self._baseCloudUrl, targetImageId)
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
        self.failUnlessEqual([ x.getLongName() for x in node],
            ['8/some-file-8-1-x86 (emi-0435d06d)'])


    def testGetInstances1(self):
        # We need to mock the image data
        self._mockRequest(DescribeImages = _t(mockedData.xml_getAllImages3))

        srv = self.newService()
        uri = '%s/instances' % (self._baseCloudUrl, )
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
            [ self.cloudName ] * len(node))
        self.failUnlessEqual([x.getCloudType() for x in node],
            [ self.cloudType ] * len(node))
        self.failUnlessEqual([x.getCloudAlias() for x in node],
            [ 'euca1' ] * len(node))

        self.failUnlessEqual([x.getInstanceName() for x in node],
            [
                'reviewboard-1.0-x86_13964.img (emi-3675905f)',
                'reviewboard-1.0-x86_13965.img (emi-957590fc)'
            ])
        self.failUnlessEqual([x.getInstanceDescription() for x in node],
            [
                'reviewboard-1.0-x86_13964.img (emi-3675905f)',
                'reviewboard-1.0-x86_13965.img (emi-957590fc)'
            ])
        
        self.failUnlessEqual([x.getLaunchTime() for x in node],
            ['1207592569', '1207665151'])
        
        self.failUnlessEqual([x.getPlacement() for x in node],
            ['us-east-1c', 'imperial-russia'])

        self.assertEquals([ x.getProductCode() for x in node], [None, None])

        self.failUnlessEqual(
            [[ x.getId() for x in n.getSecurityGroup() ] for n in node ],
            [ [ 'BEA Demo' ], [ 'BEA Demo' ]])

    def testGetInstance1(self):
        srv = self.newService()
        uri = '%s/instances/AABBCC' % (self._baseCloudUrl, )
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
        uri = '%s/instances/AABBCC' % (self._baseCloudUrl, )
        client = self.newClient(srv, uri)

        response = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(response.status, 404)

    def testGetConfiguration(self):
        self.setAdmin(1)
        srv = self.newService()
        uri = '%s/configuration' % (self._baseCloudUrl, )

        client = self.newClient(srv, uri)
        response = client.request('GET')

        self.assertXMLEquals(response.read(), """\
<?xml version='1.0' encoding='UTF-8'?>
<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/%s/instances/%s/configuration">
  <alias>euca1</alias>
  <certificateData>%s</certificateData>
  <certificateKeyData>%s</certificateKeyData>
  <cloudX509Cert>%s</cloudX509Cert>
  <description>Eucalyptus server</description>
  <name>euca1.eng.rpath.com</name>
  <port>8443</port>
  <publicAccessKeyId>Public Key</publicAccessKeyId>
  <s3Bucket>Bukkit</s3Bucket>
  <secretAccessKey>Private Key</secretAccessKey>
</descriptorData>""" % (client.hostport, self.cloudType, self.cloudName,
    DUMMY_CERT, DUMMY_KEY, DUMMY_CERT))

    def testGetConfigurationStrangeTargetData(self):
        self.setAdmin(True)
        self.deleteTarget(self.cloudType, 'euca1.eng.rpath.com')
        dataDict = dict(
            port = '8443',
            certificateData = '-----BEGIN BLAH-----\n' +
                             'certHere\n' +
                             '-----END BLAH-----\n',
            certificateKeyData = '-----BEGIN BLAH-----\n' +
                             'certKeyHere\n' +
                             '-----END BLAH-----\n',
            alias = 'newbie',
            description = 'Some fake data here',
            publicAccessKeyId = 'public key ID',
            secretAccessKey = 'secret key data',
            cloudX509Cert = 'x509 cert',
            s3Bucket = 'bukkit',
            )
        self.setTargetData(self.cloudType, 'euca1.eng.rpath.com', dataDict)

        srv = self.newService()
        uri = '%s/configuration' % (self._baseCloudUrl, )

        client = self.newClient(srv, uri)
        response = client.request('GET')

        self.assertXMLEquals(response.read(), """\
<?xml version='1.0' encoding='UTF-8'?>
<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/%s/instances/%s/configuration">
  <alias>%s</alias>
  <certificateData>%s</certificateData>
  <certificateKeyData>%s</certificateKeyData>
  <cloudX509Cert>%s</cloudX509Cert>
  <description>%s</description>
  <name>%s</name>
  <port>%s</port>
  <publicAccessKeyId>%s</publicAccessKeyId>
  <s3Bucket>%s</s3Bucket>
  <secretAccessKey>%s</secretAccessKey>
</descriptorData>""" % (client.hostport, self.cloudType, self.cloudName,
            dataDict['alias'],
            dataDict['certificateData'], dataDict['certificateKeyData'],
            dataDict['cloudX509Cert'], dataDict['description'],
            self.cloudName, dataDict['port'],
            dataDict['publicAccessKeyId'],
            dataDict['s3Bucket'],
            dataDict['secretAccessKey'],
            ))

    def testGetConfigurationMissingTarget(self):
        self.deleteTarget(self.cloudType, self.cloudName)

        srv = self.newService()
        uri = '%s/configuration' % (self._baseCloudUrl, )

        client = self.newClient(srv, uri)
        e = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(e.status, 404)

    def testGetConfigurationPermissionDenied(self):
        srv = self.newService()
        uri = '%s/configuration' % (self._baseCloudUrl, )

        client = self.newClient(srv, uri)
        response = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(response.status, 403)
        self.assertXMLEquals(response.contents, '<?xml version="1.0" encoding="UTF-8"?>\n<fault>\n  <code>403</code>\n  <message>Permission Denied - user is not adminstrator</message>\n</fault>')

    def testSetCredentialsEC2Fail(self):
        # Force a failure
        self.mock(deuca.eucaclient.EucalyptusClient, 'drvValidateCredentials',
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
        uri = 'clouds/%s/descriptor/configuration' % self.cloudType

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getDisplayName(), "Eucalyptus Configuration")
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'Configure Eucalyptus'})
        dataFields = dsc.getDataFields()
        self.failUnlessEqual([ df.name for df in dataFields ],
            ['name', 'port', 'alias', 'description', 'publicAccessKeyId',
             'secretAccessKey', 'certificateData', 'certificateKeyData',
             'cloudX509Cert', 's3Bucket'])
        self.failUnlessEqual([ df.type for df in dataFields ],
            ['str', 'int'] + ['str'] * (len(dataFields) - 2))
        self.failUnlessEqual([ df.multiple for df in dataFields ],
            [None] * len(dataFields))
        self.failUnlessEqual([ df.descriptions.asDict() for df in dataFields ],
            [{None: 'Eucalyptus Server Address'},
              {None: 'Eucalyptus Server Port'},
              {None: 'Descriptive Name'},
              {None: 'Full Description'},
              {None: 'Access Key ID'},
              {None: 'Secret Access Key'},
              {None: 'X.509 Certificate'},
              {None: 'X.509 Private Key'},
              {None: 'Cloud X.509 Certificate'},
              {None: 'Storage (Walrus) Bucket'}  ])
        pref = self.makeUri(client,
            "help/targets/drivers/%s/configuration/" % self.cloudType)
        helpData = [ { None : pref + x } for x in [
            'serverName.html', 'serverPort.html', 'alias.html',
            'description.html', 'accessKey.html',
            'secretAccessKey.html', 'certificateData.html',
            'certificateKeyData.html', 'cloudX509Cert.html',
            's3Bucket.html', ] ]
        self.failUnlessEqual([ df.helpAsDict for df in dataFields ], helpData)

    def testProxyAccess(self):
        srv = self.newService()
        uri = '%s/images' % (self._baseCloudUrl, )
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = images.Handler()
        nodes = hndlr.parseString(response.read())
        self.failUnlessEqual([x.getImageId() for x in nodes],
            ['0000000000000000000000000000000000000001',
            '361d7fa1d99431e16a3a438c8d4ebaa79aea075a',])

        # Fetch the proxy file
        from catalogService.rest.drivers.ec2.ec2client import EC2Connection
        # No need to talk to the proxy, so the proxy file should not exist
        self.failIf(os.path.exists(EC2Connection._proxyFile))

    def testGetCredentials(self):
        srv = self.newService()
        uri = self._baseCloudUrl + '/users/%(username)s/credentials'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = credentials.Handler()
        data = response.read()
        self.failUnlessEqual(data, """\
<?xml version='1.0' encoding='UTF-8'?>
<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/%s/instances/%s/users/JeanValjean/credentials">
  <publicAccessKeyId>User public key</publicAccessKeyId>
  <secretAccessKey>User private key</secretAccessKey>
</descriptorData>
""" %
        (client.hostport, self.cloudType, self.cloudName))

        # Wrong user name
        uri = self._baseCloudUrl + '/users/NOSUCHUSER/credentials'
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
        uri = self._baseCloudUrl + '/users/%(username)s/credentials?_method=GET'

        client = self.newClient(srv, uri)
        response = client.request('POST')
        hndlr = credentials.Handler()
        data = response.read()
        self.assertXMLEquals(data, """<?xml version='1.0' encoding='UTF-8'?>\n<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/%s/instances/%s/users/JeanValjean/credentials">\n  <publicAccessKeyId>User public key</publicAccessKeyId>\n  <secretAccessKey>User private key</secretAccessKey>\n</descriptorData>\n""" %
            (client.hostport, self.cloudType, self.cloudName))

        # Wrong user name
        uri = self._baseCloudUrl + '/users/NOSUCHUSER/credentials'
        client = self.newClient(srv, uri)
        e = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(e.status, 401)


    def testGetUserCredentialsNoCredentials(self):
        self.restdb.targetMgr.setTargetCredentialsForUser(
            self.cloudType, self.cloudName, 'JeanValjean', dict())
        self.restdb.commit()

        srv = self.newService()
        uri = self._baseCloudUrl + '/users/%(username)s/credentials'
        client = self.newClient(srv, uri)

        response = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(response.status, 404)
        self.assertXMLEquals(response.contents, """
<?xml version='1.0' encoding='UTF-8'?>
<fault>
  <code>404</code>
  <message>User credentials not configured</message>
</fault>""")

    def testGetLaunchDescriptor(self):
        srv = self.newService()
        uri = self._baseCloudUrl + '/descriptor/launch'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getDisplayName(), 'Eucalyptus Launch Parameters')
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'Eucalyptus Launch Parameters'})
        self.failUnlessEqual([ df.name for df in dsc.getDataFields() ],
            ['imageId', 'instanceName', 'instanceDescription',
             'instanceType', 'availabilityZone',
             'minCount', 'maxCount', 'keyName',
             'securityGroups', 'remoteIp', 'userData', 'tags'])
        ftypes = [ df.type for df in dsc.getDataFields() ]
        self.failUnlessEqual([ ftypes[0], ftypes[1], ftypes[2],
                ftypes[5], ftypes[6], ftypes[9],
                               ftypes[10] ],
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
                    ('SAS Demo', {None: 'Permissions for SAS demo'}),
                    ('build-cluster', {None: 'private group for rMake build cluster in ec2'})
                ]
            ])
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
            [None, None, None, 'm3.medium', None, 1, 1, None,
                ['SAS Demo'], None, None, None])

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
                {None: 'Additional tags'},])
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

    def testNewInstances(self):
        # We need to mock the image data
        self._mockRequest(DescribeImages = _t(mockedData.xml_getAllImages2),
                CreateTags=mockedData.xml_ec2CreateTags)

        srv = self.newService()
        uri = self._baseCloudUrl + '/instances'

        client = self.newClient(srv, uri)
        response = client.request('POST', _t(mockedData.xml_newInstanceEuca1))

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        imageUrlPath = self._baseCloudUrl + '/images/emi-afa642c6'

        node = jobmodels.Job()
        node.parseStream(response)
        self.failUnlessEqual(node.get_id(), self.makeUri(client, jobUrlPath))
        self.failUnlessEqual(node.get_imageId(), self.makeUri(client, imageUrlPath))

        node = self.waitForJob(srv, jobUrlPath, "Completed")
        #self.failUnlessEqual(node.getImageId(), self.makeUri(client, imageUrlPath))

        instanceIds = ['i-e2df098b', 'i-e5df098c']

        results = node.get_resultResource()
        _p =  self._baseCloudUrl + '/instances/'
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
""" % (certHash, base64.b64encode(certContents), bootUuid, zoneAddresses, conaryProxies)

        self.failUnlessEqual(params['UserData'], base64.b64encode(userData))
        self.failUnlessEqual(params['Placement.AvailabilityZone'], 'us-east-1c')

    def testNewInstancesWithDeployment(self):
        # We need to mock the image data
        self._mockRequest(DescribeImages = _t(mockedData.xml_getAllImages2),
                CreateTags=mockedData.xml_ec2CreateTags)

        uri = self._baseCloudUrl + '/instances'

        imageId = '361d7fa1d99431e16a3a438c8d4ebaa79aea075a'

        srv, client, job, response = self._setUpNewInstanceTest(
            self.cloudName, '', imageId = imageId)

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        imageUrlPath = '%s/images/%s' % (self._baseCloudUrl, imageId)

        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))
        self.failUnlessEqual(job.get_imageId(), self.makeUri(client, imageUrlPath))
        job = self.waitForJob(srv, jobUrlPath, "Completed")
        expInstanceIds = ['i-e2df098b', 'i-e5df098c']
        self.failUnlessEqual(
            [ os.path.basename(x.get_href()) for x in job.resultResource],
            expInstanceIds)
        imageId = 'emi-00112233'
        uri = '%s/images/%s' % (self._baseCloudUrl, imageId)

        # Make sure the proper architecture was passed in
        self.failUnlessEqual(
            file(os.path.join(self.workDir, "invocation")).read(),
            """\
Extra args: ('some-file-6-1-x86_6', 'i386')
Extra kwargs:
    kernelImage: None
    targetConfiguration:
        alias: euca1
        certificateData: -----BEGIN CERTIFICATE-----
-----END CERTIFICATE-----

        certificateKeyData: -----BEGIN PRIVATE KEY-----
-----END PRIVATE KEY-----

        cloudAlias: euca1
        cloudX509Cert: -----BEGIN CERTIFICATE-----
-----END CERTIFICATE-----

        description: Eucalyptus server
        fullDescription: Eucalyptus server
        name: euca1.eng.rpath.com
        port: 8443
        publicAccessKeyId: Public Key
        s3Bucket: Bukkit
        secretAccessKey: Private Key
""")

        # Make sure we can address that image with this new id
        client = self.newClient(srv, uri)
        response = client.request('GET')
        self.failUnlessEqual(response.status, 200)

    def _setUpNewInstanceTest(self, cloudName, imageName, imageId=None,
            requestXml=None):
        if not imageId:
            imageId = '361d7fa1-d994-31e1-6a3a-438c8d4ebaa7'
        cloudType = self.cloudType

        def fakeDaemonize(slf, *args, **kwargs):
            slf.postFork()
            return slf.function(*args, **kwargs)
        self.mock(baseDriver.CatalogJobRunner, 'backgroundRun', fakeDaemonize)

        def fakeOpenUrl(slf, url, headers):
            return StringIO.StringIO(url)
        self.mock(deuca.driver, "openUrl", fakeOpenUrl)

        baseFileName = 'some-file-6-1-x86'
        def fakeExtractImage(slf, path):
            workdir = path[:-4]
            workdir = os.path.join(workdir, baseFileName)
            sdir = os.path.join(workdir, baseFileName)
            util.mkdirChain(sdir)
            fileName = os.path.join(sdir, '%s-root.ext3' % baseFileName)
            file(fileName, "w")
            return workdir

        def fakeBundleImage(slf, inputFSImage, bundlePath, *args, **kwargs):
            bfn = os.path.basename(inputFSImage)
            bfn = bfn.replace('-root.ext3', '')
            file("%s/%s.manifest.xml" % (bundlePath, bfn), "w")
            inv = file(os.path.join(self.workDir, "invocation"), "w")
            inv.write("Extra args: %s\n" % (args, ))
            def _write(indent, outf, key, value):
                indentStr = "    " * indent
                if isinstance(value, dict):
                    outf.write("%s%s:\n" % (indentStr, key))
                    for k, v in sorted(value.items()):
                        _write(indent+1, outf, k, v)
                else:
                    outf.write("%s%s: %s\n" % (indentStr, key, value))
            _write(0, inv, "Extra kwargs", kwargs)
            inv.close()
        self.mock(deuca.driver, "_bundleImage", fakeBundleImage)

        oldGetCredentialsIsoFile = deuca.driver.getCredentialsIsoFile
        def fakeGetCredentialsIsoFile(slf):
            ret = oldGetCredentialsIsoFile(slf)
            # Rename ISO file to something predictible
            dest = os.path.join(os.path.dirname(ret), 'credentials.iso')
            os.rename(ret, dest)
            return dest

        self.mock(deuca.driver, "extractImage", fakeExtractImage)
        self.mock(deuca.driver, "getCredentialsIsoFile", fakeGetCredentialsIsoFile)
        srv = self.newService()
        uri = 'clouds/%s/instances/%s/instances' % (cloudType, cloudName)

        if requestXml is None:
            requestXml = _t(mockedData.xml_newInstanceEuca1).replace(
                "<imageId>emi-afa642c6</imageId>",
                "<imageId>%s</imageId>" % imageId)
        client = self.newClient(srv, uri)
        response = client.request('POST', requestXml)

        job = self.getJobFromResponse(response)
        return srv, client, job, response

def _t(data):
    return data.replace(
        'ami-', 'emi-').replace(
        'aki-', 'eki-').replace(
        'ari-', 'eri-')

class MockedRequest(object):
    data = dict(
        DescribeImages = _t(mockedData.xml_getAllImages1),
        DescribeInstances = _t(mockedData.xml_getAllInstances1),
        DescribeKeyPairs = _t(mockedData.xml_getAllKeyPairs1),
        DescribeRegions = _t(mockedData.xml_getAllRegions1),
        DescribeAvailabilityZones = _t(mockedData.xml_getAllZones1),
        DescribeSecurityGroups = _t(mockedData.xml_getAllSecurityGroups1),
        RunInstances = _t(mockedData.xml_runInstances1),
        TerminateInstances = _t(mockedData.xml_awsTerminateInstances1),
        CreateSecurityGroup = _t(mockedData.xml_createSecurityGroupSuccess),
        AuthorizeSecurityGroupIngress = _t(mockedData.xml_authorizeSecurityGroupIngressSuccess),
        RevokeSecurityGroupIngress = _t(mockedData.xml_revokeSecurityGroupIngressSuccess),
        RegisterImage = _t(mockedData.xml_registerImage1)
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
        PUT = {
                None : 200,
                'some-file-6-1-x86.manifest.xml' : 200 
        },
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


_xmlNewCloud = """
<descriptorData>
  <cloudAlias>newbie</cloudAlias>
  <fullDescription>Brand new cloud</fullDescription>
  <name>newbie.eng.rpath.com</name>
  <accountId>867-5309</accountId>
  <publicAccessKeyId>Public key    </publicAccessKeyId>
  <secretAccessKey>\tSecret key</secretAccessKey>
  <certificateData>%s</certificateData>
  <certificateKeyData>%s</certificateKeyData>
  <launchUsers>a,b,c</launchUsers>
  <launchGroups>d,e,f</launchGroups>
  <s3Bucket>S3 Bucket</s3Bucket>
</descriptorData>""" % (DUMMY_CERT, DUMMY_KEY)

_xmlNewEC2Creds = """
<descriptorData>
  <accountId>1122334455</accountId>
  <publicAccessKeyId>awsSecretAccessKey</publicAccessKeyId>
  <secretAccessKey>Supr sikrt</secretAccessKey>
</descriptorData>
"""

if __name__ == "__main__":
    testsuite.main()
