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

from lxml import etree
import os
import httplib
import StringIO

from conary.lib import util

import testbase

from catalogService.restClient import ResponseError

from catalogService import instanceStore
from catalogService import storage
from catalogService.rest import baseDriver
from catalogService.rest.drivers import vmware
from catalogService.rest.models import clouds
from catalogService.rest.models import credentials
from catalogService.rest.models import descriptor
from catalogService.rest.models import images
from catalogService.rest.models import instances

from catalogService_test import mockedData

class FakeSocket(StringIO.StringIO):
    def makefile(self, *args):
        # Poor man's refcount. We don't want the closing of the main request
        # to also close the response
        count = getattr(self, 'count', 0)
        self.count = count + 1
        return self

    def close(self):
        count = getattr(self, 'count', 0)
        if count == 0:
            StringIO.StringIO.close(self)
            return
        self.count = count - 1

class HTTPResponse(httplib.HTTPResponse):
    def __init__(self, *args, **kw):
        httplib.HTTPResponse.__init__(self, *args, **kw)
        self._readBuf = None

    def _readAll(self):
        self._readBuf = httplib.HTTPResponse.read(self)

    def read(self, *args, **kw):
        return self._readBuf

class MockTransport(httplib.HTTPSConnection):
    useRealWorld = False

    def __init__(self, *args, **kw):
        httplib.HTTPSConnection.__init__(self, *args, **kw)
        self._sendBuf = []

    def connect(self):
        if self.useRealWorld:
            httplib.HTTPSConnection.connect(self)

    def send(self, buf):
        self._sendBuf.append(buf)
        if self.useRealWorld:
            httplib.HTTPSConnection.send(self, buf)

    def getresponse(self):
        requestData = ''.join(self._sendBuf)
        # trim off the HTTP headers
        requestData = requestData[requestData.find('\r\n\r\n') + 4:]
        if not self.useRealWorld:
            #if not mockedData.vmwareSoapData.has_key(requestData):
            #    import epdb;epdb.st()
            responseData = mockedData.vmwareSoapData[requestData]
            if isinstance(responseData, mockedData.HTTPResponse):
                responseData = responseData.getData()
            self.sock = FakeSocket(responseData)
        response = httplib.HTTPSConnection.getresponse(self)
        if self.useRealWorld:
            length = response.length
            sio = StringIO.StringIO(response.read())
            response.fp = sio
            response.length = length
            import pprint
            pprint.pprint({requestData:sio.getvalue()})
        return response

class VMwareTest(testbase.TestCase):
    TARGETS = [
        ('vmware', mockedData.tmp_vmwareName1,
            dict(
                 alias = mockedData.tmp_vmwareAlias1,
                 description = mockedData.tmp_vmwareDescription1,
                 defaultDiskProvisioning = 'twoGbMaxExtentSparse',
            )),
    ]
    USER_TARGETS = [
        ('JeanValjean', 'vmware', mockedData.tmp_vmwareName1, dict(
             username = 'abc',
             password = '12345678',
            )),
    ]
    cloudName = mockedData.tmp_vmwareName1
    cloudType = 'vmware'
    _baseCloudUrl = 'clouds/%s/instances/%s' % (cloudType, cloudName)

    def setUp(self):
        testbase.TestCase.setUp(self)
        self.mock(vmware.driver, 'VimServiceTransport', MockTransport)
        # MockTransport.useRealWorld = True
        if MockTransport.useRealWorld:
            self.mock(vmware.driver, 'drvGetCloudCredentialsForUser',
                lambda x: dict(username = 'eng', password = 'CHANGEME'))
        for k, v in mockedData.vmwareSoapData.items():
            if isinstance(v, mockedData.HTTPResponse):
                v.reset()
        self.mock(vmware.driver.ProgressUpdate, 'INTERVAL', 0.0001)

    def  _replaceVmwareData(self, dataDict):
        vmwareSoapData = mockedData.vmwareSoapData.copy()
        vmwareSoapData.update(dataDict)
        self.mock(mockedData, 'vmwareSoapData', vmwareSoapData)

    def testInternalGetAllInstances(self):
        inst = vmware.driver.Instance(instanceName='foobar')
        inst.setCredentials([ 1, 2, 3 ])
        hndlr = instances.Handler()
        self.failUnlessEqual(hndlr.toXml(inst, prettyPrint=True), """\
<?xml version='1.0' encoding='UTF-8'?>
<instance xmlNodeHash="c5732bfb9e528e004a85db404448d54c4a990c5b">
  <credentials>
    <opaqueCredentialsId>1</opaqueCredentialsId>
    <opaqueCredentialsId>2</opaqueCredentialsId>
    <opaqueCredentialsId>3</opaqueCredentialsId>
  </credentials>
  <instanceName>foobar</instanceName>
</instance>
""")

    def testGetClouds1(self):
        srv = self.newService()
        uri = 'clouds/vmware/instances'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = clouds.Handler()
        response = util.BoundedStringIO(response.read())
        nodes = hndlr.parseFile(response)

        self.failUnlessEqual([x.getCloudName() for x in nodes],
            ['virtcenter.eng.rpath.com'])

        self.failUnlessEqual([x.getCloudAlias() for x in nodes],
            ['virtcenter'])

        self.failUnlessEqual([x.getDescription() for x in nodes],
            ['virtual center'])

    def testGetInstances1(self):
        srv = self.newService()
        uri = 'clouds/vmware/instances/virtcenter.eng.rpath.com/instances'
        client = self.newClient(srv, uri)

        # Add the instance in the store too, make sure it's overwritten by the
        # real code
        self.storagePath = os.path.join(self.workDir, "storage")
        cfg = storage.StorageConfig(storagePath =
            os.path.join(self.storagePath, "instances", "vmware"))
        store = instanceStore.InstanceStore(
            vmware.vmwareclient.InstanceStorage(cfg),
            'virtcenter.eng.rpath.com/JeanValjean')
        instanceId = '50344408-f9b7-3927-417b-14258d839e26'
        store.setInstanceName(instanceId, "Bleeeeep")
        store.setExpiration(instanceId, 10000)
        store.setImageId(instanceId, '361d7fa1-d994-31e1-6a3a-438c8d4ebaa7')

        response = client.request('GET')
        self.failUnlessEqual(response.msg['Content-Type'], 'application/xml')
        self.failUnlessEqual(response.msg['Cache-Control'], 'no-store')
        hndlr = instances.Handler()
        response = util.BoundedStringIO(response.read())
        nodes = hndlr.parseFile(response)
        self.failUnless(
            isinstance(nodes, instances.BaseInstances),
            nodes)
        self.failUnlessEqual([x.getInstanceId() for x in nodes],
                             ['50344408-f9b7-3927-417b-14258d839e26', '50348202-8fcd-a662-2585-aabbccddeeff'])
        self.failUnlessEqual([x.getInstanceName() for x in nodes],
            ['Solaris10a', 'without-annotation'])
        self.failUnlessEqual([x.getInstanceDescription() for x in nodes],
            [u'\u00fc', ''])
        self.failUnlessEqual([x.getLaunchTime() for x in nodes],
            ['1226931868', None])

    def testCredentialsProtection(self):
        # Make sure we don't expose credentials, passwords should be wrapped
        # in a ProtectedUnicode
        origDrvGetCloudCredentialsForUser = vmware.driver.drvGetCloudCredentialsForUser
        credsFile = os.path.join(self.workDir, 'protectedCredentials')
        def mockDrvGetCloudCredentialsForUser(*args, **kwargs):
            # This is called in a different process, so write the type
            # of the password field to disk
            ret = origDrvGetCloudCredentialsForUser(*args, **kwargs)
            file(credsFile, "a").write("%s\n" % type(ret['password']).__name__)
            return ret
        self.mock(vmware.driver, 'drvGetCloudCredentialsForUser', mockDrvGetCloudCredentialsForUser)

        srv = self.newService()
        instId = '50344408-f9b7-3927-417b-14258d839e26'
        uri = 'clouds/vmware/instances/virtcenter.eng.rpath.com/instances'
        uri += '/' + instId
        client = self.newClient(srv, uri)

        response = client.request('GET')
        self.assertEquals(file(credsFile).read().strip(),
            "ProtectedUnicode")

    def testGetInstance1(self):
        srv = self.newService()
        instId = '50344408-f9b7-3927-417b-14258d839e26'
        uri = 'clouds/vmware/instances/virtcenter.eng.rpath.com/instances'
        uri += '/' + instId
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = instances.Handler()
        node = hndlr.parseString(response.read())

        # Normally we should only get one instance, but the call is mocked
        self.failUnlessEqual(node.getInstanceId(), instId)

    def testGetImagesESX35(self):
        self._replaceVmwareData({
            mockedData.vmwareRetrieveServiceContentRequest :
                mockedData.vmwareRetrieveServiceContentResponseESX35})

        srv = self.newService()
        uri = 'clouds/vmware/instances/virtcenter.eng.rpath.com/images'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = images.Handler()
        response = util.BoundedStringIO(response.read())
        nodes = hndlr.parseFile(response)
        self.failUnless(
            isinstance(nodes, images.BaseImages),
            nodes)

        # ESX has no templates
        self.failUnlessEqual([x.getImageId() for x in nodes],
                             ['00000000-0000-0000-0000-0000000000a9',
                              '361d7fa1-d994-31e1-6a3a-438c8d4ebaa7',
                              'plainEsx-Sha1-sum0-0000-000000000000'])
        self.assertEquals([x.getBuildPageUrl() for x in nodes],
            ['http://test.rpath.local2/project/foo/build?id=169',
             'http://test.rpath.local2/project/foo/build?id=6',
             'http://test.rpath.local2/project/foo/build?id=69',])
        self.assertEquals([x.getDownloadUrl() for x in nodes],
            ['http://test.rpath.local2/downloadImage?id=692',
             'http://test.rpath.local2/downloadImage?id=6',
             'http://test.rpath.local2/downloadImage?id=691',])
        self.failUnlessEqual([x.getLongName() for x in nodes],
            ['169/some-file-6-1-x86', '6/some-file-6-1-x86', '69/some-file-6-1-x86'])

    def testGetImages1(self):
        srv = self.newService()
        uri = 'clouds/vmware/instances/virtcenter.eng.rpath.com/images'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = images.Handler()
        response = util.BoundedStringIO(response.read())
        nodes = hndlr.parseFile(response)
        self.failUnless(
            isinstance(nodes, images.BaseImages),
            nodes)

        self.failUnlessEqual([x.getImageId() for x in nodes],
                             [
                              '00000000-0000-0000-0000-0000000000a9',
                              '50348202-8fcd-a662-2585-c4db19d28079',
                              'aaaaaabb-bbbb-bbbc-cccc-ccccccdddddd',
                              'sha1ForO-vf09-1111-1111-111111111111',
#                              'sha1ForO-vf10-1111-1111-111111111111',
                              ])
        self.assertEquals([x.getBuildId() for x in nodes],
            ['169', None, '6', '69'])
        self.assertEquals([x.getBuildPageUrl() for x in nodes],
            ['http://test.rpath.local2/project/foo/build?id=169',
            None, 'http://test.rpath.local2/project/foo/build?id=7',
            'http://test.rpath.local2/project/foo/build?id=69'])
        self.assertEquals([x.getDownloadUrl() for x in nodes],
            ['http://test.rpath.local2/downloadImage?id=692',
            None, 'http://test.rpath.local2/downloadImage?id=7',
            'http://test.rpath.local2/downloadImage?id=692'])
        self.failUnlessEqual([x.getLongName() for x in nodes],
            ['169/some-file-6-1-x86', u'Ma\xefs', '6/some-file-6-1-x86',
             '69/some-file-6-1-x86'])

    def testGetConfigurationDescriptor(self):
        srv = self.newService()
        uri = 'clouds/vmware/descriptor/configuration'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getDisplayName(), "VMware Configuration")
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'Configure VMware'})
        self.failUnlessEqual([ df.name for df in dsc.getDataFields() ],
            ['name', 'alias', 'description', 'defaultDiskProvisioning', ])
        self.failUnlessEqual([ df.type for df in dsc.getDataFields()[:-1] ],
            ['str', 'str', 'str',])
        field = dsc.getDataField('defaultDiskProvisioning')
        self.assertEquals(field.required, True)
        self.assertEquals(field.default, ['flat'])
        self.assertEquals([ x.key for x in field.enumeratedType.describedValue ],
            [
                'sparse', 'flat',
                'thin', 'thick',
                'monolithicSparse', 'monolithicFlat',
                'twoGbMaxExtentSparse', 'twoGbMaxExtentFlat',
            ])
        self.failUnlessEqual([ df.multiple for df in dsc.getDataFields() ],
            [None, None, None, None,])
        self.failUnlessEqual([ df.descriptions.asDict()
                for df in dsc.getDataFields() ],
            [
                {None : 'Server Address'}, {None : 'Name'},
                {None : 'Full Description'},
                {None : 'Default Disk Provisioning (ESX 5.x+)'},
              ])

        def _helpurl(data):
            if data is None:
                return {}
            return { None:
                self.makeUri(client, "help/targets/drivers/%s/configuration/%s" %
                    (self.cloudType, data)) }
        self.failUnlessEqual([ df.helpAsDict for df in dsc.getDataFields() ],
            [ _helpurl(x) for x in [
                'serverName.html',
                'alias.html',
                'description.html',
                'defaultDiskProvisioning.html',
            ] ]
        )

    def testGetCredentialsDescriptor(self):
        srv = self.newService()
        uri = 'clouds/vmware/descriptor/credentials'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.CredentialsDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getDisplayName(), "VMware User Credentials")
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'User Credentials for VMware'})
        self.failUnlessEqual([ df.name for df in dsc.getDataFields() ],
            ['username', 'password'])
        self.failUnlessEqual([ df.type for df in dsc.getDataFields() ],
            ['str', 'str'])
        self.failUnlessEqual([ df.multiple for df in dsc.getDataFields() ],
            [None] * len(dsc.getDataFields()))
        self.failUnlessEqual([ df.descriptions.asDict()
                for df in dsc.getDataFields() ],
            [{None : 'User Name'}, {None : 'Password'}])
        self.failUnlessEqual([ df.constraints.descriptions.asDict()
                for df in dsc.getDataFields() ],
            [{None: u'Field must contain between 1 and 32 characters'}, 
             {None: u'Field must contain between 1 and 32 characters'}]) 
        self.failUnlessEqual([ df.constraints.presentation()
                for df in dsc.getDataFields() ],
            [
                [{'constraintName': 'length', 'value': 32}],
                [{'constraintName': 'length', 'value': 32}]
            ])
        self.failUnlessEqual([ df.password for df in dsc.getDataFields() ],
            [None, True])

    def testGetConfiguration(self):
        self.setAdmin(True)
        srv = self.newService()
        uri = 'clouds/vmware/instances/virtcenter.eng.rpath.com/configuration'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        self.assertXMLEquals(response.read(), """\
<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/vmware/instances/virtcenter.eng.rpath.com/configuration">
    <alias>virtcenter</alias>
    <defaultDiskProvisioning>twoGbMaxExtentSparse</defaultDiskProvisioning>
    <description>virtual center</description>
    <name>virtcenter.eng.rpath.com</name>
</descriptorData>""" %
            client.hostport)

    def testGetCredentials(self):
        srv = self.newService()
        uri = 'clouds/vmware/instances/virtcenter.eng.rpath.com/users/%(username)s/credentials?_method=GET'

        client = self.newClient(srv, uri)
        response = client.request('POST')
        hndlr = credentials.Handler()
        data = response.read()
        self.assertXMLEquals(data, """<?xml version='1.0' encoding='UTF-8'?>\n<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/vmware/instances/virtcenter.eng.rpath.com/users/JeanValjean/credentials">\n  <username>abc</username>\n  <password>12345678</password>\n</descriptorData>\n""" % client.hostport)

        # Wrong user name
        uri = 'clouds/vmware/instances/virtcenter.eng.rpath.com/users/NOSUCHUSER/credentials'
        client = self.newClient(srv, uri)
        e = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(e.status, 401)

        # bad cloud name (this should probably be moved to the instances test)
        uri = 'clouds/vmware/instances/badcloud.eng.rpath.com/users/NOSUCHUSER/credentials'
        client = self.newClient(srv, uri)
        e = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(e.status, 404)

    def testNewCloud(self):
        srv = self.newService()
        uri = 'clouds/vmware/instances'
        client = self.newClient(srv, uri)

        reqData = _xmlNewCloud
        response = client.request('POST', reqData)

        hndl = clouds.Handler()
        node = hndl.parseString(response.read())

        cloudId = "http://%s/TOPLEVEL/clouds/%s/instances/%s" % (
            client.hostport, 'vmware', 'newbie.eng.rpath.com')
        self.failUnlessEqual(node.getId(), cloudId)
        self.failUnlessEqual(node.getCloudAlias(), 'newbie')
        self.failUnlessEqual(node.getCloudName(), 'newbie.eng.rpath.com')
        self.failUnlessEqual(node.getType().getText(), 'vmware')

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
        uri = 'clouds/vmware/instances'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndl = clouds.Handler()
        nodes = hndl.parseString(response.read())
        self.failUnlessEqual(len(nodes), 2)
        node = nodes[0]
        self.failUnlessEqual(node.getCloudAlias(), 'newbie')

        # Try to enumerate images - it should fail
        uri = 'clouds/vmware/instances/newbie.eng.rpath.com/images'
        client = self.newClient(srv, uri)
        resp = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(resp.status, 400)
        self.assertXMLEquals(resp.contents, '<?xml version="1.0" encoding="UTF-8"?>\n<fault>\n  <code>400</code>\n  <message>Target credentials not set for user</message>\n</fault>')


    def testSetCredentials(self):
        cloudName = 'virtcenter.eng.rpath.com'
        srv = self.newService()
        uri = 'clouds/vmware/instances/virtcenter.eng.rpath.com/users/%(username)s/credentials?_method=PUT'

        hndlr = credentials.Handler()

        client = self.newClient(srv, uri)
        response = client.request('POST', body = _xmlNewCreds)

        data = response.read()
        node = hndlr.parseString(data)

        self.failUnlessEqual(node.getValid(), True)

        # Make sure credentials made it

        creds = self.restdb.targetMgr.getTargetCredentialsForUser('vmware',
            mockedData.tmp_vmwareName1, 'JeanValjean')
        self.failUnlessEqual(creds, dict(username='abc',
                                         password='12345678'))

    def testTerminateInstance1(self):
        self._replaceVmwareData({
            mockedData.vmwareWaitForUpdatesRequest1 :
                mockedData.HTTPResponse([
                    mockedData.vmwareWaitForUpdatesResponseRegisterVM1,
                ]),
        })

        srv = self.newService()
        uri = 'clouds/vmware/instances/virtcenter.eng.rpath.com/instances/50344408-f9b7-3927-417b-14258d839e26'
        client = self.newClient(srv, uri)

        response = client.request('DELETE')
        hndlr = instances.Handler()
        response = util.BoundedStringIO(response.read())
        nodes = hndlr.parseFile(response)
        self.failUnless(
            isinstance(nodes, instances.BaseInstances),
            nodes)
        self.failUnlessEqual([x.getInstanceId() for x in nodes],
                             ['50344408-f9b7-3927-417b-14258d839e26'])
        self.failUnlessEqual([x.getState() for x in nodes],
                             ['Terminating'])

    def testGetImageDeploymentDescriptor(self):
        srv = self.newService()
        uri = 'clouds/vmware/instances/virtcenter.eng.rpath.com/descriptor/deployImage'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getRootElement(), "newImage")
        self.failUnlessEqual(dsc.getDisplayName(), "VMware Image Upload Parameters")
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'VMware Image Upload Parameters'})
        self.failUnlessEqual([ df.name for df in dsc.getDataFields() ],
            ['imageId', 'imageName', 'imageDescription', 'dataCenter',
                'vmfolder-datacenter-2', 'cr-datacenter-2',
                'network-datacenter-2',
                'dataStoreSelection-domain-c5',
                'dataStoreFreeSpace-domain-c5-filter',
                'dataStoreLeastOvercommitted-domain-c5-filter',
                'dataStore-domain-c5', 'resourcePool-domain-c5'])
        self.failUnlessEqual([ df.constraintsPresentation
                for df in dsc.getDataFields() ],
            [
                [{'max': 32, 'constraintName': 'range', 'min': 1}],
                [{'constraintName': 'length', 'value': 76}],
                [{'constraintName': 'length', 'value': 128}],
                [],
                [],
                [],
                [],
                [],
                [],
                [],
                [],
                [],
            ])

    def testGetLaunchDescriptor(self):
        srv = self.newService()
        uri = 'clouds/vmware/instances/virtcenter.eng.rpath.com/descriptor/launch'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getRootElement(), "newInstance")
        self.failUnlessEqual(dsc.getDisplayName(), "VMware Launch Parameters")
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'VMware Launch Parameters'})
        self.failUnlessEqual([ df.name for df in dsc.getDataFields() ],
            ['imageId', 'instanceName', 'instanceDescription',
                'vmCPUs', 'vmMemory', 'rootSshKeys',
                'dataCenter',
                'vmfolder-datacenter-2',
                'cr-datacenter-2', 'network-datacenter-2',
                'dataStoreSelection-domain-c5',
                'dataStoreFreeSpace-domain-c5-filter',
                'dataStoreLeastOvercommitted-domain-c5-filter',
                'dataStore-domain-c5', 'resourcePool-domain-c5'])
        ftypes = [ df.type for df in dsc.getDataFields() ]
        self.failUnlessEqual(ftypes[:6],
            ['str', 'str', 'str', 'int', 'int', 'str', ])
        self.failUnlessEqual([ [ (x.key, x.descriptions.asDict()) for x in ftype ]
            for ftype in [ ftypes[6] ] ],
            [[(u'datacenter-2', {None: u'rPath'})]])
        expMultiple = [None] * len(dsc.getDataFields())
        self.failUnlessEqual([ df.multiple for df in dsc.getDataFields() ],
            expMultiple)
        self.failUnlessEqual([ df.required for df in dsc.getDataFields() ],
            [ True, True, None, True, True, None, True, True, True, True, True,
                True, True, True, True, ] )
        self.failUnlessEqual([ df.hidden for df in dsc.getDataFields() ],
            [ True, None, None, None, None, None, None, None, None, None, None,
                None, None, None, None, ] )
        self.failUnlessEqual([ df.descriptions.asDict()
                for df in dsc.getDataFields() ],
            [
                {None: 'Image ID'},
                {None: 'Instance Name'},
                {None: 'Instance Description'},
                {None: 'Number of Virtual CPUs'},
                {None: 'RAM (Megabytes)'},
                {None: 'Root SSH keys'},
                {None: 'Data Center'},
                {None: 'VM Folder'},
                {None: 'Compute Resource'},
                {None: 'Network'},
                {None: 'Data Store Selection'},
                {None: 'Filter'},
                {None: 'Filter'},
                {None: 'Data Store'},
                {None: 'Resource Pool'},
            ])
        self.failUnlessEqual([ df.constraintsPresentation
                for df in dsc.getDataFields() ],
            [
                [{'max': 32, 'constraintName': 'range', 'min': 1}],
                [{'constraintName': 'length', 'value': 32}],
                [{'constraintName': 'length', 'value': 128}],
                [{'max': 32, 'constraintName': 'range', 'min': 1}],
                [{'max': 131072, 'constraintName': 'range', 'min': 256}],
                [{'constraintName': 'length', 'value': 4096}],
                [],
                [],
                [],
                [],
                [],
                [],
                [],
                [],
                [],
            ])
        self.failUnlessEqual([ df.getDefault() for df in dsc.getDataFields() ],
            [None, None, None, 1, 1024, None, 'datacenter-2', 'group-v3', 'domain-c5', 'dvportgroup-9987',
             'dataStoreFreeSpace-domain-c5', '*', '*',
             'datastore-18', 'resgroup-50'])
        df = dsc.getDataField('network-datacenter-2')
        self.failUnlessEqual( [ x.descriptions.asDict() for x in df.type ],
            [ {None : 'Engineering lab'} ] )
        self.failUnlessEqual( [ x.key for x in df.type ],
            [ 'dvportgroup-9987' ])

        df = dsc.getDataField('vmfolder-datacenter-2')
        self.failUnlessEqual( [ x.descriptions.asDict() for x in df.type ],
            [
                {None: '/vm'},
                {None: '/vm/subfolder1'},
                {None: '/vm/subfolder1/subfolder11'},
                {None: '/vm/subfolder2'},
            ])
        self.failUnlessEqual( [ x.key for x in df.type ],
            ['group-v3', 'group-v31', 'group-v311', 'group-v32'])

        def _helpurl(data):
            if data is None:
                return {}
            return { None:
                self.makeUri(client, "help/targets/drivers/%s/launch/%s" %
                    (self.cloudType, data)) }

        self.failUnlessEqual([ df.helpAsDict
                for df in dsc.getDataFields() ],
            [ _helpurl(x) for x in [
                None,
                'instanceName.html',
                'instanceDescription.html',
                'vmCPUs.html',
                'vmMemory.html',
                'rootSshKeys.html',
                'dataCenter.html',
                'vmfolder.html',
                'computeResource.html',
                'network.html',
                'dataStoreSelection.html',
                None,
                None,
                'dataStore.html',
                'resourcePool.html',
            ]])

    def testGetLaunchDescriptor2(self):
        vmwareRetrievePropertiesEnvBrowserReq1 = \
            mockedData._vmwareReqRetrievePropertiesSimpleTemplate % dict(
                klass = 'ClusterComputeResource', path = 'environmentBrowser', value = 'domain-c10')
        data = mockedData.vmwareRetrievePropertiesEnvBrowserResp.data
        ret1 = mockedData.HTTPResponse(data.replace('domain-c5', 'domain-c10').
            replace('envbrowser-5', 'envbrowser-10'))
        vmwareRetrievePropertiesEnvBrowserReq2 = \
            mockedData._vmwareReqRetrievePropertiesSimpleTemplate % dict(
                klass = 'ClusterComputeResource', path = 'environmentBrowser', value = 'domain-c20')
        ret2 = mockedData.HTTPResponse(data.replace('domain-c5', 'domain-c20').
            replace('envbrowser-5', 'envbrowser-20'))

        queryConfigTargetReq1 = mockedData.vmwareQueryConfigTargetReq1.replace(
            'envbrowser-5', 'envbrowser-10')

        queryConfigTargetReq2 = mockedData.vmwareQueryConfigTargetReq1.replace(
            'envbrowser-5', 'envbrowser-20')

        self._replaceVmwareData({
            mockedData.vmwareRetrievePropertiesReq1:
                mockedData.vmwareRetrievePropertiesResp2,
            vmwareRetrievePropertiesEnvBrowserReq1 : ret1,
            vmwareRetrievePropertiesEnvBrowserReq2 : ret2,
            queryConfigTargetReq1 : mockedData.vmwareQueryConfigTargetResp10,
            queryConfigTargetReq2 : mockedData.vmwareQueryConfigTargetResp20,
        })
        srv = self.newService()
        uri = 'clouds/vmware/instances/virtcenter.eng.rpath.com/descriptor/launch'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getDisplayName(), "VMware Launch Parameters")
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'VMware Launch Parameters'})
        self.failUnlessEqual([ df.name for df in dsc.getDataFields() ],
            ['imageId', 'instanceName', 'instanceDescription',
                'vmCPUs', 'vmMemory', 'rootSshKeys',
                'dataCenter', 'vmfolder-datacenter-10', 'cr-datacenter-10',
                'vmfolder-datacenter-20', 'cr-datacenter-20',
                'network-datacenter-10', 'network-datacenter-20',
                'dataStoreSelection-domain-c10', 'dataStoreFreeSpace-domain-c10-filter', 'dataStoreLeastOvercommitted-domain-c10-filter',
                'dataStore-domain-c10',
                'dataStoreSelection-domain-c20', 'dataStoreFreeSpace-domain-c20-filter', 'dataStoreLeastOvercommitted-domain-c20-filter',
                'dataStore-domain-c20',
                'resourcePool-domain-c10', 'resourcePool-domain-c20'])
        ftypes = [ df.type for df in dsc.getDataFields() ]
        self.failUnlessEqual(ftypes[:6],
            ['str', 'str', 'str', 'int', 'int', 'str', ])
        self.failUnlessEqual([ [ (x.key, x.descriptions.asDict()) for x in ftype ]
            for ftype in [ ftypes[6] ] ],
                [[('datacenter-10', {None: 'rPath 1'}),
                  ('datacenter-20', {None: 'rPath 2'})]])
        expMultiple = [None] * len(dsc.getDataFields())
        self.failUnlessEqual([ df.multiple for df in dsc.getDataFields() ],
            expMultiple)
        self.failUnlessEqual([ df.required for df in dsc.getDataFields() ],
            [ True, True, None, True, True, None, ] + [ True ] * (len(dsc.getDataFields()) - 6))
        self.failUnlessEqual([ df.hidden for df in dsc.getDataFields() ],
            [ True, None, None ] + [ None ] * (len(dsc.getDataFields()) - 3))
        self.failUnlessEqual([ df.descriptions.asDict()
                for df in dsc.getDataFields() ],
            [
                {None: 'Image ID'},
                {None: 'Instance Name'},
                {None: 'Instance Description'},
                {None: 'Number of Virtual CPUs'},
                {None: 'RAM (Megabytes)'},
                {None: 'Root SSH keys'},
                {None: 'Data Center'},
                {None: 'VM Folder'},
                {None: 'Compute Resource'},
                {None: 'VM Folder'},
                {None: 'Compute Resource'},
                {None: 'Network'},
                {None: 'Network'},
                {None: 'Data Store Selection'},
                {None: 'Filter'},
                {None: 'Filter'},
                {None: 'Data Store'},
                {None: 'Data Store Selection'},
                {None: 'Filter'},
                {None: 'Filter'},
                {None: 'Data Store'},
                {None: 'Resource Pool'},
                {None: 'Resource Pool'},
            ])
        self.failUnlessEqual([ df.constraintsPresentation
                for df in dsc.getDataFields() ],
            [
                [{'max': 32, 'constraintName': 'range', 'min': 1}],
                [{'constraintName': 'length', 'value': 32}],
                [{'constraintName': 'length', 'value': 128}],
                [{'max': 32, 'constraintName': 'range', 'min': 1}],
                [{'max': 131072, 'constraintName': 'range', 'min': 256}],
                [{'constraintName': 'length', 'value': 4096}],
            ] + [ [] ] * (len(dsc.getDataFields()) - 6))
        self.failUnlessEqual([ df.getDefault() for df in dsc.getDataFields() ],
            [None, None, None, 1, 1024, None,
            'datacenter-10', 'group-v10', 'domain-c10', 'group-v20', 'domain-c20',
            'network-10', 'network-20',
            'dataStoreFreeSpace-domain-c10', '*', '*',
            'datastore-101',
            'dataStoreFreeSpace-domain-c20', '*', '*',
            'datastore-201',
            'resgroup-100', 'resgroup-200'])

        def _descr(df):
            if df.type == 'str':
                return "String"
            return [ (x.key, x.descriptions.asDict()) for x in df.type ]

        dfields = dsc.getDataFields()[6:]
        self.failUnlessEqual(
            [ _descr(df) for df in dfields ],
            [
                [
                    ('datacenter-10', {None: 'rPath 1'}),
                    ('datacenter-20', {None: 'rPath 2'}),
                ],
                [('group-v10', {None: '/vm 10'})],
                [('domain-c10', {None: 'lab 1'})],
                [('group-v20', {None: '/vm 20'})],
                [('domain-c20', {None: 'lab 2'})],
                [
                    ('network-10', {None: 'VM Network 10'}),
                    ('dvportgroup-101', {None: 'Engineering Lab 10'}),
                ],
                [
                    ('network-20', {None: 'VM Network 20'}),
                    ('dvportgroup-201', {None: 'Engineering Lab 20'}),
                ],
                [
                    ('dataStoreFreeSpace-domain-c10',
                        {None: 'Most free space'}),
                    ('dataStoreLeastOvercommitted-domain-c10',
                        {None: 'Least Overcommitted'}),
                    ('dataStoreManual-domain-c10',
                        {None: 'Manual'})
                ],
                'String', 'String',
                [
                    ('datastore-101', {None: 'datastore 101 - 381  GiB free'}),
                    ('datastore-102', {None: 'datastore 102 - 381  GiB free'}),
                ],
                [
                    ('dataStoreFreeSpace-domain-c20',
                        {None: 'Most free space'}),
                    ('dataStoreLeastOvercommitted-domain-c20',
                        {None: 'Least Overcommitted'}),
                    ('dataStoreManual-domain-c20',
                        {None: 'Manual'})
                ],
                'String', 'String',
                [
                    ('datastore-201', {None: 'datastore 201 - 381  GiB free'}),
                    ('datastore-202', {None: 'datastore 202 - 381  GiB free'}),
                ],
                [
                    ('resgroup-101', {None: 'Resource Pool 101'}),
                    ('resgroup-100', {None: 'Resource Pool 100'}),
                    ('resgroup-10', {None: 'Resources'}),
                ],
                [
                    ('resgroup-20', {None: 'Resources'}),
                    ('resgroup-200', {None: 'Resource Pool 200'}),
                    ('resgroup-201', {None: 'Resource Pool 201'}),
                ],
            ])

        dfields = dsc.getDataFields()[7:]
        self.failUnlessEqual([
            (df.conditional.fieldName, df.conditional.value)
                for df in dfields ],
            [
                ('dataCenter', 'datacenter-10'),
                ('dataCenter', 'datacenter-10'),
                ('dataCenter', 'datacenter-20'),
                ('dataCenter', 'datacenter-20'),
                ('dataCenter', 'datacenter-10'),
                ('dataCenter', 'datacenter-20'),
                ('cr-datacenter-10', 'domain-c10'),
                ('dataStoreSelection-domain-c10', 'dataStoreFreeSpace-domain-c10'),
                ('dataStoreSelection-domain-c10', 'dataStoreLeastOvercommitted-domain-c10'),
                ('dataStoreSelection-domain-c10', 'dataStoreManual-domain-c10'),
                ('cr-datacenter-20', 'domain-c20'),
                ('dataStoreSelection-domain-c20', 'dataStoreFreeSpace-domain-c20'),
                ('dataStoreSelection-domain-c20', 'dataStoreLeastOvercommitted-domain-c20'),
                ('dataStoreSelection-domain-c20', 'dataStoreManual-domain-c20'),
                ('cr-datacenter-10', 'domain-c10'),
                ('cr-datacenter-20', 'domain-c20'),
            ])

    def testGetLaunchDescriptorVsphere50(self):
        self._replaceVmwareData({
            mockedData.vmwareRetrieveServiceContentRequest :
                mockedData.vmwareRetrieveServiceContentResponse50})

        srv = self.newService()
        uri = 'clouds/vmware/instances/virtcenter.eng.rpath.com/descriptor/launch'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getRootElement(), "newInstance")
        field = dsc.getDataField('diskProvisioning')
        self.assertEquals(field.required, True)
        self.assertEquals(field.default, ['twoGbMaxExtentSparse'])
        self.assertEquals([ x.key for x in field.enumeratedType.describedValue ],
            [
                'sparse', 'flat',
                'thin', 'thick',
                'monolithicSparse', 'monolithicFlat',
                'twoGbMaxExtentSparse', 'twoGbMaxExtentFlat',
            ])
        self.assertEquals([ x.descriptions.asDict() for x in field.enumeratedType.describedValue ],
            [
                {None: 'Monolithic Sparse or Thin'},
                {None: 'Monolithic Flat or Thick'},
                {None: 'Thin (Allocated on demand)'},
                {None: 'Thick (Preallocated)'},
                {None: 'Monolithic Sparse (Allocated on demand)'},
                {None: 'Monolithic Flat (Preallocated)'},
                {None: 'Sparse 2G Maximum Extent'},
                {None: 'Flat 2G Maximum Extent'},
            ])

    def _setUpNewImageTest(self, cloudName, daemonizeFunc, imageName,
            imageId = None, downloadFileFunc = None, asOvf = True,
            requestXmlTemplate = None):
        self._mockFunctions(daemonizeFunc=daemonizeFunc,
            downloadFileFunc=downloadFileFunc, asOvf=asOvf)
        if not imageId:
            imageId = '361d7fa1-d994-31e1-6a3a-438c8d4ebaa7'
        cloudType = vmware.driver.cloudType

        srv = self.newService()
        uri = 'clouds/%s/instances/%s/images' % (cloudType, cloudName)

        if requestXmlTemplate is None:
            requestXmlTemplate = mockedData.xml_newImageVMware1
        requestXml = requestXmlTemplate % imageId
        client = self.newClient(srv, uri)
        response = client.request('POST', requestXml)

        job = self.getJobFromResponse(response)
        return srv, client, job, response

    def _setUpNewInstanceTest(self, cloudName, daemonizeFunc, imageName,
            imageId = None, downloadFileFunc = None, asOvf = True):
        self._mockFunctions(daemonizeFunc=daemonizeFunc,
            downloadFileFunc=downloadFileFunc, asOvf=asOvf)
        if not imageId:
            imageId = '361d7fa1-d994-31e1-6a3a-438c8d4ebaa7'
        cloudType = vmware.driver.cloudType

        srv = self.newService()
        uri = 'clouds/%s/instances/%s/instances' % (cloudType, cloudName)

        requestXml = mockedData.xml_newInstanceVMware1 % imageId
        client = self.newClient(srv, uri)
        response = client.request('POST', requestXml)

        job = self.getJobFromResponse(response)
        return srv, client, job, response

    def _mockFunctions(self, daemonizeFunc, downloadFileFunc = None, asOvf = True):
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

        oldGetCredentialsIsoFile = vmware.driver.getCredentialsIsoFile
        def fakeGetCredentialsIsoFile(slf):
            ret = oldGetCredentialsIsoFile(slf)
            # Rename ISO file to something predictible
            dest = os.path.join(os.path.dirname(ret), 'credentials.iso')
            os.rename(ret, dest)
            return dest

        self.mock(vmware.driver, "downloadFile", fakeDownloadFile)
        self.mock(vmware.driver, "Archive", ModifiedArchive)
        self.mock(vmware.driver, "getCredentialsIsoFile", fakeGetCredentialsIsoFile)
        cont = []
        def fakeGenerateString(slf, keyLength):
            ret = "00000000-0000-0000-%04d-000000000000" % len(cont)
            cont.append(ret)
            return ret

        self.mock(vmware.driver.instanceStorageClass, '_generateString',
            fakeGenerateString)

    def testNewInstances_1(self):
        cloudName = 'virtcenter.eng.rpath.com'
        cloudType = vmware.driver.cloudType
        def fakeDaemonize(*args, **kwargs):
            pass

        imageId = 'aaaaaabb-bbbb-bbbc-cccc-ccccccdddddd'
        srv, client, job, response = self._setUpNewInstanceTest(
            cloudName, fakeDaemonize, '', imageId = imageId, asOvf = True)

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        self.failUnlessEqual(job.get_id(),
            self.makeUri(client, jobUrlPath))
        self.failUnlessEqual(job.get_imageId(),
            self.makeUri(client, "clouds/vmware/instances/virtcenter.eng.rpath.com/images/" + imageId))

        # Enumerate instances
        response = client.request('GET')
        hndlr = instances.Handler()
        nodes = hndlr.parseString(response.read())

        self.failUnlessEqual(len(nodes), 2)

        # Grab the job
        client = self.newClient(srv, jobUrlPath)
        response = client.request('GET')

        job = self.getJobFromResponse(response)

        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))

    def testNewInstances_2(self):
        cloudName = 'virtcenter.eng.rpath.com'
        def fakeDaemonize(slf, *args, **kwargs):
            slf.postFork()
            return slf.function(*args, **kwargs)

        imageId = 'aaaaaabb-bbbb-bbbc-cccc-ccccccdddddd'
        # Mock _putFile so we don't really upload something
        putFiles = []
        def fakePutFile(inUrl, outUrl, session = None, method = None,
                callback=None):
            if hasattr(inUrl, 'read'):
                inObj = inUrl
            else:
                inObj = file(inUrl)
            putFiles.append((outUrl, method))
            fout = file(os.devnull, "w")
            if callback:
                callback = callback.progress
            util.copyfileobj(inObj, fout, callback = callback,
                bufSize = 1024 * 1024)
        from catalogService.libs.viclient import vmutils
        self.mock(vmutils, "_putFile", fakePutFile)
        srv, client, job, response = self._setUpNewInstanceTest(
            cloudName, fakeDaemonize, '', imageId = imageId, asOvf = True)

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))

        #self.failUnlessEqual(node.getInstanceId(), "FAKE000")
        #self.failUnlessEqual(node.getReservationId(), None)
        #self.failUnlessEqual(node.getInstanceName(), "instance-foo")
        #self.failUnlessEqual(node.getInstanceDescription(),
        #    "just words and stuff")
        #certFile = os.path.join(self.storagePath, "instances",
        #    "vmware", "virtcenter.eng.rpath.com", "JeanValjean",
        #    "vmuuid10", "x509cert")
        #self.failUnless(os.path.exists(certFile))

        # Enumerate instances
        response = client.request('GET')
        hndlr = instances.Handler()
        nodes = hndlr.parseString(response.read())

        self.failUnlessEqual(len(nodes), 2)

        # Grab the job
        client = self.newClient(srv, jobUrlPath)
        response = client.request('GET')

        job = self.getJobFromResponse(response)
        self.failUnlessEqual([ x.get_content() for x in job.history ],
            ['Launching instance from image aaaaaabb-bbbb-bbbc-cccc-ccccccdddddd (type VMWARE_OVF_IMAGE)',
            'Downloading image', 'Exploding archive',
            'Uploading image to VMware',
            'Importing OVF descriptor',
            'Importing OVF: 0% complete',
            'Importing OVF: 10% complete',
            'Importing OVF: 20% complete',
            'Importing OVF: 30% complete',
            'Importing OVF: 40% complete',
            'Importing OVF: 50% complete',
            'Importing OVF: 60% complete',
            'Importing OVF: 70% complete',
            'Importing OVF: 80% complete',
            'Importing OVF: 90% complete',
            'Importing OVF: 100% complete',
            'Importing OVF: 100% complete',
            'Reconfiguring VM', 'Converting VM to template',
            'Cloning template',
            'Uploading initial configuration',
            'Creating initial configuration disc',
            'Launching', 'Instance launched', 'Instance(s) running: ', 'Done'])
        self.failUnlessEqual(job.get_statusMessage(), 'Done')
        self.failUnlessEqual([ x.href for x in job.get_resultResource() ],
            [ self.makeUri(client, self._baseCloudUrl + '/instances/vmuuid10') ])

    def testNewInstances35_1(self):
        self._replaceVmwareData({
            mockedData.vmwareRetrieveServiceContentRequest :
                mockedData.vmwareRetrieveServiceContentResponse35})

        cloudName = 'virtcenter.eng.rpath.com'
        cloudType = vmware.driver.cloudType
        def fakeDaemonize(*args, **kwargs):
            pass

        imageId = '361d7fa1-d994-31e1-6a3a-438c8d4ebaa7'
        srv, client, job, response = self._setUpNewInstanceTest(
            cloudName, fakeDaemonize, '', imageId = imageId,
            asOvf=False)

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        self.failUnlessEqual(job.get_id(),
            self.makeUri(client, jobUrlPath))
        self.failUnlessEqual(job.get_imageId(),
            self.makeUri(client, "clouds/vmware/instances/virtcenter.eng.rpath.com/images/" + imageId))

        # Enumerate instances
        response = client.request('GET')
        hndlr = instances.Handler()
        nodes = hndlr.parseString(response.read())

        self.failUnlessEqual(len(nodes), 2)

        # Grab the job
        client = self.newClient(srv, jobUrlPath)
        response = client.request('GET')

        job = self.getJobFromResponse(response)

        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))

    def testNewInstances35_2(self):
        self._replaceVmwareData({
            mockedData.vmwareRetrieveServiceContentRequest :
                mockedData.vmwareRetrieveServiceContentResponse35,
            mockedData.vmwareWaitForUpdatesRequest1 :
                mockedData.HTTPResponse([
                    mockedData.vmwareWaitForUpdatesResponseRegisterVM1,
                    mockedData.vmwareWaitForUpdatesResponseReconfigVM1,
                    mockedData.vmwareWaitForUpdatesResponseCloneVM1,
                    mockedData.vmwareWaitForUpdatesResponseReconfigVM1,
                    mockedData.vmwareWaitForUpdatesResponsePowerOnVM1,
                ]),
        })

        cloudName = 'virtcenter.eng.rpath.com'
        cloudType = vmware.driver.cloudType
        def fakeDaemonize(slf, *args, **kwargs):
            return slf.function(*args, **kwargs)

        imageId = '361d7fa1-d994-31e1-6a3a-438c8d4ebaa7'
        # Mock _putFile so we don't really upload something
        putFiles = []
        def fakePutFile(inObj, outUrl, session = None):
            putFiles.append(outUrl)
        from catalogService.libs.viclient import vmutils
        self.mock(vmutils, "_putFile", fakePutFile)
        srv, client, job, response = self._setUpNewInstanceTest(
            cloudName, fakeDaemonize, '', imageId = imageId, asOvf = False)

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        self.failUnlessEqual(job.get_id(),
            self.makeUri(client, jobUrlPath))

        #self.failUnlessEqual(node.getInstanceId(), "FAKE000")
        #self.failUnlessEqual(node.getReservationId(), None)
        #self.failUnlessEqual(node.getInstanceName(), "instance-foo")
        #self.failUnlessEqual(node.getInstanceDescription(),
        #    "just words and stuff")
        #certFile = os.path.join(self.storagePath, "instances",
        #    "vmware", "virtcenter.eng.rpath.com", "JeanValjean",
        #    "vmuuid10", "x509cert")
        #self.failUnless(os.path.exists(certFile))

        # Enumerate instances
        response = client.request('GET')
        hndlr = instances.Handler()
        nodes = hndlr.parseString(response.read())

        self.failUnlessEqual(len(nodes), 2)

        # Grab the job
        client = self.newClient(srv, jobUrlPath)
        response = client.request('GET')

        job = self.getJobFromResponse(response)

        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))

        self.failUnlessEqual([ x.get_content() for x in job.history ],
            ['Launching instance from image 361d7fa1-d994-31e1-6a3a-438c8d4ebaa7 (type VMWARE_ESX_IMAGE)',
             'Downloading image', 'Exploding archive',
             'Uploading image to VMware', 'Registering VM',
             'Reconfiguring VM', 'Converting VM to template',
             'Cloning template', 'Uploading initial configuration',
             'Creating initial configuration disc', 'Launching',
             'Instance launched', 'Instance(s) running: ', 'Done'])

    def testNewInstancesESX_1(self):
        cloudName = 'virtcenter.eng.rpath.com'
        cloudType = vmware.driver.cloudType

        # Mock RetrieveServiceContent to force ESX
        self._replaceVmwareData({
            mockedData.vmwareRetrieveServiceContentRequest :
            mockedData.vmwareRetrieveServiceContentResponseESX})

        def fakeDaemonize(slf, *args, **kwargs):
            return slf.function(*args, **kwargs)

        imageId = 'aaaaaabb-bbbb-bbbc-cccc-ccccccdddddd'

        # Mock _putFile so we don't really upload something
        putFiles = []
        def fakePutFile(inObj, outUrl, session = None, method = None,
                callback=None):
            putFiles.append((outUrl, method))
            fout = file(os.devnull, "w")
            if callback:
                callback = callback.progress
            util.copyfileobj(inObj, fout, callback = callback,
                bufSize = 1024 * 1024)
        from catalogService.libs.viclient import vmutils
        self.mock(vmutils, "_putFile", fakePutFile)
        srv, client, job, response = self._setUpNewInstanceTest(
            cloudName, fakeDaemonize, '', imageId = imageId)

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))

        # Enumerate instances
        response = client.request('GET')
        hndlr = instances.Handler()
        nodes = hndlr.parseString(response.read())

        self.failUnlessEqual(len(nodes), 2)

        # Grab the job
        client = self.newClient(srv, jobUrlPath)
        response = client.request('GET')

        job = self.getJobFromResponse(response)
        self.failUnlessEqual([ x.get_content() for x in job.history ],
            ['Launching instance from image aaaaaabb-bbbb-bbbc-cccc-ccccccdddddd (type VMWARE_OVF_IMAGE)',
            'Downloading image', 'Exploding archive',
            'Uploading image to VMware',
            'Importing OVF descriptor',
            'Importing OVF: 0% complete',
            'Importing OVF: 10% complete',
            'Importing OVF: 20% complete',
            'Importing OVF: 30% complete',
            'Importing OVF: 40% complete',
            'Importing OVF: 50% complete',
            'Importing OVF: 60% complete',
            'Importing OVF: 70% complete',
            'Importing OVF: 80% complete',
            'Importing OVF: 90% complete',
            'Importing OVF: 100% complete',
            'Importing OVF: 100% complete',
            'Reconfiguring VM',
            'Uploading initial configuration',
            'Creating initial configuration disc',
            'Launching', 'Instance launched', 'Instance(s) running: ', 'Done'])

    def testNewInstancesESX35_1(self):
        cloudName = 'virtcenter.eng.rpath.com'
        cloudType = vmware.driver.cloudType

        # Mock RetrieveServiceContent to force ESX
        self._replaceVmwareData({
            mockedData.vmwareRetrieveServiceContentRequest :
                mockedData.vmwareRetrieveServiceContentResponseESX35,
            mockedData.vmwareWaitForUpdatesRequest2 :
                mockedData.HTTPResponse([
                    mockedData.vmwareWaitForUpdatesResponseRegisterVM1,
                    mockedData.vmwareWaitForUpdatesResponseReconfigVM1,
                    mockedData.vmwareWaitForUpdatesResponseReconfigVM1,
                    mockedData.vmwareWaitForUpdatesResponsePowerOnVM1,
                ]),
        })

        def fakeDaemonize(slf, *args, **kwargs):
            return slf.function(*args, **kwargs)

        imageId = '361d7fa1-d994-31e1-6a3a-438c8d4ebaa7'

        # Mock _putFile so we don't really upload something
        putFiles = []
        def fakePutFile(inObj, outUrl, session = None):
            putFiles.append(outUrl)
        from catalogService.libs.viclient import vmutils
        self.mock(vmutils, "_putFile", fakePutFile)
        srv, client, job, response = self._setUpNewInstanceTest(
            cloudName, fakeDaemonize, '', imageId = imageId, asOvf=False)

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))

        # Enumerate instances
        response = client.request('GET')
        hndlr = instances.Handler()
        nodes = hndlr.parseString(response.read())

        self.failUnlessEqual(len(nodes), 2)

        # Grab the job
        client = self.newClient(srv, jobUrlPath)
        response = client.request('GET')

        job = self.getJobFromResponse(response)
        self.failUnlessEqual([ x.get_content() for x in job.history ],
            ['Launching instance from image 361d7fa1-d994-31e1-6a3a-438c8d4ebaa7 (type VMWARE_ESX_IMAGE)',
             'Downloading image', 'Exploding archive',
             'Uploading image to VMware', 'Registering VM',
             'Reconfiguring VM', 'Uploading initial configuration',
             'Creating initial configuration disc',
             'Launching',
             'Instance launched', 'Instance(s) running: ', 'Done'])


    def testNewInstances35RegisterVMTimeout(self):
        # RBL-4786
        cloudName = 'virtcenter.eng.rpath.com'
        cloudType = vmware.driver.cloudType
        def fakeDaemonize(slf, *args, **kwargs):
            return slf.function(*args, **kwargs)

        # Mock _putFile so we don't really upload something
        putFiles = []
        def fakePutFile(inObj, outUrl, session = None, method = None,
                callback=None):
            putFiles.append(outUrl)
        from catalogService.libs.viclient import vmutils
        self.mock(vmutils, "_putFile", fakePutFile)

        logFilePath = os.path.join(self.workDir, "loginLogFile")
        from catalogService.libs.viclient import client as vclient
        origLogin = vclient.VimService.login

        def mockedLogin(cls, *args, **kwargs):
            file(logFilePath, "a").write("Logging in\n")
            return origLogin(*args, **kwargs)
        self.mock(vclient.VimService, 'login', mockedLogin)

        imageId = '361d7fa1-d994-31e1-6a3a-438c8d4ebaa7'
        try:
            self._replaceVmwareData({
                mockedData.vmwareRetrieveServiceContentRequest :
                    mockedData.vmwareRetrieveServiceContentResponse35,
                mockedData.vmwareRegisterVMreq :
                    mockedData.vmwareRegisterVMreqAuthTimeout})

            resp = self.failUnlessRaises(ResponseError,
                self._setUpNewInstanceTest, cloudName, fakeDaemonize, '',
                imageId = imageId, asOvf=False)
            msg = 'FaultException: The session is not authenticated.'
            self.failUnless(msg in resp.contents,
                "%s not in %s" % (msg, repr(resp.contents)))
            # We should see 2 login tries: the original one and the retry
            self.failUnlessEqual(len(file(logFilePath).readlines()), 2)
        finally:
            pass

    def testNewInstances35_4(self):
        self._replaceVmwareData({
            mockedData.vmwareRetrieveServiceContentRequest :
                mockedData.vmwareRetrieveServiceContentResponse35})

        cloudName = 'virtcenter.eng.rpath.com'
        cloudType = vmware.driver.cloudType
        def fakeDaemonize(slf, *args, **kwargs):
            return slf.function(*args, **kwargs)

        self._replaceVmwareData({
            mockedData.vmwareReqGetVirtualMachineProps1 :
                mockedData.vmwareResponseGetVirtualMachinePropsWithAnnot,
            mockedData.vmwareWaitForUpdatesRequest1 :
                mockedData.HTTPResponse([
                    mockedData.vmwareWaitForUpdatesResponseRegisterVM1,
                    mockedData.vmwareWaitForUpdatesResponseReconfigVM1,
                    mockedData.vmwareWaitForUpdatesResponseCloneVM1,
                    mockedData.vmwareWaitForUpdatesResponseReconfigVM1,
                    mockedData.vmwareWaitForUpdatesResponsePowerOnVM1,
                ]),
        })

        # Mock _putFile so we don't really upload something
        putFilePath = os.path.join(self.workDir, "putLogFile")
        def fakePutFile(inObj, outUrl, session = None):
            file(putFilePath, "a").write("%s\n" % outUrl)

        from catalogService.libs.viclient import vmutils
        self.mock(vmutils, "_putFile", fakePutFile)

        imageId = 'aaaaaabb-bbbb-bbbc-cccc-ccccccdddddd'
        imageId = '361d7fa1-d994-31e1-6a3a-438c8d4ebaa7'
        srv, client, job, response = self._setUpNewInstanceTest(
            cloudName, fakeDaemonize, '', imageId = imageId, asOvf=False)

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        self.failUnlessEqual(job.get_id(),
            self.makeUri(client, jobUrlPath))
        self.failUnlessEqual(job.get_imageId(),
            self.makeUri(client, "clouds/vmware/instances/virtcenter.eng.rpath.com/images/" + imageId))

        # Enumerate instances
        response = client.request('GET')
        hndlr = instances.Handler()
        nodes = hndlr.parseString(response.read())

        self.failUnlessEqual(len(nodes), 2)

        # Grab the job
        client = self.newClient(srv, jobUrlPath)
        response = client.request('GET')

        job = self.getJobFromResponse(response)

        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))

        self.failUnlessEqual([ x.strip() for x in file(putFilePath) ],
            [
            'https://virtcenter.eng.rpath.com/folder/template-some-file-6-1-x86-1/foo.vmx?dcPath=rPath&dsName=nas2-nfs',
            'https://virtcenter.eng.rpath.com/folder/instance-foo/credentials.iso?dcPath=rPath&dsName=nas2-nfs',
            ])

    def testDeployImage1(self):
        cloudName = 'virtcenter.eng.rpath.com'
        def fakeDaemonize(slf, *args, **kwargs):
            slf.postFork()
            return slf.function(*args, **kwargs)

        imageId = 'aaaaaabb-bbbb-bbbc-cccc-ccccccdddddd'
        # Mock _putFile so we don't really upload something
        putFiles = []
        def fakePutFile(inUrl, outUrl, session = None, method = None,
                callback=None):
            if hasattr(inUrl, 'read'):
                inObj = inUrl
            else:
                inObj = file(inUrl)
            putFiles.append((outUrl, method))
            fout = file(os.devnull, "w")
            if callback:
                callback = callback.progress
            util.copyfileobj(inObj, fout, callback = callback,
                bufSize = 1024 * 1024)
        from catalogService.libs.viclient import vmutils
        self.mock(vmutils, "_putFile", fakePutFile)
        srv, client, job, response = self._setUpNewImageTest(
            cloudName, fakeDaemonize, '', imageId = imageId, asOvf = True)

        jobUrlPath = 'jobs/types/image-deployment/jobs/1'
        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))

        #self.failUnlessEqual(node.getInstanceId(), "FAKE000")
        #self.failUnlessEqual(node.getReservationId(), None)
        #self.failUnlessEqual(node.getInstanceName(), "instance-foo")
        #self.failUnlessEqual(node.getInstanceDescription(),
        #    "just words and stuff")
        #certFile = os.path.join(self.storagePath, "instances",
        #    "vmware", "virtcenter.eng.rpath.com", "JeanValjean",
        #    "vmuuid10", "x509cert")
        #self.failUnless(os.path.exists(certFile))

        # Enumerate instances
        response = client.request('GET')
        hndlr = images.Handler()
        nodes = hndlr.parseString(response.read())

        self.failUnlessEqual(len(nodes), 4)

        # Grab the job
        client = self.newClient(srv, jobUrlPath)
        response = client.request('GET')

        job = self.getJobFromResponse(response)
        self.failUnlessEqual([ x.get_content() for x in job.history ],
            ['Running', 'Downloading image', 'Exploding archive',
            'Uploading image to VMware',
            'Importing OVF descriptor',
            'Importing OVF: 0% complete',
            'Importing OVF: 10% complete',
            'Importing OVF: 20% complete',
            'Importing OVF: 30% complete',
            'Importing OVF: 40% complete',
            'Importing OVF: 50% complete',
            'Importing OVF: 60% complete',
            'Importing OVF: 70% complete',
            'Importing OVF: 80% complete',
            'Importing OVF: 90% complete',
            'Importing OVF: 100% complete',
            'Importing OVF: 100% complete',
            'Reconfiguring VM', 'Converting VM to template',
            'Image deployed', 'Done'])
        self.failUnlessEqual(job.get_statusMessage(), 'Done')
        self.failUnlessEqual([ x.href for x in job.get_resultResource() ],
            [ self.makeUri(client, self._baseCloudUrl + '/images/vmuuid10') ])

    def testDeployImageVsphere50(self, diskProvisioning='thin'):
        vmwareCreateImportSpecRequestThin = mockedData.vmwareCreateImportSpecRequest2.replace(
            '</networkMapping>',
            '</networkMapping><ns1:diskProvisioning>%s</ns1:diskProvisioning>' % diskProvisioning)

        self._replaceVmwareData({
            vmwareCreateImportSpecRequestThin : mockedData.vmwareCreateImportSpecResponse1,
            mockedData.vmwareRetrieveServiceContentRequest :
                mockedData.vmwareRetrieveServiceContentResponse50})

        import pickle
        orig_deployImageFromFile = vmware.driver._deployImageFromFile
        invocationFile = os.path.join(self.workDir, "_deployImageFromFile")
        def mock_deployImageFromFile(slf, *args, **kwargs):
            pickle.dump((args[-4:], kwargs), file(invocationFile, "w"))
            return orig_deployImageFromFile(slf, *args, **kwargs)
        self.mock(vmware.driver, '_deployImageFromFile', mock_deployImageFromFile)

        cloudName = 'virtcenter.eng.rpath.com'
        def fakeDaemonize(slf, *args, **kwargs):
            slf.postFork()
            return slf.function(*args, **kwargs)

        imageId = 'aaaaaabb-bbbb-bbbc-cccc-ccccccdddddd'
        # Mock _putFile so we don't really upload something
        putFiles = []
        def fakePutFile(inUrl, outUrl, session = None, method = None,
                callback=None):
            if hasattr(inUrl, 'read'):
                inObj = inUrl
            else:
                inObj = file(inUrl)
            putFiles.append((outUrl, method))
            fout = file(os.devnull, "w")
            if callback:
                callback = callback.progress
            util.copyfileobj(inObj, fout, callback = callback,
                bufSize = 1024 * 1024)
        from catalogService.libs.viclient import vmutils
        self.mock(vmutils, "_putFile", fakePutFile)
        srv, client, job, response = self._setUpNewImageTest(
            cloudName, fakeDaemonize, '', imageId = imageId, asOvf = True)

        jobUrlPath = 'jobs/types/image-deployment/jobs/1'
        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))

        #self.failUnlessEqual(node.getInstanceId(), "FAKE000")
        #self.failUnlessEqual(node.getReservationId(), None)
        #self.failUnlessEqual(node.getInstanceName(), "instance-foo")
        #self.failUnlessEqual(node.getInstanceDescription(),
        #    "just words and stuff")
        #certFile = os.path.join(self.storagePath, "instances",
        #    "vmware", "virtcenter.eng.rpath.com", "JeanValjean",
        #    "vmuuid10", "x509cert")
        #self.failUnless(os.path.exists(certFile))

        # Enumerate instances
        response = client.request('GET')
        hndlr = images.Handler()
        nodes = hndlr.parseString(response.read())

        self.failUnlessEqual(len(nodes), 4)

        # Grab the job
        client = self.newClient(srv, jobUrlPath)
        response = client.request('GET')

        job = self.getJobFromResponse(response)
        self.failUnlessEqual([ x.get_content() for x in job.history ],
            ['Running', 'Downloading image', 'Exploding archive',
            'Uploading image to VMware',
            'Importing OVF descriptor',
            'Importing OVF: 0% complete',
            'Importing OVF: 10% complete',
            'Importing OVF: 20% complete',
            'Importing OVF: 30% complete',
            'Importing OVF: 40% complete',
            'Importing OVF: 50% complete',
            'Importing OVF: 60% complete',
            'Importing OVF: 70% complete',
            'Importing OVF: 80% complete',
            'Importing OVF: 90% complete',
            'Importing OVF: 100% complete',
            'Importing OVF: 100% complete',
            'Reconfiguring VM', 'Converting VM to template',
            'Image deployed', 'Done'])
        self.failUnlessEqual(job.get_statusMessage(), 'Done')
        self.failUnlessEqual([ x.href for x in job.get_resultResource() ],
            [ self.makeUri(client, self._baseCloudUrl + '/images/vmuuid10') ])

        # We've requested thin provisioning
        invocation = pickle.load(file(invocationFile))
        self.assertEquals(invocation[0][-1], diskProvisioning)

    def testDeployImageVsphere50_defaultDiskProvisioning(self):
        # We won't specify disk provisioning in the launch args. It
        # should use the target's default
        self.mock(mockedData, 'xml_newImageVMware1',
            mockedData.xml_newImageVMware1.replace(
                '<diskProvisioning>thin</diskProvisioning>', ''))
        self.testDeployImageVsphere50(diskProvisioning='twoGbMaxExtentSparse')

    def testDeployImage_mostFreeSpace(self):
        # datastore-559 has the most free space
        soapReqDatastoreSummary = \
                mockedData._vmwareReqRetrievePropertiesSimpleTemplate % dict(
                    klass = 'Datastore', path = 'summary', value = 'datastore-559')

        soapRespDatastoreSummary = mockedData.HTTPResponse(
                mockedData.vmwareRetrievePropertiesDatastoreSummaryResponse.data.replace('datastore-18', 'datastore-559'))
        soapReqCreateImportSpec = mockedData.vmwareCreateImportSpecRequest2.replace(
                'datastore-18', 'datastore-559')
        self._replaceVmwareData({
            soapReqDatastoreSummary : soapRespDatastoreSummary,
            soapReqCreateImportSpec : mockedData.vmwareCreateImportSpecResponse1,
        })
        newImageNode = etree.fromstring(mockedData.xml_newImageVMware1)
        newImageNode.find('dataStoreSelection-domain-c5').text = 'dataStoreFreeSpace-domain-c5'
        etree.SubElement(newImageNode, 'dataStoreFreeSpace-domain-c5-filter').text = 'esx*-local'
        newImageNode.remove(newImageNode.find('dataStore-domain-c5'))
        self.mock(mockedData, 'xml_newImageVMware1',
            etree.tostring(newImageNode))
        self.testDeployImage1()

    def testDeployImage_leastOvercommitted(self):
        # datastore-565 has the least overcommitted
        soapReqDatastoreSummary = \
                mockedData._vmwareReqRetrievePropertiesSimpleTemplate % dict(
                    klass = 'Datastore', path = 'summary', value = 'datastore-565')

        soapRespDatastoreSummary = mockedData.HTTPResponse(
                mockedData.vmwareRetrievePropertiesDatastoreSummaryResponse.data.replace('datastore-18', 'datastore-565'))
        soapReqCreateImportSpec = mockedData.vmwareCreateImportSpecRequest2.replace(
                'datastore-18', 'datastore-565')
        self._replaceVmwareData({
            soapReqDatastoreSummary : soapRespDatastoreSummary,
            soapReqCreateImportSpec : mockedData.vmwareCreateImportSpecResponse1,
        })
        newImageNode = etree.fromstring(mockedData.xml_newImageVMware1)
        newImageNode.find('dataStoreSelection-domain-c5').text = 'dataStoreLeastOvercommitted-domain-c5'
        etree.SubElement(newImageNode, 'dataStoreLeastOvercommitted-domain-c5-filter').text = 'esx*-local'
        newImageNode.remove(newImageNode.find('dataStore-domain-c5'))
        self.mock(mockedData, 'xml_newImageVMware1',
            etree.tostring(newImageNode))
        self.testDeployImage1()


    def testGetLaunchDescriptorComputeResourceDisabled(self):
        try:
            self._replaceVmwareData({
                mockedData.vmwareRetrievePropertiesEnvBrowserReq :
                    mockedData.vmwareRetrievePropertiesEnvBrowserRespDisabledCR})
            srv = self.newService()
            uri = 'clouds/vmware/instances/virtcenter.eng.rpath.com/descriptor/launch'

            client = self.newClient(srv, uri)
            response = client.request('GET')

            dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
            self.failUnlessEqual(dsc.getDisplayName(), "VMware Launch Parameters")
            self.failUnlessEqual(dsc.getDescriptions(), {None : 'VMware Launch Parameters'})
            # The data store should no longer be there (if we had multiple one
            # of them should show up)
            self.failUnlessEqual([ df.name for df in dsc.getDataFields() ],
                ['imageId', 'instanceName', 'instanceDescription', 'vmCPUs', 'vmMemory', 'rootSshKeys', 'dataCenter'])
        finally:
            pass

    def testSanitizeOvfDescriptor(self):
        ovfDescriptorTempl = """\
<ovf:Envelope xmlns:cim="http://schemas.dmtf.org/wbem/wscim/1/common" xmlns:ovf="http://www.vmware.com/schema/ovf/1/envelope" xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData" xmlns:vmw="http://www.vmware.com/schema/ovf" xmlns:vssd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ovf:version="0.9">
  <References>
    <File ovf:href="ginkgo-1-x86.vmdk" ovf:id="file1" ovf:size="237913088"/>
  </References>
  <Section xsi:type="ovf:DiskSection_Type">
    <Info>Meta-information about the virtual disks</Info>
    <Disk ovf:capacity="2733637632" ovf:diskId="vmdisk1" ovf:fileRef="file1" ovf:format="http://www.vmware.com/specifications/vmdk.html#sparse"/>
  </Section>
  <Section xsi:type="ovf:NetworkSection_Type">
    <Info>The list of logical networks</Info>
    <Network ovf:name="bridged">
      <Description>The bridged network</Description>
    </Network>
  </Section>
  <Content ovf:id="ginkgo" xsi:type="ovf:VirtualSystem_Type">
    <Info>A virtual machine</Info>
    <Section ovf:id="36" xsi:type="ovf:OperatingSystemSection_Type">
      <Info>The kind of installed guest operating system</Info>
    </Section>
    <Section xsi:type="ovf:VirtualHardwareSection_Type">
      <Info>Virtual hardware requirements for a virtual machine</Info>
      <System>
        <vssd:InstanceId>0</vssd:InstanceId>
        <vssd:VirtualSystemIdentifier>ginkgo</vssd:VirtualSystemIdentifier>
        <vssd:VirtualSystemType>vmx-04</vssd:VirtualSystemType>
      </System>
      <Item>
        <rasd:Caption>1 virtual CPU(s)</rasd:Caption>
        <rasd:Description>Number of Virtual CPUs</rasd:Description>
        <rasd:InstanceId>1</rasd:InstanceId>
        <rasd:ResourceType>3</rasd:ResourceType>
        <rasd:AllocationUnits>MegaHertz</rasd:AllocationUnits>
        <rasd:VirtualQuantity>1</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:Caption>256MB of memory</rasd:Caption>
        <rasd:Description>Memory Size</rasd:Description>
        <rasd:InstanceId>2</rasd:InstanceId>
        <rasd:ResourceType>4</rasd:ResourceType>
        <rasd:AllocationUnits>MegaBytes</rasd:AllocationUnits>
        <rasd:VirtualQuantity>256</rasd:VirtualQuantity>
      </Item>
      <Item ovf:required="false">
        <rasd:Caption>usb</rasd:Caption>
        <rasd:Description>USB Controller</rasd:Description>
        <rasd:InstanceId>3</rasd:InstanceId>
        <rasd:ResourceType>23</rasd:ResourceType>
        <rasd:Address>0</rasd:Address>
        <rasd:BusNumber>0</rasd:BusNumber>
      </Item>
      <Item>
        <rasd:Caption>scsiController0</rasd:Caption>
        <rasd:Description>SCSI Controller</rasd:Description>
        <rasd:InstanceId>4</rasd:InstanceId>
        <rasd:ResourceType>6</rasd:ResourceType>
        <rasd:ResourceSubType>lsilogic</rasd:ResourceSubType>
        <rasd:Address>0</rasd:Address>
        <rasd:BusNumber>0</rasd:BusNumber>
      </Item>
      <Item>
        <rasd:Caption>ideController1</rasd:Caption>
        <rasd:Description>IDE Controller</rasd:Description>
        <rasd:InstanceId>5</rasd:InstanceId>
        <rasd:ResourceType>5</rasd:ResourceType>
        <rasd:Address>1</rasd:Address>
        <rasd:BusNumber>1</rasd:BusNumber>
      </Item>%s
      <Item>
        <rasd:Caption>disk1</rasd:Caption>
        <rasd:InstanceId>1001</rasd:InstanceId>
        <rasd:ResourceType>17</rasd:ResourceType>
        <rasd:HostResource>/disk/vmdisk1</rasd:HostResource>
        <rasd:Parent>4</rasd:Parent>
        <rasd:AddressOnParent>0</rasd:AddressOnParent>
      </Item>%s
    </Section>
    <Section ovf:required="false" xsi:type="ovf:AnnotationSection_Type">
      <Info>A human-readable annotation</Info>
      <Annotation></Annotation>
    </Section>
  </Content>
</ovf:Envelope>
"""
        cdrom1 = """\
      <Item ovf:required="false">
        <rasd:Caption>cdrom1</rasd:Caption>
        <rasd:InstanceId>6</rasd:InstanceId>
        <rasd:ResourceType>15</rasd:ResourceType>
        <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
        <rasd:Parent>5</rasd:Parent>
        <rasd:AddressOnParent>0</rasd:AddressOnParent>
      </Item>"""

        brokenEthernet0 = """\
      <Item>
        <rasd:Caption>ethernet0</rasd:Caption>
        <rasd:Description>PCNet32 ethernet adapter on &quot;bridged&quot;</rasd:Description>
        <rasd:InstanceId>8</rasd:InstanceId>
        <rasd:ResourceType>10</rasd:ResourceType>
        <rasd:ResourceSubType>PCNet32</rasd:ResourceSubType>
        <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
        <rasd:Connection>bridged</rasd:Connection>
        <rasd:AddressOnParent>1</rasd:AddressOnParent>
      </Item>"""

        e1000Ethernet0 = """\
      <Item>
        <rasd:Caption>ethernet0</rasd:Caption>
        <rasd:Description>E1000 ethernet adapter</rasd:Description>
        <rasd:InstanceId>1002</rasd:InstanceId>
        <rasd:ResourceType>10</rasd:ResourceType>
        <rasd:ResourceSubType>E1000</rasd:ResourceSubType>
        <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
        <rasd:Connection>bridged</rasd:Connection>
      </Item>"""

        from catalogService.libs.viclient import client
        ret = client.VimService.sanitizeOvfDescriptor(ovfDescriptorTempl %
            (cdrom1, brokenEthernet0))
        self.assertXMLEquals(ret, ovfDescriptorTempl % ("", e1000Ethernet0))

    def testSanitizeOvfDescriptor2(self):
        ovfDescriptorTempl = """\
<Envelope ovf:version="0.9" xml:lang="en-US" xmlns="http://www.vmware.com/schema/ovf/1/envelope" xmlns:ovf="http://www.vmware.com/schema/ovf/1/envelope" xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData" xmlns:vssd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <References>
    <File ovf:href="OpenSolaris-2009.06.vmdk" ovf:id="file1" ovf:size="1493809152"/>
  </References>
  <Section xsi:type="ovf:DiskSection_Type">
    <Info>List of the virtual disks used in the package</Info>
    <Disk ovf:capacity="33778827264" ovf:diskId="vmdisk1" ovf:fileRef="file1" ovf:format="http://www.vmware.com/specifications/vmdk.html#sparse"/>
  </Section>
  <Section xsi:type="ovf:NetworkSection_Type">
    <Info>Logical networks used in the package</Info>
    <Network ovf:name="NAT">
      <Description>Logical network used by this appliance.</Description>
    </Network>
  </Section>
  <Content xsi:type="ovf:VirtualSystem_Type" ovf:id="OpenSolaris-2009.06">
    <Info>A virtual machine</Info>
    <Section xsi:type="ovf:ProductSection_Type">
      <Info>Meta-information about the installed software</Info>
      <Product>OpenSolaris 2009.06 Appliance</Product>
      <Vendor>OVF Appliances</Vendor>
      <Version>2009.06</Version>
      <ProductUrl>http://VirtualBoxImages.com/OpenSolaris-2009.06</ProductUrl>
      <VendorUrl>http://OVFAppliances.com</VendorUrl>
    </Section>
    <Section xsi:type="ovf:OperatingSystemSection_Type" ovf:id="29">
      <Info>The kind of installed guest operating system</Info>
      <Description>OpenSolaris</Description>
    </Section>
    <Section xsi:type="ovf:VirtualHardwareSection_Type">
      <Info>Virtual hardware requirements for a virtual machine</Info>
      <System>
        <vssd:InstanceId>0</vssd:InstanceId>
        <vssd:VirtualSystemIdentifier>OpenSolaris-2009.06</vssd:VirtualSystemIdentifier>
        <vssd:VirtualSystemType>vmx-6</vssd:VirtualSystemType>
      </System>
      <Item>
        <rasd:Description>Number of virtual CPUs</rasd:Description>
        <rasd:InstanceId>1</rasd:InstanceId>
        <rasd:ResourceType>3</rasd:ResourceType>
        <rasd:VirtualQuantity>1</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:Caption>739 MB of memory</rasd:Caption>
        <rasd:Description>Memory Size</rasd:Description>
        <rasd:InstanceId>2</rasd:InstanceId>
        <rasd:ResourceType>4</rasd:ResourceType>
        <rasd:AllocationUnits>MegaBytes</rasd:AllocationUnits>
        <rasd:VirtualQuantity>739</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:Description>IDE Controller</rasd:Description>
        <rasd:InstanceId>3</rasd:InstanceId>
        <rasd:ResourceType>5</rasd:ResourceType>
        <rasd:ResourceSubType>PIIX4</rasd:ResourceSubType>
        <rasd:Address>1</rasd:Address>
        <rasd:BusNumber>1</rasd:BusNumber>
      </Item>
      <Item>
        <rasd:Caption>floppy0</rasd:Caption>
        <rasd:Description>Floppy Drive</rasd:Description>
        <rasd:InstanceId>4</rasd:InstanceId>
        <rasd:ResourceType>14</rasd:ResourceType>
        <rasd:AutomaticAllocation>false</rasd:AutomaticAllocation>
        <rasd:AddressOnParent>0</rasd:AddressOnParent>
      </Item>%s
      <Item>
        <rasd:Caption>usb</rasd:Caption>
        <rasd:Description>USB Controller</rasd:Description>
        <rasd:InstanceId>6</rasd:InstanceId>
        <rasd:ResourceType>23</rasd:ResourceType>
        <rasd:Address>0</rasd:Address>
        <rasd:BusNumber>0</rasd:BusNumber>
      </Item>
      <Item>
        <rasd:Caption>sound</rasd:Caption>
        <rasd:Description>Sound Card</rasd:Description>
        <rasd:InstanceId>7</rasd:InstanceId>
        <rasd:ResourceType>35</rasd:ResourceType>
        <rasd:ResourceSubType>ensoniq1371</rasd:ResourceSubType>
        <rasd:AutomaticAllocation>false</rasd:AutomaticAllocation>
        <rasd:AddressOnParent>3</rasd:AddressOnParent>
      </Item>
      <Item>
        <rasd:Caption>disk1</rasd:Caption>
        <rasd:Description>Disk Image</rasd:Description>
        <rasd:InstanceId>8</rasd:InstanceId>
        <rasd:ResourceType>17</rasd:ResourceType>
        <rasd:HostResource>/disk/vmdisk1</rasd:HostResource>
        <rasd:Parent>3</rasd:Parent>
        <rasd:AddressOnParent>0</rasd:AddressOnParent>
      </Item>%s
    </Section>
  </Content>
</Envelope>
"""
        cdrom1 = """\
      <Item>
        <rasd:Caption>cdrom1</rasd:Caption>
        <rasd:Description>CD-ROM Drive</rasd:Description>
        <rasd:InstanceId>9</rasd:InstanceId>
        <rasd:ResourceType>15</rasd:ResourceType>
        <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
        <rasd:Parent>3</rasd:Parent>
        <rasd:AddressOnParent>0</rasd:AddressOnParent>
      </Item>"""

        brokenEthernet0 = """\
      <Item>
        <rasd:Caption>Ethernet adapter on 'NAT'</rasd:Caption>
        <rasd:InstanceId>5</rasd:InstanceId>
        <rasd:ResourceType>10</rasd:ResourceType>
        <rasd:ResourceSubType>E1000</rasd:ResourceSubType>
        <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
        <rasd:Connection>NAT</rasd:Connection>
      </Item>"""

        e1000Ethernet0 = """\
      <Item>
        <rasd:Caption>ethernet0</rasd:Caption>
        <rasd:Description>E1000 ethernet adapter</rasd:Description>
        <rasd:InstanceId>9</rasd:InstanceId>
        <rasd:ResourceType>10</rasd:ResourceType>
        <rasd:ResourceSubType>E1000</rasd:ResourceSubType>
        <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
        <rasd:Connection>NAT</rasd:Connection>
      </Item>"""

        from catalogService.libs.viclient import client
        ret = client.VimService.sanitizeOvfDescriptor(ovfDescriptorTempl %
            (brokenEthernet0, cdrom1))
        self.assertXMLEquals(ret, ovfDescriptorTempl % ("", e1000Ethernet0))

    def testSanitizeOvfDescriptorOVF10(self):
        ovfDescriptorTempl = """\
<?xml version="1.0" encoding="UTF-8"?>
<Envelope vmw:buildId="build-258902" xmlns="http://schemas.dmtf.org/ovf/envelope/1" xmlns:cim="http://schemas.dmtf.org/wbem/wscim/1/common" xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1" xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData" xmlns:vmw="http://www.vmware.com/schema/ovf" xmlns:vssd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <References>
    <File ovf:href="opensolaris-disk1.vmdk" ovf:id="file1" ovf:size="1351238144"/>
  </References>
  <DiskSection>
    <Info>Virtual disk information</Info>
    <Disk ovf:capacity="8" ovf:capacityAllocationUnits="byte * 2^30" ovf:diskId="vmdisk1" ovf:fileRef="file1" ovf:format="http://www.vmware.com/interfaces/specifications/vmdk.html#streamOptimized" ovf:populatedSize="3411738624"/>
  </DiskSection>
  <NetworkSection>
    <Info>The list of logical networks</Info>
    <Network ovf:name="blabbedy">
      <Description>The blabbedy network</Description>
    </Network>
  </NetworkSection>
  <VirtualSystem ovf:id="opensolaris">
    <Info>A virtual machine</Info>
    <Name>opensolaris</Name>
    <OperatingSystemSection ovf:id="29" ovf:version="10" vmw:osType="solaris10Guest">
      <Info>The kind of installed guest operating system</Info>
      <Description>Sun Solaris 10 (32-bit)</Description>
    </OperatingSystemSection>
    <VirtualHardwareSection>
      <Info>Virtual hardware requirements</Info>
      <System>
        <vssd:ElementName>Virtual Hardware Family</vssd:ElementName>
        <vssd:InstanceID>0</vssd:InstanceID>
        <vssd:VirtualSystemIdentifier>opensolaris</vssd:VirtualSystemIdentifier>
        <vssd:VirtualSystemType>vmx-07</vssd:VirtualSystemType>
      </System>
      <Item>
        <rasd:AllocationUnits>hertz * 10^6</rasd:AllocationUnits>
        <rasd:Description>Number of Virtual CPUs</rasd:Description>
        <rasd:ElementName>1 virtual CPU(s)</rasd:ElementName>
        <rasd:InstanceID>1</rasd:InstanceID>
        <rasd:ResourceType>3</rasd:ResourceType>
        <rasd:VirtualQuantity>1</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:AllocationUnits>byte * 2^20</rasd:AllocationUnits>
        <rasd:Description>Memory Size</rasd:Description>
        <rasd:ElementName>3072MB of memory</rasd:ElementName>
        <rasd:InstanceID>2</rasd:InstanceID>
        <rasd:ResourceType>4</rasd:ResourceType>
        <rasd:VirtualQuantity>3072</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:Address>0</rasd:Address>
        <rasd:Description>SCSI Controller</rasd:Description>
        <rasd:ElementName>SCSI controller 0</rasd:ElementName>
        <rasd:InstanceID>3</rasd:InstanceID>
        <rasd:ResourceSubType>lsilogic</rasd:ResourceSubType>
        <rasd:ResourceType>6</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:Address>1</rasd:Address>
        <rasd:Description>IDE Controller</rasd:Description>
        <rasd:ElementName>IDE 1</rasd:ElementName>
        <rasd:InstanceID>4</rasd:InstanceID>
        <rasd:ResourceType>5</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:Address>0</rasd:Address>
        <rasd:Description>IDE Controller</rasd:Description>
        <rasd:ElementName>IDE 0</rasd:ElementName>
        <rasd:InstanceID>5</rasd:InstanceID>
        <rasd:ResourceType>5</rasd:ResourceType>
      </Item>
      <Item ovf:required="false">
        <rasd:AddressOnParent>0</rasd:AddressOnParent>
        <rasd:AutomaticAllocation>false</rasd:AutomaticAllocation>
        <rasd:Description>Floppy Drive</rasd:Description>
        <rasd:ElementName>Floppy drive 1</rasd:ElementName>
        <rasd:InstanceID>6</rasd:InstanceID>
        <rasd:ResourceType>14</rasd:ResourceType>
      </Item>%s
      <Item>
        <rasd:AddressOnParent>0</rasd:AddressOnParent>
        <rasd:ElementName>Hard disk 1</rasd:ElementName>
        <rasd:HostResource>ovf:/disk/vmdisk1</rasd:HostResource>
        <rasd:InstanceID>9</rasd:InstanceID>
        <rasd:Parent>3</rasd:Parent>
        <rasd:ResourceType>17</rasd:ResourceType>
      </Item>%s
      <vmw:Config ovf:required="false" vmw:key="cpuHotAddEnabled" vmw:value="false"/>
      <vmw:Config ovf:required="false" vmw:key="memoryHotAddEnabled" vmw:value="false"/>
      <vmw:Config ovf:required="false" vmw:key="tools.syncTimeWithHost" vmw:value="false"/>
    </VirtualHardwareSection>
  </VirtualSystem>
</Envelope>"""

        cdrom1 = """\
      <Item ovf:required="false">
        <rasd:AddressOnParent>0</rasd:AddressOnParent>
        <rasd:AutomaticAllocation>false</rasd:AutomaticAllocation>
        <rasd:ElementName>CD/DVD Drive 1</rasd:ElementName>
        <rasd:InstanceID>7</rasd:InstanceID>
        <rasd:Parent>4</rasd:Parent>
        <rasd:ResourceType>15</rasd:ResourceType>
      </Item>"""

        brokenEthernet0 = """\
      <Item>
        <rasd:AddressOnParent>7</rasd:AddressOnParent>
        <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
        <rasd:Connection>bridged</rasd:Connection>
        <rasd:Description>E1000 ethernet adapter on &quot;bridged&quot;</rasd:Description>
        <rasd:ElementName>Network adapter 1</rasd:ElementName>
        <rasd:InstanceID>8</rasd:InstanceID>
        <rasd:ResourceSubType>E1000</rasd:ResourceSubType>
        <rasd:ResourceType>10</rasd:ResourceType>
      </Item>"""

        e1000Ethernet0 = """\
      <Item>
        <rasd:AddressOnParent>7</rasd:AddressOnParent>
        <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
        <rasd:Connection>blabbedy</rasd:Connection>
        <rasd:Description>E1000 ethernet adapter</rasd:Description>
        <rasd:ElementName>ethernet0</rasd:ElementName>
        <rasd:InstanceID>10</rasd:InstanceID>
        <rasd:ResourceSubType>E1000</rasd:ResourceSubType>
        <rasd:ResourceType>10</rasd:ResourceType>
      </Item>"""

        from catalogService.libs.viclient import client
        ret = client.VimService.sanitizeOvfDescriptor(ovfDescriptorTempl %
            (cdrom1, brokenEthernet0))
        self.assertXMLEquals(ret, ovfDescriptorTempl % ("", e1000Ethernet0))

    def testSanitizeOvfDescriptorOVF10_withNS(self):
        ovfDescriptorTempl = """\
<ovf:Envelope xmlns:vssd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData" xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData" xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1" xmlns:cim="http://schemas.dmtf.org/wbem/wscim/1/common">
  <ovf:References>
    <ovf:File ovf:href="wookie-1-x86_64.vmdk.gz" ovf:id="fileId_1" ovf:size="404508193" ovf:compression="gzip"/>
  </ovf:References>
  <ovf:DiskSection>
    <ovf:Info>Describes the set of virtual disks</ovf:Info>
    <ovf:Disk ovf:diskId="diskId_1" ovf:capacity="2860515328" ovf:fileRef="fileId_1" ovf:format="http://www.vmware.com/interfaces/specifications/vmdk.html#streamOptimized"/>
  </ovf:DiskSection>
  <ovf:NetworkSection>
    <ovf:Info>List of logical networks used in the package</ovf:Info>
    <ovf:Network ovf:name="Network Name">
      <ovf:Description>Network Description</ovf:Description>
    </ovf:Network>
  </ovf:NetworkSection>
  <ovf:VirtualSystem ovf:id="wookie-1-x86_64">
    <ovf:Info/>
    <ovf:VirtualHardwareSection>
      <ovf:Info>Describes the set of virtual hardware</ovf:Info>
      %s
      <ovf:Item>
        <rasd:Caption>Virtual CPU</rasd:Caption>
        <rasd:Description>Number of virtual CPUs</rasd:Description>
        <rasd:ElementName>some virt cpu</rasd:ElementName>
        <rasd:InstanceID>1</rasd:InstanceID>
        <rasd:ResourceType>3</rasd:ResourceType>
        <rasd:VirtualQuantity>1</rasd:VirtualQuantity>
      </ovf:Item>
      <ovf:Item>
        <rasd:AllocationUnits>MegaBytes</rasd:AllocationUnits>
        <rasd:Caption>256 MB of Memory</rasd:Caption>
        <rasd:Description>Memory Size</rasd:Description>
        <rasd:ElementName>some mem size</rasd:ElementName>
        <rasd:InstanceID>2</rasd:InstanceID>
        <rasd:ResourceType>4</rasd:ResourceType>
        <rasd:VirtualQuantity>256</rasd:VirtualQuantity>
      </ovf:Item>%s
      <ovf:Item>
        <rasd:AddressOnParent>0</rasd:AddressOnParent>
        <rasd:Caption>Harddisk</rasd:Caption>
        <rasd:ElementName>Hard disk</rasd:ElementName>
        <rasd:HostResource>ovf:/disk/diskId_1</rasd:HostResource>
        <rasd:InstanceID>5</rasd:InstanceID>
        <rasd:Parent>4</rasd:Parent>
        <rasd:ResourceType>17</rasd:ResourceType>
      </ovf:Item>
      <ovf:Item>
        <rasd:Caption>SCSI Controller 0 - LSI Logic</rasd:Caption>
        <rasd:ElementName>LSILOGIC</rasd:ElementName>
        <rasd:InstanceID>4</rasd:InstanceID>
        <rasd:ResourceSubType>LsiLogic</rasd:ResourceSubType>
        <rasd:ResourceType>6</rasd:ResourceType>
      </ovf:Item>%s
    </ovf:VirtualHardwareSection>
  </ovf:VirtualSystem>
</ovf:Envelope>"""

        brokenEthernet0 = """\
      <ovf:Item>
        <rasd:AllocationUnits>Interface</rasd:AllocationUnits>
        <rasd:Connection>Network Name</rasd:Connection>
        <rasd:Description>Network Interface</rasd:Description>
        <rasd:ElementName>Network Interface</rasd:ElementName>
        <rasd:InstanceID>3</rasd:InstanceID>
        <rasd:ResourceType>10</rasd:ResourceType>
      </ovf:Item>"""

        e1000Ethernet0 = """\
      <ovf:Item>
        <rasd:AddressOnParent>7</rasd:AddressOnParent>
        <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
        <rasd:Connection>Network Name</rasd:Connection>
        <rasd:Description>E1000 ethernet adapter</rasd:Description>
        <rasd:ElementName>ethernet0</rasd:ElementName>
        <rasd:InstanceID>6</rasd:InstanceID>
        <rasd:ResourceSubType>E1000</rasd:ResourceSubType>
        <rasd:ResourceType>10</rasd:ResourceType>
      </ovf:Item>"""

        systemNode = """\
      <ovf:System>
        <vssd:InstanceID>0</vssd:InstanceID>
        <vssd:VirtualSystemIdentifier>wookie-1-x86_64</vssd:VirtualSystemIdentifier>
        <vssd:VirtualSystemType>vmx-04</vssd:VirtualSystemType>
      </ovf:System>
"""

        from catalogService.libs.viclient import client
        ret = client.VimService.sanitizeOvfDescriptor(ovfDescriptorTempl %
            ("", brokenEthernet0, ""))
        self.assertXMLEquals(ret, ovfDescriptorTempl %
            (systemNode, "", e1000Ethernet0))


_xmlNewCloud = """
<descriptorData>
  <alias>newbie</alias>
  <description>Brand new cloud</description>
  <name>newbie.eng.rpath.com</name>
</descriptorData>"""

_xmlNewCreds = """
<descriptorData>
  <username>abc</username>
  <password>12345678</password>
</descriptorData>
"""

if __name__ == "__main__":
    testsuite.main()
