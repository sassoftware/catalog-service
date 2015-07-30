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

import copy
import gzip
import httplib
import json
import io
import os
import StringIO

import requests
from requests import adapters as Radapters, models as Rmodels, Session as RSession
from conary.lib import util

from novaclient import client as nvclient

import testbase

from catalogService.restClient import ResponseError

from catalogService.rest import baseDriver
from catalogService.rest.drivers import openstack as dopenstack
from catalogService.rest.models import clouds
from catalogService.rest.models import descriptor
from catalogService.rest.models import images
from catalogService.rest.models import instances
from catalogService.rest.models import jobs as jobmodels

from catalogService_test import mockedData

from testutils import mock

class HandlerTest(testbase.TestCase):
    cloudType = 'openstack'
    cloudName = 'openstack1.eng.rpath.com'

    TARGETS = [
        (cloudType, cloudName, dict(
            nova_port = 5001,
            alias = 'openstack1',
            description = 'OpenStack server',
            project_name = 'MyProject123',
        )),
    ]
    MINT_CFG = testbase.TestCase.MINT_CFG + [
        ('proxy', 'http http://user:pass@host:3129'),
        ('proxy', 'https https://user:pass@host:3129'),
    ]

    USER_TARGETS = [
        ('JeanValjean', cloudType, cloudName, dict(
                username = 'Jean_Valjean',
                password = 'supersikrit',
            )),
    ]

    _baseCloudUrl = 'clouds/%s/instances/%s' % (cloudType, cloudName)

    class InstancesHandler(instances.Handler):
        instanceClass = dopenstack.driver.Instance


    def setUp(self):
        testbase.TestCase.setUp(self)

        self._mockRequest()

        # Mock the external IP determination
        def fakeOpenUrl(slf, url):
            return util.BoundedStringIO("""\
<clientInfo><remoteIp>1.2.3.4</remoteIp><hostName>rdu-wireless.rpath.com</hostName></clientInfo>""")
        self.mock(dopenstack.driver, '_openUrl', fakeOpenUrl)
        baseDriver.CatalogJobRunner.preFork = lambda *args: None

        self.mock(dopenstack.driver,
            'LAUNCH_NETWORK_TIMEOUT', 10)
        self.mock(dopenstack.driver,
            'LAUNCH_TIMEOUT', 10)
        self.mock(dopenstack.driver,
            'WAIT_RUNNING_STATE_SLEEP', .1)
        self.mock(dopenstack.driver,
            'WAIT_NETWORK_SLEEP', .1)

    def _mockRequest(self, **kwargs):
        self.mock(dopenstack.openstackclient, 'KeystoneSession', KeystoneSession)
        KeystoneSession.reset()
        KeystoneSession.setData(MockedClientData())
        self.mock(requests, 'Session', lambda: KeystoneSession._Sess.Session)

    def testSecureToInsecureFallback(self):
        def callbackSecurePasses(self, **kwargs):
            secure = kwargs.pop('secure')
            if secure:
                return 'secure passed'
            else:
                raise Exception("shouldn't get here")
        def callbackInsecurePasses(self, **kwargs):
            secure = kwargs.pop('secure')

            if secure:
                raise Exception("secure doesn't work")
            else:
                return 'insecure passed'
        def callbackBothFail(self, **kwargs):
            secure = kwargs.pop('secure')
            raise Exception("%s doesn't work" % ('secure' if secure else 'insecure'))

        # Mock the client init to allow testing of the fallback method
        self.mock(dopenstack.openstackclient.OpenStackClient, '__init__', lambda self: None)
        client = dopenstack.openstackclient.OpenStackClient()

        self.assertEquals('secure passed',
                client._secureToInsecureFallback(callbackSecurePasses))
        self.assertEquals('insecure passed',
                client._secureToInsecureFallback(callbackInsecurePasses))
        # when both secure and insecure fail, the secure exception should be raised
        ex = self.failUnlessRaises(Exception, client._secureToInsecureFallback,
                callbackBothFail)
        self.assertEquals("secure doesn't work", str(ex))

    def testUtctime(self):
        from catalogService.rest import baseDriver
        func = baseDriver.BaseDriver.utctime
        tests = [
            ('2011-03-04T17:18:19.000Z', 1299259099),
            ('2011-03-04T17:18:19.12345Z', 1299259099),
            ('2011-03-04T17:18:19Z', 1299259099),
        ]
        for src, expected in tests:
            self.failUnlessEqual(func(src), expected)

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
            [ 'openstack1' ])

        self.failUnlessEqual([x.getDescription() for x in nodes],
            ['OpenStack server'])

    def testRemoveCloud(self):
        srv = self.newService()
        uri = self._baseCloudUrl
        client = self.newClient(srv, uri)

        response = client.request('DELETE')

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
                '04afdb08-90a2-48a1-a6ba-de54940679ad',
                '215854b1-e1fb-4de4-8557-701254768315',
                '2f0bb8a4-8da1-44d2-b2f8-c0bad9e79e0f',
                '34229a3f-f7cd-4a29-ac9e-0321186e7557',
                '710c1a84-7867-4b04-bdbd-dc585e29c48e',
                '9401325c-4dac-436f-936b-4af7a49431fd',
                'a00000000000000000000000000000000000000a',
        ]
        self.failUnlessEqual([x.getImageId() for x in node], imageIds)
        # make sure the ?_method=GET portion of the URI didn't persist
        self.failUnlessEqual([x.getId() for x in node],
            [ self.makeUri(client, "%s/%s" % (correctedUri, x)) \
                    for x in imageIds ])

        # this data comes from the mockModule for mint. we're just testing
        # that it gets integrated
        self.assertEquals([x.getProductDescription() for x in node],
            ['product description for bar', None, None, None, None, None, None,
                'words words SPARKY words'])
        self.assertEquals([x.getBuildDescription() for x in node],
            ['build description for bar 98', None, None, None, None, None, None,
                'just words and stuff'])
        self.assertEquals([x.getIsDeployed() for x in node],
            [True, True, True, True, True, True, True, False])
        self.assertEquals([x.getIsPrivate_rBuilder() for x in node],
            [False, None, None, None, None, None, None, False])
        self.assertEquals([x.getProductName() for x in node],
            ['bar project', None, 'ubuntu-14.04.1-lts', 'Cirros',  'w2k12r2vhd',
                'RHEL 7.0 Cloud Image', 'w2k12 r2', 'foo project'])
        self.assertEquals([x.getRole() for x in node],
            ['developer', None, None, None, None, None, None, 'developer'])
        self.assertEquals([x.getPublisher() for x in node],
            ['Bob Loblaw', None, None, None, None, None, None, 'Bob Loblaw'])
        self.assertEquals([x.getAwsAccountNumber() for x in node],
            [None, None, None, None, None, None, None, None])
        self.assertEquals([x.getBuildName() for x in node],
            ['bar project', None, None, None, None, None, None, 'foo project'])
        self.assertEquals([x.getIs_rBuilderImage() for x in node],
            [True, False, False, False, False, False, False, True])
        self.assertEquals([x.getBuildPageUrl() for x in node],
            [
             'http://test.rpath.local2/project/bar/build?id=98',
             None, None, None, None, None, None,
             'http://test.rpath.local2/project/foo/build?id=96'])
        self.assertEquals([ x.getProductCode() for x in node],
            [None, None, None, None, None, None, None, None])

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
            ['98/some-file-98-1-x86'])

        # Should be able to fetch the image with the target image id too
        targetImageId = '9b16fb4a-8e3c-4b85-abe4-60b4c6d0975f'
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
            ['98/some-file-98-1-x86'])


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
        expId = ['22b896bf-af13-420b-a7db-2fadff3b3279',
                '37208896-004b-4291-bab7-5cd89fcf71b9']
        self.failUnlessEqual([x.getInstanceId() for x in node],
            expId)
        self.failUnlessEqual([x.getId() for x in node],
            [ self.makeUri(client, "%s/%s" % (uri, x)) for x in expId ])
        self.failUnlessEqual([x.getCloudName() for x in node],
            [ self.cloudName ] * len(node))
        self.failUnlessEqual([x.getCloudType() for x in node],
            [ self.cloudType ] * len(node))
        self.failUnlessEqual([x.getCloudAlias() for x in node],
            [ 'openstack1' ] * len(node))

        self.failUnlessEqual([x.getInstanceName() for x in node],
            [
                'vincent1', 'jules1',
            ])
        self.failUnlessEqual([x.getInstanceDescription() for x in node],
            [
                'vincent1', 'jules1',
            ])
        
        self.failUnlessEqual([x.getLaunchTime() for x in node],
            ['2014-09-30T13:49:19Z', '2014-09-30T13:31:58Z'])
        
        self.failUnlessEqual([x.getPlacement() for x in node],
            [None, None, ])

        self.assertEquals([ x.getProductCode() for x in node], [None, None])

    def testGetInstance1(self):
        srv = self.newService()
        instanceId = '22b896bf-af13-420b-a7db-2fadff3b3279'
        uri = '%s/instances/%s' % (self._baseCloudUrl, instanceId)
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = self.InstancesHandler()
        node = hndlr.parseString(response.read())

        # Normally we should only get one instance, but the call is mocked
        self.failUnlessEqual(node.getInstanceId(), instanceId)
        self.failUnlessEqual(node.getInstanceName(), 'vincent1')
        self.failUnlessEqual(node.getPublicDnsName(), '10.124.16.51')
        self.failUnlessEqual(node.getPrivateDnsName(), '10.210.1.12')

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
  <alias>openstack1</alias>
  <description>OpenStack server</description>
  <name>openstack1.eng.rpath.com</name>
  <nova_port>5001</nova_port>
  <project_name>MyProject123</project_name>
</descriptorData>""" % (client.hostport, self.cloudType, self.cloudName))

    def testGetConfigurationStrangeTargetData(self):
        self.setAdmin(True)
        self.deleteTarget(self.cloudType, 'openstack1.eng.rpath.com')
        dataDict = dict(
            nova_port = '5001',
            alias = 'newbie',
            description = 'Some fake data here',
            project_name = 'My Project',
            )
        self.setTargetData(self.cloudType, 'openstack1.eng.rpath.com', dataDict)

        srv = self.newService()
        uri = '%s/configuration' % (self._baseCloudUrl, )

        client = self.newClient(srv, uri)
        response = client.request('GET')

        self.assertXMLEquals(response.read(), """\
<?xml version='1.0' encoding='UTF-8'?>
<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/%s/instances/%s/configuration">
  <alias>%s</alias>
  <description>%s</description>
  <name>%s</name>
  <nova_port>%s</nova_port>
  <project_name>%s</project_name>
</descriptorData>""" % (client.hostport, self.cloudType, self.cloudName,
            dataDict['alias'],
            dataDict['description'],
            self.cloudName, dataDict['nova_port'],
            dataDict['project_name'],
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

    def testSetCredentialsFail(self):
        # Force a failure
        self.mock(dopenstack.openstackclient.OpenStackClient, 'drvValidateCredentials',
            lambda *args: False)

        srv = self.newService()
        uri = self._baseCloudUrl + '/users/%(username)s/credentials?_method=PUT'

        client = self.newClient(srv, uri)
        resp = self.failUnlessRaises(ResponseError,
               client.request, 'POST', body = _xmlNewCredsBad)

        self.failUnlessEqual(resp.status, 403)
        self.failUnlessEqual(resp.headers['Content-Type'], 'application/xml')
        self.assertXMLEquals(resp.contents, '<?xml version="1.0" encoding="UTF-8"?>\n<fault>\n  <code>403</code>\n  <message>The supplied credentials are invalid</message>\n</fault>')

    def testGetConfigurationDescriptor(self):
        srv = self.newService()
        uri = 'clouds/%s/descriptor/configuration' % self.cloudType

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getDisplayName(), "OpenStack Configuration")
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'Configure OpenStack'})
        dataFields = dsc.getDataFields()
        self.failUnlessEqual([ df.name for df in dataFields ],
            ['name', 'nova_port', 'alias', 'description', 'project_name',])
        self.failUnlessEqual([ df.type for df in dataFields ],
            [ 'str', 'int', 'str', 'str', 'str' ])
        self.failUnlessEqual([ df.multiple for df in dataFields ],
            [None] * len(dataFields))
        self.failUnlessEqual([ df.descriptions.asDict() for df in dataFields ],

            [{None: u'Nova Server'}, {None: u'Nova Port'},
                {None: u'Name'}, {None: u'Full Description'},
                {None: 'Project Name'},])
        pref = self.makeUri(client,
            "help/targets/drivers/%s/configuration/" % self.cloudType)
        helpData = [ { None : pref + x } for x in [
            'novaServerName.html', 'novaPortNumber.html',
            'alias.html', 'description.html', 'project_name.html', ] ]
        self.failUnlessEqual([ df.helpAsDict for df in dataFields ],
            helpData)

    def testProxyAccess(self):
        srv = self.newService()
        uri = '%s/images' % (self._baseCloudUrl, )
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = images.Handler()
        nodes = hndlr.parseString(response.read())
        self.failUnlessEqual([x.getImageId() for x in nodes],
                ['0000000000000000000000000000000000000001',
                    '04afdb08-90a2-48a1-a6ba-de54940679ad',
                    '215854b1-e1fb-4de4-8557-701254768315',
                    '2f0bb8a4-8da1-44d2-b2f8-c0bad9e79e0f',
                    '34229a3f-f7cd-4a29-ac9e-0321186e7557',
                    '710c1a84-7867-4b04-bdbd-dc585e29c48e',
                    '9401325c-4dac-436f-936b-4af7a49431fd',
                    'a00000000000000000000000000000000000000a',
                    ])

        raise testsuite.SkipTestException("nova has no proxy support")

        # Fetch the proxy file
        from catalogService.rest.drivers.ec2.ec2client import EC2Connection
        # No need to talk to the proxy, so the proxy file should not exist
        self.failIf(os.path.exists(EC2Connection._proxyFile))

    def testGetCredentials(self):
        srv = self.newService()
        uri = self._baseCloudUrl + '/users/%(username)s/credentials'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        data = response.read()
        self.failUnlessEqual(data, """\
<?xml version='1.0' encoding='UTF-8'?>
<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/%s/instances/%s/users/JeanValjean/credentials">
  <username>Jean_Valjean</username>
  <password>supersikrit</password>
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
        data = response.read()
        self.failUnlessEqual(data, """<?xml version='1.0' encoding='UTF-8'?>
<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/%s/instances/%s/users/JeanValjean/credentials">
  <username>Jean_Valjean</username>
  <password>supersikrit</password>
</descriptorData>
""" % (client.hostport, self.cloudType, self.cloudName))

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
        self.failUnlessEqual(dsc.getDisplayName(), 'OpenStack Launch Parameters')
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'OpenStack Launch Parameters'})
        self.failUnlessEqual([ df.name for df in dsc.getDataFields() ],
            ['imageId', 'instanceName', 'instanceDescription',
             'availabilityZone', 'flavor', 'network', 'keyName', 'floatingIp', ])
        ftypes = [ df.type for df in dsc.getDataFields() ]
        self.failUnlessEqual([ ftypes[0], ftypes[1], ftypes[2]],
            ['str', 'str', 'str', ])
        self.failUnlessEqual([ [ (x.key, x.descriptions.asDict()) for x in ftype ]
            for ftype in ftypes[3:8] ],
            [
                [
                    ('sashq-d122', {None: 'sashq-d122'}),
                ],
                [
                    (u'1', {None: u'm1.tiny (VCPUs: 1, RAM: 512 MB)'}),
                    (u'2', {None: u'm1.small (VCPUs: 1, RAM: 2048 MB)'}),
                    (u'3', {None: u'm1.medium (VCPUs: 2, RAM: 4096 MB)'}),
                    (u'4', {None: u'm1.large (VCPUs: 4, RAM: 8192 MB)'}),
                    (u'5', {None: u'm1.xlarge (VCPUs: 8, RAM: 16384 MB)'})
                ],
                [
                    (u'95ecd186-2a20-4d19-8ecc-41061c1f6898', {None: u'bosh'}),
                    (u'ad73348d-ccd4-44d7-8a23-7a5daf97d35b', {None: u'boshdev'}),
                    (u'c082c5ef-1654-42b6-ac4e-6291a1089816', {None: u'dostei'}),
                    (u'8b0068fe-596a-429e-8357-2c4ed51cfc14', {None: u'FloatingNet'}),
                ],
                [
                    ('jean_valjean', {None: 'jean_valjean'}),
                    ('insp_javert', {None: 'insp_javert'}),
                    ],
                [
                    ('new floating ip-SAS Network (VLAN0000)',
                        {None: '[New floating IP in SAS Network (VLAN0000)]'}),
                    ('new floating ip-SAS Network (VLAN0001)',
                        {None: '[New floating IP in SAS Network (VLAN0001)]'}),
                    ('4130b5d0-0df4-4df5-9ba1-000000000010',
                        {None: '10.10.10.100 in pool SAS Network (VLAN0001)'}),
                    ('4130b5d0-0df4-4df5-9ba1-000000000000',
                        {None: '10.20.10.100 in pool SAS Network (VLAN0000)'}),
                ],
            ])
        expMultiple = [None, None, None, None, None, None, None, None, ]
        self.failUnlessEqual([ df.multiple for df in dsc.getDataFields() ],
            expMultiple)
        self.failUnlessEqual([ df.required for df in dsc.getDataFields() ],
            [ True, True, None, True, True, True, None, True,] )
        self.failUnlessEqual([ df.hidden for df in dsc.getDataFields() ],
            [ True, None, None, None, None, None, None, None, ] )
        prefix = self.makeUri(client, "help/targets/drivers/%s/launch/" % self.cloudType)
        self.failUnlessEqual([ df.helpAsDict for df in dsc.getDataFields() ],
            [
                {},
                {None: prefix + 'instanceName.html'},
                {None: prefix + 'instanceDescription.html'},
                {None: prefix + 'availabilityZones.html'},
                {None: prefix + 'flavor.html'},
                {None: prefix + 'network.html'},
                {None: prefix + 'keyPair.html'},
                {None: prefix + 'floatingIp.html'},
            ])
        self.failUnlessEqual([ df.getDefault() for df in dsc.getDataFields() ],
            [None, None, None, 'sashq-d122', '1', '95ecd186-2a20-4d19-8ecc-41061c1f6898', None, 'new floating ip-SAS Network (VLAN0000)'])

        self.failUnlessEqual([ df.descriptions.asDict() for df in dsc.getDataFields() ],
            [
                {None: 'Image ID'},
                {None: 'Instance Name'},
                {None: 'Instance Description'},
                {None: 'Availability Zone', 'fr_FR': u'Zone de disponibilit\xe9'},
                {None: 'Flavor'},
                {None: 'Network'},
                {None: 'SSH Key Pair', 'fr_FR': 'Paire de clefs'},
                {None: 'Floating IP'},
            ])
        self.failUnlessEqual([ df.constraintsPresentation for df in dsc.getDataFields() ],
            [
                [{'max': 32, 'constraintName': 'range', 'min': 1}],
                [{'constraintName': 'length', 'value': 32}],
                [{'constraintName': 'length', 'value': 128}],
                [],
                [],
                [],
                [],
                [],
            ])

    def testGetLaunchDescriptorNoKeys(self):
        noKeys = lambda args: None
        self.mock(dopenstack.openstackclient.OpenStackClient, '_cliGetKeyPairs', noKeys)
        srv = self.newService()
        uri = self._baseCloudUrl + '/descriptor/launch'

        client = self.newClient(srv, uri)
        response = self.failUnlessRaises(ResponseError, client.request, 'GET')

    def testGetLaunchDescriptorEmptyKeys(self):
        emptyKeys = lambda args: []
        self.mock(dopenstack.openstackclient.OpenStackClient, '_cliGetKeyPairs', emptyKeys)
        srv = self.newService()
        uri = self._baseCloudUrl + '/descriptor/launch'

        client = self.newClient(srv, uri)
        response = self.failUnlessRaises(ResponseError, client.request, 'GET')

    def testNewInstances(self):
        srv = self.newService()
        uri = self._baseCloudUrl + '/instances'

        imageId = '0000000000000000000000000000000000000001'
        requestXml = _t(mockedData.xml_newInstanceOpenStackTempl % dict(
            imageId=imageId, flavor=1, instanceName="newinst34",
            instanceDescription="newinst34 description",
            keyName='jean_valjean',))

        client = self.newClient(srv, uri)
        response = client.request('POST', requestXml)

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        imageUrlPath = "%s/images/%s" % (self._baseCloudUrl, imageId)

        node = jobmodels.Job()
        node.parseStream(response)
        self.failUnlessEqual(node.get_id(), self.makeUri(client, jobUrlPath))
        self.failUnlessEqual(node.get_imageId(), self.makeUri(client, imageUrlPath))

        node = self.waitForJob(srv, jobUrlPath, "Completed")

        instanceIds = ['37208896-004b-4291-bab7-5cd89fcf71b9', ]

        results = node.get_resultResource()
        _p =  self._baseCloudUrl + '/instances/'
        self.failUnlessEqual([ x.get_href() for x in results ],
            [ self.makeUri(client, _p + x) for x in instanceIds ])

        jobId = os.path.basename(node.id)
        cu = self.restdb.db.cursor()
        cu.execute("SELECT job_uuid FROM jobs WHERE job_id = ?", jobId)
        bootUuid, = cu.fetchone()

    def testNewInstancesWithDeployment(self):
        uri = self._baseCloudUrl + '/instances'

        imageId = 'a00000000000000000000000000000000000000a'

        srv, client, job, response = self._setUpNewInstanceTest(
            self.cloudName, '', imageId = imageId)

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        imageUrlPath = '%s/images/%s' % (self._baseCloudUrl, imageId)

        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))
        self.failUnlessEqual(job.get_imageId(), self.makeUri(client, imageUrlPath))
        job = self.waitForJob(srv, jobUrlPath, "Completed")
        expInstanceIds = ['37208896-004b-4291-bab7-5cd89fcf71b9', ]
        self.failUnlessEqual(
            [ os.path.basename(x.get_href()) for x in job.resultResource],
            expInstanceIds)
        imageId = 'ami-00112233'
        uri = '%s/images/%s' % (self._baseCloudUrl, imageId)

        # Make sure we can address that image with this new id
        client = self.newClient(srv, uri)
        response = client.request('GET')
        self.failUnlessEqual(response.status, 200)

    def _setUpNewInstanceTest(self, cloudName, imageName, imageId=None,
            requestXml=None):
        if not imageId:
            imageId = '0903de41206786d4407ff24ab6e972c0d6b801f3'
        cloudType = self.cloudType

        fakeDaemonize = lambda slf, *args, **kwargs: slf.function(*args, **kwargs)
        self.mock(baseDriver.CatalogJobRunner, 'backgroundRun', fakeDaemonize)

        def fakeOpenUrl(slf, url, headers):
            sio = StringIO.StringIO()
            gz = gzip.GzipFile(fileobj=sio, mode='wb')
            gz.write(url)
            gz.close()
            sio.seek(0)
            return sio
        self.mock(dopenstack.driver, "openUrl", fakeOpenUrl)

        baseFileName = 'some-file-6-1-x86'
        def fakeExtractImage(slf, path):
            workdir = path[:-4]
            workdir = os.path.join(workdir, baseFileName)
            sdir = os.path.join(workdir, baseFileName)
            util.mkdirChain(sdir)
            fileName = os.path.join(sdir, '%s-root.ext3' % baseFileName)
            file(fileName, "w")
            return workdir
        self.mock(dopenstack.driver, "extractImage", fakeExtractImage)

        oldGetCredentialsIsoFile = dopenstack.driver.getCredentialsIsoFile
        def fakeGetCredentialsIsoFile(slf):
            ret = oldGetCredentialsIsoFile(slf)
            # Rename ISO file to something predictible
            dest = os.path.join(os.path.dirname(ret), 'credentials.iso')
            os.rename(ret, dest)
            return dest

        self.mock(dopenstack.driver, "getCredentialsIsoFile", fakeGetCredentialsIsoFile)
        srv = self.newService()
        uri = 'clouds/%s/instances/%s/instances' % (cloudType, cloudName)

        if requestXml is None:
            requestXml = _t(mockedData.xml_newInstanceOpenStackTempl % dict(
                imageId=imageId, flavor=1, instanceName="newinst34",
                instanceDescription="newinst34 description",
                keyName='jean_valjean',))
        client = self.newClient(srv, uri)
        response = client.request('POST', requestXml)

        job = self.getJobFromResponse(response)
        return srv, client, job, response

class CannedData(object):
    discovery = (300, dict(headers={
            u'connection': u'keep-alive',
            u'content-length': u'962',
            u'content-type': u'application/json',
            u'vary': u'X-Auth-Token'},
        body={"versions":
            {"values": [
                {"status": "stable", "updated": "2013-03-06T00:00:00Z", "media-types": [{"base": "application/json", "type": "application/vnd.openstack.identity-v3+json"}, {"base": "application/xml", "type": "application/vnd.openstack.identity-v3+xml"}], "id": "v3.0", "links": [{"href": "https://openstack1.eng.rpath.com:5000/v3/", "rel": "self"}]},
                {"status": "stable", "updated": "2014-04-17T00:00:00Z", "media-types": [{"base": "application/json", "type": "application/vnd.openstack.identity-v2.0+json"}, {"base": "application/xml", "type": "application/vnd.openstack.identity-v2.0+xml"}], "id": "v2.0", "links": [{"href": "https://openstack1.eng.rpath.com:5000/v2.0/", "rel": "self"}, ]}
                ]}}
            ))
    authenticate = (200, dict(headers={
            'connection': u'keep-alive',
            'content-length': u'10642',
            'content-type': u'application/json',
            'vary': u'X-Auth-Token'},
        body={
            'access': {
                'metadata': {'is_admin': 0,
                    'roles': ['9fe2ff9ee4384b1894a90878d3e92bab']},

                'serviceCatalog': [
                    {'endpoints': [{'adminURL': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97', 'id': '1884140635164bf69d6d0f5cdfd1a98c', 'internalURL': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97', 'publicURL': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'nova', 'type': 'compute'},
                    {'endpoints': [{'adminURL': 'https://openstack1.eng.rpath.com:9696/', 'id': '581dcd45918d4f1285f86f66ba81bb63', 'internalURL': 'https://openstack1.eng.rpath.com:9696/', 'publicURL': 'https://openstack1.eng.rpath.com:9696/', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'neutron', 'type': 'network'},
                    {'endpoints': [{'adminURL': 'https://openstack1.eng.rpath.com:8776/v2/44a04a897db842a49ff3f13cf5759a97', 'id': '2899953f4d4a43c4852dfc9b0e8a5c94', 'internalURL': 'https://openstack1.eng.rpath.com:8776/v2/44a04a897db842a49ff3f13cf5759a97', 'publicURL': 'https://openstack1.eng.rpath.com:8776/v2/44a04a897db842a49ff3f13cf5759a97', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'cinder_v2', 'type': 'volumev2'}, 
                    {'endpoints': [{'adminURL': 'https://openstack1.eng.rpath.com:8080', 'id': '09165a102946414492faa7cc7d77c7e3', 'internalURL': 'https://openstack1.eng.rpath.com:8080', 'publicURL': 'https://openstack1.eng.rpath.com:8080', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'swift_s3', 'type': 's3'},
                    {'endpoints': [{'adminURL': 'https://openstack1.eng.rpath.com:9292', 'id': '344144550996447198eb11c4e5b6bab9', 'internalURL': 'https://openstack1.eng.rpath.com:9292', 'publicURL': 'https://openstack1.eng.rpath.com:9292', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'glance', 'type': 'image'},
                    {'endpoints': [{'adminURL': 'https://openstack1.eng.rpath.com:8777', 'id': '3166ece0b2a24e338b998b2382e5c958', 'internalURL': 'https://openstack1.eng.rpath.com:8777', 'publicURL': 'https://openstack1.eng.rpath.com:8777', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'ceilometer', 'type': 'metering'},
                    {'endpoints': [{'adminURL': 'https://openstack1.eng.rpath.com:8000/v1/', 'id': '0be1ad10b0584cd28c70fccb742386ad', 'internalURL': 'https://openstack1.eng.rpath.com:8000/v1/', 'publicURL': 'https://openstack1.eng.rpath.com:8000/v1/', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'heat-cfn', 'type': 'cloudformation'},
                    {'endpoints': [{'adminURL': 'https://openstack1.eng.rpath.com:8776/v1/44a04a897db842a49ff3f13cf5759a97', 'id': '2fe7e8ec6a0b4a49915d0fde8707a507', 'internalURL': 'https://openstack1.eng.rpath.com:8776/v1/44a04a897db842a49ff3f13cf5759a97', 'publicURL': 'https://openstack1.eng.rpath.com:8776/v1/44a04a897db842a49ff3f13cf5759a97', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'cinder', 'type': 'volume'},
                    {'endpoints': [{'adminURL': 'https://openstack1.eng.rpath.com:8773/services/Admin', 'id': '3a5120493aac4268893016bac46bd67b', 'internalURL': 'https://openstack1.eng.rpath.com:8773/services/Cloud', 'publicURL': 'https://openstack1.eng.rpath.com:8773/services/Cloud', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'nova_ec2', 'type': 'ec2'},
                    {'endpoints': [{'adminURL': 'https://openstack1.eng.rpath.com:8004/v1/44a04a897db842a49ff3f13cf5759a97', 'id': '71b396582d394cd1ade54fed2cf0d255', 'internalURL': 'https://openstack1.eng.rpath.com:8004/v1/44a04a897db842a49ff3f13cf5759a97', 'publicURL': 'https://openstack1.eng.rpath.com:8004/v1/44a04a897db842a49ff3f13cf5759a97', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'heat', 'type': 'orchestration'}, 
                    {'endpoints': [{'adminURL': 'https://openstack1.eng.rpath.com:8080/', 'id': '11140882b89b45828b18dac762d1767a', 'internalURL': 'https://openstack1.eng.rpath.com:8080/v1/AUTH_44a04a897db842a49ff3f13cf5759a97', 'publicURL': 'https://openstack1.eng.rpath.com:8080/v1/AUTH_44a04a897db842a49ff3f13cf5759a97', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'swift', 'type': 'object-store'},
                    {'endpoints': [{'adminURL': 'https://openstack1.eng.rpath.com:35357/v2.0', 'id': '36faa60b5cd446c1b3c991fae6475130', 'internalURL': 'https://openstack1.eng.rpath.com:5000/v2.0', 'publicURL': 'https://openstack1.eng.rpath.com:5000/v2.0', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'keystone', 'type': 'identity'}],
                'token': {'expires': '2020-09-24T16:41:23Z', 'id': 'SuperSecretToken123', 'issued_at': '2014-09-24T15:41:23.659449', 'tenant': {'description': 'Platform Development Technologies', 'enabled': True, 'id': '44a04a897db842a49ff3f13cf5759a97', 'name': 'MyProject123'}},
                'user': {'id': 'Mihai Ibanescu', 'name': 'miiban', 'roles': [{'name': '_member_'}], 'roles_links': [], 'username': 'miiban'}
                }
                }
            ))

    images_listDetailed = (200, dict(headers={
            'content-type' : 'application/json',
            },
        body={
            'images': [
             {'OS-EXT-IMG-SIZE:size': 12592820224,
              'created': '2014-09-23T23:52:46Z',
              'id': '34229a3f-f7cd-4a29-ac9e-0321186e7557',
              'links': [{'href': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/34229a3f-f7cd-4a29-ac9e-0321186e7557',
                          'rel': 'self'},
                         {'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/34229a3f-f7cd-4a29-ac9e-0321186e7557',
                          'rel': 'bookmark'},
                         {'href': 'https://openstack1.eng.rpath.com:9292/44a04a897db842a49ff3f13cf5759a97/images/34229a3f-f7cd-4a29-ac9e-0321186e7557',
                          'rel': 'alternate',
                          'type': 'application/vnd.openstack.image'}],
              'metadata': {'description': 'vhf'},
              'minDisk': 0,
              'minRam': 2048,
              'name': 'w2k12r2vhd',
              'progress': 100,
              'status': 'ACTIVE',
              'updated': '2014-09-23T23:56:51Z'},
             {'OS-EXT-IMG-SIZE:size': 12462981120,
              'created': '2014-09-23T23:35:22Z',
              'id': '9401325c-4dac-436f-936b-4af7a49431fd',
              'links': [{'href': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/9401325c-4dac-436f-936b-4af7a49431fd',
                          'rel': 'self'},
                         {'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/9401325c-4dac-436f-936b-4af7a49431fd',
                          'rel': 'bookmark'},
                         {'href': 'https://openstack1.eng.rpath.com:9292/44a04a897db842a49ff3f13cf5759a97/images/9401325c-4dac-436f-936b-4af7a49431fd',
                          'rel': 'alternate',
                          'type': 'application/vnd.openstack.image'}],
              'metadata': {'description': 'w2k12 r2'},
              'minDisk': 0,
              'minRam': 2048,
              'name': 'w2k12 r2',
              'progress': 100,
              'status': 'ACTIVE',
              'updated': '2014-09-23T23:39:20Z'},
             {'OS-EXT-IMG-SIZE:size': 0,
              'created': '2014-09-22T15:54:34Z',
              'id': '04afdb08-90a2-48a1-a6ba-de54940679ad',
              'links': [{'href': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/04afdb08-90a2-48a1-a6ba-de54940679ad',
                          'rel': 'self'},
                         {'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/04afdb08-90a2-48a1-a6ba-de54940679ad',
                          'rel': 'bookmark'},
                         {'href': 'https://openstack1.eng.rpath.com:9292/44a04a897db842a49ff3f13cf5759a97/images/04afdb08-90a2-48a1-a6ba-de54940679ad',
                          'rel': 'alternate',
                          'type': 'application/vnd.openstack.image'}],
              'metadata': {},
              'minDisk': 0,
              'minRam': 0,
              'name': None,
              'progress': 25,
              'status': 'SAVING',
              'updated': '2014-09-22T15:54:34Z'},
             {'OS-EXT-IMG-SIZE:size': 255590912,
              'created': '2014-09-11T02:17:49Z',
              'id': '215854b1-e1fb-4de4-8557-701254768315',
              'links': [{'href': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/215854b1-e1fb-4de4-8557-701254768315',
                          'rel': 'self'},
                         {'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/215854b1-e1fb-4de4-8557-701254768315',
                          'rel': 'bookmark'},
                         {'href': 'https://openstack1.eng.rpath.com:9292/44a04a897db842a49ff3f13cf5759a97/images/215854b1-e1fb-4de4-8557-701254768315',
                          'rel': 'alternate',
                          'type': 'application/vnd.openstack.image'}],
              'metadata': {},
              'minDisk': 5,
              'minRam': 1024,
              'name': 'ubuntu-14.04.1-lts',
              'progress': 100,
              'status': 'ACTIVE',
              'updated': '2014-09-11T02:23:02Z'},
             {'OS-EXT-IMG-SIZE:size': 322830336,
              'created': '2014-09-02T15:57:13Z',
              'id': '9b16fb4a-8e3c-4b85-abe4-60b4c6d0975f',
              'links': [{'href': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/9b16fb4a-8e3c-4b85-abe4-60b4c6d0975f',
                          'rel': 'self'},
                         {'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/9b16fb4a-8e3c-4b85-abe4-60b4c6d0975f',
                          'rel': 'bookmark'},
                         {'href': 'https://openstack1.eng.rpath.com:9292/44a04a897db842a49ff3f13cf5759a97/images/9b16fb4a-8e3c-4b85-abe4-60b4c6d0975f',
                          'rel': 'alternate',
                          'type': 'application/vnd.openstack.image'}],
              'metadata': {'description': 'Red Hat Enterprise Linux 6.5 Cloud Image'},
              'minDisk': 0,
              'minRam': 0,
              'name': 'RHEL 6.5 Cloud Image',
              'progress': 100,
              'status': 'ACTIVE',
              'updated': '2014-09-02T15:57:15Z'},
             {'OS-EXT-IMG-SIZE:size': 13167616,
              'created': '2014-09-02T15:50:30Z',
              'id': '2f0bb8a4-8da1-44d2-b2f8-c0bad9e79e0f',
              'links': [{'href': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/2f0bb8a4-8da1-44d2-b2f8-c0bad9e79e0f',
                          'rel': 'self'},
                         {'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/2f0bb8a4-8da1-44d2-b2f8-c0bad9e79e0f',
                          'rel': 'bookmark'},
                         {'href': 'https://openstack1.eng.rpath.com:9292/44a04a897db842a49ff3f13cf5759a97/images/2f0bb8a4-8da1-44d2-b2f8-c0bad9e79e0f',
                          'rel': 'alternate',
                          'type': 'application/vnd.openstack.image'}],
              'metadata': {},
              'minDisk': 0,
              'minRam': 0,
              'name': 'Cirros',
              'progress': 100,
              'status': 'ACTIVE',
              'updated': '2014-09-02T15:50:30Z'},
             {'OS-EXT-IMG-SIZE:size': 435131904,
              'created': '2014-08-27T15:48:12Z',
              'id': '710c1a84-7867-4b04-bdbd-dc585e29c48e',
              'links': [{'href': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/710c1a84-7867-4b04-bdbd-dc585e29c48e',
                          'rel': 'self'},
                         {'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/710c1a84-7867-4b04-bdbd-dc585e29c48e',
                          'rel': 'bookmark'},
                         {'href': 'https://openstack1.eng.rpath.com:9292/44a04a897db842a49ff3f13cf5759a97/images/710c1a84-7867-4b04-bdbd-dc585e29c48e',
                          'rel': 'alternate',
                          'type': 'application/vnd.openstack.image'}],
              'metadata': {'description': 'Red Hat Enterprise Linux 7.0 Cloud Image'},
              'minDisk': 0,
              'minRam': 0,
              'name': 'RHEL 7.0 Cloud Image',
              'progress': 100,
              'status': 'ACTIVE',
              'updated': '2014-08-27T15:48:14Z'}]
            }))

    floatingIpPools_list = (200, dict(body={
        'floating_ip_pools' : [
            {'name' : 'SAS Network (VLAN0000)'},
            {'name' : 'SAS Network (VLAN0001)'},
        ]
        }))

    floatingIps_list = (200, dict(body={
        'floating_ips' : [
            {'fixed_ip': None,
             'id': '4130b5d0-0df4-4df5-9ba1-000000000000',
             'instance_id': None,
             'ip': '10.20.10.100',
             'pool': 'SAS Network (VLAN0000)'},
            {'fixed_ip': '192.168.20.101',
             'id': '4130b5d0-0df4-4df5-9ba1-000000000001',
             'instance_id': 'bbbbbbbb-76dc-43a1-b846-000000000001',
             'ip': '10.20.10.101',
             'pool': 'SAS Network (VLAN0000)'},
            {'fixed_ip': None,
             'id': '4130b5d0-0df4-4df5-9ba1-000000000010',
             'instance_id': None,
             'ip': '10.10.10.100',
             'pool': 'SAS Network (VLAN0001)'},
            {'fixed_ip': '192.168.10.101',
             'id': '4130b5d0-0df4-4df5-9ba1-000000000011',
             'instance_id': 'bbbbbbbb-76dc-43a1-b846-000000000011',
             'ip': '10.10.10.101',
             'pool': 'SAS Network (VLAN0001)'},
        ]
        }))
    floatingIps_create = (200, dict(body={
        'floating_ip' : {
             'fixed_ip': None,
             'id': '4130b5d0-0df4-4df5-9ba1-000000000002',
             'instance_id': None,
             'ip': '10.20.10.102',
             'pool': 'SAS Network (VLAN0000)',
             },
        }))

    server_get = (200, dict(body={
        'server' : {
              'OS-DCF:diskConfig': 'MANUAL',
               'OS-EXT-AZ:availability_zone': 'nova',
               'OS-EXT-STS:power_state': 1,
               'OS-EXT-STS:task_state': None,
               'OS-EXT-STS:vm_state': 'active',
               'OS-SRV-USG:launched_at': '2014-09-30T13:32:48.000000',
               'OS-SRV-USG:terminated_at': None,
               'accessIPv4': '',
               'accessIPv6': '',
               'addresses': {'pdt-network1': [{'OS-EXT-IPS-MAC:mac_addr': 'fa:16:3e:31:f6:70',
                                                 'OS-EXT-IPS:type': 'fixed',
                                                 'addr': '10.210.1.11',
                                                 'version': 4}]},
               'config_drive': '',
               'created': '2014-09-30T13:31:58Z',
               'flavor': {'id': '2',
                           'links': [{'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/flavors/2',
                                       'rel': 'bookmark'}]},
               'hostId': '07d94005d463e0fbaeb2dd75bdc36762f93eaea4e6dd92354441aea0',
               'id': '37208896-004b-4291-bab7-5cd89fcf71b9',
               'image': {'id': 'a17f23b5-15e8-48f0-974f-fd0e6b659739',
                          'links': [{'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/a17f23b5-15e8-48f0-974f-fd0e6b659739',
                                      'rel': 'bookmark'}]},
               'key_name': None,
               'links': [{'href': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/servers/37208896-004b-4291-bab7-5cd89fcf71b9',
                           'rel': 'self'},
                          {'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/servers/37208896-004b-4291-bab7-5cd89fcf71b9',
                           'rel': 'bookmark'}],
               'metadata': {},
               'name': 'jules1',
               'os-extended-volumes:volumes_attached': [],
               'progress': 0,
               'security_groups': [{'name': 'default'}],
               'status': 'ACTIVE',
               'tenant_id': '44a04a897db842a49ff3f13cf5759a97',
               'updated': '2014-09-30T13:32:49Z',
               'user_id': 'Mihai Ibanescu'
            }}))

    servers_listDetailed = (200, dict(body={
'servers': [{'OS-DCF:diskConfig': 'MANUAL',
               'OS-EXT-AZ:availability_zone': 'nova',
               'OS-EXT-STS:power_state': 1,
               'OS-EXT-STS:task_state': None,
               'OS-EXT-STS:vm_state': 'active',
               'OS-SRV-USG:launched_at': '2014-09-30T13:49:28.000000',
               'OS-SRV-USG:terminated_at': None,
               'accessIPv4': '',
               'accessIPv6': '',
               'addresses': {'pdt-network1': [{'OS-EXT-IPS-MAC:mac_addr': 'fa:16:3e:17:0b:81',
                                                 'OS-EXT-IPS:type': 'fixed',
                                                 'addr': '10.210.1.12',
                                                 'version': 4},
                                                {'OS-EXT-IPS-MAC:mac_addr': 'fa:16:3e:17:0b:81',
                                                 'OS-EXT-IPS:type': 'floating',
                                                 'addr': '10.124.16.51',
                                                 'version': 4}]},
               'config_drive': '',
               'created': '2014-09-30T13:49:19Z',
               'flavor': {'id': '2',
                           'links': [{'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/flavors/2',
                                       'rel': 'bookmark'}]},
               'hostId': '07d94005d463e0fbaeb2dd75bdc36762f93eaea4e6dd92354441aea0',
               'id': '22b896bf-af13-420b-a7db-2fadff3b3279',
               'image': {'id': 'a17f23b5-15e8-48f0-974f-fd0e6b659739',
                          'links': [{'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/a17f23b5-15e8-48f0-974f-fd0e6b659739',
                                      'rel': 'bookmark'}]},
               'key_name': None,
               'links': [{'href': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/servers/22b896bf-af13-420b-a7db-2fadff3b3279',
                           'rel': 'self'},
                          {'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/servers/22b896bf-af13-420b-a7db-2fadff3b3279',
                           'rel': 'bookmark'}],
               'metadata': {},
               'name': 'vincent1',
               'os-extended-volumes:volumes_attached': [],
               'progress': 0,
               'security_groups': [{'name': 'WideOpen'}],
               'status': 'ACTIVE',
               'tenant_id': '44a04a897db842a49ff3f13cf5759a97',
               'updated': '2014-09-30T13:49:28Z',
               'user_id': 'Mihai Ibanesc'},
              {'OS-DCF:diskConfig': 'MANUAL',
               'OS-EXT-AZ:availability_zone': 'nova',
               'OS-EXT-STS:power_state': 1,
               'OS-EXT-STS:task_state': None,
               'OS-EXT-STS:vm_state': 'active',
               'OS-SRV-USG:launched_at': '2014-09-30T13:32:48.000000',
               'OS-SRV-USG:terminated_at': None,
               'accessIPv4': '',
               'accessIPv6': '',
               'addresses': {'pdt-network1': [
                            {
                                'OS-EXT-IPS-MAC:mac_addr': 'fa:16:3e:31:f6:70',
                                'OS-EXT-IPS:type': 'fixed',
                                'addr': '10.210.1.11',
                                'version': 4,
                                },
                            {
                                'OS-EXT-IPS-MAC:mac_addr': 'fa:16:3e:31:f6:70',
                                'OS-EXT-IPS:type': 'floating',
                                'addr': '10.100.1.11',
                                'version': 4,
                                },
                            ]},
               'config_drive': '',
               'created': '2014-09-30T13:31:58Z',
               'flavor': {'id': '2',
                           'links': [{'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/flavors/2',
                                       'rel': 'bookmark'}]},
               'hostId': '07d94005d463e0fbaeb2dd75bdc36762f93eaea4e6dd92354441aea0',
               'id': '37208896-004b-4291-bab7-5cd89fcf71b9',
               'image': {'id': 'a17f23b5-15e8-48f0-974f-fd0e6b659739',
                          'links': [{'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/a17f23b5-15e8-48f0-974f-fd0e6b659739',
                                      'rel': 'bookmark'}]},
               'key_name': None,
               'links': [{'href': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/servers/37208896-004b-4291-bab7-5cd89fcf71b9',
                           'rel': 'self'},
                          {'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/servers/37208896-004b-4291-bab7-5cd89fcf71b9',
                           'rel': 'bookmark'}],
               'metadata': {},
               'name': 'jules1',
               'os-extended-volumes:volumes_attached': [],
               'progress': 0,
               'security_groups': [{'name': 'default'}],
               'status': 'ACTIVE',
               'tenant_id': '44a04a897db842a49ff3f13cf5759a97',
               'updated': '2014-09-30T13:32:49Z',
               'user_id': 'Mihai Ibanescu'}
              ]
        }))
    servers_listDetailedWithNetwork = (
        servers_listDetailed[0], copy.deepcopy(servers_listDetailed[1]))
    for i, srv in enumerate(servers_listDetailedWithNetwork[1]['body']['servers']):
        srv['addresses']['public'] = [
                { 'version' : 4, 'addr' : "10.210.100.%s" % (i+100),
                    'OS-EXT-IPS:type': 'fixed'},
                { 'version' : 4, 'addr' : "10.100.100.%s" % (i+100),
                    'OS-EXT-IPS:type': 'floating'},
        ]

    servers_add_floating_ip = (200, dict(body={
        }))

    avzones_list = (200, dict(body={
 u'availabilityZoneInfo': [{u'hosts': None,
                            u'zoneName': u'sashq-d122',
                            u'zoneState': {u'available': True}}]}
))

    networks_list = (200, dict(body={
 u'networks': [{u'broadcast': None,
                u'cidr': None,
                u'cidr_v6': None,
                u'dns1': None,
                u'dns2': None,
                u'gateway': None,
                u'gateway_v6': None,
                u'id': u'8b0068fe-596a-429e-8357-2c4ed51cfc14',
                u'label': u'FloatingNet',
                u'netmask': None,
                u'netmask_v6': None},
               {u'broadcast': None,
                u'cidr': None,
                u'cidr_v6': None,
                u'dns1': None,
                u'dns2': None,
                u'gateway': None,
                u'gateway_v6': None,
                u'id': u'95ecd186-2a20-4d19-8ecc-41061c1f6898',
                u'label': u'bosh',
                u'netmask': None,
                u'netmask_v6': None},
               {u'broadcast': None,
                u'cidr': None,
                u'cidr_v6': None,
                u'dns1': None,
                u'dns2': None,
                u'gateway': None,
                u'gateway_v6': None,
                u'id': u'ad73348d-ccd4-44d7-8a23-7a5daf97d35b',
                u'label': u'boshdev',
                u'netmask': None,
                u'netmask_v6': None},
               {u'broadcast': None,
                u'cidr': None,
                u'cidr_v6': None,
                u'dns1': None,
                u'dns2': None,
                u'gateway': None,
                u'gateway_v6': None,
                u'id': u'c082c5ef-1654-42b6-ac4e-6291a1089816',
                u'label': u'dostei',
                u'netmask': None,
                u'netmask_v6': None}]}
))

    flavors_listDetailed = (200, dict(body={
        'flavors': [
            {
               'OS-FLV-DISABLED:disabled': False,
               'OS-FLV-EXT-DATA:ephemeral': 0,
               'disk': 1,
               'id': '1',
               'links': [
                    {'href': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/flavors/1', 'rel': 'self'},
                    {'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/flavors/1', 'rel': 'bookmark'}],
               'name': 'm1.tiny',
               'os-flavor-access:is_public': True,
               'ram': 512,
               'rxtx_factor': 1.0,
               'swap': '',
               'vcpus': 1},
            {
               'OS-FLV-DISABLED:disabled': False,
               'OS-FLV-EXT-DATA:ephemeral': 0,
               'disk': 20,
               'id': '2',
               'links': [
                   {'href': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/flavors/2', 'rel': 'self'},
                   {'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/flavors/2', 'rel': 'bookmark'}],
               'name': 'm1.small',
               'os-flavor-access:is_public': True,
               'ram': 2048,
               'rxtx_factor': 1.0,
               'swap': '',
               'vcpus': 1},
            {
               'OS-FLV-DISABLED:disabled': False,
               'OS-FLV-EXT-DATA:ephemeral': 0,
               'disk': 40,
               'id': '3',
               'links': [
                   {'href': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/flavors/3', 'rel': 'self'},
                   {'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/flavors/3', 'rel': 'bookmark'}],
               'name': 'm1.medium',
               'os-flavor-access:is_public': True,
               'ram': 4096,
               'rxtx_factor': 1.0,
               'swap': '',
               'vcpus': 2},
            {
               'OS-FLV-DISABLED:disabled': False,
               'OS-FLV-EXT-DATA:ephemeral': 0,
               'disk': 80,
               'id': '4',
               'links': [
                   {'href': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/flavors/4', 'rel': 'self'},
                   {'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/flavors/4', 'rel': 'bookmark'}],
               'name': 'm1.large',
               'os-flavor-access:is_public': True,
               'ram': 8192,
               'rxtx_factor': 1.0,
               'swap': '',
               'vcpus': 4},
            {
               'OS-FLV-DISABLED:disabled': False,
               'OS-FLV-EXT-DATA:ephemeral': 0,
               'disk': 160,
               'id': '5',
               'links': [
                   {'href': 'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/flavors/5', 'rel': 'self'},
                   {'href': 'https://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/flavors/5', 'rel': 'bookmark'}],
               'name': 'm1.xlarge',
               'os-flavor-access:is_public': True,
               'ram': 16384,
               'rxtx_factor': 1.0,
               'swap': '',
               'vcpus': 8}
            ]}))

    keypairs_list = (200, dict(body={
        'keypairs' : [
            {'keypair' : {
                'public_key' : "ssh-rsa AAAABB",
                'name' : 'jean_valjean',
                'fingerprint' : '00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00',
                }},
            {'keypair' : {
                'public_key' : "ssh-rsa AAAACC",
                'name' : 'insp_javert',
                'fingerprint' : '00:00:00:00:00:00:00:00:00:00:00:00:00:00:11:11',
                }},
            ],
        }))

    glance_schemas_image = (200, dict(body={
  u'additionalProperties': { u'type': u'string'},
  u'links': [ { u'href': u'{self}', u'rel': u'self'},
              { u'href': u'{file}', u'rel': u'enclosure'},
              { u'href': u'{schema}', u'rel': u'describedby'}],
  u'name': u'image',
  u'properties': { u'architecture': { u'description': u'Operating system architecture as specified in http://docs.openstack.org/trunk/openstack-compute/admin/content/adding-images.html',
                                      u'is_base': False,
                                      u'type': u'string'},
                   u'checksum': { u'description': u'md5 hash of image contents. (READ-ONLY)',
                                  u'maxLength': 32,
                                  u'type': u'string'},
                   u'container_format': { u'description': u'Format of the container',
                                          u'enum': [ u'ami',
                                                     u'ari',
                                                     u'aki',
                                                     u'bare',
                                                     u'ovf',
                                                     u'ova'],
                                          u'type': u'string'},
                   u'created_at': { u'description': u'Date and time of image registration (READ-ONLY)',
                                    u'type': u'string'},
                   u'direct_url': { u'description': u'URL to access the image file kept in external store (READ-ONLY)',
                                    u'type': u'string'},
                   u'disk_format': { u'description': u'Format of the disk',
                                     u'enum': [ u'ami',
                                                u'ari',
                                                u'aki',
                                                u'vhd',
                                                u'vmdk',
                                                u'raw',
                                                u'qcow2',
                                                u'vdi',
                                                u'iso'],
                                     u'type': u'string'},
                   u'file': { u'description': u'(READ-ONLY)',
                              u'type': u'string'},
                   u'id': { u'description': u'An identifier for the image',
                            u'pattern': u'^([0-9a-fA-F]){8}-([0-9a-fA-F]){4}-([0-9a-fA-F]){4}-([0-9a-fA-F]){4}-([0-9a-fA-F]){12}$',
                            u'type': u'string'},
                   u'instance_uuid': { u'description': u'ID of instance used to create this image.',
                                       u'is_base': False,
                                       u'type': u'string'},
                   u'kernel_id': { u'description': u'ID of image stored in Glance that should be used as the kernel when booting an AMI-style image.',
                                   u'is_base': False,
                                   u'pattern': u'^([0-9a-fA-F]){8}-([0-9a-fA-F]){4}-([0-9a-fA-F]){4}-([0-9a-fA-F]){4}-([0-9a-fA-F]){12}$',
                                   u'type': u'string'},
                   u'locations': { u'description': u'A set of URLs to access the image file kept in external store',
                                   u'items': { u'properties': { u'metadata': { u'type': u'object'},
                                                                u'url': { u'maxLength': 255,
                                                                          u'type': u'string'}},
                                               u'required': [ u'url',
                                                              u'metadata'],
                                               u'type': u'object'},
                                   u'type': u'array'},
                   u'min_disk': { u'description': u'Amount of disk space (in GB) required to boot image.',
                                  u'type': u'integer'},
                   u'min_ram': { u'description': u'Amount of ram (in MB) required to boot image.',
                                 u'type': u'integer'},
                   u'name': { u'description': u'Descriptive name for the image',
                              u'maxLength': 255,
                              u'type': u'string'},
                   u'os_distro': { u'description': u'Common name of operating system distribution as specified in http://docs.openstack.org/trunk/openstack-compute/admin/content/adding-images.html',
                                   u'is_base': False,
                                   u'type': u'string'},
                   u'os_version': { u'description': u'Operating system version as specified by the distributor',
                                    u'is_base': False,
                                    u'type': u'string'},
                   u'owner': { u'description': u'Owner of the image',
                               u'maxLength': 255,
                               u'type': u'string'},
                   u'protected': { u'description': u'If true, image will not be deletable.',
                                   u'type': u'boolean'},
                   u'ramdisk_id': { u'description': u'ID of image stored in Glance that should be used as the ramdisk when booting an AMI-style image.',
                                    u'is_base': False,
                                    u'pattern': u'^([0-9a-fA-F]){8}-([0-9a-fA-F]){4}-([0-9a-fA-F]){4}-([0-9a-fA-F]){4}-([0-9a-fA-F]){12}$',
                                    u'type': u'string'},
                   u'schema': { u'description': u'(READ-ONLY)',
                                u'type': u'string'},
                   u'self': { u'description': u'(READ-ONLY)',
                              u'type': u'string'},
                   u'size': { u'description': u'Size of image file in bytes (READ-ONLY)',
                              u'type': u'integer'},
                   u'status': { u'description': u'Status of the image (READ-ONLY)',
                                u'enum': [ u'queued',
                                           u'saving',
                                           u'active',
                                           u'killed',
                                           u'deleted',
                                           u'pending_delete'],
                                u'type': u'string'},
                   u'tags': { u'description': u'List of strings related to the image',
                              u'items': { u'maxLength': 255,
                                          u'type': u'string'},
                              u'type': u'array'},
                   u'updated_at': { u'description': u'Date and time of the last image modification (READ-ONLY)',
                                    u'type': u'string'},
                   u'virtual_size': { u'description': u'Virtual size of image in bytes (READ-ONLY)',
                                      u'type': u'integer'},
                   u'visibility': { u'description': u'Scope of image accessibility',
                                    u'enum': [u'public', u'private'],
                                    u'type': u'string'}}}
        ))

    glance_schemas_member = (200, dict(body={
 u'name': u'member',
 u'properties': {u'created_at': {u'description': u'Date and time of image member creation',
                                 u'type': u'string'},
                 u'image_id': {u'description': u'An identifier for the image',
                               u'pattern': u'^([0-9a-fA-F]){8}-([0-9a-fA-F]){4}-([0-9a-fA-F]){4}-([0-9a-fA-F]){4}-([0-9a-fA-F]){12}$',
                               u'type': u'string'},
                 u'member_id': {u'description': u'An identifier for the image member (tenantId)',
                                u'type': u'string'},
                 u'schema': {u'type': u'string'},
                 u'status': {u'description': u'The status of this image member',
                             u'enum': [u'pending', u'accepted', u'rejected'],
                             u'type': u'string'},
                 u'updated_at': {u'description': u'Date and time of last modification of image member',
                                 u'type': u'string'}}}
))

    glance_schemas_metadef_restype = (200, dict(body={
 u'additionalProperties': False,
 u'name': u'resource_type_association',
 u'properties': {u'created_at': {u'description': u'Date and time of resource type association (READ-ONLY)',
                                 u'format': u'date-time',
                                 u'type': u'string'},
                 u'name': {u'description': u'Resource type names should be aligned with Heat resource types whenever possible: http://docs.openstack.org/developer/heat/template_guide/openstack.html',
                           u'maxLength': 80,
                           u'type': u'string'},
                 u'prefix': {u'description': u'Specifies the prefix to use for the given resource type. Any properties in the namespace should be prefixed with this prefix when being applied to the specified resource type. Must include prefix separator (e.g. a colon :).',
                             u'maxLength': 80,
                             u'type': u'string'},
                 u'properties_target': {u'description': u'Some resource types allow more than one key / value pair per instance.  For example, Cinder allows user and image metadata on volumes. Only the image properties metadata is evaluated by Nova (scheduling or drivers). This property allows a namespace target to remove the ambiguity.',
                                        u'maxLength': 80,
                                        u'type': u'string'},
                 u'updated_at': {u'description': u'Date and time of the last resource type association modification (READ-ONLY)',
                                 u'format': u'date-time',
                                 u'type': u'string'}},
 u'required': [u'name']}
))

    glance_schemas_metadef_property = (200, dict(body={
 u'additionalProperties': False,
 u'definitions': {u'positiveInteger': {u'minimum': 0, u'type': u'integer'},
                  u'positiveIntegerDefault0': {u'allOf': [{u'$ref': u'#/definitions/positiveInteger'},
                                                          {u'default': 0}]},
                  u'stringArray': {u'items': {u'type': u'string'},
                                   u'minItems': 1,
                                   u'type': u'array',
                                   u'uniqueItems': True}},
 u'name': u'property',
 u'properties': {u'additionalItems': {u'type': u'boolean'},
                 u'default': {},
                 u'description': {u'type': u'string'},
                 u'enum': {u'type': u'array'},
                 u'items': {u'properties': {u'enum': {u'type': u'array'},
                                            u'type': {u'enum': [u'array',
                                                                u'boolean',
                                                                u'integer',
                                                                u'number',
                                                                u'object',
                                                                u'string',
                                                                None],
                                                      u'type': u'string'}},
                            u'type': u'object'},
                 u'maxItems': {u'$ref': u'#/definitions/positiveInteger'},
                 u'maxLength': {u'$ref': u'#/definitions/positiveInteger'},
                 u'maximum': {u'type': u'number'},
                 u'minItems': {u'$ref': u'#/definitions/positiveIntegerDefault0'},
                 u'minLength': {u'$ref': u'#/definitions/positiveIntegerDefault0'},
                 u'minimum': {u'type': u'number'},
                 u'name': {u'type': u'string'},
                 u'pattern': {u'format': u'regex', u'type': u'string'},
                 u'readonly': {u'type': u'boolean'},
                 u'required': {u'$ref': u'#/definitions/stringArray'},
                 u'title': {u'type': u'string'},
                 u'type': {u'enum': [u'array',
                                     u'boolean',
                                     u'integer',
                                     u'number',
                                     u'object',
                                     u'string',
                                     None],
                           u'type': u'string'},
                 u'uniqueItems': {u'default': False, u'type': u'boolean'}},
 u'required': [u'type', u'title', u'name']}
))

    glance_schemas_metadef_object = (200, dict(body={
 u'additionalProperties': False,
 u'definitions': {u'positiveInteger': {u'minimum': 0, u'type': u'integer'},
                  u'positiveIntegerDefault0': {u'allOf': [{u'$ref': u'#/definitions/positiveInteger'},
                                                          {u'default': 0}]},
                  u'property': {u'additionalProperties': {u'properties': {u'additionalItems': {u'type': u'boolean'},
                                                                          u'default': {},
                                                                          u'description': {u'type': u'string'},
                                                                          u'enum': {u'type': u'array'},
                                                                          u'items': {u'properties': {u'enum': {u'type': u'array'},
                                                                                                     u'type': {u'enum': [u'array',
                                                                                                                         u'boolean',
                                                                                                                         u'integer',
                                                                                                                         u'number',
                                                                                                                         u'object',
                                                                                                                         u'string',
                                                                                                                         None],
                                                                                                               u'type': u'string'}},
                                                                                     u'type': u'object'},
                                                                          u'maxItems': {u'$ref': u'#/definitions/positiveInteger'},
                                                                          u'maxLength': {u'$ref': u'#/definitions/positiveInteger'},
                                                                          u'maximum': {u'type': u'number'},
                                                                          u'minItems': {u'$ref': u'#/definitions/positiveIntegerDefault0'},
                                                                          u'minLength': {u'$ref': u'#/definitions/positiveIntegerDefault0'},
                                                                          u'minimum': {u'type': u'number'},
                                                                          u'name': {u'type': u'string'},
                                                                          u'pattern': {u'format': u'regex',
                                                                                       u'type': u'string'},
                                                                          u'readonly': {u'type': u'boolean'},
                                                                          u'required': {u'$ref': u'#/definitions/stringArray'},
                                                                          u'title': {u'type': u'string'},
                                                                          u'type': {u'enum': [u'array',
                                                                                              u'boolean',
                                                                                              u'integer',
                                                                                              u'number',
                                                                                              u'object',
                                                                                              u'string',
                                                                                              None],
                                                                                    u'type': u'string'},
                                                                          u'uniqueItems': {u'default': False,
                                                                                           u'type': u'boolean'}},
                                                          u'required': [u'title',
                                                                        u'type'],
                                                          u'type': u'object'},
                                u'type': u'object'},
                  u'stringArray': {u'items': {u'type': u'string'},
                                   u'type': u'array',
                                   u'uniqueItems': True}},
 u'name': u'object',
 u'properties': {u'created_at': {u'description': u'Date and time of object creation (READ-ONLY)',
                                 u'format': u'date-time',
                                 u'type': u'string'},
                 u'description': {u'type': u'string'},
                 u'name': {u'type': u'string'},
                 u'properties': {u'$ref': u'#/definitions/property'},
                 u'required': {u'$ref': u'#/definitions/stringArray'},
                 u'schema': {u'type': u'string'},
                 u'self': {u'type': u'string'},
                 u'updated_at': {u'description': u'Date and time of the last object modification (READ-ONLY)',
                                 u'format': u'date-time',
                                 u'type': u'string'}},
 u'required': [u'name']}
))

    glance_schemas_metadef_namespace = (200, dict(body={
 u'additionalProperties': False,
 u'definitions': {u'positiveInteger': {u'minimum': 0, u'type': u'integer'},
                  u'positiveIntegerDefault0': {u'allOf': [{u'$ref': u'#/definitions/positiveInteger'},
                                                          {u'default': 0}]},
                  u'property': {u'additionalProperties': {u'properties': {u'additionalItems': {u'type': u'boolean'},
                                                                          u'default': {},
                                                                          u'description': {u'type': u'string'},
                                                                          u'enum': {u'type': u'array'},
                                                                          u'items': {u'properties': {u'enum': {u'type': u'array'},
                                                                                                     u'type': {u'enum': [u'array',
                                                                                                                         u'boolean',
                                                                                                                         u'integer',
                                                                                                                         u'number',
                                                                                                                         u'object',
                                                                                                                         u'string',
                                                                                                                         None],
                                                                                                               u'type': u'string'}},
                                                                                     u'type': u'object'},
                                                                          u'maxItems': {u'$ref': u'#/definitions/positiveInteger'},
                                                                          u'maxLength': {u'$ref': u'#/definitions/positiveInteger'},
                                                                          u'maximum': {u'type': u'number'},
                                                                          u'minItems': {u'$ref': u'#/definitions/positiveIntegerDefault0'},
                                                                          u'minLength': {u'$ref': u'#/definitions/positiveIntegerDefault0'},
                                                                          u'minimum': {u'type': u'number'},
                                                                          u'name': {u'type': u'string'},
                                                                          u'pattern': {u'format': u'regex',
                                                                                       u'type': u'string'},
                                                                          u'readonly': {u'type': u'boolean'},
                                                                          u'required': {u'$ref': u'#/definitions/stringArray'},
                                                                          u'title': {u'type': u'string'},
                                                                          u'type': {u'enum': [u'array',
                                                                                              u'boolean',
                                                                                              u'integer',
                                                                                              u'number',
                                                                                              u'object',
                                                                                              u'string',
                                                                                              None],
                                                                                    u'type': u'string'},
                                                                          u'uniqueItems': {u'default': False,
                                                                                           u'type': u'boolean'}},
                                                          u'required': [u'title',
                                                                        u'type'],
                                                          u'type': u'object'},
                                u'type': u'object'},
                  u'stringArray': {u'items': {u'type': u'string'},
                                   u'type': u'array',
                                   u'uniqueItems': True}},
 u'name': u'namespace',
 u'properties': {u'created_at': {u'description': u'Date and time of namespace creation (READ-ONLY)',
                                 u'format': u'date-time',
                                 u'type': u'string'},
                 u'description': {u'description': u'Provides a user friendly description of the namespace.',
                                  u'maxLength': 500,
                                  u'type': u'string'},
                 u'display_name': {u'description': u'The user friendly name for the namespace. Used by UI if available.',
                                   u'maxLength': 80,
                                   u'type': u'string'},
                 u'namespace': {u'description': u'The unique namespace text.',
                                u'maxLength': 80,
                                u'type': u'string'},
                 u'objects': {u'items': {u'properties': {u'description': {u'type': u'string'},
                                                         u'name': {u'type': u'string'},
                                                         u'properties': {u'$ref': u'#/definitions/property'},
                                                         u'required': {u'$ref': u'#/definitions/stringArray'}},
                                         u'type': u'object'},
                              u'type': u'array'},
                 u'owner': {u'description': u'Owner of the namespace.',
                            u'maxLength': 255,
                            u'type': u'string'},
                 u'properties': {u'$ref': u'#/definitions/property'},
                 u'protected': {u'description': u'If true, namespace will not be deletable.',
                                u'type': u'boolean'},
                 u'resource_type_associations': {u'items': {u'properties': {u'name': {u'type': u'string'},
                                                                            u'prefix': {u'type': u'string'},
                                                                            u'properties_target': {u'type': u'string'}},
                                                            u'type': u'object'},
                                                 u'type': u'array'},
                 u'schema': {u'type': u'string'},
                 u'self': {u'type': u'string'},
                 u'updated_at': {u'description': u'Date and time of the last namespace modification (READ-ONLY)',
                                 u'format': u'date-time',
                                 u'type': u'string'},
                 u'visibility': {u'description': u'Scope of namespace accessibility.',
                                 u'enum': [u'public', u'private'],
                                 u'type': u'string'}},
 u'required': [u'namespace']}
))

    glance_images_create = (201, dict(body={
        "container_format": 'bare',
        "created_at": "2011-09-01T03:53:25.901097",
        "disk_format": 'raw',
        "file" : "/v2/images/b6001727-0029-4e9b-afa0-e7aaba8d733b/file",
        "id": 'b6001727-0029-4e9b-afa0-e7aaba8d733b',
        "min_disk" : 0,
        "min_ram" : 0,
        "name": "test-misa-11",
        "owner": "c23a2d96514a43078a6f0648cd455fb6",
        "protected" : False,
        "schema" : "/v2/schemas/image",
        "self" : "/v2/images/b6001727-0029-4e9b-afa0-e7aaba8d733b",
        "status": "active",
        "tags" : [],
        "updated_at": "2011-09-01T03:53:26.279266",
        "visibility" : "private",
        }))

    glance_image1 = (200, dict(body=
             {
              'checksum' : 'd2541be574050cdf12deffffa8d8966b',
              'container_format' : 'bare',
              'created_at': '2014-09-23T23:52:46Z',
              'disk_format': 'raw',
              "file" : "/v2/images/b6001727-0029-4e9b-afa0-e7aaba8d733b/file",
              'id': 'b6001727-0029-4e9b-afa0-e7aaba8d733b',
              'min_disk': 0,
              'min_ram': 2048,
              'name': 'test-misa-11',
              "owner": "c23a2d96514a43078a6f0648cd455fb6",
              "protected" : False,
              "schema" : "/v2/schemas/image",
              "self" : "/v2/images/b6001727-0029-4e9b-afa0-e7aaba8d733b",
              'size': 12592820224,
              'status': 'active',
              'tags' : [],
              'updated_at': '2014-09-23T23:56:51Z'}))

    glance_image1_update = (200, dict(body=dict(
        image=glance_image1[1]['body'])))

    server_create = (200, dict(body={u'server': {u'status': u'BUILD', u'uuid': u'73d29965-aeee-4ebc-ae6a-13dd03b752c8', u'hostId': u'', u'addresses': {}, u'imageRef': 2, u'adminPass': u'Y9VfddavL2AMJMnz', u'flavorRef': u'http://dhcp107.eng.rpath.com:8774/v1.1/flavors/1', u'links': [{u'href': u'http://dhcp107.eng.rpath.com:8774/v1.1/servers/5', u'rel': u'self'}, {u'href': u'http://dhcp107.eng.rpath.com:8774/servers/5', u'rel': u'bookmark'}], u'metadata': {}, u'id': '37208896-004b-4291-bab7-5cd89fcf71b9', u'name': u'test-misa-11'}}))

class MockedClientData(object):
    data = {
        'https://openstack1.eng.rpath.com:5001/' : dict(
            GET = CannedData.discovery,
        ),
        'https://openstack1.eng.rpath.com:5000/v2.0/tokens' : dict(
            POST = CannedData.authenticate,
        ),
        'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/detail' : dict(
            GET = CannedData.images_listDetailed,
        ),
        'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/servers/37208896-004b-4291-bab7-5cd89fcf71b9/action' : dict(
            POST = CannedData.servers_add_floating_ip,
            ),
        'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/servers/detail' : dict(
            GET = mockedData.MultiResponse([
                CannedData.servers_listDetailed,
                CannedData.servers_listDetailed,
                CannedData.servers_listDetailedWithNetwork,
                CannedData.servers_listDetailedWithNetwork,
                CannedData.servers_listDetailedWithNetwork,
            ]),
        ),
        'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/os-availability-zone' : dict(
            GET = CannedData.avzones_list,
        ),
        'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/os-networks' : dict(
            GET = CannedData.networks_list,
        ),
        'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/flavors/detail' : dict(
            GET = CannedData.flavors_listDetailed,
        ),
        'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/os-keypairs' : dict(
            GET = CannedData.keypairs_list,
            ),
        'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/os-floating-ips' : dict(
            GET = CannedData.floatingIps_list,
            POST = CannedData.floatingIps_create,
        ),
        'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/os-floating-ip-pools' : dict(
            GET = CannedData.floatingIpPools_list,
        ),
        'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/servers' : dict(
            POST = CannedData.server_create,
        ),
        'https://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/servers/37208896-004b-4291-bab7-5cd89fcf71b9' : dict(
            GET = CannedData.server_get,
            ),
        'https://openstack1.eng.rpath.com:9292/v2/schemas/image' : dict(
            GET = CannedData.glance_schemas_image,
            ),
        'https://openstack1.eng.rpath.com:9292/v2/schemas/member' : dict(
            GET = CannedData.glance_schemas_member,
            ),
        'https://openstack1.eng.rpath.com:9292/v2/schemas/metadefs/resource_type' : dict(
            GET = CannedData.glance_schemas_metadef_restype,
            ),
        'https://openstack1.eng.rpath.com:9292/v2/schemas/metadefs/property' : dict(
            GET = CannedData.glance_schemas_metadef_property,
            ),
        'https://openstack1.eng.rpath.com:9292/v2/schemas/metadefs/object' : dict(
            GET = CannedData.glance_schemas_metadef_object,
            ),
        'https://openstack1.eng.rpath.com:9292/v2/schemas/metadefs/namespace' : dict(
            GET = CannedData.glance_schemas_metadef_namespace,
            ),
        'https://openstack1.eng.rpath.com:9292/v2/images' : dict(
            POST = CannedData.glance_images_create,
            ),
        'https://openstack1.eng.rpath.com:9292/v2/images/b6001727-0029-4e9b-afa0-e7aaba8d733b/file' : dict(
            PUT = CannedData.glance_image1_update),
        'https://openstack1.eng.rpath.com:9292/v2/images/b6001727-0029-4e9b-afa0-e7aaba8d733b' : dict(
            GET = CannedData.glance_image1),
    }
    def __init__(self):
        self.data = copy.deepcopy(self.__class__.data)

    def getMockedData(self, req):
        method = req.method
        path = req.url
        mdict = self.data.get(path, None)
        if mdict is None:
            raise RuntimeError("Mock me", path)
        rdata = mdict.get(method, None)
        if rdata is None:
            raise RuntimeError("Mock me", path, method)
        if isinstance(rdata, tuple):
            status, rdata = rdata
        else:
            status = 200
        if isinstance(rdata, mockedData.MultiResponse):
            resp = rdata.getData()
            headers = resp.data.get('headers', {})
            body = resp.data.get('body')
            status = resp.status
        else:
            headers = rdata.get('headers', {})
            body = rdata.get('body')
        if isinstance(body, dict):
            body = json.dumps(body)
        return status, headers, body

class TestAdapter(Radapters.HTTPAdapter):
    def __init__(self):
        Radapters.HTTPAdapter.__init__(self)
        self._data = None

    def setData(self, data):
        self._data = data

    @classmethod
    def _httplibResponse(cls, status=None, headers={}, body=None):
        if status is None:
            status = 200
        reason = httplib.responses[status]
        resp = httplib.HTTPResponse(mock.MockObject())
        resp.fp = io.BytesIO()
        resp.fp.write("HTTP/1.1 %s %s\r\n" % (status, reason))
        for k, v in headers.items():
            if k.lower() == 'content-length':
                continue
            h = "%s: %s\r\n" % (k, v)
            resp.fp.write(h.encode('utf-8'))
        if body is not None:
            resp.fp.write("Content-Length: %d\r\n" % len(body))
        resp.fp.write("\r\n")
        if body is not None:
            resp.fp.write(body)
        resp.fp.seek(0)
        resp.begin()
        return resp

    def send(self, request, *args, **kwargs):
        status, headers, body = self._data.getMockedData(request)
        response = Rmodels.Response()
        response = Radapters.HTTPResponse.from_httplib(
                self._httplibResponse(status=status,
                body=body, headers=headers),
                preload_content=False, decode_content=False)
        return self.build_response(request, response)

KeystoneSessionBase = dopenstack.openstackclient.KeystoneSession
class KeystoneSession(KeystoneSessionBase):
    class _Sess(object):
        __slots__ = []
        Calls = []
        Session = None
        Adapter = None
        def __init__(self):
            if self.__class__.Session is not None:
                return
            sess = self.__class__.Session = RSession()
            adapter = self.__class__.Adapter = TestAdapter()
            sess.mount("https://", adapter)
        def request(self, *args, **kwargs):
            self.Calls.append((args, kwargs))
            return self.Session.request(*args, **kwargs)
        @classmethod
        def setData(cls, data):
            cls.Adapter.setData(data)
        def reset(self):
            del self.Calls[:]
    Session = _Sess()
    def __init__(self, *args, **kwargs):
        kwargs.update(session=self.Session)
        KeystoneSessionBase.__init__(self, *args, **kwargs)
    @classmethod
    def setData(cls, data):
        cls.Session.setData(data)
    @classmethod
    def reset(cls):
        cls.Session.reset()

def _t(data):
    return data

_xmlNewCredsBad = """
<descriptorData>
  <username>blahblah</username>
  <password>blippy</password>
</descriptorData>
"""

if __name__ == "__main__":
    testsuite.main()
