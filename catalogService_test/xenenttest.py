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

import XenAPI

from conary.lib import util

import testbase

from catalogService.restClient import ResponseError

from catalogService.rest import baseDriver
from catalogService.rest.drivers import xenent
from catalogService.rest.models import clouds
from catalogService.rest.models import credentials
from catalogService.rest.models import descriptor
from catalogService.rest.models import images
from catalogService.rest.models import instances

from catalogService_test import mockedData

class DummyTransportDefaults(object):
    dataMap = {
        'session.login_with_password': ({
            'Status': 'Success',
            'Value': 'OpaqueRef:10106a67-3258-d1cf-74e9-86f599c380cb'},),
        'host.get_API_version_major' : mockedData.xenent_host_get_API_version_major1,
        'host.get_record' : {
            'OpaqueRef:host1' : mockedData.xenent_host_get_record1,
            'OpaqueRef:host2' : mockedData.xenent_host_get_record2,
        },
        'pool.get_all' : mockedData.xenent_pool_get_all1,
        'pool.get_all_records' : mockedData.xenent_listPools1,
        'pool.get_master' : mockedData.xenent_pool_get_master1,
        'task.create' : mockedData.xenent_task_create1,
        'task.get_record' : mockedData.xenent_task_get_record1,
        'task.get_status' : mockedData.xenent_task_get_status1,
        'PBD.get_host' : {
            'OpaqueRef:pbd1' : mockedData.xenent_PBD_get_host1,
            'OpaqueRef:pbd2' : mockedData.xenent_PBD_get_host2,
        },
        'SR.get_all_records' : mockedData.xenent_listSRs1,
        'SR.get_uuid' : mockedData.xenent_SR_get_uuid1,
        'SR.get_by_uuid' : mockedData.xenent_SR_get_by_uuid1,
        'VBD.create' : mockedData.xenent_VBD_create1,
        'VBD.get_record' : {
            'OpaqueRef:vbd1' : mockedData.xenent_VBD_get_record1,
            'OpaqueRef:vbd2' : mockedData.xenent_VBD_get_record2,
        },
        'VDI.create' : mockedData.xenent_VDI_create1,
        'VDI.set_name_description' : mockedData.xenent_VDI_set_name_description1,
        'VDI.set_name_label' : mockedData.xenent_VDI_set_name_label1,
        'VDI.set_other_config' : mockedData.xenent_VDI_set_other_config1,
        'VIF.create' : mockedData.xenent_VM_set_generic,
        'VM_guest_metrics.get_networks' : {
            'OpaqueRef:GuestMetricsNetworks1' : mockedData.xenent_VM_guest_metrics_get_networks1,
            'OpaqueRef:GuestMetricsNetworks2' : mockedData.xenent_VM_guest_metrics_get_networks2,
        },
        'VM_metrics.get_record' : mockedData.xenent_VM_metrics_get_record1,
        'VM.add_to_other_config' : mockedData.xenent_VM_set_generic,
        'VM.clean_shutdown' : mockedData.xenent_VM_set_generic,
        'VM.clone' : mockedData.xenent_VM_clone1,
        'VM.destroy' : mockedData.xenent_VM_destroy1,
        'VM.get_all_records' : mockedData.xenent_listInstances1,
        'VM.get_by_uuid' : mockedData.xenent_VM_get_by_uuid1,
        'VM.get_record' : mockedData.xenent_VM_get_record1,
        'VM.get_uuid' : mockedData.xenent_VM_get_uuid1,
        'VM.provision' : mockedData.xenent_VM_set_generic,
        'VM.remove_from_other_config' : mockedData.xenent_VM_set_generic,
        'VM.set_HVM_boot_params' : mockedData.xenent_VM_set_generic,
        'VM.set_HVM_boot_policy' : mockedData.xenent_VM_set_generic,
        'VM.set_is_a_template' : mockedData.xenent_VM_set_generic,
        'VM.set_name_description' : mockedData.xenent_VM_set_generic,
        'VM.set_PV_args' : mockedData.xenent_VM_set_generic,
        'VM.set_PV_bootloader_args' : mockedData.xenent_VM_set_generic,
        'VM.set_PV_bootloader' : mockedData.xenent_VM_set_generic,
        'VM.set_PV_kernel' : mockedData.xenent_VM_set_generic,
        'VM.set_PV_legacy_args' : mockedData.xenent_VM_set_generic,
        'VM.set_PV_ramdisk' : mockedData.xenent_VM_set_generic,
        'VM.start' : mockedData.xenent_VM_set_generic,
        'VM.get_name_label' : mockedData.xenent_VM_get_name_label,
        'PIF.get_all_records' : mockedData.xenent_PIF_get_all_records1,
        'PIF.get_network' : mockedData.xenent_PIF_get_network1,
    }

class DummyTransport(XenAPI.xmlrpclib.Transport):
    dataMap = {}
    def request(self, host, handler, request, verbose = 0):
        dataMap = DummyTransportDefaults.dataMap.copy()
        dataMap.update(self.dataMap)

        params, methodname = XenAPI.xmlrpclib.loads(request)
        if 0:
            if methodname == 'session.login_with_password':
                params = ('root', 'XXXXXXXXXXXX', )
                request = XenAPI.xmlrpclib.dumps(params,
                                                 methodname = methodname)
            data = XenAPI.xmlrpclib.Transport.request(self, host, handler,
                                                     request, verbose)
            return data
        if methodname.split('.')[-1].startswith('__'):
            return "AAA"
        if methodname not in dataMap:
            raise Exception("Mock me", methodname, params)
        data = dataMap[methodname]
        if isinstance(data, dict):
            if params[1] not in data:
                raise Exception("Mock me", methodname, params)
            data = data[params[1]]
        return data

class DummyRestClientConnection(object):
    data = {
        ("PUT", "/import?sr_id=OpaqueRef:SRref1&task_id=OpaqueRef:NoBananas") : "",
    }
    def __init__(self, host, port = None, **kwargs):
        self.host = host
        self.port = port
        self._response = None

    def connect(self):
        pass

    def request(self, method, path, body = None, headers = None):
        data = self.data[(method, path)]
        status = 200
        if isinstance(data, tuple):
            status, data = status
        self._response = mockedData.MockedResponse(data)
        self._response.status = status
        self._response.msg = "Blah?"
        self._response.reason = "Blah?"

    def getresponse(self):
        return self._response

    def set_debuglevel(self, val):
        pass

class DummyRestClientConnectionFailing(DummyRestClientConnection):
    def connect(self):
        import socket
        raise socket.error(111, "Connection refused")

class XenSession(XenAPI.Session):
    def __init__(self, uri, transport = None, encoding = None, verbose = 0,
                 allow_none = 1):
        transport = DummyTransport()
        XenAPI.Session.__init__(self, uri, transport=transport,
                                encoding=encoding, verbose=verbose,
                                allow_none=allow_none)

def mockedResolveAddress(slf, addr):
    map = {
        '1.1.1.1' : 'node1.blah.com',
        '2.2.2.2' : 'node2.blah.com',
    }
    return map[addr]

class HandlerTest(testbase.TestCase):
    CLOUD_TYPE = 'xen-enterprise'
    TARGETS = [
      (CLOUD_TYPE, mockedData.tmp_xenentName1, dict(
             alias = mockedData.tmp_xenentAlias1,
             description = mockedData.tmp_xenentDescription1,
             useDeploymentDaemon = "no",
        ),
      ),
      (CLOUD_TYPE, mockedData.tmp_xenentName2, dict(
             alias = mockedData.tmp_xenentAlias2,
             description = mockedData.tmp_xenentDescription2,
             useDeploymentDaemon = "no",
        ),
      ),
    ]
    USER_TARGETS = [
        ('JeanValjean', CLOUD_TYPE, mockedData.tmp_xenentName1, dict(
             username = 'root',
             password = 'SomePassword',
            )),
        ('JeanValjean', CLOUD_TYPE, mockedData.tmp_xenentName2, dict(
             username = 'root',
             password = 'SomePassword',
            )),
    ]
    cloudName = mockedData.tmp_xenentName1
    cloudType = CLOUD_TYPE


    def setUp(self):
        testbase.TestCase.setUp(self)
        # Reset any mocking
        DummyTransport.dataMap = {}
        self.mock(xenent.driver, 'XenSessionClass', XenSession)
        from catalogService.rest.drivers.xenent import xenentclient
        self.mock(xenentclient.XenEntHostCache, 'resolveAddress',
            mockedResolveAddress)

    def testAuthenticationFailure(self):
        DummyTransport.dataMap['session.login_with_password'] = ({
            'Status': 'Failure',
            'ErrorDescription': ['SESSION_AUTHENTICATION_FAILED', 'root', 'Authentication failure'],
        }, )
        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances/%s/instances' % mockedData.tmp_xenentName1
        client = self.newClient(srv, uri)

        response = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(response.status, 403)
        self.assertXMLEquals(response.contents, """
<?xml version='1.0' encoding='UTF-8'?>
<fault>
  <code>403</code>
  <message>User root: Authentication failure</message>
</fault>""")

    def testGetClouds1(self):
        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = clouds.Handler()
        response = util.BoundedStringIO(response.read())
        nodes = hndlr.parseFile(response)

        self.failUnlessEqual([x.getCloudName() for x in nodes],
            ['abc.eng.rpath.com', 'xs01.eng.rpath.com'])

        self.failUnlessEqual([x.getCloudAlias() for x in nodes],
            ['abc', 'xs01'])

        self.failUnlessEqual([x.getDescription() for x in nodes],
            ['abc cloud', 'xs01 cloud'])

    def testRemoveCloud(self):
        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances/abc.eng.rpath.com'
        client = self.newClient(srv, uri)

        response = client.request('DELETE')
        hndlr = clouds.Handler()

        self.assertXMLEquals(response.read(), "<?xml version='1.0' encoding='UTF-8'?>\n<clouds/>")

        # Removing a second time should give a 404
        response = self.failUnlessRaises(ResponseError, client.request, 'DELETE')
        self.failUnlessEqual(response.status, 404)

        # Cloud enumeration should no loger reveal aws
        uri = 'clouds/xen-enterprise/instances'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        nodes = hndlr.parseString(response.read())
        self.failUnlessEqual(len(nodes), 1)

        # Instance enumeration should fail with 404 (bad cloud name)
        uri = 'clouds/xen-enterprise/instances/abc.eng.rpath.com/instances'
        client = self.newClient(srv, uri)

        response = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(response.status, 404)

    def testGetInstances1(self):
        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances/xs01.eng.rpath.com/instances'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        self.failUnlessEqual(response.msg['Content-Type'], 'application/xml')
        self.failUnlessEqual(response.msg['Cache-Control'], 'no-store')
        hndlr = instances.Handler()
        nodes = hndlr.parseString(response.read())
        self.failUnless(
            isinstance(nodes, instances.BaseInstances),
            nodes)

        self.failUnlessEqual([x.getInstanceId() for x in nodes],
            ['0a5bb7f9-8b2b-436e-8e5f-e157101ce7f1',
             'VmUuid1',
             'c1af2f03-2e0c-0807-9447-9883c578aa32',
             '98aef2dc-e6f3-803c-f490-791b847d3a3e',
             '9b01f3fb-3e66-4c0b-9a8f-3c8ea1a6769e',
             '1fce577a-f49c-f956-cbdf-45ffae28fd02'])

        self.failUnlessEqual([x.getInstanceName() for x in nodes],
            ['rPath Appliance Platform - Linux Service import',
             'rPath Appliance Platform - Linux Service import (1)',
             'Support Issue replication import (1)',
             'rpath update service import',
             'Control domain on host: localhost.localdomain',
             'Support Issue replication import'])
        self.failUnlessEqual([x.getInstanceDescription() for x in nodes],
            ['Created by rPath rBuilder',
             'Created by rPath rBuilder',
             'Created by rPath rBuilder',
             'Created by rPath rBuilder',
             'The domain which manages physical devices and manages other domains',
            'Created by rPath rBuilder'])
        self.failUnlessEqual([x.getPublicDnsName() for x in nodes],
            [None, '10.0.0.1', None, '10.0.0.2', '10.0.0.1', None])
        self.failUnlessEqual([x.getState() for x in nodes],
            ['Halted', 'Halted', 'Halted', 'Running', 'Running', 'Suspended'])

        self.failUnlessEqual([x.getLaunchTime() for x in nodes],
            [None, None, None, '1236348916', None, None])

    def testGetInstance1(self):
        srv = self.newService()
        instId = '9b01f3fb-3e66-4c0b-9a8f-3c8ea1a6769e'
        uri = 'clouds/xen-enterprise/instances/xs01.eng.rpath.com/instances'
        uri += '/' + instId
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = instances.Handler()
        node = hndlr.parseString(response.read())

        # Normally we should only get one instance, but the call is mocked
        self.failUnlessEqual(node.getInstanceId(), instId)

    def testGetImages1(self):
        DummyTransport.dataMap['VM.get_all_records'] = mockedData.xenent_listImages1

        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances/xs01.eng.rpath.com/images'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndlr = images.Handler()
        response = util.BoundedStringIO(response.read())
        nodes = hndlr.parseFile(response)
        self.failUnless(
            isinstance(nodes, images.BaseImages),
            nodes)

        self.failUnlessEqual([x.getImageId() for x in nodes],
            ['0903de41206786d4407ff24ab6e972c0d6b801f3',
             '0xPrivateImage',
             '52f75c4d-9782-15a2-6f76-a96a71d3d9b1',
             'b3fb7387bb04b1403bc0eb06bd55c0ef5f02d9bb',
             'c4664768-622b-8ab7-a76f-5a1c62c2688f',
             'd0bf8f0e-afce-d9fb-8121-e9e174a7c99b',])
        self.assertEquals([x.getBuildPageUrl() for x in nodes],
            ['http://test.rpath.local2/project/foo/build?id=6',
             'http://test.rpath.local2/project/foo/build?id=7',
             None,
             'http://test.rpath.local2/project/foo/build?id=1',
             None, None,])

    def testGetConfigurationDescriptor(self):
        srv = self.newService()
        uri = 'clouds/xen-enterprise/descriptor/configuration'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getDisplayName(), "Xen Enterprise Cloud Configuration")
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'Configure Xen Enterprise Cloud'})
        self.failUnlessEqual([ df.name for df in dsc.getDataFields() ],
            ['name', 'alias', 'description'])
        fnames = [ df.type for df in dsc.getDataFields() ]
        self.failUnlessEqual(
            [ fnames[0], fnames[1], fnames[2] ],
            ['str', 'str', 'str'])
        self.failUnlessEqual([ df.multiple for df in dsc.getDataFields() ],
            [None, None, None])
        self.failUnlessEqual([ df.descriptions.asDict() for df in dsc.getDataFields() ],
            [{None : 'Server Address'}, 
             {None : 'Name'},
             {None : 'Full Description'}])

        pref = self.makeUri(client,
            "help/targets/drivers/%s/configuration/" % self.cloudType)
        helpData = [ { None : pref + x } for x in [
            'serverName.html', 'alias.html', 'description.html' ] ]
        self.failUnlessEqual([ df.helpAsDict for df in dsc.getDataFields() ],
            helpData)

    def testGetCredentialsDescriptor(self):
        srv = self.newService()
        uri = 'clouds/xen-enterprise/descriptor/credentials'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.CredentialsDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getDisplayName(), "Xen Enterprise User Credentials")
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'User Credentials for Xen Enterprise'})
        self.failUnlessEqual([ df.name for df in dsc.getDataFields() ],
            ['username', 'password'])
        self.failUnlessEqual([ df.type for df in dsc.getDataFields() ],
            ['str', 'str'])
        self.failUnlessEqual([ df.multiple for df in dsc.getDataFields() ],
            [None] * len(dsc.getDataFields()))
        self.failUnlessEqual([ df.descriptions.asDict() for df in dsc.getDataFields() ],
            [{None : 'User Name'}, {None : 'Password'}])
        self.failUnlessEqual([ df.constraints.descriptions.asDict() for df in dsc.getDataFields() ],
            [{None: u'Field must contain between 1 and 32 characters'},
             {None: u'Field must contain between 1 and 32 characters'}])
        self.failUnlessEqual([ df.constraintsPresentation for df in dsc.getDataFields() ],
            [
                [{'constraintName': 'length', 'value': 32}],
                [{'constraintName': 'length', 'value': 32}]
            ])
        self.failUnlessEqual([ df.password for df in dsc.getDataFields() ],
            [None, True])

    def testGetConfiguration(self):
        self.setAdmin(True)
        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances/xs01.eng.rpath.com/configuration'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        self.assertXMLEquals(response.read(), """<?xml version='1.0' encoding='UTF-8'?>\n<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/xen-enterprise/instances/xs01.eng.rpath.com/configuration">\n  <alias>xs01</alias>\n  <description>xs01 cloud</description>\n  <name>xs01.eng.rpath.com</name>\n</descriptorData>\n""" %
            client.hostport)

    def testGetCredentials(self):
        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances/xs01.eng.rpath.com/users/%(username)s/credentials?_method=GET'

        client = self.newClient(srv, uri)
        response = client.request('POST')
        hndlr = credentials.Handler()
        data = response.read()
        self.assertXMLEquals(data, """<?xml version='1.0' encoding='UTF-8'?>\n<descriptorData version="1.1" id="http://%s/TOPLEVEL/clouds/xen-enterprise/instances/xs01.eng.rpath.com/users/JeanValjean/credentials">\n  <username>root</username>\n  <password>SomePassword</password>\n</descriptorData>\n""" % client.hostport)

        # Wrong user name
        uri = 'clouds/xen-enterprise/instances/xs01.eng.rpath.com/users/NOSUCHUSER/credentials'
        client = self.newClient(srv, uri)
        e = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(e.status, 401)

    def testGetCredentialsNoCreds(self):
        # Remove credentials
        cloudName = 'xs01.eng.rpath.com'
        self.restdb.targetMgr.setTargetCredentialsForUser(
            self.CLOUD_TYPE, cloudName, 'JeanValjean', {})
        uri = 'clouds/xen-enterprise/instances/xs01.eng.rpath.com/users/%(username)s/credentials'
        srv = self.newService()
        client = self.newClient(srv, uri)
        response = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(response.status, 404)
        self.assertXMLEquals(response.contents, """\
<?xml version='1.0' encoding='UTF-8'?>
<fault>
  <code>404</code>
  <message>User credentials not configured</message>
</fault>""")

    def testNewCloud(self):
        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances'
        client = self.newClient(srv, uri)

        reqData = _xmlNewCloud
        response = client.request('POST', reqData)

        hndl = clouds.Handler()
        node = hndl.parseString(response.read())

        cloudId = "http://%s/TOPLEVEL/clouds/%s/instances/%s" % (
            client.hostport, 'xen-enterprise', 'newbie.eng.rpath.com')
        self.failUnlessEqual(node.getId(), cloudId)
        self.failUnlessEqual(node.getCloudAlias(), 'newbie')
        self.failUnlessEqual(node.getCloudName(), 'newbie.eng.rpath.com')
        self.failUnlessEqual(node.getType().getText(), 'xen-enterprise')

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

        # Enumerate xen clouds - we should have 3 of them now
        uri = 'clouds/xen-enterprise/instances'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        hndl = clouds.Handler()
        nodes = hndl.parseString(response.read())
        self.failUnlessEqual(len(nodes), 3)
        node = nodes[1]
        self.failUnlessEqual(node.getCloudAlias(), 'newbie')

        # Try to enumerate images - it should fail
        uri = 'clouds/xen-enterprise/instances/newbie.eng.rpath.com/images'
        client = self.newClient(srv, uri)
        resp = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(resp.status, 400)
        self.assertXMLEquals(resp.contents, '<?xml version="1.0" encoding="UTF-8"?>\n<fault>\n  <code>400</code>\n  <message>Target credentials not set for user</message>\n</fault>')

    def testNewCloudWithDeploymentDaemon(self):
        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances'
        client = self.newClient(srv, uri)

        reqData = _xmlNewCloud2
        response = client.request('POST', reqData)

        hndl = clouds.Handler()
        node = hndl.parseString(response.read())

        cloudId = self.makeUri(client, "clouds/%s/instances/%s" % (
            'xen-enterprise', 'newbie.eng.rpath.com'))
        self.failUnlessEqual(node.getId(), cloudId)

    def no_testUpload1(self):
        # Not intended to run as part of the testsuite (yet)
        client = xenent.xenentclient.UploadClient("http://foo:bar@localhost:1234/abc")
        sio = util.BoundedStringIO("01234" * 5)
        sio.seek(0)
        resp = client.request(sio)

    def no_testUpload2(self):
        # Not intended to run as part of the testsuite
        taskId = 'OpaqueRef:db2acba8-2346-3aee-dc8b-b36f7a84f7fe'
        client = xenent.xenentclient.UploadClient("http://root:PASS@xenent-02.eng.rpath.com/import?task_id=%s&sr_id=OpaqueRef:e39b751d-723d-6a54-851c-f194f9381394" % taskId)
        sio = file("/tmp/lochdns-2.0.1-x86.xva")
        resp = client.request(sio)

    def testSetCredentials(self):
        cloudName = 'xs01.eng.rpath.com'
        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances/xs01.eng.rpath.com/users/%(username)s/credentials?_method=PUT'

        hndlr = credentials.Handler()

        client = self.newClient(srv, uri)
        response = client.request('POST', body = _xmlNewCreds)

        data = response.read()
        node = hndlr.parseString(data)

        self.failUnlessEqual(node.getValid(), True)

        # Make sure credentials made it
        creds = self.restdb.targetMgr.getTargetCredentialsForUser(
            'xen-enterprise', cloudName, 'JeanValjean')
        self.failUnlessEqual(creds, dict(username='boo',
                                         password='blah'))

    def testSetCredentialsFail(self):
        DummyTransport.dataMap['session.login_with_password'] = ({
            'Status': 'Failure',
            'ErrorDescription': ['SESSION_AUTHENTICATION_FAILED', 'root', 'Authentication failure'],
        }, )
        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances/xs01.eng.rpath.com/users/%(username)s/credentials?_method=PUT'

        hndlr = credentials.Handler()

        client = self.newClient(srv, uri)
        response = self.failUnlessRaises(ResponseError,
            client.request, 'POST', body = _xmlNewCreds)
        self.failUnlessEqual(response.status, 403)

    def testGetLaunchDescriptorDefaultSr(self):
        DummyTransport.dataMap['pool.get_all_records'] = mockedData.xenent_listPools1
        DummyTransport.dataMap['SR.get_uuid'] = mockedData.xenent_SR_get_uuid2
        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances/xs01.eng.rpath.com/descriptor/launch'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        ftypes = [ df.type for df in dsc.getDataFields() ]
        self.failUnlessEqual(
            [ ftypes[0], ftypes[1], ftypes[2] ],
            ['str', 'str', 'str'])
        self.failUnlessEqual([ [ (x.key, x.descriptions.asDict()) for x in ftype ]
            for ftype in [ ftypes[3] ] ],
            [
                [
                    ('b9e4d88e-88e9-3a2e-92ff-4b180f3fee5d',
                        {None: 'Local storage (lvm) on node2.blah.com'}),
                    ('494115e9-0901-9719-1a13-c0857fd4d3d8',
                        {None: 'Local storage (lvm) on node1.blah.com'}),
                    ('65168a01-302f-9886-a1b3-eb467e8a113b',
                        {None: u'nas2.eng (nfs)'}),
                    ('eab9d53e-ae74-9fa9-c5ff-edd32a944657',
                        {None: 'NFS virtual disk storage (nfs)'}),
                ]
            ])
        self.failUnlessEqual([ df.getDefault() for df in dsc.getDataFields() ],
            [None, None, None, 'b9e4d88e-88e9-3a2e-92ff-4b180f3fee5d'])

    def testGetLaunchDescriptorNoDefaultSr(self):
        # In this scenario, the pools point to an invalid SR
        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances/xs01.eng.rpath.com/descriptor/launch'

        client = self.newClient(srv, uri)
        response = client.request('GET')

        dsc = descriptor.ConfigurationDescriptor(fromStream = response.read())
        self.failUnlessEqual(dsc.getDisplayName(), "Xen Enterprise Launch Parameters")
        self.failUnlessEqual(dsc.getDescriptions(), {None : 'Xen Enterprise Launch Parameters'})
        self.failUnlessEqual([ df.name for df in dsc.getDataFields() ],
            ['imageId', 'instanceName', 'instanceDescription',
             'storageRepository'])
        ftypes = [ df.type for df in dsc.getDataFields() ]
        self.failUnlessEqual(
            [ ftypes[0], ftypes[1], ftypes[2] ],
            ['str', 'str', 'str'])
        self.failUnlessEqual([ [ (x.key, x.descriptions.asDict()) for x in ftype ]
            for ftype in [ ftypes[3] ] ],
            [
                [
                    ('494115e9-0901-9719-1a13-c0857fd4d3d8',
                        {None: 'Local storage (lvm) on node1.blah.com'}),
                    ('65168a01-302f-9886-a1b3-eb467e8a113b',
                        {None: u'nas2.eng (nfs)'}),
                    ('b9e4d88e-88e9-3a2e-92ff-4b180f3fee5d',
                        {None: 'Local storage (lvm) on node2.blah.com'}),
                    ('eab9d53e-ae74-9fa9-c5ff-edd32a944657',
                        {None: 'NFS virtual disk storage (nfs)'}),
                ]
            ])
        expMultiple = [None] * len(dsc.getDataFields())
        self.failUnlessEqual([ df.multiple for df in dsc.getDataFields() ],
            expMultiple)
        self.failUnlessEqual([ df.required for df in dsc.getDataFields() ],
            [ True, True, None, True, ] )
        self.failUnlessEqual([ df.hidden for df in dsc.getDataFields() ],
            [ True, None, None, None, ] )
        self.failUnlessEqual([ df.descriptions.asDict() for df in dsc.getDataFields() ],
            [
                {None: 'Image ID'},
                {None: 'Instance Name'},
                {None: 'Instance Description'},
                {None: 'Storage Repository'},
            ])
        self.failUnlessEqual([ df.constraintsPresentation for df in dsc.getDataFields() ],
            [
                [{'max': 32, 'constraintName': 'range', 'min': 1}],
                [{'value': 32, 'constraintName': 'length'}],
                [{'value': 128, 'constraintName': 'length'}],
                [],
            ])
        self.failUnlessEqual([ df.getDefault() for df in dsc.getDataFields() ],
            [None, None, None, '494115e9-0901-9719-1a13-c0857fd4d3d8'])

    def testGetLaunchDescriptorNoSrDefined(self):
        # No SRs defined. We should fail gracefully
        DummyTransport.dataMap['SR.get_uuid'] = mockedData.xenent_SR_get_uuid1
        DummyTransport.dataMap['SR.get_all_records'] = mockedData.xenent_listSRs2
        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances/xs01.eng.rpath.com/descriptor/launch'

        client = self.newClient(srv, uri)
        response = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(response.status, 500)
        self.assertXMLEquals(response.contents, """\
<?xml version='1.0' encoding='UTF-8'?>
<fault>
  <code>500</code>
  <message>No Storage Repositories defined</message>
</fault>""")

    def _setUpNewInstanceTest(self, cloudName, daemonizeFunc, imageName,
            imageId = None, downloadFileFunc = None):
        if not imageId:
            imageId = '0903de41206786d4407ff24ab6e972c0d6b801f3'
        cloudType = xenent.driver.cloudType

        self.mock(baseDriver.CatalogJobRunner, 'backgroundRun', daemonizeFunc)
        self.mock(xenent.xenentclient, 'HTTPConnection',
            DummyRestClientConnection)

        if downloadFileFunc:
            fakeDownloadFile = downloadFileFunc
        else:
            def fakeDownloadFile(slf, url, destFile, headers = None):
                file(destFile, "w").write(url)

        self.mock(xenent.driver, "downloadFile", fakeDownloadFile)

        srv = self.newService()
        uri = 'clouds/%s/instances/%s/instances' % (cloudType, cloudName)

        requestXml = mockedData.xml_newInstanceXen1 % imageId
        client = self.newClient(srv, uri)
        response = client.request('POST', requestXml)

        job = self.getJobFromResponse(response)
        return srv, client, job, response

    def testNewInstances1(self):
        cloudName = 'xs01.eng.rpath.com'
        cloudType = xenent.driver.cloudType
        def fakeDaemonize(*args, **kwargs):
            pass

        srv, client, job, response = self._setUpNewInstanceTest(
            cloudName, fakeDaemonize, '')

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))
        self.failUnlessEqual(job.get_imageId(),
            self.makeUri(client, "clouds/xen-enterprise/instances/xs01.eng.rpath.com/images/0903de41206786d4407ff24ab6e972c0d6b801f3"))

        # Enumerate instances
        response = client.request('GET')
        hndlr = instances.Handler()
        nodes = hndlr.parseString(response.read())

        self.failUnlessEqual(len(nodes), 6)

        # Grab the job
        client = self.newClient(srv, jobUrlPath)
        response = client.request('GET')

        job = self.getJobFromResponse(response)

        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))

    def testNewInstances2(self):
        cloudName = 'xs01.eng.rpath.com'
        cloudType = xenent.driver.cloudType
        def fakeDaemonize(slf, *args, **kwargs):
            return slf.function(*args, **kwargs)

        srv, client, job, response = self._setUpNewInstanceTest(
            cloudName, fakeDaemonize, 'some-file-6-1-x86')

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))

        # Grab the job
        client = self.newClient(srv, jobUrlPath)
        response = client.request('GET')

        job = self.getJobFromResponse(response)
        self.failUnlessEqual([ x.get_content() for x in job.history ],
            ['Launching instance from image 0903de41206786d4407ff24ab6e972c0d6b801f3 (type XEN_OVA)',
             'Downloading image', 'Importing image',
             'Cloning template', 'Attaching credentials', 'Launching',
             'Instance(s) running: VmUuid1', 'Instance VmUuid1: 10.0.0.1',
             'Done'])


    def testNewInstances3NoImage(self):
        cloudName = 'xs01.eng.rpath.com'
        cloudType = xenent.driver.cloudType
        def fakeDaemonize(slf, func, *args, **kwargs):
            return func(*args, **kwargs)

        response = self.failUnlessRaises(ResponseError,
            self._setUpNewInstanceTest,
            cloudName, fakeDaemonize, 'some-file-6-1-x86',
            imageId = 'no such image')
        self.failUnlessEqual(response.status, 404)

    def testNewInstances4(self):
        cloudName = 'xs01.eng.rpath.com'
        cloudType = xenent.driver.cloudType

        def fakeDownloadFile(slf, url, destFile, headers = None):
            if headers != { 'Cookie' : 'pysid=CookieMonster'}:
                raise Exception("pysid not passed in")
            file(destFile, "w").write(url)

        def fakeDaemonize(slf, *args, **kwargs):
            slf.function.im_self.zoneAddresses = [
                '10.0.0.1:8883',
                '10.0.0.2:8883',
            ]
            return slf.function(*args, **kwargs)

        def fakeMakeRequest(slf, loginUrl, data, headers):
            class FakeAddInfoUrl(object):
                pass
            o = FakeAddInfoUrl()
            o.headers = {'set-cookie': 'pysid=CookieMonster;foo=bar'}
            return o

        self.mock(xenent.xenentclient.baseDriver.CookieClient, "makeRequest", fakeMakeRequest)

        srv, client, job, response = self._setUpNewInstanceTest(
            cloudName, fakeDaemonize, 'some-file-7-1-x86',
            imageId = '0xPrivateImage',
            downloadFileFunc = fakeDownloadFile)

        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))

    def testNewInstances5NoCookie(self):
        cloudName = 'xs01.eng.rpath.com'
        cloudType = xenent.driver.cloudType

        def fakeDownloadFile(slf, url, destFile, headers = None):
            if headers:
                raise Exception("pysid was passed in")
            raise xenent.xenentclient.errors.DownloadError(
                "No no no, you don't love me and I know now")

        def fakeDaemonize(slf, *args, **kwargs):
            return slf.function(*args, **kwargs)

        def fakeMakeRequest(slf, loginUrl, data, headers):
            class FakeAddInfoUrl(object):
                pass
            o = FakeAddInfoUrl()
            o.headers = {}
            return o

        self.mock(xenent.xenentclient.baseDriver.CookieClient, "makeRequest", fakeMakeRequest)

        srv, client, job, response = self._setUpNewInstanceTest(
            cloudName, fakeDaemonize, 'some-file-7-1-x86',
            imageId = '0xPrivateImage',
            downloadFileFunc = fakeDownloadFile)
        jobUrlPath = 'jobs/types/instance-launch/jobs/1'
        self.failUnlessEqual(job.get_id(), self.makeUri(client, jobUrlPath))
        job = self.waitForJob(srv, jobUrlPath, "Failed")

        errorResponse = job.get_errorResponse()
        sio = util.BoundedStringIO()
        errorResponse.export(sio, 0, '')
        sio.seek(0)
        self.assertXMLEquals(sio.getvalue(), """<errorResponse><fault><code>404</code><message>No no no, you don't love me and I know now</message></fault></errorResponse>""")

    def testTerminateInstance(self):
        cloudName = 'xs01.eng.rpath.com'
        cloudType = xenent.driver.cloudType

        instId = '98aef2dc-e6f3-803c-f490-791b847d3a3e'
        srv = self.newService()
        uri = 'clouds/%s/instances/%s/instances/%s' % (cloudType, cloudName,
           instId)

        client = self.newClient(srv, uri)
        response = client.request('DELETE')

        hndlr = instances.Handler()
        nodes = hndlr.parseString(response.read())
        self.failUnlessEqual([ x.getState() for x in nodes ],
            ['Terminating'])

    def testGetLaunchDescriptorNoCredentials(self):
        # RBL-3945
        cloudName = 'xs01.eng.rpath.com'
        self.restdb.targetMgr.setTargetCredentialsForUser(
            self.CLOUD_TYPE, cloudName, 'JeanValjean', {})
        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances/xs01.eng.rpath.com/descriptor/launch'

        client = self.newClient(srv, uri)
        response = self.failUnlessRaises(ResponseError, client.request, 'GET')
        self.failUnlessEqual(response.status, 404)
        self.assertXMLEquals(response.contents, """
<?xml version="1.0" encoding="UTF-8"?>
<fault>
  <code>404</code>
  <message>User has no credentials set</message>
</fault>""")

    def testGetCloudsNoCredentials(self):
        # RBL-3945
        cloudName = 'xs01.eng.rpath.com'
        self.restdb.targetMgr.setTargetCredentialsForUser(
            self.CLOUD_TYPE, cloudName, 'JeanValjean', {})

        srv = self.newService()
        uri = 'clouds/xen-enterprise/instances'
        client = self.newClient(srv, uri)

        response = client.request('GET')
        self.failUnlessEqual(response.msg['Content-Type'], 'application/xml')
        self.failUnlessEqual(response.msg['Cache-Control'], 'no-store')
        hndlr = clouds.Handler()
        nodes = hndlr.parseString(response.read())

        self.failUnlessEqual([x.getCloudName() for x in nodes],
            ['abc.eng.rpath.com', 'xs01.eng.rpath.com'])

        prefix = self.makeUri(client, "clouds/xen-enterprise/instances/abc.eng.rpath.com")
        self.failUnlessEqual(
            [ x.getDescriptorLaunch().getHref() for x in nodes ],
            [ self.makeUri(client,
                "clouds/xen-enterprise/instances/%s/descriptor/launch" %
                    (x.getCloudName(), ))
                    for x in nodes ])

_xmlNewCloud = """
<descriptorData>
  <alias>newbie</alias>
  <description>Brand new cloud</description>
  <name>newbie.eng.rpath.com</name>
  <useDeploymentDaemon>no</useDeploymentDaemon>
  <deploymentDaemonPort>12123</deploymentDaemonPort>
</descriptorData>"""

_xmlNewCloud2 = """
<descriptorData>
  <alias>newbie</alias>
  <description>Brand new cloud</description>
  <name>newbie.eng.rpath.com</name>
  <useDeploymentDaemon>yes</useDeploymentDaemon>
  <deploymentDaemonPort>12345</deploymentDaemonPort>
</descriptorData>"""


_xmlNewCreds = """
<descriptorData>
  <username>boo</username>
  <password>blah</password>
</descriptorData>
"""

if __name__ == "__main__":
    testsuite.main()
