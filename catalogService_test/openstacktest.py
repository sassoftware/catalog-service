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
import httplib2
import os
import StringIO

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

class HandlerTest(testbase.TestCase):
    cloudType = 'openstack'
    cloudName = 'openstack1.eng.rpath.com'

    TARGETS = [
        (cloudType, cloudName, dict(
            nova_port = 8443,
            glance_server = 'glance1.eng.rpath.com',
            glance_port = 9443,
            alias = 'openstack1',
            description = 'OpenStack server',
        )),
    ]
    MINT_CFG = testbase.TestCase.MINT_CFG + [
        ('proxy', 'http http://user:pass@host:3129'),
        ('proxy', 'https https://user:pass@host:3129'),
    ]

    USER_TARGETS = [
        ('JeanValjean', cloudType, cloudName, dict(
                username = 'Jean_Valjean',
                auth_token = 'supersikrit',
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
        dopenstack.driver.NovaClientClass = NovaClientClass
        NovaClientClass.HTTPClient.MockedData = MockedClientData()
        dopenstack.driver.GlanceClientClass = GlanceClientClass
        GlanceClientClass.HTTPConnection.MockedData = MockedGlanceData()

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
            '1',
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
            ['product description for bar', None, 'words words SPARKY words'])
        self.assertEquals([x.getBuildDescription() for x in node],
            ['build description for bar 98', None, 'just words and stuff'])
        self.assertEquals([x.getIsDeployed() for x in node],
            [True, True, False])
        self.assertEquals([x.getIsPrivate_rBuilder() for x in node],
            [False, None, False])
        self.assertEquals([x.getProductName() for x in node],
            ['bar project', 'misa-test-euca', 'foo project'])
        self.assertEquals([x.getRole() for x in node],
            ['developer', None, 'developer'])
        self.assertEquals([x.getPublisher() for x in node],
            ['Bob Loblaw', None, 'Bob Loblaw'])
        self.assertEquals([x.getAwsAccountNumber() for x in node],
            [None, None, None])
        self.assertEquals([x.getBuildName() for x in node],
            ['bar project', None, 'foo project'])
        self.assertEquals([x.getIs_rBuilderImage() for x in node],
            [True, False, True])
        self.assertEquals([x.getBuildPageUrl() for x in node],
            [
             'http://test.rpath.local2/project/bar/build?id=98',
             None,
             'http://test.rpath.local2/project/foo/build?id=96'])
        self.assertEquals([ x.getProductCode() for x in node],
            [None, None, None])

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
        targetImageId = '2'
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
        expId = ['4', '5', ]
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
            [None, None, ])
        
        self.failUnlessEqual([x.getPlacement() for x in node],
            [None, None, ])

        self.assertEquals([ x.getProductCode() for x in node], [None, None])

    def testGetInstance1(self):
        srv = self.newService()
        instanceId = '4'
        uri = '%s/instances/%s' % (self._baseCloudUrl, instanceId)
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = self.InstancesHandler()
        node = hndlr.parseString(response.read())

        # Normally we should only get one instance, but the call is mocked
        self.failUnlessEqual(node.getInstanceId(), instanceId)
        self.failUnlessEqual(node.getInstanceName(), 'vincent1')
        self.failUnlessEqual(node.getPublicDnsName(), None)
        self.failUnlessEqual(node.getPrivateDnsName(), '192.168.10.3')

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
  <glance_port>9443</glance_port>
  <glance_server>glance1.eng.rpath.com</glance_server>
  <name>openstack1.eng.rpath.com</name>
  <nova_port>8443</nova_port>
</descriptorData>""" % (client.hostport, self.cloudType, self.cloudName))

    def testGetConfigurationStrangeTargetData(self):
        self.setAdmin(True)
        self.deleteTarget(self.cloudType, 'openstack1.eng.rpath.com')
        dataDict = dict(
            nova_port = '8443',
            glance_server = 'glance2.example.com',
            glance_port = 42,
            alias = 'newbie',
            description = 'Some fake data here',
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
  <glance_port>%s</glance_port>
  <glance_server>%s</glance_server>
  <name>%s</name>
  <nova_port>%s</nova_port>
</descriptorData>""" % (client.hostport, self.cloudType, self.cloudName,
            dataDict['alias'],
            dataDict['description'],
            dataDict['glance_port'],
            dataDict['glance_server'],
            self.cloudName, dataDict['nova_port'],
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
            ['name', 'nova_port', 'glance_server', 'glance_port', 'alias',
             'description'])
        self.failUnlessEqual([ df.type for df in dataFields ],
            [ 'str', 'int', 'str', 'int', 'str', 'str' ])
        self.failUnlessEqual([ df.multiple for df in dataFields ],
            [None] * len(dataFields))
        self.failUnlessEqual([ df.descriptions.asDict() for df in dataFields ],

            [{None: u'Nova Server'}, {None: u'Nova Port'},
             {None: u'Glance Server'}, {None: u'Glance Port'},
             {None: u'Name'}, {None: u'Full Description'}])
        pref = self.makeUri(client,
            "help/targets/drivers/%s/configuration/" % self.cloudType)
        helpData = [ { None : pref + x } for x in [
            'novaServerName.html', 'novaPortNumber.html',
            'glanceServerName.html', 'glancePortNumber.html',
            'alias.html', 'description.html', ] ]
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
            '1',
            'a00000000000000000000000000000000000000a',])

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
  <auth_token>supersikrit</auth_token>
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
  <auth_token>supersikrit</auth_token>
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

        instanceIds = ['5', ]

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
        expInstanceIds = ['5', ]
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
    authentication = (204, dict(headers=
            {'status': '204', 'content-length': '0',
             'x-auth-token': '52371969addeb371a67f27d5d3e4fbb407b97f5f',
             'x-cdn-management-url': '',
             'x-server-management-url': 'http://dhcp107.eng.rpath.com:8774/v1.1/',
             'date': 'Sun, 28 Aug 2011 03:51:31 GMT',
             'x-storage-url': '',
             'content-type': 'text/plain; charset=UTF-8'},
            body=None))

    images_listDetailed = (200, dict(body={u'images': [{u'status': u'ACTIVE', u'updated': u'2011-08-28T02:32:16Z', u'name': u'misa-test', u'links': [{u'href': u'http://dhcp107.eng.rpath.com:8774/v1.1/images/2', u'rel': u'self'}, {u'href': u'http://dhcp107.eng.rpath.com:8774/images/2', u'rel': u'bookmark'}], u'created': u'2011-08-28T02:31:02Z', u'id': 2, u'metadata': {}}, {u'status': u'ACTIVE', u'updated': u'2011-08-28T02:41:43Z', u'name': u'misa-test-euca', u'links': [{u'href': u'http://dhcp107.eng.rpath.com:8774/v1.1/images/1', u'rel': u'self'}, {u'href': u'http://dhcp107.eng.rpath.com:8774/images/1', u'rel': u'bookmark'}], u'created': u'2011-08-27T21:46:34Z', u'id': 1, u'metadata': {}}]}))

    servers_listDetailed = (200, dict(body={u'servers': [
        {
            u'status': u'ACTIVE',
            u'uuid': u'4de97a57-4f76-4189-89f8-2628c6678841',
            u'hostId': u'6ba15e416f9f7c0fb07572e513e2da11a621052e7bb93c4f47d1b889',
            u'addresses': {
                u'public': [],
                u'private': [{u'version': 4, u'addr': u'192.168.10.3'}]
            },
            u'imageRef': 1,
            u'links': [
                {u'href': u'http://dhcp107.eng.rpath.com:8774/v1.1/servers/4',
                    u'rel': u'self'},
                {u'href': u'http://dhcp107.eng.rpath.com:8774/servers/4',
                    u'rel': u'bookmark'},
            ],
            u'metadata': {},
            u'id': 4,
            u'name': u'vincent1',
        },
        {
            u'status': u'ACTIVE',
            u'uuid': u'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeee1',
            u'hostId': u'decafbad0deadbeef0decafbad0deadbeef1decafbad0deadbeef000',
            u'addresses': {
                u'public': [],
                u'private': [{u'version': 4, u'addr': u'192.168.10.4'}]
            },
            u'imageRef': 2,
            u'links': [
                {u'href': u'http://dhcp107.eng.rpath.com:8774/v1.1/servers/4',
                    u'rel': u'self'},
                {u'href': u'http://dhcp107.eng.rpath.com:8774/servers/4',
                    u'rel': u'bookmark'},
            ],
            u'metadata': {},
            u'id': 5,
            u'name': u'jules1',
        },
    ]}))
    servers_listDetailedWithNetwork = (
        servers_listDetailed[0], copy.deepcopy(servers_listDetailed[1]))
    for i, srv in enumerate(servers_listDetailedWithNetwork[1]['body']['servers']):
        srv['addresses']['public'] = [
            dict(version=4, addr="10.100.100.%s" % (i+100)),
        ]

    flavors_listDetailed = (200, dict(body={u'flavors': [{u'disk': 40, u'ram': 4096, u'id': 3, u'links': [{u'href': u'http://dhcp107.eng.rpath.com:8774/v1.1/flavors/3', u'rel': u'self'}, {u'href': u'http://dhcp107.eng.rpath.com:8774/flavors/3', u'rel': u'bookmark'}], u'name': u'm1.medium'}, {u'disk': 80, u'ram': 8192, u'id': 4, u'links': [{u'href': u'http://dhcp107.eng.rpath.com:8774/v1.1/flavors/4', u'rel': u'self'}, {u'href': u'http://dhcp107.eng.rpath.com:8774/flavors/4', u'rel': u'bookmark'}], u'name': u'm1.large'}, {u'disk': 0, u'ram': 512, u'id': 1, u'links': [{u'href': u'http://dhcp107.eng.rpath.com:8774/v1.1/flavors/1', u'rel': u'self'}, {u'href': u'http://dhcp107.eng.rpath.com:8774/flavors/1', u'rel': u'bookmark'}], u'name': u'm1.tiny'}, {u'disk': 160, u'ram': 16384, u'id': 5, u'links': [{u'href': u'http://dhcp107.eng.rpath.com:8774/v1.1/flavors/5', u'rel': u'self'}, {u'href': u'http://dhcp107.eng.rpath.com:8774/flavors/5', u'rel': u'bookmark'}], u'name': u'm1.xlarge'}, {u'disk': 20, u'ram': 2048, u'id': 2, u'links': [{u'href': u'http://dhcp107.eng.rpath.com:8774/v1.1/flavors/2', u'rel': u'self'}, {u'href': u'http://dhcp107.eng.rpath.com:8774/flavors/2', u'rel': u'bookmark'}], u'name': u'm1.small'}]}))

    glance_images_create = (201, dict(body='''{"image": {"status": "active", "name": "TBD", "deleted": false, "container_format": null, "created_at": "2011-09-01T03:53:25.901097", "disk_format": null, "updated_at": "2011-09-01T03:53:26.279266", "id": 12, "location": "file:///var/lib/glance/images/12", "checksum": "3a2a35081e6c06035ac747715423c316", "is_public": true, "deleted_at": null, "properties": {}, "size": 22339}}'''))

    server_create = (200, dict(body={u'server': {u'status': u'BUILD', u'uuid': u'73d29965-aeee-4ebc-ae6a-13dd03b752c8', u'hostId': u'', u'addresses': {}, u'imageRef': 2, u'adminPass': u'Y9VfddavL2AMJMnz', u'flavorRef': u'http://dhcp107.eng.rpath.com:8774/v1.1/flavors/1', u'links': [{u'href': u'http://dhcp107.eng.rpath.com:8774/v1.1/servers/5', u'rel': u'self'}, {u'href': u'http://dhcp107.eng.rpath.com:8774/servers/5', u'rel': u'bookmark'}], u'metadata': {}, u'id': 5, u'name': u'test-misa-11'}}))

class MockedClientData(object):
    data = {
        '/v1.1/' : dict(
            GET = CannedData.authentication,
        ),
        '/v1.1//images/detail' : dict(
            GET = CannedData.images_listDetailed,
        ),
        '/v1.1//servers/detail' : dict(
            GET = mockedData.MultiResponse([
                CannedData.servers_listDetailed,
                CannedData.servers_listDetailed,
                CannedData.servers_listDetailedWithNetwork,
                CannedData.servers_listDetailedWithNetwork,
            ]),
        ),
        '/v1.1//flavors/detail' : dict(
            GET = CannedData.flavors_listDetailed,
        ),
        '/v1.1//servers' : dict(
            POST = CannedData.server_create,
        ),
    }
    def __init__(self):
        self.data = copy.deepcopy(self.__class__.data)

    def getResponse(self, method, path, body=None):
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
        headers.update(status=str(status))
        resp = httplib2.Response(headers)
        return resp, body

class MockedGlanceData(MockedClientData):
    data = {
        '/v1/images' : dict(POST=CannedData.glance_images_create),
    }
    def getResponse(self, method, path, body=None):
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
        response = mockedData.MockedResponse(body)
        response.status = status
        response.msg = "Blah?"
        response.reason = "Blah?"
        return response

class NovaClientClass(dopenstack.openstackclient.NovaClient):
    class HTTPClient(nvclient.HTTPClient):
        MockedData = None
        def request(self, url, method, *args, **kwargs):
            body = kwargs.get('body')
            path = httplib2.urlparse.urlsplit(url).path
            resp = self.MockedData.getResponse(method, path, body=body)
            return resp

    def __init__(self, username, api_key, project_id, auth_url, timeout=None):
        dopenstack.openstackclient.NovaClient.__init__(self, username, api_key,
                project_id, auth_url, timeout=None)
        self.client = self.HTTPClient(username, api_key,
                project_id, auth_url, timeout=timeout)

class GlanceClientClass(dopenstack.openstackclient.GlanceClient):
    class HTTPConnection(httplib.HTTPConnection):
        MockedData = None
        def putrequest(self, method, url, *args, **kwargs):
            self._method = method
            self._url = url
            self._headers = {}
            self._body = []
        def putheader(self, header, *args, **kwargs):
            self._headers[header] = (args, kwargs)
        def endheaders(self, *args, **kwargs):
            pass
        def send(self, str):
            self._body.append(str)
        def getresponse(self):
            ret = self.MockedData.getResponse(self._method, self._url)
            return ret
    class HTTPSConnection(httplib.HTTPSConnection):
        "Not used"
    def get_connection_type(self):
        """
        Returns the proper connection type
        """
        if self.use_ssl:
            return self.HTTPSConnection
        return self.HTTPConnection


def _t(data):
    return data

_xmlNewCredsBad = """
<descriptorData>
  <username>blahblah</username>
  <auth_token>blippy</auth_token>
</descriptorData>
"""

if __name__ == "__main__":
    testsuite.main()
