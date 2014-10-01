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
        self.failUnlessEqual(node.getPublicDnsName(), '10.210.1.12')
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
             'flavor', ])
        ftypes = [ df.type for df in dsc.getDataFields() ]
        self.failUnlessEqual([ ftypes[0], ftypes[1], ftypes[2]],
            ['str', 'str', 'str', ])
        self.failUnlessEqual([ [ (x.key, x.descriptions.asDict()) for x in ftype ]
            for ftype in [ ftypes[3], ] ],
            [
                [
                    ('1', {None: 'm1.tiny'}),
                    ('2', {None: 'm1.small'}),
                    ('3', {None: 'm1.medium'}),
                    ('4', {None: 'm1.large'}),
                    ('5', {None: 'm1.xlarge'}),
                ],
            ])
        expMultiple = [None, None, None, None,]
        self.failUnlessEqual([ df.multiple for df in dsc.getDataFields() ],
            expMultiple)
        self.failUnlessEqual([ df.required for df in dsc.getDataFields() ],
            [ True, True, None, True,] )
        self.failUnlessEqual([ df.hidden for df in dsc.getDataFields() ],
            [ True, None, None, None,] )
        prefix = self.makeUri(client, "help/targets/drivers/%s/launch/" % self.cloudType)
        self.failUnlessEqual([ df.helpAsDict for df in dsc.getDataFields() ],
            [
                {},
                {None: prefix + 'instanceName.html'},
                {None: prefix + 'instanceDescription.html'},
                {None: prefix + 'flavor.html'},
            ])
        self.failUnlessEqual([ df.getDefault() for df in dsc.getDataFields() ],
            [None, None, None, '1', ])

        self.failUnlessEqual([ df.descriptions.asDict() for df in dsc.getDataFields() ],
            [
                {None: 'Image ID'},
                {None: 'Instance Name'},
                {None: 'Instance Description'},
                {None: 'Flavor'},
            ])
        self.failUnlessEqual([ df.constraintsPresentation for df in dsc.getDataFields() ],
            [
                [{'max': 32, 'constraintName': 'range', 'min': 1}],
                [{'constraintName': 'length', 'value': 32}],
                [{'constraintName': 'length', 'value': 128}],
                [],
            ])

    def testNewInstances(self):
        srv = self.newService()
        uri = self._baseCloudUrl + '/instances'

        imageId = '0000000000000000000000000000000000000001'
        requestXml = _t(mockedData.xml_newInstanceOpenStackTempl % dict(
            imageId=imageId, flavor=1, instanceName="newinst34",
            instanceDescription="newinst34 description",))

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
                instanceDescription="newinst34 description",))
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
                {"status": "stable", "updated": "2013-03-06T00:00:00Z", "media-types": [{"base": "application/json", "type": "application/vnd.openstack.identity-v3+json"}, {"base": "application/xml", "type": "application/vnd.openstack.identity-v3+xml"}], "id": "v3.0", "links": [{"href": "http://openstack1.eng.rpath.com:5000/v3/", "rel": "self"}]},
                {"status": "stable", "updated": "2014-04-17T00:00:00Z", "media-types": [{"base": "application/json", "type": "application/vnd.openstack.identity-v2.0+json"}, {"base": "application/xml", "type": "application/vnd.openstack.identity-v2.0+xml"}], "id": "v2.0", "links": [{"href": "http://openstack1.eng.rpath.com:5000/v2.0/", "rel": "self"}, ]}
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
                    {'endpoints': [{'adminURL': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97', 'id': '1884140635164bf69d6d0f5cdfd1a98c', 'internalURL': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97', 'publicURL': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'nova', 'type': 'compute'},
                    {'endpoints': [{'adminURL': 'http://openstack1.eng.rpath.com:9696/', 'id': '581dcd45918d4f1285f86f66ba81bb63', 'internalURL': 'http://openstack1.eng.rpath.com:9696/', 'publicURL': 'http://openstack1.eng.rpath.com:9696/', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'neutron', 'type': 'network'},
                    {'endpoints': [{'adminURL': 'http://openstack1.eng.rpath.com:8776/v2/44a04a897db842a49ff3f13cf5759a97', 'id': '2899953f4d4a43c4852dfc9b0e8a5c94', 'internalURL': 'http://openstack1.eng.rpath.com:8776/v2/44a04a897db842a49ff3f13cf5759a97', 'publicURL': 'http://openstack1.eng.rpath.com:8776/v2/44a04a897db842a49ff3f13cf5759a97', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'cinder_v2', 'type': 'volumev2'}, 
                    {'endpoints': [{'adminURL': 'http://openstack1.eng.rpath.com:8080', 'id': '09165a102946414492faa7cc7d77c7e3', 'internalURL': 'http://openstack1.eng.rpath.com:8080', 'publicURL': 'http://openstack1.eng.rpath.com:8080', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'swift_s3', 'type': 's3'},
                    {'endpoints': [{'adminURL': 'http://openstack1.eng.rpath.com:9292', 'id': '344144550996447198eb11c4e5b6bab9', 'internalURL': 'http://openstack1.eng.rpath.com:9292', 'publicURL': 'http://openstack1.eng.rpath.com:9292', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'glance', 'type': 'image'},
                    {'endpoints': [{'adminURL': 'http://openstack1.eng.rpath.com:8777', 'id': '3166ece0b2a24e338b998b2382e5c958', 'internalURL': 'http://openstack1.eng.rpath.com:8777', 'publicURL': 'http://openstack1.eng.rpath.com:8777', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'ceilometer', 'type': 'metering'},
                    {'endpoints': [{'adminURL': 'http://openstack1.eng.rpath.com:8000/v1/', 'id': '0be1ad10b0584cd28c70fccb742386ad', 'internalURL': 'http://openstack1.eng.rpath.com:8000/v1/', 'publicURL': 'http://openstack1.eng.rpath.com:8000/v1/', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'heat-cfn', 'type': 'cloudformation'},
                    {'endpoints': [{'adminURL': 'http://openstack1.eng.rpath.com:8776/v1/44a04a897db842a49ff3f13cf5759a97', 'id': '2fe7e8ec6a0b4a49915d0fde8707a507', 'internalURL': 'http://openstack1.eng.rpath.com:8776/v1/44a04a897db842a49ff3f13cf5759a97', 'publicURL': 'http://openstack1.eng.rpath.com:8776/v1/44a04a897db842a49ff3f13cf5759a97', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'cinder', 'type': 'volume'},
                    {'endpoints': [{'adminURL': 'http://openstack1.eng.rpath.com:8773/services/Admin', 'id': '3a5120493aac4268893016bac46bd67b', 'internalURL': 'http://openstack1.eng.rpath.com:8773/services/Cloud', 'publicURL': 'http://openstack1.eng.rpath.com:8773/services/Cloud', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'nova_ec2', 'type': 'ec2'},
                    {'endpoints': [{'adminURL': 'http://openstack1.eng.rpath.com:8004/v1/44a04a897db842a49ff3f13cf5759a97', 'id': '71b396582d394cd1ade54fed2cf0d255', 'internalURL': 'http://openstack1.eng.rpath.com:8004/v1/44a04a897db842a49ff3f13cf5759a97', 'publicURL': 'http://openstack1.eng.rpath.com:8004/v1/44a04a897db842a49ff3f13cf5759a97', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'heat', 'type': 'orchestration'}, 
                    {'endpoints': [{'adminURL': 'http://openstack1.eng.rpath.com:8080/', 'id': '11140882b89b45828b18dac762d1767a', 'internalURL': 'http://openstack1.eng.rpath.com:8080/v1/AUTH_44a04a897db842a49ff3f13cf5759a97', 'publicURL': 'http://openstack1.eng.rpath.com:8080/v1/AUTH_44a04a897db842a49ff3f13cf5759a97', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'swift', 'type': 'object-store'},
                    {'endpoints': [{'adminURL': 'http://openstack1.eng.rpath.com:35357/v2.0', 'id': '36faa60b5cd446c1b3c991fae6475130', 'internalURL': 'http://openstack1.eng.rpath.com:5000/v2.0', 'publicURL': 'http://openstack1.eng.rpath.com:5000/v2.0', 'region': 'RegionOne'}], 'endpoints_links': [], 'name': 'keystone', 'type': 'identity'}],
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
              'links': [{'href': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/34229a3f-f7cd-4a29-ac9e-0321186e7557',
                          'rel': 'self'},
                         {'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/34229a3f-f7cd-4a29-ac9e-0321186e7557',
                          'rel': 'bookmark'},
                         {'href': 'http://openstack1.eng.rpath.com:9292/44a04a897db842a49ff3f13cf5759a97/images/34229a3f-f7cd-4a29-ac9e-0321186e7557',
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
              'links': [{'href': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/9401325c-4dac-436f-936b-4af7a49431fd',
                          'rel': 'self'},
                         {'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/9401325c-4dac-436f-936b-4af7a49431fd',
                          'rel': 'bookmark'},
                         {'href': 'http://openstack1.eng.rpath.com:9292/44a04a897db842a49ff3f13cf5759a97/images/9401325c-4dac-436f-936b-4af7a49431fd',
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
              'links': [{'href': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/04afdb08-90a2-48a1-a6ba-de54940679ad',
                          'rel': 'self'},
                         {'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/04afdb08-90a2-48a1-a6ba-de54940679ad',
                          'rel': 'bookmark'},
                         {'href': 'http://openstack1.eng.rpath.com:9292/44a04a897db842a49ff3f13cf5759a97/images/04afdb08-90a2-48a1-a6ba-de54940679ad',
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
              'links': [{'href': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/215854b1-e1fb-4de4-8557-701254768315',
                          'rel': 'self'},
                         {'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/215854b1-e1fb-4de4-8557-701254768315',
                          'rel': 'bookmark'},
                         {'href': 'http://openstack1.eng.rpath.com:9292/44a04a897db842a49ff3f13cf5759a97/images/215854b1-e1fb-4de4-8557-701254768315',
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
              'links': [{'href': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/9b16fb4a-8e3c-4b85-abe4-60b4c6d0975f',
                          'rel': 'self'},
                         {'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/9b16fb4a-8e3c-4b85-abe4-60b4c6d0975f',
                          'rel': 'bookmark'},
                         {'href': 'http://openstack1.eng.rpath.com:9292/44a04a897db842a49ff3f13cf5759a97/images/9b16fb4a-8e3c-4b85-abe4-60b4c6d0975f',
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
              'links': [{'href': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/2f0bb8a4-8da1-44d2-b2f8-c0bad9e79e0f',
                          'rel': 'self'},
                         {'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/2f0bb8a4-8da1-44d2-b2f8-c0bad9e79e0f',
                          'rel': 'bookmark'},
                         {'href': 'http://openstack1.eng.rpath.com:9292/44a04a897db842a49ff3f13cf5759a97/images/2f0bb8a4-8da1-44d2-b2f8-c0bad9e79e0f',
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
              'links': [{'href': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/710c1a84-7867-4b04-bdbd-dc585e29c48e',
                          'rel': 'self'},
                         {'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/710c1a84-7867-4b04-bdbd-dc585e29c48e',
                          'rel': 'bookmark'},
                         {'href': 'http://openstack1.eng.rpath.com:9292/44a04a897db842a49ff3f13cf5759a97/images/710c1a84-7867-4b04-bdbd-dc585e29c48e',
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
                           'links': [{'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/flavors/2',
                                       'rel': 'bookmark'}]},
               'hostId': '07d94005d463e0fbaeb2dd75bdc36762f93eaea4e6dd92354441aea0',
               'id': '22b896bf-af13-420b-a7db-2fadff3b3279',
               'image': {'id': 'a17f23b5-15e8-48f0-974f-fd0e6b659739',
                          'links': [{'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/a17f23b5-15e8-48f0-974f-fd0e6b659739',
                                      'rel': 'bookmark'}]},
               'key_name': None,
               'links': [{'href': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/servers/22b896bf-af13-420b-a7db-2fadff3b3279',
                           'rel': 'self'},
                          {'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/servers/22b896bf-af13-420b-a7db-2fadff3b3279',
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
               'addresses': {'pdt-network1': [{'OS-EXT-IPS-MAC:mac_addr': 'fa:16:3e:31:f6:70',
                                                 'OS-EXT-IPS:type': 'fixed',
                                                 'addr': '10.210.1.11',
                                                 'version': 4}]},
               'config_drive': '',
               'created': '2014-09-30T13:31:58Z',
               'flavor': {'id': '2',
                           'links': [{'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/flavors/2',
                                       'rel': 'bookmark'}]},
               'hostId': '07d94005d463e0fbaeb2dd75bdc36762f93eaea4e6dd92354441aea0',
               'id': '37208896-004b-4291-bab7-5cd89fcf71b9',
               'image': {'id': 'a17f23b5-15e8-48f0-974f-fd0e6b659739',
                          'links': [{'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/a17f23b5-15e8-48f0-974f-fd0e6b659739',
                                      'rel': 'bookmark'}]},
               'key_name': None,
               'links': [{'href': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/servers/37208896-004b-4291-bab7-5cd89fcf71b9',
                           'rel': 'self'},
                          {'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/servers/37208896-004b-4291-bab7-5cd89fcf71b9',
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
            dict(version=4, addr="10.100.100.%s" % (i+100)),
        ]

    flavors_listDetailed = (200, dict(body={
        'flavors': [
            {
               'OS-FLV-DISABLED:disabled': False,
               'OS-FLV-EXT-DATA:ephemeral': 0,
               'disk': 1,
               'id': '1',
               'links': [
                    {'href': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/flavors/1', 'rel': 'self'},
                    {'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/flavors/1', 'rel': 'bookmark'}],
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
                   {'href': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/flavors/2', 'rel': 'self'},
                   {'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/flavors/2', 'rel': 'bookmark'}],
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
                   {'href': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/flavors/3', 'rel': 'self'},
                   {'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/flavors/3', 'rel': 'bookmark'}],
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
                   {'href': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/flavors/4', 'rel': 'self'},
                   {'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/flavors/4', 'rel': 'bookmark'}],
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
                   {'href': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/flavors/5', 'rel': 'self'},
                   {'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/flavors/5', 'rel': 'bookmark'}],
               'name': 'm1.xlarge',
               'os-flavor-access:is_public': True,
               'ram': 16384,
               'rxtx_factor': 1.0,
               'swap': '',
               'vcpus': 8}
            ]}))

    glance_images_create = (201, dict(body={
        "image": {
            "status": "active",
            "name": "test-misa-11",
            "container_format": 'bare',
            "created_at": "2011-09-01T03:53:25.901097",
            "disk_format": 'raw',
            "updated_at": "2011-09-01T03:53:26.279266",
            "id": 'b6001727-0029-4e9b-afa0-e7aaba8d733b',
            "location": "file:///var/lib/glance/images/12",
            "checksum": "3a2a35081e6c06035ac747715423c316",
            "is_public": True,
            "properties": {},
            "size": 22339
            }}))

    glance_image1 = (200, dict(body=
             {'OS-EXT-IMG-SIZE:size': 12592820224,
              'created': '2014-09-23T23:52:46Z',
              'id': 'b6001727-0029-4e9b-afa0-e7aaba8d733b',
              'links': [{'href': 'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/b6001727-0029-4e9b-afa0-e7aaba8d733b',
                          'rel': 'self'},
                         {'href': 'http://openstack1.eng.rpath.com:8774/44a04a897db842a49ff3f13cf5759a97/images/b6001727-0029-4e9b-afa0-e7aaba8d733b',
                          'rel': 'bookmark'},
                         {'href': 'http://openstack1.eng.rpath.com:9292/44a04a897db842a49ff3f13cf5759a97/images/b6001727-0029-4e9b-afa0-e7aaba8d733b',
                          'rel': 'alternate',
                          'type': 'application/vnd.openstack.image'}],
              'metadata': {'description': 'vhf'},
              'minDisk': 0,
              'minRam': 2048,
              'name': 'test-misa-11',
              'progress': 100,
              'status': 'ACTIVE',
              'updated': '2014-09-23T23:56:51Z'}))

    glance_image1_update = (200, dict(body=dict(
        image=glance_image1[1]['body'])))

    server_create = (200, dict(body={u'server': {u'status': u'BUILD', u'uuid': u'73d29965-aeee-4ebc-ae6a-13dd03b752c8', u'hostId': u'', u'addresses': {}, u'imageRef': 2, u'adminPass': u'Y9VfddavL2AMJMnz', u'flavorRef': u'http://dhcp107.eng.rpath.com:8774/v1.1/flavors/1', u'links': [{u'href': u'http://dhcp107.eng.rpath.com:8774/v1.1/servers/5', u'rel': u'self'}, {u'href': u'http://dhcp107.eng.rpath.com:8774/servers/5', u'rel': u'bookmark'}], u'metadata': {}, u'id': '37208896-004b-4291-bab7-5cd89fcf71b9', u'name': u'test-misa-11'}}))

class MockedClientData(object):
    data = {
        'http://openstack1.eng.rpath.com:5001/' : dict(
            GET = CannedData.discovery,
        ),
        'http://openstack1.eng.rpath.com:5000/v2.0/tokens' : dict(
            POST = CannedData.authenticate,
        ),
        'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/images/detail' : dict(
            GET = CannedData.images_listDetailed,
        ),
        'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/servers/detail' : dict(
            GET = mockedData.MultiResponse([
                CannedData.servers_listDetailed,
                CannedData.servers_listDetailed,
                CannedData.servers_listDetailedWithNetwork,
                CannedData.servers_listDetailedWithNetwork,
            ]),
        ),
        'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/flavors/detail' : dict(
            GET = CannedData.flavors_listDetailed,
        ),
        'http://openstack1.eng.rpath.com:8774/v2/44a04a897db842a49ff3f13cf5759a97/servers' : dict(
            POST = CannedData.server_create,
        ),
        'http://openstack1.eng.rpath.com:9292/v1/images' : dict(
            POST = CannedData.glance_images_create,
            ),
        'http://openstack1.eng.rpath.com:9292/v1/images/b6001727-0029-4e9b-afa0-e7aaba8d733b' : dict(
            GET = CannedData.glance_image1,
            HEAD = '',
            PUT = CannedData.glance_image1_update),
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
            sess.mount("http://", adapter)
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
