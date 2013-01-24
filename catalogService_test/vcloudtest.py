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

import os
import re
import urllib

from conary.lib import util

import testbase

from catalogService.restClient import ResponseError

from catalogService.rest import baseDriver
from catalogService.rest.drivers import vcloud as dvcloud
from catalogService.rest.models import clouds
from catalogService.rest.models import credentials
from catalogService.rest.models import descriptor
from catalogService.rest.models import images
from catalogService.rest.models import instances

from catalogService_test import mockedData

class HandlerTest(testbase.TestCase):
    cloudType = 'vcloud'
    serverName = 'vcloud.eng.rpath.com'
    organization = 'rPath'
    cloudName = "%s-%s" % (serverName, organization)

    TARGETS = [
        (cloudType, cloudName, dict(
            organization = 'rPath',
            alias = 'vcloud target',
            description = 'description for vcloud target',
            port = 1443,
            serverName = serverName,
        )),
    ]
    MINT_CFG = testbase.TestCase.MINT_CFG + [
        ('proxy', 'http http://user:pass@host:3129'),
        ('proxy', 'https https://user:pass@host:3129'),
    ]

    USER_TARGETS = [
        ('JeanValjean', cloudType, cloudName, dict(
                username = 'jean_valjean',
                password = 'cosette123',
            )),
    ]

    _baseCloudUrl = 'clouds/%s/instances/%s' % (cloudType, cloudName)

    class InstancesHandler(instances.Handler):
        instanceClass = dvcloud.driver.Instance

    def setUp(self):
        testbase.TestCase.setUp(self)
        self.mockedData = MockedClientData()
        self._mockRequest()
        # Speed things up a little
        self.mock(dvcloud.vcloudclient.RestClient,
            'TIMEOUT_VAPP_INSTANTIATED', .1)
        self.mock(dvcloud.vcloudclient.RestClient,
            'TIMEOUT_OVF_DESCRIPTOR_PROCESSED', .1)
        self.mock(dvcloud.vcloudclient.VCloudClient,
            'LAUNCH_NETWORK_TIMEOUT', 10)
        self.mock(dvcloud.vcloudclient.VCloudClient,
            'LAUNCH_TIMEOUT', 10)
        self.mock(dvcloud.vcloudclient.VCloudClient,
            'WAIT_RUNNING_STATE_SLEEP', .1)
        self.mock(dvcloud.vcloudclient.VCloudClient,
            'WAIT_NETWORK_SLEEP', .1)

    def _mockRequest(self, **kwargs):
        origClient = dvcloud.vcloudclient.RestClient
        class MockClient(origClient):
            def connect(slf):
                pass
            def request(slf, method, body=None, headers=None,
                    contentLength=None, callback=None):
                resp = self.mockedData.getResponse(method, slf.path, body)
                if resp.status != 200:
                    raise ResponseError(resp.status, resp.reason, {}, resp)
                return resp
        self.mock(dvcloud.vcloudclient, 'RestClient', MockClient)

    def testNewCloud(self):
        srv = self.newService()
        uri = 'clouds/%s/instances' % (self.cloudType, )
        client = self.newClient(srv, uri)

        reqData = _xmlNewCloud
        response = client.request('POST', reqData)

        hndl = clouds.Handler()
        node = hndl.parseString(response.read())

        cloudId = "http://%s/TOPLEVEL/clouds/%s/instances/%s" % (
            client.hostport, self.cloudType, 'vcloud2.eng.rpath.com-rPath')
        self.failUnlessEqual(node.getId(), cloudId)
        self.failUnlessEqual(node.getCloudAlias(), 'vcloud2')
        self.failUnlessEqual(node.getCloudName(), 'vcloud2.eng.rpath.com-rPath')
        self.failUnlessEqual(node.getType().getText(), self.cloudType)

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

        # Enumerate clouds - we should have 2 of them now
        uri = 'clouds/%s/instances' % (self.cloudType, )
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndl = clouds.Handler()
        nodes = hndl.parseString(response.read())
        self.failUnlessEqual(
            [ x.getCloudAlias() for x in nodes ],
            [ 'vcloud target', 'vcloud2' ])

        # Try to enumerate images - it should fail
        uri = 'clouds/%s/instances/%s/images' % (self.cloudType,
            'vcloud2.eng.rpath.com-rPath')
        client = self.newClient(srv, uri)
        resp = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(resp.status, 400)
        self.assertXMLEquals(resp.contents, '<?xml version="1.0" encoding="UTF-8"?>\n<fault>\n  <code>400</code>\n  <message>Target credentials not set for user</message>\n</fault>')

    def testSetCredentials(self):
        cloudName = 'virtcenter.eng.rpath.com'
        srv = self.newService()
        uri = self._baseCloudUrl + '/users/%(username)s/credentials?_method=PUT'

        hndlr = credentials.Handler()

        client = self.newClient(srv, uri)
        response = client.request('POST', body = _xmlNewCreds)

        data = response.read()
        node = hndlr.parseString(data)

        self.failUnlessEqual(node.getValid(), True)

        # Make sure credentials made it

        creds = self.restdb.targetMgr.getTargetCredentialsForUser(
            self.cloudType, self.cloudName, 'JeanValjean')
        self.failUnlessEqual(creds, dict(username='abc',
                                         password='12345678'))


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
            [ 'vcloud target' ])

        self.failUnlessEqual([x.getDescription() for x in nodes],
            ['description for vcloud target'])

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
            '169',
            'sha1ForOvf101111111111111111111111111111',
            'vappTemplate-1537853377',
        ]
        self.failUnlessEqual([x.getImageId() for x in node], imageIds)
        # make sure the ?_method=GET portion of the URI didn't persist
        self.failUnlessEqual([x.getId() for x in node],
            [ self.makeUri(client,
                "%s/%s" % (correctedUri, x)) for x in imageIds ])

        # this data comes from the mockModule for mint. we're just testing
        # that it gets integrated
        self.assertEquals([x.getProductDescription() for x in node],
                ['foo layered product description', 'words words SPARKY words',
                    None,])
        self.assertEquals([x.getBuildDescription() for x in node],
                ['foo layered description', 'just words and stuff',
                    None,])
        self.assertEquals([x.getIsPrivate_rBuilder() for x in node],
            [False, False, None,])
        self.assertEquals([x.getProductName() for x in node],
            ['foo layered', 'foo project', 'test 1',])
        self.assertEquals([x.getRole() for x in node],
            ['developer', 'developer', None])
        self.assertEquals([x.getPublisher() for x in node],
            ['Bob Loblaw', 'Bob Loblaw', None])
        self.assertEquals([x.getAwsAccountNumber() for x in node],
                [None, None, None])
        self.assertEquals([x.getBuildName() for x in node],
            ['foo layered', 'foo project', None])
        self.assertEquals([x.getIs_rBuilderImage() for x in node],
            [True, True, False])
        self.assertEquals([x.getBuildPageUrl() for x in node],
            ['http://test.rpath.local2/project/foo/build?id=169',
             'http://test.rpath.local2/project/foo/build?id=69',
             None,])
        self.assertEquals([ x.getProductCode() for x in node],
            [None, None, None])

    def testGetImage1(self):
        srv = self.newService()
        imageId = 'sha1ForOvf101111111111111111111111111111'
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
            ['69/some-file-6-1-x86'])

        # Should be able to fetch the image with the target image id too
        targetImageId = 'vappTemplate-1537853377'
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
            [targetImageId])
        self.failUnlessEqual([ x.getLongName() for x in node],
            ['test 1'])


    def testGetInstances1(self):
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
        expId = ['vm-1366228531', 'vm-8675309', ]
        self.failUnlessEqual([x.getInstanceId() for x in node],
            expId)
        self.failUnlessEqual([x.getId() for x in node],
            [ self.makeUri(client, "%s/%s" % (uri, urllib.quote(x).replace('%', '%%'))) for x in expId ])
        self.failUnlessEqual([x.getCloudName() for x in node],
            [ self.cloudName ] * len(node))
        self.failUnlessEqual([x.getCloudType() for x in node],
            [ self.cloudType ] * len(node))
        self.failUnlessEqual([x.getCloudAlias() for x in node],
            [ 'vcloud target' ] * len(node))

        self.failUnlessEqual([x.getInstanceName() for x in node],
            [
                'test 21', 'test 101',
            ])
        self.failUnlessEqual([x.getInstanceDescription() for x in node],
            [
                '', '',
            ])
        self.failUnlessEqual([x.getState() for x in node],
            [
                'powered_off', 'powered_off',
            ])
        self.failUnlessEqual([x.getLaunchTime() for x in node],
            [ None, None, ])
        
        self.failUnlessEqual([x.getPlacement() for x in node],
            [ None, None, ])

        self.assertEquals([ x.getProductCode() for x in node], [None, None, ])

    def testGetInstance1(self):
        instanceId = 'vm-1366228531'
        srv = self.newService()
        uri = '%s/instances/%s' % (self._baseCloudUrl, instanceId)
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = self.InstancesHandler()
        node = hndlr.parseString(response.read())

        # Normally we should only get one instance, but the call is mocked
        self.failUnlessEqual(node.getInstanceId(), instanceId)
        self.failUnlessEqual(node.getState(), 'powered_off')

    def testGetInstance2(self):
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
  <alias>vcloud target</alias>
  <description>description for vcloud target</description>
  <organization>rPath</organization>
  <port>1443</port>
  <serverName>vcloud.eng.rpath.com</serverName>
</descriptorData>""" % (client.hostport, self.cloudType, self.cloudName,))

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

    def testGetConfigurationDescriptor(self):
        srv = self.newService()
        uri = 'clouds/%s/descriptor/configuration' % (self.cloudType, )

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getDisplayName(), "vCloud Configuration")
        self.failUnlessEqual(dsc.getDescriptions(),
            {None : 'Configure VMware vCloud'})
        dataFields = dsc.getDataFields()
        self.failUnlessEqual([ df.name for df in dataFields ],
            ['serverName', 'port', 'alias', 'description', 'organization', ])
        self.failUnlessEqual([ df.type for df in dataFields ],
            ['str', 'int', 'str', 'str', 'str', ])
        self.failUnlessEqual([ df.multiple for df in dataFields ],
            [None] * len(dataFields))
        self.failUnlessEqual([ df.descriptions.asDict() for df in dataFields ],
            [{None : 'Server Address'}, {None: 'Server Port'}, {None : 'Name'},
              {None : 'Full Description'},  {None: 'Organization'},])
        pref = self.makeUri(client,
            "help/targets/drivers/%s/configuration/" % self.cloudType)
        helpData = [ { None : pref + x } for x in [
            'serverName.html', 'serverPort.html', 'alias.html',
            'description.html', 'organization.html', ]]
        self.failUnlessEqual([ df.helpAsDict for df in dataFields ],
            helpData)

    def testGetCredentials(self):
        srv = self.newService()
        uri = self._baseCloudUrl + '/users/%(username)s/credentials'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        data = response.read()
        self.failUnlessEqual(data, """\
<?xml version='1.0' encoding='UTF-8'?>
<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/%s/instances/%s/users/JeanValjean/credentials">
  <username>jean_valjean</username>
  <password>cosette123</password>
</descriptorData>
""" %
        (client.hostport, self.cloudType, self.cloudName))

        # Wrong user name
        uri = self._baseCloudUrl + '/users/NOSUCHUSER/credentials'
        client = self.newClient(srv, uri)
        e = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(e.status, 401)

        # bad cloud name (this should probably be moved to the instances test)
        uri = 'clouds/%s/instances/badcloud.eng.rpath.com/users/NOSUCHUSER/credentials' % (self.cloudType, )
        client = self.newClient(srv, uri)
        e = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(e.status, 404)

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

    def testGetImageDeploymentDescriptor(self):
        srv = self.newService()
        uri = self._baseCloudUrl + '/descriptor/deployImage'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getRootElement(), "newImage")
        self.failUnlessEqual(dsc.getDisplayName(), 'VMware vCloud Image Upload Parameters')
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'VMware vCloud Image Upload Parameters'})
        self.failUnlessEqual([ df.name for df in dsc.getDataFields() ],
            ['imageId', 'imageName', 'imageDescription',
             'catalog', 'dataCenter', ])

    def testGetLaunchDescriptorNoNetworks(self):
        self.mockedData.data['/api/v1.0/vdc/52889018'] = dict(
            GET = CannedData.getVdc52889018NoNetworks,
        )
        srv = self.newService()
        uri = self._baseCloudUrl + '/descriptor/launch'

        client = self.newClient(srv, uri)
        e = self.assertRaises(ResponseError, client.request, 'GET')
        self.assertEquals(e.status, 400)
        self.assertEquals(e.reason, 'Unable to find a functional datacenter for user jean_valjean')

    def testGetImageDeploymentDescriptorNoCatalogs(self):
        self.mockedData.data['/api/v1.0/org/335573498'] = dict(
            GET = CannedData.getOrgNoCatalogs,
        )
        srv = self.newService()
        uri = self._baseCloudUrl + '/descriptor/deployImage'

        client = self.newClient(srv, uri)
        e = self.assertRaises(ResponseError, client.request, 'GET')
        self.assertEquals(e.status, 400)
        self.assertEquals(e.reason, 'Unable to find writable catalogs for user jean_valjean')


    def testGetLaunchDescriptor(self):
        srv = self.newService()
        uri = self._baseCloudUrl + '/descriptor/launch'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getRootElement(), "newInstance")
        self.failUnlessEqual(dsc.getDisplayName(), 'VMware vCloud Launch Parameters')
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'VMware vCloud Launch Parameters'})
        self.failUnlessEqual([ df.name for df in dsc.getDataFields() ],
            ['imageId', 'instanceName', 'instanceDescription',
             'catalog', 'dataCenter', 'network-vdc-52889018', ])
        ftypes = [ df.type for df in dsc.getDataFields() ]
        self.failUnlessEqual([ ftypes[0], ftypes[1], ftypes[2]],
            ['str', 'str', 'str'])
        self.failUnlessEqual([ [ (x.key, x.descriptions.asDict()) for x in ftype ]
            for ftype in [ ftypes[3], ftypes[4], ftypes[5], ] ],
            [
                [
                    ('catalog-1007548327', {None: u'misa-catalog-1'}),
                    ('catalog-1422628290', {None: u'misa-catalog-2'}),
                    ('catalog-2029780577', {None: u'rpath testing'}),
                ],
                [
                    ('vdc-52889018', {None: u'rPath'}),
                ],
                [
                    ('network-2072223164', {None: u'org1-network'}),
                    ('network-2009726362', {None: u'internal-192'}),
                ],
            ])
        expMultiple = [None, None, None, None, None, None]
        self.failUnlessEqual([ df.multiple for df in dsc.getDataFields() ],
            expMultiple)
        self.failUnlessEqual([ df.required for df in dsc.getDataFields() ],
            [ True, True, None, True, True, True, ] )
        self.failUnlessEqual([ df.hidden for df in dsc.getDataFields() ],
            [ True, None, None, None, None, None, ] )
        prefix = self.makeUri(client, "help/targets/drivers/%s/launch/" % self.cloudType)
        self.failUnlessEqual([ df.helpAsDict for df in dsc.getDataFields() ],
            [
                {},
                {None: prefix + 'instanceName.html'},
                {None: prefix + 'instanceDescription.html'},
                {None: prefix + 'catalog.html'},
                {None: prefix + 'dataCenter.html'},
                {None: prefix + 'network.html'},
            ])
        self.failUnlessEqual([ df.getDefault() for df in dsc.getDataFields() ],
                [None, None, None, 'catalog-1007548327', 'vdc-52889018',
                    'network-2072223164', ])

        self.failUnlessEqual([ df.descriptions.asDict() for df in dsc.getDataFields() ],
            [
                {None: 'Image ID'},
                {None: 'Instance Name'},
                {None: 'Instance Description'},
                {None: u'Catalog'},
                {None: u'Data Center'},
                {None: u'Network'},
            ])
        self.failUnlessEqual([ df.constraintsPresentation for df in dsc.getDataFields() ],
            [
                [{'max': 32, 'constraintName': 'range', 'min': 1}],
                [{'constraintName': 'length', 'value': 32}],
                [{'constraintName': 'length', 'value': 128}],
                [],
                [],
                [],
            ])

    def testDeployImage1(self):
        uri = self._baseCloudUrl + '/images'

        imageId = 'sha1ForOvf101111111111111111111111111111'
        fakeDaemonize = lambda slf, *args, **kwargs: slf.function(*args, **kwargs)

        srv, client, job, response = self._setUpNewImageTest(
            self.cloudName, fakeDaemonize, '', imageId = imageId)

        jobUrlPath = 'jobs/types/image-deployment/jobs/1'
        imageUrlPath = '%s/images/%s' % (self._baseCloudUrl, imageId)

        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))
        self.failUnlessEqual(job.get_imageId(), self.makeUri(client, imageUrlPath))
        job = self.waitForJob(srv, jobUrlPath, "Completed")
        expImageIds = [ 'vappTemplate-90220688' ]
        self.failUnlessEqual(
            [ os.path.basename(x.get_href()) for x in job.resultResource],
            expImageIds)
        imageId = 'vappTemplate-90220688'
        uri = '%s/images/%s' % (self._baseCloudUrl, imageId)

        # Make sure we can address that image with this new id
        client = self.newClient(srv, uri)
        response = client.request('GET')
        self.failUnlessEqual(response.status, 200)

        # Grab the job
        client = self.newClient(srv, jobUrlPath)
        response = client.request('GET')

        job = self.getJobFromResponse(response)
        self.failUnlessEqual([ x.get_content() for x in job.history ],
            [
                'Running',
                'Downloading image',
                'Exploding archive',
                'Uploading image to VMware vCloud',
                'Creating vApp template',
                'Waiting for OVF descriptor to be processed',
                'Waiting for OVF descriptor to be processed',
                'OVF descriptor uploaded',
                'Waiting for powered off status',
                'Resource name: image-foo',
                'Done'])
        self.failUnlessEqual(job.get_statusMessage(), 'Done')

    def testNewInstancesWithDeployment(self):
        uri = self._baseCloudUrl + '/instances'

        imageId = 'sha1ForOvf101111111111111111111111111111'
        fakeDaemonize = lambda slf, *args, **kwargs: slf.function(*args, **kwargs)

        srv, client, job, response = self._setUpNewInstanceTest(
            self.cloudName, fakeDaemonize, '', imageId = imageId)

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        imageUrlPath = '%s/images/%s' % (self._baseCloudUrl, imageId)

        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))
        self.failUnlessEqual(job.get_imageId(), self.makeUri(client, imageUrlPath))
        job = self.waitForJob(srv, jobUrlPath, "Completed")
        expInstanceIds = [ 'vm-8675309' ]
        self.failUnlessEqual(
            [ os.path.basename(x.get_href()) for x in job.resultResource],
            expInstanceIds)
        imageId = 'vappTemplate-90220688'
        uri = '%s/images/%s' % (self._baseCloudUrl, imageId)

        # Make sure we can address that image with this new id
        client = self.newClient(srv, uri)
        response = client.request('GET')
        self.failUnlessEqual(response.status, 200)

        # Grab the job
        client = self.newClient(srv, jobUrlPath)
        response = client.request('GET')

        job = self.getJobFromResponse(response)
        self.failUnlessEqual([ x.get_content() for x in job.history ],
            [
                'Launching instance from image sha1ForOvf101111111111111111111111111111 (type VMWARE_ESX_IMAGE)',
                'Downloading image',
                'Exploding archive',
                'Uploading image to VMware vCloud',
                'Creating vApp template',
                'Waiting for OVF descriptor to be processed',
                'Waiting for OVF descriptor to be processed',
                'OVF descriptor uploaded',
                'Waiting for powered off status',
                'Resource name: vapp-template-some-file-6-1-x86',
                'Waiting for task to finish',
                'Resource name: instance-foo',
                'Renaming vm: test 101 -> instance-foo',
                'Uploading initial configuration',
                'Resource name: Credentials for instance-foo',
                "Attaching media 'credentials iso' to 'test 101'",
                "Powering on 'vapp 101'",
                'Instance launched',
                'Instance(s) running: vm-8675309',
                'Waiting for network information for vm-8675309',
                'Instance vm-8675309: 10.11.12.13',
                'Done',
            ])
        self.failUnlessEqual(job.get_statusMessage(), 'Done')


    def _setUpNewImageTest(self, cloudName, daemonizeFunc, imageName,
            imageId = None, downloadFileFunc = None, asOvf = True):
        self._mockFunctions(daemonizeFunc=daemonizeFunc,
            downloadFileFunc=downloadFileFunc, asOvf=asOvf)
        if not imageId:
            imageId = 'sha1ForOvf101111111111111111111111111111'
        cloudType = dvcloud.driver.cloudType

        srv = self.newService()
        uri = 'clouds/%s/instances/%s/images' % (cloudType, cloudName)

        requestXml = mockedData.xml_newImageVCloud1 % imageId
        client = self.newClient(srv, uri)
        response = client.request('POST', requestXml)

        job = self.getJobFromResponse(response)
        return srv, client, job, response


    def _setUpNewInstanceTest(self, cloudName, daemonizeFunc, imageName,
            imageId = None, downloadFileFunc = None, asOvf = True):
        self._mockFunctions(daemonizeFunc=daemonizeFunc,
            downloadFileFunc=downloadFileFunc, asOvf=asOvf)
        if not imageId:
            imageId = 'sha1ForOvf101111111111111111111111111111'
        cloudType = dvcloud.driver.cloudType

        srv = self.newService()
        uri = 'clouds/%s/instances/%s/instances' % (cloudType, cloudName)

        requestXml = mockedData.xml_newInstanceVCloud1 % imageId
        client = self.newClient(srv, uri)
        response = client.request('POST', requestXml)

        job = self.getJobFromResponse(response)
        return srv, client, job, response


    def _mockFunctions(self, daemonizeFunc, downloadFileFunc, asOvf=True):
        self.mock(baseDriver.CatalogJobRunner, 'backgroundRun', daemonizeFunc)

        if downloadFileFunc:
            fakeDownloadFile = downloadFileFunc
        else:
            def fakeDownloadFile(slf, url, destFile, headers = None):
                file(destFile, "w").write(url)

        class ModifiedArchive(baseDriver.Archive):
            def identify(slf):
                workdir = slf.path[:-4]
                wself = baseDriver.weakref.ref(slf)
                slf.archive = slf.CommandArchive(wself, workdir, cmd=[])
                baseDir = os.path.join(workdir, 'some-file-6-1-x86')
                util.mkdirChain(baseDir)
                if asOvf:
                    fileName = os.path.join(baseDir, 'foo.ovf')
                    file(fileName, "w").write(mockedData.vmwareOvfDescriptor1)
                    # Create a vmdk file (zeros only, in our case)
                    fileName = os.path.join(baseDir, "some-file-6-1-x86.vmdk")
                    f = file(fileName, "w")
                    f.seek(10 * 1024 * 1024 - 1)
                    f.write('\0')
                    f.close()
                else:
                    fileName = os.path.join(baseDir, 'foo.vmx')
                    file(fileName, "w")
            def extract(slf):
                slf.log("Exploding archive")

        oldGetCredentialsIsoFile = dvcloud.driver.getCredentialsIsoFile
        def fakeGetCredentialsIsoFile(slf):
            ret = oldGetCredentialsIsoFile(slf)
            # Rename ISO file to something predictible
            dest = os.path.join(os.path.dirname(ret), 'credentials.iso')
            os.rename(ret, dest)
            return dest

        self.mock(dvcloud.driver, "downloadFile", fakeDownloadFile)
        self.mock(dvcloud.driver, "Archive", ModifiedArchive)
        self.mock(dvcloud.driver, "getCredentialsIsoFile", fakeGetCredentialsIsoFile)
        cont = []
        def fakeGenerateString(slf, keyLength):
            ret = "00000000-0000-0000-%04d-000000000000" % len(cont)
            cont.append(ret)
            return ret

        self.mock(dvcloud.driver.instanceStorageClass, '_generateString',
            fakeGenerateString)

class CannedData(object):
    versions = """\
<?xml version="1.0" encoding="UTF-8"?>
<SupportedVersions xmlns="http://www.vmware.com/vcloud/versions" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.vmware.com/vcloud/versions http://vcloud.eng.rpath.com/api/versions/schema/versions.xsd">
    <VersionInfo>
        <Version>1.0</Version>
        <LoginUrl>https://vcloud.eng.rpath.com/api/v1.0/login</LoginUrl>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.catalog+xml</MediaType>
            <ComplexTypeName>CatalogType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.catalogItem+xml</MediaType>
            <ComplexTypeName>CatalogItemType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.error+xml</MediaType>
            <ComplexTypeName>ErrorType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.instantiateOvfParams+xml</MediaType>
            <ComplexTypeName>InstantiateOvfParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.media+xml</MediaType>
            <ComplexTypeName>MediaType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.network+xml</MediaType>
            <ComplexTypeName>NetworkType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.org+xml</MediaType>
            <ComplexTypeName>OrgType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.orgList+xml</MediaType>
            <ComplexTypeName>OrgListType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.task+xml</MediaType>
            <ComplexTypeName>TaskType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.tasksList+xml</MediaType>
            <ComplexTypeName>TasksListType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.uploadVAppTemplateParams+xml</MediaType>
            <ComplexTypeName>UploadVAppTemplateParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.vApp+xml</MediaType>
            <ComplexTypeName>VAppType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.vAppTemplate+xml</MediaType>
            <ComplexTypeName>VAppTemplateType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.vm+xml</MediaType>
            <ComplexTypeName>VmType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.vdc+xml</MediaType>
            <ComplexTypeName>VdcType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.vmPendingAnswer+xml</MediaType>
            <ComplexTypeName>VmQuestionAnswerType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.composeVAppParams+xml</MediaType>
            <ComplexTypeName>ComposeVAppParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.cloneVAppParams+xml</MediaType>
            <ComplexTypeName>CloneVAppParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.cloneMediaParams+xml</MediaType>
            <ComplexTypeName>CloneMediaParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.cloneVAppTemplateParams+xml</MediaType>
            <ComplexTypeName>CloneVAppTemplateParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.controlAccess+xml</MediaType>
            <ComplexTypeName>ControlAccessParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.deployVAppParams+xml</MediaType>
            <ComplexTypeName>DeployVAppParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.instantiateVAppTemplateParams+xml</MediaType>
            <ComplexTypeName>InstantiateVAppTemplateParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.mediaInsertOrEjectParams+xml</MediaType>
            <ComplexTypeName>MediaInsertOrEjectParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.networkConfigSection+xml</MediaType>
            <ComplexTypeName>NetworkConfigSectionType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.networkConnectionSection+xml</MediaType>
            <ComplexTypeName>NetworkConnectionSectionType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.vmPendingQuestion+xml</MediaType>
            <ComplexTypeName>VmPendingQuestionType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.rasdItem+xml</MediaType>
            <ComplexTypeName>RASD_Type</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.rasdItemsList+xml</MediaType>
            <ComplexTypeName>RasdItemsListType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.screenTicket+xml</MediaType>
            <ComplexTypeName>ScreenTicketType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.undeployVAppParams+xml</MediaType>
            <ComplexTypeName>UndeployVAppParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.captureVAppParams+xml</MediaType>
            <ComplexTypeName>CaptureVAppParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.recomposeVAppParams+xml</MediaType>
            <ComplexTypeName>RecomposeVAppParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.guestCustomizationSection+xml</MediaType>
            <ComplexTypeName>GuestCustomizationSectionType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.customizationSection+xml</MediaType>
            <ComplexTypeName>CustomizationSectionType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.leaseSettingsSection+xml</MediaType>
            <ComplexTypeName>LeaseSettingsSectionType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.startupSection+xml</MediaType>
            <ComplexTypeName>StartupSection_Type</ComplexTypeName>
            <SchemaLocation>http://schemas.dmtf.org/ovf/envelope/1/dsp8023_1.1.0.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.virtualHardwareSection+xml</MediaType>
            <ComplexTypeName>VirtualHardwareSection_Type</ComplexTypeName>
            <SchemaLocation>http://schemas.dmtf.org/ovf/envelope/1/dsp8023_1.1.0.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.operatingSystemSection+xml</MediaType>
            <ComplexTypeName>OperatingSystemSection_Type</ComplexTypeName>
            <SchemaLocation>http://schemas.dmtf.org/ovf/envelope/1/dsp8023_1.1.0.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.vcloud.networkSection+xml</MediaType>
            <ComplexTypeName>NetworkSection_Type</ComplexTypeName>
            <SchemaLocation>http://schemas.dmtf.org/ovf/envelope/1/dsp8023_1.1.0.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.organization+xml</MediaType>
            <ComplexTypeName>AdminOrgType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.providervdc+xml</MediaType>
            <ComplexTypeName>ProviderVdcType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.role+xml</MediaType>
            <ComplexTypeName>RoleType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.user+xml</MediaType>
            <ComplexTypeName>UserType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vcloud+xml</MediaType>
            <ComplexTypeName>VCloudType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vdc+xml</MediaType>
            <ComplexTypeName>AdminVdcType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.group+xml</MediaType>
            <ComplexTypeName>GroupType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.publishCatalogParams+xml</MediaType>
            <ComplexTypeName>PublishCatalogParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.right+xml</MediaType>
            <ComplexTypeName>RightType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.catalog+xml</MediaType>
            <ComplexTypeName>CatalogType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.network+xml</MediaType>
            <ComplexTypeName>NetworkType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.networkPool+xml</MediaType>
            <ComplexTypeName>NetworkPoolType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vdcReferences+xml</MediaType>
            <ComplexTypeName>VdcReferencesType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/master.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vmwExtension+xml</MediaType>
            <ComplexTypeName>VMWExtensionType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vmwProviderVdcReferences+xml</MediaType>
            <ComplexTypeName>VMWProviderVdcReferencesType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vmwExternalNetworkReferences+xml</MediaType>
            <ComplexTypeName>VMWExternalNetworkReferencesType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vmwNetworkPoolReferences+xml</MediaType>
            <ComplexTypeName>VMWNetworkPoolReferencesType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vmwVimServerReferences+xml</MediaType>
            <ComplexTypeName>VMWVimServerReferencesType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vmwHostReferences+xml</MediaType>
            <ComplexTypeName>VMWHostReferencesType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.host+xml</MediaType>
            <ComplexTypeName>HostType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vmwvirtualcenter+xml</MediaType>
            <ComplexTypeName>VimServerType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vmwprovidervdc+xml</MediaType>
            <ComplexTypeName>VMWProviderVdcType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vmwexternalnet+xml</MediaType>
            <ComplexTypeName>VMWExternalNetworkType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.prepareHostParams+xml</MediaType>
            <ComplexTypeName>PrepareHostParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.registerVimServerParams+xml</MediaType>
            <ComplexTypeName>RegisterVimServerParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vmsObjectRefsList+xml</MediaType>
            <ComplexTypeName>VmObjectRefsListType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.importVmAsVAppParams+xml</MediaType>
            <ComplexTypeName>ImportVmAsVAppParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.importVmAsVAppTemplateParams+xml</MediaType>
            <ComplexTypeName>ImportVmAsVAppTemplateParamsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.resourcePoolList+xml</MediaType>
            <ComplexTypeName>ResourcePoolListType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.licensingReport+xml</MediaType>
            <ComplexTypeName>LicensingReportType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.licensingReportList+xml</MediaType>
            <ComplexTypeName>LicensingReportListType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vmwNetworkPool+xml</MediaType>
            <ComplexTypeName>VMWNetworkPoolType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.portGroupPool+xml</MediaType>
            <ComplexTypeName>PortGroupPoolType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vlanPool+xml</MediaType>
            <ComplexTypeName>VlanPoolType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.fencePool+xml</MediaType>
            <ComplexTypeName>FencePoolType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vimObjectRefs+xml</MediaType>
            <ComplexTypeName>VimObjectRefsType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vimObjectRef+xml</MediaType>
            <ComplexTypeName>VimObjectRefType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
        <MediaTypeMapping>
            <MediaType>application/vnd.vmware.admin.vmObjectRef+xml</MediaType>
            <ComplexTypeName>VmObjectRefType</ComplexTypeName>
            <SchemaLocation>http://vcloud.eng.rpath.com/api/v1.0/schema/vmwextensions.xsd</SchemaLocation>
        </MediaTypeMapping>
    </VersionInfo>
</SupportedVersions>
"""
    login = """\
<OrgList xmlns="http://www.vmware.com/vcloud/v1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" type="application/vnd.vmware.vcloud.orgList+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/org/" xsi:schemaLocation="http://www.vmware.com/vcloud/v1 http://vcd1a.eng.rpath.com/api/v1.0/schema/master.xsd">
    <Org type="application/vnd.vmware.vcloud.org+xml" name="Test-BU" href="https://svl-vcd-2.cisco.com/api/v1.0/org/443efa57-bd9f-4a5b-8f35-70391da47ffc"/>
    <Org type="application/vnd.vmware.vcloud.org+xml" name="rPath" href="https://vcd1a.eng.rpath.com/api/v1.0/org/335573498"/>
</OrgList>"""

    getOrg = """\
<?xml version="1.0" encoding="UTF-8"?>
<Org xmlns="http://www.vmware.com/vcloud/v1" name="rPath" type="application/vnd.vmware.vcloud.org+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/org/335573498" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.vmware.com/vcloud/v1 http://vcd1a.eng.rpath.com/api/v1.0/schema/master.xsd">
    <Link rel="down" type="application/vnd.vmware.vcloud.vdc+xml" name="rPath" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/52889018"/>
    <Link rel="down" type="application/vnd.vmware.vcloud.vdc+xml" name="org-vdc-amd" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1966130069"/>
    <Link rel="down" type="application/vnd.vmware.vcloud.tasksList+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/tasksList/335573498"/>
    <Link rel="down" type="application/vnd.vmware.vcloud.catalog+xml" name="misa-catalog-1" href="https://vcd1a.eng.rpath.com/api/v1.0/catalog/1007548327"/>
    <Link rel="down" type="application/vnd.vmware.vcloud.controlAccess+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/org/335573498/catalog/1007548327/controlAccess/"/>
    <Link rel="controlAccess" type="application/vnd.vmware.vcloud.controlAccess+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/org/335573498/catalog/1007548327/action/controlAccess"/>
    <Link rel="down" type="application/vnd.vmware.vcloud.catalog+xml" name="misa-catalog-2" href="https://vcd1a.eng.rpath.com/api/v1.0/catalog/1422628290"/>
    <Link rel="down" type="application/vnd.vmware.vcloud.controlAccess+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/org/335573498/catalog/1422628290/controlAccess/"/>
    <Link rel="controlAccess" type="application/vnd.vmware.vcloud.controlAccess+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/org/335573498/catalog/1422628290/action/controlAccess"/>
    <Link rel="down" type="application/vnd.vmware.vcloud.catalog+xml" name="misa-catalog-2" href="https://vcd1a.eng.rpath.com/api/v1.0/catalog/1422628290"/>
    <Link rel="down" type="application/vnd.vmware.vcloud.controlAccess+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/org/335573498/catalog/1422628290/controlAccess/"/>
    <Link rel="controlAccess" type="application/vnd.vmware.vcloud.controlAccess+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/org/335573498/catalog/1422628290/action/controlAccess"/>
    <Link rel="down" type="application/vnd.vmware.vcloud.catalog+xml" name="misa-catalog-1" href="https://vcd1a.eng.rpath.com/api/v1.0/catalog/1007548327"/>
    <Link rel="down" type="application/vnd.vmware.vcloud.controlAccess+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/org/335573498/catalog/1007548327/controlAccess/"/>
    <Link rel="controlAccess" type="application/vnd.vmware.vcloud.controlAccess+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/org/335573498/catalog/1007548327/action/controlAccess"/>
    <Link rel="down" type="application/vnd.vmware.vcloud.catalog+xml" name="rpath testing" href="https://vcd1a.eng.rpath.com/api/v1.0/catalog/2029780577"/>
    <Link rel="down" type="application/vnd.vmware.vcloud.controlAccess+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/org/335573498/catalog/2029780577/controlAccess/"/>
    <Link rel="down" type="application/vnd.vmware.vcloud.catalog+xml" name="rpath testing" href="https://vcd1a.eng.rpath.com/api/v1.0/catalog/8675309"/>
    <Link rel="down" type="application/vnd.vmware.vcloud.controlAccess+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/org/335573498/catalog/8675309/controlAccess/"/>
    <Description>rPath</Description>
    <FullName>rPath</FullName>
</Org>"""

    getOrgNoCatalogs = re.sub('<Link .* href=".*/catalog/.*".*/>', '', getOrg)

    getVdc52889018 = """\
<?xml version="1.0" encoding="UTF-8"?>
<Vdc xmlns="http://www.vmware.com/vcloud/v1" status="1" name="rPath" type="application/vnd.vmware.vcloud.vdc+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/52889018" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.vmware.com/vcloud/v1 http://vcd1a.eng.rpath.com/api/v1.0/schema/master.xsd">
    <Link rel="add" type="application/vnd.vmware.vcloud.uploadVAppTemplateParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/52889018/action/uploadVAppTemplate"/>
    <Link rel="add" type="application/vnd.vmware.vcloud.media+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/52889018/media"/>
    <Link rel="add" type="application/vnd.vmware.vcloud.instantiateVAppTemplateParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/52889018/action/instantiateVAppTemplate"/>
    <Link rel="add" type="application/vnd.vmware.vcloud.cloneVAppParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/52889018/action/cloneVApp"/>
    <Link rel="add" type="application/vnd.vmware.vcloud.cloneVAppTemplateParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/52889018/action/cloneVAppTemplate"/>
    <Link rel="add" type="application/vnd.vmware.vcloud.cloneMediaParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/52889018/action/cloneMedia"/>
    <Link rel="add" type="application/vnd.vmware.vcloud.captureVAppParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/52889018/action/captureVApp"/>
    <Link rel="add" type="application/vnd.vmware.vcloud.composeVAppParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/52889018/action/composeVApp"/>
    <Link rel="move" type="application/vnd.vmware.vcloud.moveMediaParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/52889018/action/moveMedia"/>
    <Link rel="move" type="application/vnd.vmware.vcloud.moveVAppParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/52889018/action/moveVApp"/>
    <Link rel="move" type="application/vnd.vmware.vcloud.moveVAppTemplateParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/52889018/action/moveVAppTemplate"/>
    <Description>rPath Organization vDC</Description>
    <AllocationModel>AllocationVApp</AllocationModel>
    <StorageCapacity>
        <Units>MB</Units>
        <Allocated>51200</Allocated>
        <Limit>51200</Limit>
        <Used>10024</Used>
        <Overhead>0</Overhead>
    </StorageCapacity>
    <ComputeCapacity>
        <Cpu>
            <Units>MHz</Units>
            <Allocated>0</Allocated>
            <Limit>0</Limit>
            <Used>0</Used>
            <Overhead>0</Overhead>
        </Cpu>
        <Memory>
            <Units>MB</Units>
            <Allocated>0</Allocated>
            <Limit>0</Limit>
            <Used>0</Used>
            <Overhead>0</Overhead>
        </Memory>
    </ComputeCapacity>
    <ResourceEntities>
        <ResourceEntity type="application/vnd.vmware.vcloud.vApp+xml" name="vApp_misa_2" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865"/>
        <ResourceEntity type="application/vnd.vmware.vcloud.vApp+xml" name="vapp 101" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-9198675309"/>
        <ResourceEntity type="application/vnd.vmware.vcloud.vAppTemplate+xml" name="test 1" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-1537853377"/>
        <ResourceEntity type="application/vnd.vmware.vcloud.vAppTemplate+xml" name="test 1" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-1537853377"/>
    </ResourceEntities>
    <AvailableNetworks>
        <Network type="application/vnd.vmware.vcloud.network+xml" name="org1-network" href="https://vcd1a.eng.rpath.com/api/v1.0/network/2072223164"/>
        <Network type="application/vnd.vmware.vcloud.network+xml" name="internal-192" href="https://vcd1a.eng.rpath.com/api/v1.0/network/2009726362"/>
    </AvailableNetworks>
    <NicQuota>0</NicQuota>
    <NetworkQuota>1</NetworkQuota>
    <VmQuota>4</VmQuota>
    <IsEnabled>true</IsEnabled>
</Vdc>"""

    getVdc52889018NoNetworks = re.sub(
        re.compile('<AvailableNetworks>.*</AvailableNetworks>', flags=re.DOTALL),
        '<AvailableNetworks/>',
        getVdc52889018)

    getVdc1966130069 = """\
<?xml version="1.0" encoding="UTF-8"?>
<Vdc xmlns="http://www.vmware.com/vcloud/v1" status="1" name="vdc-org-1" type="application/vnd.vmware.vcloud.vdc+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1819101334" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.vmware.com/vcloud/v1 http://vcd1a.eng.rpath.com/api/v1.0/schema/master.xsd">
    <Link rel="up" type="application/vnd.vmware.vcloud.org+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/org/696425917"/>
    <Link rel="add" type="application/vnd.vmware.vcloud.uploadVAppTemplateParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1819101334/action/uploadVAppTemplate"/>
    <Link rel="add" type="application/vnd.vmware.vcloud.media+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1819101334/media"/>
    <Link rel="add" type="application/vnd.vmware.vcloud.instantiateVAppTemplateParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1819101334/action/instantiateVAppTemplate"/>
    <Link rel="add" type="application/vnd.vmware.vcloud.cloneVAppParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1819101334/action/cloneVApp"/>
    <Link rel="add" type="application/vnd.vmware.vcloud.cloneVAppTemplateParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1819101334/action/cloneVAppTemplate"/>
    <Link rel="add" type="application/vnd.vmware.vcloud.cloneMediaParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1819101334/action/cloneMedia"/>
    <Link rel="add" type="application/vnd.vmware.vcloud.captureVAppParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1819101334/action/captureVApp"/>
    <Link rel="add" type="application/vnd.vmware.vcloud.composeVAppParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1819101334/action/composeVApp"/>
    <Link rel="move" type="application/vnd.vmware.vcloud.moveMediaParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1819101334/action/moveMedia"/>
    <Link rel="move" type="application/vnd.vmware.vcloud.moveVAppParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1819101334/action/moveVApp"/>
    <Link rel="move" type="application/vnd.vmware.vcloud.moveVAppTemplateParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1819101334/action/moveVAppTemplate"/>
    <AllocationModel>ReservationPool</AllocationModel>
    <StorageCapacity>
        <Units>MB</Units>
        <Allocated>58050</Allocated>
        <Limit>58050</Limit>
        <Used>17408</Used>
        <Overhead>0</Overhead>
    </StorageCapacity>
    <ComputeCapacity>
        <Cpu>
            <Units>MHz</Units>
            <Allocated>1300</Allocated>
            <Limit>1300</Limit>
            <Used>0</Used>
            <Overhead>0</Overhead>
        </Cpu>
        <Memory>
            <Units>MB</Units>
            <Allocated>5007</Allocated>
            <Limit>5007</Limit>
            <Used>0</Used>
            <Overhead>0</Overhead>
        </Memory>
    </ComputeCapacity>
    <ResourceEntities>
        <ResourceEntity type="application/vnd.vmware.vcloud.vApp+xml" name="vApp_misa_1" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1626129624"/>
        <ResourceEntity type="application/vnd.vmware.vcloud.vAppTemplate+xml" name="test 2" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-12513145"/>
        <ResourceEntity type="application/vnd.vmware.vcloud.vAppTemplate+xml" name="test 3" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-1912306245"/>
        <ResourceEntity type="application/vnd.vmware.vcloud.vAppTemplate+xml" name="test 2" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-653547238"/>
        <ResourceEntity type="application/vnd.vmware.vcloud.vAppTemplate+xml" name="test 3" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-618477289"/>
        <ResourceEntity type="application/vnd.vmware.vcloud.vAppTemplate+xml" name="test 3" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-1735891145"/>
        <ResourceEntity type="application/vnd.vmware.vcloud.vAppTemplate+xml" name="test 2" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-961210114"/>
        <ResourceEntity type="application/vnd.vmware.vcloud.vAppTemplate+xml" name="test 3" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-1294361836"/>
    </ResourceEntities>
    <AvailableNetworks>
        <Network type="application/vnd.vmware.vcloud.network+xml" name="org1-network" href="https://vcd1a.eng.rpath.com/api/v1.0/network/2072223164"/>
        <Network type="application/vnd.vmware.vcloud.network+xml" name="internal-192" href="https://vcd1a.eng.rpath.com/api/v1.0/network/2009726362"/>
    </AvailableNetworks>
    <NicQuota>0</NicQuota>
    <NetworkQuota>1024</NetworkQuota>
    <VmQuota>100</VmQuota>
    <IsEnabled>false</IsEnabled>
</Vdc>"""

    _vappTemplateBase = """\
<?xml version="1.0" encoding="UTF-8"?>
<VAppTemplate xmlns="http://www.vmware.com/vcloud/v1" xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1" ovfDescriptorUploaded="false" status="0" name="test 21" type="application/vnd.vmware.vcloud.vAppTemplate+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-90220688" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://schemas.dmtf.org/ovf/envelope/1 http://schemas.dmtf.org/ovf/envelope/1/dsp8023_1.1.0.xsd http://www.vmware.com/vcloud/v1 http://vcd1a.eng.rpath.com/api/v1.0/schema/master.xsd">
    <Link rel="up" type="application/vnd.vmware.vcloud.vdc+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1966130069"/>
    <Link rel="remove" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-90220688"/>
    <Description>description for test 21</Description>
    <Files>
        <File size="-1" bytesTransferred="0" name="descriptor.ovf">
            <Link rel="upload:default" href="https://172.16.160.32:443/transfer/eb1046d7-dbb9-4cbe-a95d-08e6450af7ea/descriptor.ovf"/>
        </File>
    </Files>
    <Children/>
    <LeaseSettingsSection type="application/vnd.vmware.vcloud.leaseSettingsSection+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-90220688/leaseSettingsSection/" ovf:required="false">
        <ovf:Info>Lease settings section</ovf:Info>
        <Link rel="edit" type="application/vnd.vmware.vcloud.leaseSettingsSection+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-90220688/leaseSettingsSection/"/>
        <StorageLeaseInSeconds>0</StorageLeaseInSeconds>
    </LeaseSettingsSection>
    <CustomizationSection type="application/vnd.vmware.vcloud.customizationSection+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-90220688/customizationSection/" ovf:required="false">
        <ovf:Info>VApp template customization section</ovf:Info>
        <CustomizeOnInstantiate>false</CustomizeOnInstantiate>
    </CustomizationSection>
</VAppTemplate>
"""
    uploadVAppTemplate_90220688_new = _vappTemplateBase
    uploadVAppTemplate_90220688_ovf_uploading = _vappTemplateBase
    uploadVAppTemplate_90220688_ovf_uploaded = _vappTemplateBase.replace(
        'ovfDescriptorUploaded="false"',
            'ovfDescriptorUploaded="true"').replace(
        'size="-1" bytesTransferred="0"',
            'size="1234" bytesTransferred="1234"').replace(
        '</File>',
            '</File>'
            '<File size="12345678" bytesTransferred="0" name="some-file-6-1-x86/some-file-6-1-x86.vmdk">'
              '<Link rel="upload:default" href="https://172.16.160.32:443/transfer/00000000-0000-0000-0000-000000000001/some-file-6-1-x86.vmdk"/>'
            '</File>')
    uploadVAppTemplate_90220688_vmdk_transferring = uploadVAppTemplate_90220688_ovf_uploaded.replace(
        'bytesTransferred="0" name=',
            'bytesTransferred="%s" name=')
    uploadVAppTemplate_90220688_files_uploaded = uploadVAppTemplate_90220688_vmdk_transferring % 12345678
    uploadVAppTemplate_90220688_upload_finished = uploadVAppTemplate_90220688_files_uploaded.replace(
        'status="0"', 'status="8"')
    addVappTemplateToCatalog_90220688 = """\
<?xml version="1.0" encoding="UTF-8"?>
<CatalogItem xmlns="http://www.vmware.com/vcloud/v1" name="test 22" type="application/vnd.vmware.vcloud.catalogItem+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/catalogItem/862096767" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.vmware.com/vcloud/v1 http://vcd1a.eng.rpath.com/api/v1.0/schema/master.xsd">
    <Link rel="up" type="application/vnd.vmware.vcloud.catalog+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/catalog/1895122695"/>
    <Link rel="edit" type="application/vnd.vmware.vcloud.catalogItem+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/catalogItem/862096767"/>
    <Link rel="remove" href="https://vcd1a.eng.rpath.com/api/v1.0/catalogItem/862096767"/>
    <Description>description for test 21</Description>
    <Entity type="application/vnd.vmware.vcloud.vAppTemplate+xml" name="test 22" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-90220688"/>
</CatalogItem>"""
    uploadVAppTemplate_90220688_upload_finished_ovf = uploadVAppTemplate_90220688_upload_finished.replace(
    "<Description>",
    """<Link rel="ovf" href="https://vcd1a.eng.rpath.com/api/v1.0/vAppTemplate/vappTemplate-90220688/ovf"/>
    <Description>"""
    )
    getVappTemplate90220688_ovf = """\
<?xml version="1.0" encoding="UTF-8"?>
<ovf:Envelope xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1" xmlns:vcloud="http://www.vmware.com/vcloud/v1" xmlns:vssd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData" xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2.22.0/CIM_VirtualSystemSettingData.xsd http://schemas.dmtf.org/ovf/envelope/1 http://schemas.dmtf.org/ovf/envelope/1/dsp8023_1.1.0.xsd http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2.22.0/CIM_ResourceAllocationSettingData.xsd http://www.vmware.com/vcloud/v1 http://vcd1a.eng.rpath.com/api/v1.0/schema/master.xsd">
    <ovf:References/>
    <ovf:NetworkSection>
        <ovf:Info>The list of logical networks</ovf:Info>
        <ovf:Network ovf:name="dvportgroup-19802">
            <ovf:Description>The dvportgroup-19802 network</ovf:Description>
        </ovf:Network>
    </ovf:NetworkSection>
    <vcloud:NetworkConfigSection ovf:required="false">
        <ovf:Info>The configuration parameters for logical networks</ovf:Info>
        <vcloud:NetworkConfig networkName="dvportgroup-19802">
            <vcloud:Description>The dvportgroup-19802 network</vcloud:Description>
            <vcloud:Configuration>
                <vcloud:IpScope>
                    <vcloud:IsInherited>false</vcloud:IsInherited>
                    <vcloud:Gateway>192.168.254.1</vcloud:Gateway>
                    <vcloud:Netmask>255.255.255.0</vcloud:Netmask>
                    <vcloud:Dns1>192.168.254.1</vcloud:Dns1>
                </vcloud:IpScope>
                <vcloud:FenceMode>isolated</vcloud:FenceMode>
            </vcloud:Configuration>
            <vcloud:IsDeployed>false</vcloud:IsDeployed>
        </vcloud:NetworkConfig>
    </vcloud:NetworkConfigSection>
    <vcloud:LeaseSettingsSection ovf:required="false">
        <ovf:Info>Lease settings section</ovf:Info>
        <vcloud:DeploymentLeaseInSeconds>0</vcloud:DeploymentLeaseInSeconds>
        <vcloud:StorageLeaseInSeconds>7776000</vcloud:StorageLeaseInSeconds>
        <vcloud:StorageLeaseExpiration>2012-03-11T10:53:56.067-04:00</vcloud:StorageLeaseExpiration>
    </vcloud:LeaseSettingsSection>
    <vcloud:CustomizationSection ovf:required="false">
        <ovf:Info>VApp template customization section</ovf:Info>
        <vcloud:CustomizeOnInstantiate>true</vcloud:CustomizeOnInstantiate>
    </vcloud:CustomizationSection>
    <ovf:VirtualSystem ovf:id="misa-foobar-11">
        <ovf:Info>A virtual machine: A virtual machine</ovf:Info>
        <ovf:Name>misa-foobar-11</ovf:Name>
        <ovf:OperatingSystemSection xmlns:vmw="http://www.vmware.com/schema/ovf" ovf:id="101" vmw:osType="otherLinux64Guest">
            <ovf:Info>Specifies the operating system installed</ovf:Info>
            <ovf:Description>Other Linux (64-bit)</ovf:Description>
        </ovf:OperatingSystemSection>
        <ovf:VirtualHardwareSection>
            <ovf:Info>Virtual hardware requirements</ovf:Info>
            <ovf:System>
                <vssd:ElementName>Virtual Hardware Family</vssd:ElementName>
                <vssd:InstanceID>0</vssd:InstanceID>
                <vssd:VirtualSystemIdentifier>misa-foobar-11</vssd:VirtualSystemIdentifier>
                <vssd:VirtualSystemType>vmx-04</vssd:VirtualSystemType>
            </ovf:System>
            <ovf:Item>
                <rasd:Address>00:50:56:01:01:11</rasd:Address>
                <rasd:AddressOnParent>0</rasd:AddressOnParent>
                <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
                <rasd:Connection vcloud:primaryNetworkConnection="true" vcloud:ipAddressingMode="DHCP">dvportgroup-19802</rasd:Connection>
                <rasd:Description>PCNet32 ethernet adapter</rasd:Description>
                <rasd:ElementName>Network adapter 0</rasd:ElementName>
                <rasd:InstanceID>1</rasd:InstanceID>
                <rasd:ResourceSubType>PCNet32</rasd:ResourceSubType>
                <rasd:ResourceType>10</rasd:ResourceType>
            </ovf:Item>
            <ovf:Item>
                <rasd:Address>0</rasd:Address>
                <rasd:Description>SCSI Controller</rasd:Description>
                <rasd:ElementName>SCSI Controller 0</rasd:ElementName>
                <rasd:InstanceID>2</rasd:InstanceID>
                <rasd:ResourceSubType>lsilogic</rasd:ResourceSubType>
                <rasd:ResourceType>6</rasd:ResourceType>
            </ovf:Item>
            <ovf:Item>
                <rasd:AddressOnParent>0</rasd:AddressOnParent>
                <rasd:Description>Hard disk</rasd:Description>
                <rasd:ElementName>Hard disk 1</rasd:ElementName>
                <rasd:HostResource vcloud:capacity="808" vcloud:busType="6" vcloud:busSubType="lsilogic"/>
                <rasd:InstanceID>2000</rasd:InstanceID>
                <rasd:Parent>2</rasd:Parent>
                <rasd:ResourceType>17</rasd:ResourceType>
            </ovf:Item>
            <ovf:Item>
                <rasd:Address>0</rasd:Address>
                <rasd:Description>IDE Controller</rasd:Description>
                <rasd:ElementName>IDE Controller 0</rasd:ElementName>
                <rasd:InstanceID>3</rasd:InstanceID>
                <rasd:ResourceType>5</rasd:ResourceType>
            </ovf:Item>
            <ovf:Item>
                <rasd:AddressOnParent>0</rasd:AddressOnParent>
                <rasd:AutomaticAllocation>false</rasd:AutomaticAllocation>
                <rasd:Description>CD/DVD Drive</rasd:Description>
                <rasd:ElementName>CD/DVD Drive 1</rasd:ElementName>
                <rasd:HostResource/>
                <rasd:InstanceID>3000</rasd:InstanceID>
                <rasd:Parent>3</rasd:Parent>
                <rasd:ResourceType>15</rasd:ResourceType>
            </ovf:Item>
            <ovf:Item>
                <rasd:AllocationUnits>hertz * 10^6</rasd:AllocationUnits>
                <rasd:Description>Number of Virtual CPUs</rasd:Description>
                <rasd:ElementName>1 virtual CPU(s)</rasd:ElementName>
                <rasd:InstanceID>4</rasd:InstanceID>
                <rasd:Reservation>0</rasd:Reservation>
                <rasd:ResourceType>3</rasd:ResourceType>
                <rasd:VirtualQuantity>1</rasd:VirtualQuantity>
                <rasd:Weight>0</rasd:Weight>
            </ovf:Item>
            <ovf:Item>
                <rasd:AllocationUnits>byte * 2^20</rasd:AllocationUnits>
                <rasd:Description>Memory Size</rasd:Description>
                <rasd:ElementName>384 MB of memory</rasd:ElementName>
                <rasd:InstanceID>5</rasd:InstanceID>
                <rasd:Reservation>0</rasd:Reservation>
                <rasd:ResourceType>4</rasd:ResourceType>
                <rasd:VirtualQuantity>384</rasd:VirtualQuantity>
                <rasd:Weight>0</rasd:Weight>
            </ovf:Item>
        </ovf:VirtualHardwareSection>
        <vcloud:NetworkConnectionSection ovf:required="false">
            <ovf:Info>Specifies the available VM network connections</ovf:Info>
            <vcloud:PrimaryNetworkConnectionIndex>0</vcloud:PrimaryNetworkConnectionIndex>
            <vcloud:NetworkConnection network="dvportgroup-19802">
                <vcloud:NetworkConnectionIndex>0</vcloud:NetworkConnectionIndex>
                <vcloud:IsConnected>true</vcloud:IsConnected>
                <vcloud:MACAddress>00:50:56:01:01:11</vcloud:MACAddress>
                <vcloud:IpAddressAllocationMode>DHCP</vcloud:IpAddressAllocationMode>
            </vcloud:NetworkConnection>
        </vcloud:NetworkConnectionSection>
        <vcloud:GuestCustomizationSection ovf:required="false">
            <ovf:Info>Specifies Guest OS Customization Settings</ovf:Info>
            <vcloud:Enabled>true</vcloud:Enabled>
            <vcloud:ChangeSid>false</vcloud:ChangeSid>
            <vcloud:VirtualMachineId>263085386</vcloud:VirtualMachineId>
            <vcloud:JoinDomainEnabled>false</vcloud:JoinDomainEnabled>
            <vcloud:UseOrgSettings>false</vcloud:UseOrgSettings>
            <vcloud:AdminPasswordEnabled>true</vcloud:AdminPasswordEnabled>
            <vcloud:AdminPasswordAuto>true</vcloud:AdminPasswordAuto>
            <vcloud:ResetPasswordRequired>false</vcloud:ResetPasswordRequired>
            <vcloud:CustomizationScript/>
            <vcloud:ComputerName>misa-foobar-11</vcloud:ComputerName>
        </vcloud:GuestCustomizationSection>
    </ovf:VirtualSystem>
</ovf:Envelope>"""
    InstantiateVappTemplate_new = """\
<?xml version="1.0" encoding="UTF-8"?>
<VApp xmlns="http://www.vmware.com/vcloud/v1" deployed="false" status="0" name="my-vapp-2" type="application/vnd.vmware.vcloud.vApp+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-9198675309" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.vmware.com/vcloud/v1 http://vcd1a.eng.rpath.com/api/v1.0/schema/master.xsd">
    <Link rel="down" type="application/vnd.vmware.vcloud.controlAccess+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-9198675309/controlAccess/"/>
    <Link rel="up" type="application/vnd.vmware.vcloud.vdc+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1966130069"/>
    <Description>description for my-vapp-2</Description>
    <Tasks>
        <Task status="running" startTime="2011-07-28T10:08:04.376-04:00" operation="Creating Virtual Application my-vapp-2(9198675309)" expiryTime="2011-10-26T10:08:04.376-04:00" endTime="9999-12-31T23:59:59.999-05:00" type="application/vnd.vmware.vcloud.task+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/task/3bh1ghv1spttmr2vt3s">
            <Owner type="application/vnd.vmware.vcloud.vApp+xml" name="my-vapp-2" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-9198675309"/>
        </Task>
    </Tasks>
</VApp>"""

    getVapp1836764865 = """\
<VApp xmlns="http://www.vmware.com/vcloud/v1" xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1" xmlns:vssd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData" xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData" deployed="false" status="8" name="vApp_misa_2" type="application/vnd.vmware.vcloud.vApp+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2.22.0/CIM_VirtualSystemSettingData.xsd http://schemas.dmtf.org/ovf/envelope/1 http://schemas.dmtf.org/ovf/envelope/1/dsp8023_1.1.0.xsd http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2.22.0/CIM_ResourceAllocationSettingData.xsd http://www.vmware.com/vcloud/v1 http://vcd1a.eng.rpath.com/api/v1.0/schema/master.xsd">
    <Link rel="power:powerOn" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865/power/action/powerOn"/>
    <Link rel="deploy" type="application/vnd.vmware.vcloud.deployVAppParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865/action/deploy"/>
    <Link rel="down" type="application/vnd.vmware.vcloud.controlAccess+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865/controlAccess/"/>
    <Link rel="controlAccess" type="application/vnd.vmware.vcloud.controlAccess+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865/action/controlAccess"/>
    <Link rel="recompose" type="application/vnd.vmware.vcloud.recomposeVAppParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865/action/recomposeVApp"/>
    <Link rel="up" type="application/vnd.vmware.vcloud.vdc+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vdc/1966130069"/>
    <Link rel="edit" type="application/vnd.vmware.vcloud.vApp+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865"/>
    <Link rel="remove" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865"/>
    <Description>vapp2 description</Description>
    <LeaseSettingsSection type="application/vnd.vmware.vcloud.leaseSettingsSection+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865/leaseSettingsSection/" ovf:required="false">
        <ovf:Info>Lease settings section</ovf:Info>
        <Link rel="edit" type="application/vnd.vmware.vcloud.leaseSettingsSection+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865/leaseSettingsSection/"/>
        <DeploymentLeaseInSeconds>0</DeploymentLeaseInSeconds>
        <StorageLeaseInSeconds>0</StorageLeaseInSeconds>
    </LeaseSettingsSection>
    <ovf:StartupSection xmlns:vcloud="http://www.vmware.com/vcloud/v1" vcloud:href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865/startupSection/" vcloud:type="application/vnd.vmware.vcloud.startupSection+xml">
        <ovf:Info>VApp startup section</ovf:Info>
        <ovf:Item ovf:stopDelay="0" ovf:stopAction="powerOff" ovf:startDelay="0" ovf:startAction="powerOn" ovf:order="0" ovf:id="test 21"/>
        <Link rel="edit" type="application/vnd.vmware.vcloud.startupSection+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865/startupSection/"/>
    </ovf:StartupSection>
    <ovf:NetworkSection xmlns:vcloud="http://www.vmware.com/vcloud/v1" vcloud:href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865/networkSection/" vcloud:type="application/vnd.vmware.vcloud.networkSection+xml">
        <ovf:Info>The list of logical networks</ovf:Info>
        <ovf:Network ovf:name="none">
            <ovf:Description>This is a special place-holder used for disconnected network interfaces.</ovf:Description>
        </ovf:Network>
    </ovf:NetworkSection>
    <NetworkConfigSection type="application/vnd.vmware.vcloud.networkConfigSection+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865/networkConfigSection/" ovf:required="false">
        <ovf:Info>The configuration parameters for logical networks</ovf:Info>
        <Link rel="edit" type="application/vnd.vmware.vcloud.networkConfigSection+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865/networkConfigSection/"/>
        <NetworkConfig networkName="none">
            <Description>This is a special place-holder used for disconnected network interfaces.</Description>
            <Configuration>
                <IpScope>
                    <IsInherited>false</IsInherited>
                    <Gateway>196.254.254.254</Gateway>
                    <Netmask>255.255.0.0</Netmask>
                    <Dns1>196.254.254.254</Dns1>
                </IpScope>
                <FenceMode>isolated</FenceMode>
            </Configuration>
            <IsDeployed>false</IsDeployed>
        </NetworkConfig>
    </NetworkConfigSection>
    <Children>
        <Vm deployed="false" status="8" name="test 21" type="application/vnd.vmware.vcloud.vm+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531">
            <Link rel="power:powerOn" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/power/action/powerOn"/>
            <Link rel="deploy" type="application/vnd.vmware.vcloud.deployVAppParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/action/deploy"/>
            <Link rel="up" type="application/vnd.vmware.vcloud.vApp+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vapp-1836764865"/>
            <Link rel="edit" type="application/vnd.vmware.vcloud.vm+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531"/>
            <Link rel="remove" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531"/>
            <Link rel="screen:thumbnail" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/screen"/>
            <Link rel="media:insertMedia" type="application/vnd.vmware.vcloud.mediaInsertOrEjectParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/media/action/insertMedia"/>
            <Link rel="media:ejectMedia" type="application/vnd.vmware.vcloud.mediaInsertOrEjectParams+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/media/action/ejectMedia"/>
            <Description/>
            <ovf:VirtualHardwareSection xmlns:vcloud="http://www.vmware.com/vcloud/v1" vcloud:href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/virtualHardwareSection/" vcloud:type="application/vnd.vmware.vcloud.virtualHardwareSection+xml">
                <ovf:Info>Virtual hardware requirements</ovf:Info>
                <ovf:System>
                    <vssd:ElementName>Virtual Hardware Family</vssd:ElementName>
                    <vssd:InstanceID>0</vssd:InstanceID>
                    <vssd:VirtualSystemIdentifier>test 21</vssd:VirtualSystemIdentifier>
                    <vssd:VirtualSystemType>vmx-07</vssd:VirtualSystemType>
                </ovf:System>
                <ovf:Item>
                    <rasd:Address>00:50:56:01:02:37</rasd:Address>
                    <rasd:AddressOnParent>0</rasd:AddressOnParent>
                    <rasd:AutomaticAllocation>false</rasd:AutomaticAllocation>
                    <rasd:Connection vcloud:primaryNetworkConnection="true" vcloud:ipAddressingMode="NONE">none</rasd:Connection>
                    <rasd:Description>PCNet32 ethernet adapter</rasd:Description>
                    <rasd:ElementName>Network adapter 0</rasd:ElementName>
                    <rasd:InstanceID>1</rasd:InstanceID>
                    <rasd:ResourceSubType>PCNet32</rasd:ResourceSubType>
                    <rasd:ResourceType>10</rasd:ResourceType>
                </ovf:Item>
                <ovf:Item>
                    <rasd:Address>0</rasd:Address>
                    <rasd:Description>SCSI Controller</rasd:Description>
                    <rasd:ElementName>SCSI Controller 0</rasd:ElementName>
                    <rasd:InstanceID>2</rasd:InstanceID>
                    <rasd:ResourceSubType>lsilogic</rasd:ResourceSubType>
                    <rasd:ResourceType>6</rasd:ResourceType>
                </ovf:Item>
                <ovf:Item>
                    <rasd:AddressOnParent>0</rasd:AddressOnParent>
                    <rasd:Description>Hard disk</rasd:Description>
                    <rasd:ElementName>Hard disk 1</rasd:ElementName>
                    <rasd:HostResource vcloud:capacity="2144" vcloud:busType="6" vcloud:busSubType="lsilogic"/>
                    <rasd:InstanceID>2000</rasd:InstanceID>
                    <rasd:Parent>2</rasd:Parent>
                    <rasd:ResourceType>17</rasd:ResourceType>
                </ovf:Item>
                <ovf:Item vcloud:href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/virtualHardwareSection/cpu" vcloud:type="application/vnd.vmware.vcloud.rasdItem+xml">
                    <rasd:AllocationUnits>hertz * 10^6</rasd:AllocationUnits>
                    <rasd:Description>Number of Virtual CPUs</rasd:Description>
                    <rasd:ElementName>1 virtual CPU(s)</rasd:ElementName>
                    <rasd:InstanceID>3</rasd:InstanceID>
                    <rasd:Reservation>0</rasd:Reservation>
                    <rasd:ResourceType>3</rasd:ResourceType>
                    <rasd:VirtualQuantity>1</rasd:VirtualQuantity>
                    <rasd:Weight>0</rasd:Weight>
                    <Link rel="edit" type="application/vnd.vmware.vcloud.rasdItem+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/virtualHardwareSection/cpu"/>
                </ovf:Item>
                <ovf:Item vcloud:href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/virtualHardwareSection/memory" vcloud:type="application/vnd.vmware.vcloud.rasdItem+xml">
                    <rasd:AllocationUnits>byte * 2^20</rasd:AllocationUnits>
                    <rasd:Description>Memory Size</rasd:Description>
                    <rasd:ElementName>256 MB of memory</rasd:ElementName>
                    <rasd:InstanceID>4</rasd:InstanceID>
                    <rasd:Reservation>0</rasd:Reservation>
                    <rasd:ResourceType>4</rasd:ResourceType>
                    <rasd:VirtualQuantity>256</rasd:VirtualQuantity>
                    <rasd:Weight>0</rasd:Weight>
                    <Link rel="edit" type="application/vnd.vmware.vcloud.rasdItem+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/virtualHardwareSection/memory"/>
                </ovf:Item>
                <Link rel="edit" type="application/vnd.vmware.vcloud.virtualHardwareSection+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/virtualHardwareSection/"/>
                <Link rel="down" type="application/vnd.vmware.vcloud.rasdItem+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/virtualHardwareSection/cpu"/>
                <Link rel="edit" type="application/vnd.vmware.vcloud.rasdItem+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/virtualHardwareSection/cpu"/>
                <Link rel="down" type="application/vnd.vmware.vcloud.rasdItem+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/virtualHardwareSection/memory"/>
                <Link rel="edit" type="application/vnd.vmware.vcloud.rasdItem+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/virtualHardwareSection/memory"/>
                <Link rel="down" type="application/vnd.vmware.vcloud.rasdItemsList+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/virtualHardwareSection/disks"/>
                <Link rel="edit" type="application/vnd.vmware.vcloud.rasdItemsList+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/virtualHardwareSection/disks"/>
                <Link rel="down" type="application/vnd.vmware.vcloud.rasdItemsList+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/virtualHardwareSection/media"/>
                <Link rel="down" type="application/vnd.vmware.vcloud.rasdItemsList+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/virtualHardwareSection/networkCards"/>
                <Link rel="edit" type="application/vnd.vmware.vcloud.rasdItemsList+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/virtualHardwareSection/networkCards"/>
            </ovf:VirtualHardwareSection>
            <ovf:OperatingSystemSection xmlns:vcloud="http://www.vmware.com/vcloud/v1" xmlns:vmw="http://www.vmware.com/schema/ovf" ovf:id="1" vcloud:href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/operatingSystemSection/" vcloud:type="application/vnd.vmware.vcloud.operatingSystemSection+xml" vmw:osType="otherGuest">
                <ovf:Info>Specifies the operating system installed</ovf:Info>
                <ovf:Description>Other (32-bit)</ovf:Description>
                <Link rel="edit" type="application/vnd.vmware.vcloud.operatingSystemSection+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/operatingSystemSection/"/>
            </ovf:OperatingSystemSection>
            <NetworkConnectionSection type="application/vnd.vmware.vcloud.networkConnectionSection+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/networkConnectionSection/" ovf:required="false">
                <ovf:Info>Specifies the available VM network connections</ovf:Info>
                <PrimaryNetworkConnectionIndex>0</PrimaryNetworkConnectionIndex>
                <NetworkConnection network="none">
                    <NetworkConnectionIndex>0</NetworkConnectionIndex>
                    <IsConnected>false</IsConnected>
                    <MACAddress>00:50:56:01:02:37</MACAddress>
                    <IpAddressAllocationMode>NONE</IpAddressAllocationMode>
                </NetworkConnection>
                <Link rel="edit" type="application/vnd.vmware.vcloud.networkConnectionSection+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/networkConnectionSection/"/>
            </NetworkConnectionSection>
            <GuestCustomizationSection type="application/vnd.vmware.vcloud.guestCustomizationSection+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/guestCustomizationSection/" ovf:required="false">
                <ovf:Info>Specifies Guest OS Customization Settings</ovf:Info>
                <Enabled>true</Enabled>
                <ChangeSid>false</ChangeSid>
                <VirtualMachineId>1366228531</VirtualMachineId>
                <JoinDomainEnabled>false</JoinDomainEnabled>
                <UseOrgSettings>false</UseOrgSettings>
                <AdminPasswordEnabled>true</AdminPasswordEnabled>
                <AdminPasswordAuto>true</AdminPasswordAuto>
                <ResetPasswordRequired>false</ResetPasswordRequired>
                <CustomizationScript/>
                <ComputerName>test21</ComputerName>
                <Link rel="edit" type="application/vnd.vmware.vcloud.guestCustomizationSection+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/vApp/vm-1366228531/guestCustomizationSection/"/>
            </GuestCustomizationSection>
            <VAppScopedLocalId>celery-1-x86_64</VAppScopedLocalId>
        </Vm>
    </Children>
</VApp>"""

    getVapp9198675309 = getVapp1836764865.replace(
        'vm-1366228531', 'vm-8675309').replace(
        '1836764865', '9198675309').replace(
        'name="test 21"', 'name="test 101"').replace(
        'name="vApp_misa_2"', 'name="vapp 101"')

    getVapp9198675309_poweredon = getVapp9198675309.replace(
        'status="8"', 'status="%s"' % dvcloud.models.Status.Code.POWERED_ON)

    getVapp9198675309_poweredon_w_network = getVapp9198675309_poweredon.replace(
        '</NetworkConnectionIndex>', '</NetworkConnectionIndex><IpAddress>10.11.12.13</IpAddress>')

    getCatalog2029780577 = """\
<Catalog xmlns="http://www.vmware.com/vcloud/v1" name="rpath testing" type="application/vnd.vmware.vcloud.catalog+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/catalog/2029780577" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.vmware.com/vcloud/v1 http://vcd1a.eng.rpath.com/api/v1.0/schema/master.xsd">
  <Link rel="up" type="application/vnd.vmware.vcloud.org+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/org/335573498"/>
  <Link rel="add" type="application/vnd.vmware.vcloud.catalogItem+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/catalog/2029780577/catalogItems"/>
  <CatalogItems/>
  <IsPublished>false</IsPublished>
</Catalog>
"""

    getCatalog1007548327 = getCatalog2029780577.replace('2029780577', '1007548327').replace('rpath testing', 'misa-catalog-1')
    getCatalog1422628290 = getCatalog2029780577.replace('2029780577', '1422628290').replace('rpath testing', 'misa-catalog-2')

    getCatalog8675309 = """\
<Catalog xmlns="http://www.vmware.com/vcloud/v1" name="rpath testing" type="application/vnd.vmware.vcloud.catalog+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/catalog/8675309" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.vmware.com/vcloud/v1 http://vcd1a.eng.rpath.com/api/v1.0/schema/master.xsd">
  <Link rel="up" type="application/vnd.vmware.vcloud.org+xml" href="https://vcd1a.eng.rpath.com/api/v1.0/org/335573498"/>
  <CatalogItems/>
  <IsPublished>false</IsPublished>
</Catalog>
"""

    addMedia = """\
<Media name="credentials iso" href="https://example.com/media/foo-1" status="0">
  <Files>
    <File size="20000" bytesTransferred="0" name="descriptor.ovf">
      <Link rel="upload:default" href="https://example.com/transfer/foo1"/>
    </File>
  </Files>
</Media>"""

    uploadMedia_uploading = addMedia
    uploadMedia_transferring = uploadMedia_uploading.replace(
        'bytesTransferred="0"',
        'bytesTransferred="%s"')
    uploadMedia_upload_finished = addMedia.replace(
        'status="0"',
        'status="8"')

    task_powerOn_1 = '''
<Task status="completed" href="https://example.com/tasks/task-poweron-1">
</Task>'''

    task_renameVm_1 = '''
<Task status="completed" href="https://example.com/tasks/task-renameVm-1">
</Task>'''


class MockedClientData(object):
    data = {
        '/api/versions' : dict(
            GET = CannedData.versions,
        ),
        '/api/v1.0/login' : dict(
            POST = CannedData.login,
        ),
        '/api/v1.0/org/335573498' : dict(
            GET = CannedData.getOrg,
        ),
        '/api/v1.0/catalog/2029780577' : dict(
            GET = CannedData.getCatalog2029780577,
        ),
        '/api/v1.0/catalog/1422628290' : dict(
            GET = CannedData.getCatalog1422628290,
        ),
        '/api/v1.0/catalog/1007548327' : dict(
            GET = CannedData.getCatalog1007548327,
        ),
        '/api/v1.0/catalog/8675309' : dict(
            GET = CannedData.getCatalog8675309,
        ),
        '/api/v1.0/vdc/52889018' : dict(
            GET = CannedData.getVdc52889018,
        ),
        '/api/v1.0/vdc/1966130069' : dict(
            GET = CannedData.getVdc1966130069,
        ),
        '/api/v1.0/vdc/52889018/action/uploadVAppTemplate' : dict(
            POST = (201, CannedData.uploadVAppTemplate_90220688_new),
        ),
        '/api/v1.0/vdc/52889018/action/instantiateVAppTemplate' : dict(
            POST = (201, CannedData.InstantiateVappTemplate_new),
        ),
        '/transfer/eb1046d7-dbb9-4cbe-a95d-08e6450af7ea/descriptor.ovf' : dict(
            PUT = "",
        ),
        '/transfer/00000000-0000-0000-0000-000000000001/some-file-6-1-x86.vmdk' : dict(
            PUT = "<put/>",
        ),
        '/transfer/foo1' : dict(
            PUT = "<put/>",
        ),
        '/api/v1.0/vAppTemplate/vappTemplate-90220688' : dict(
            GET = mockedData.MultiResponse([
                CannedData.uploadVAppTemplate_90220688_ovf_uploading,
                CannedData.uploadVAppTemplate_90220688_ovf_uploading,
                CannedData.uploadVAppTemplate_90220688_ovf_uploaded,
                CannedData.uploadVAppTemplate_90220688_vmdk_transferring % 4194304,
                CannedData.uploadVAppTemplate_90220688_vmdk_transferring % 8388608,
                CannedData.uploadVAppTemplate_90220688_vmdk_transferring % 12345678,
                CannedData.uploadVAppTemplate_90220688_files_uploaded,
                CannedData.uploadVAppTemplate_90220688_upload_finished,
                CannedData.uploadVAppTemplate_90220688_upload_finished_ovf,

            ])
        ),
        '/api/v1.0/catalog/1422628290/catalogItems' : dict(
            POST = (201, CannedData.addVappTemplateToCatalog_90220688),
        ),
        '/api/v1.0/vAppTemplate/vappTemplate-90220688/ovf' : dict(
            GET = CannedData.getVappTemplate90220688_ovf,
        ),
        '/api/v1.0/vApp/vapp-1836764865' : dict(
            GET = CannedData.getVapp1836764865,
        ),
        '/api/v1.0/vApp/vapp-9198675309' : dict(
            GET = mockedData.MultiResponse([
                CannedData.getVapp9198675309,
                CannedData.getVapp9198675309,
                CannedData.getVapp9198675309_poweredon,
                CannedData.getVapp9198675309_poweredon,
                CannedData.getVapp9198675309_poweredon,
                CannedData.getVapp9198675309_poweredon_w_network,
                CannedData.getVapp9198675309_poweredon_w_network,
            ]),
        ),
        '/api/v1.0/vApp/vm-8675309' : dict(
            PUT = (202, CannedData.task_renameVm_1),
        ),
        '/api/v1.0/vdc/52889018/media' : dict(
            POST = (201, CannedData.addMedia),
        ),
        '/media/foo-1' : dict(
            GET = mockedData.MultiResponse([
                CannedData.uploadMedia_uploading,
                CannedData.uploadMedia_transferring % 10000,
                CannedData.uploadMedia_transferring % 20000,
                CannedData.uploadMedia_upload_finished,
            ])
        ),
        '/api/v1.0/vApp/vapp-9198675309/power/action/powerOn' : dict(
            POST = (202, CannedData.task_powerOn_1),
        ),
        '/tasks/task-poweron-1' : dict(
            GET = CannedData.task_powerOn_1,
        ),
        '/tasks/task-renameVm-1' : dict(
            GET = CannedData.task_renameVm_1,
        ),
    }
    def __init__(self):
        import copy
        self.data = copy.deepcopy(MockedClientData.data)

    def getResponse(self, method, path, body=None):
        mdict = self.data.get(path, None)
        if mdict is None:
            raise RuntimeError("Mock me", path)
        rdata = mdict.get(method, None)
        if rdata is None:
            raise RuntimeError("Mock me", path, method)
        if isinstance(rdata, dict):
            rdata = rdata.get(body, None)
            if rdata is None:
                raise RuntimeError("Mock me", path, method, body)
        if isinstance(rdata, tuple):
            status, rdata = rdata
        else:
            status = 200
        if isinstance(rdata, mockedData.MultiResponse):
            resp = rdata.getData()
        else:
            resp = mockedData.MockedResponse(rdata, status=status)
        return resp

def _t(data):
    return data

_xmlNewCloud = """
<descriptorData>
  <alias>vcloud2</alias>
  <description>description for vcloud2</description>
  <serverName>vcloud2.eng.rpath.com</serverName>
  <organization>rPath</organization>
  <port>2443</port>
</descriptorData>"""

_xmlNewCreds = """
<descriptorData>
  <username>abc</username>
  <password>12345678</password>
</descriptorData>
"""

if __name__ == "__main__":
    testsuite.main()
