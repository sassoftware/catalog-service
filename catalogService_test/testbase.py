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
testsuite.setup()

import os
import time

from conary_test import rephelp

from testrunner import testcase

from catalogService import handler
from catalogService.rest import baseDriver
from catalogService.restClient import Client
from catalogService.rest.database import RestDatabase
from catalogService.rest.models import jobs as jobmodels

from catalogService_test import setupbase

# These imports come from mockedModules
from mint import config
from mint.db.database import Database
from mint import shimclient
from mint.django_rest.rbuilder.manager import rbuildermanager

class BuildData(object):
    buildData = {
        'XEN_OVA': [{
                'productName': 'test project',
                'buildId': 1,
                'buildName': 'test devel V2',
                'buildDescription': 'some description',
                'productDescription': 'product description',
                'createdBy': 'foouser',
                'role': 'owner',
                'isPrivate': 0,
                'baseFileName' : 'some-file-1-1-x86',
                'files' : [dict(
                    sha1 = 'b3fb7387bb04b1403bc0eb06bd55c0ef5f02d9bb',
                    fileName = 'some-file-1-1-x86.tar.gz',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=4',
                    targetImages = [],
                    fileId = 4,
                )],
                'buildPageUrl': 'http://test.rpath.local2/project/foo/build?id=1',
            },
            {
                'productName': 'foo project',
                'buildId': 6,
                'buildName': 'foo project',
                'buildDescription': 'just words and stuff',
                'productDescription': 'words words SPARKY words',
                'createdBy': 'Bob Loblaw',
                'role': 'developer',
                'isPrivate': 0,
                'baseFileName' : 'some-file-6-1-x86',
                'files' : [dict(
                    sha1 = '0903de41206786d4407ff24ab6e972c0d6b801f3',
                    fileName = 'some-file-6-1-x86.tar.gz',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=6',
                    targetImages = [],
                    fileId = 6,
                )],
                'buildPageUrl': 'http://test.rpath.local2/project/foo/build?id=6',
                'imageData' : {
                },
            },
            {
                'productName': 'bar project',
                'buildId': 7,
                'buildName': 'bar project',
                'buildDescription': 'Build for project bar',
                'productDescription': 'Product Description',
                'createdBy': 'Bob Loblaw',
                'role': 'developer',
                'isPrivate': 1,
                'baseFileName' : 'some-file-7-1-x86',
                'files' : [dict(
                    sha1 = '0xPrivateImage',
                    fileName = 'some-file-7-1-x86.tar.gz',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=7',
                    targetImages = [],
                    fileId = 7,
                )],
                'buildPageUrl': 'http://test.rpath.local2/project/foo/build?id=7',
            }],
        'VWS': [{
                'productName': 'test project',
                'buildId': 1,
                'buildName': 'test devel V2',
                'buildDescription': 'some description',
                'productDescription': 'product description',
                'createdBy': 'foouser',
                'role': 'owner',
                'isPrivate': 0,
                'baseFileName' : 'some-file-1-1-x86',
                'files' : [dict(
                    sha1 = 'b3fb7387bb04b1403bc0eb06bd55c0ef5f02d9bb',
                    fileName = 'some-file-1-1-x86.tar.gz',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=4',
                    targetImages = [],
                    fileId = 4,
                )],
                'buildPageUrl': 'http://test.rpath.local2/project/foo/build?id=1',
            },
            {
                'productName': 'foo project',
                'buildId': 6,
                'buildName': 'foo project',
                'buildDescription': 'just words and stuff',
                'productDescription': 'words words SPARKY words',
                'createdBy': 'Bob Loblaw',
                'role': 'developer',
                'isPrivate': 0,
                'baseFileName' : 'some-file-6-1-x86',
                'files' : [dict(
                    sha1 = '0903de41206786d4407ff24ab6e972c0d6b801f3',
                    fileName = 'some-file-6-1-x86.tar.gz',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=6',
                    targetImages = [],
                    fileId = 6,
                )],
                'buildPageUrl': 'http://test.rpath.local2/project/foo/build?id=6',
            }],
        'VMWARE_ESX_IMAGE': [
            # This build will be ignored in favor of the OVF one
            {
                'architecture' : 'x86',
                'productName': 'foo project',
                'buildId': 6,
                'buildName': 'foo project',
                'buildDescription': 'just words and stuff',
                'productDescription': 'words words SPARKY words',
                'createdBy': 'Bob Loblaw',
                'role': 'developer',
                'imageType' : 'VMWARE_ESX_IMAGE',
                'isPrivate': 0,
                'baseFileName' : 'some-file-6-1-x86',
                'files' : [dict(
                    sha1 = '361d7fa1d99431e16a3a438c8d4ebaa79aea075a',
                    fileName = 'some-file-6-1-x86.esx.tar.gz',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=6',
                    targetImages = [],
                    fileId = 6,
                )],
                'buildPageUrl': 'http://test.rpath.local2/project/foo/build?id=6',
            },
            # We have OVF 0.9 and 1.0 (ova). Prefer ova
            {
                'architecture' : 'x86',
                'productName': 'foo project',
                'buildId': 69,
                'buildName': 'foo project',
                'buildDescription': 'just words and stuff',
                'productDescription': 'words words SPARKY words',
                'createdBy': 'Bob Loblaw',
                'role': 'developer',
                'imageType' : 'VMWARE_ESX_IMAGE',
                'isPrivate': 0,
                'baseFileName' : 'some-file-6-1-x86',
                'files' : [
                  dict(
                    sha1 = 'plainEsxSha1sum0000000000000000000000000',
                    fileName = 'some-file-6-1-x86.esx.tar.gz',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=691',
                    fileId = 691,
                    targetImages = []),
                  dict(
                    sha1 = 'sha1ForOvf091111111111111111111111111111',
                    fileName = 'some-file-6-1-x86-ovf.tar.gz',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=692',
                    fileId = 692,
                    targetImages = []),
                  dict(
                    sha1 = 'sha1ForOvf101111111111111111111111111111',
                    fileName = 'some-file-6-1-x86.ova',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=693',
                    fileId = 693,
                    targetImages = []),
                ],
                'buildPageUrl': 'http://test.rpath.local2/project/foo/build?id=69',
                'imageData' : {
                    'vmMemory' : 512,
                    'vmCPUs' : 2,
                },
            },
            {
                'architecture' : 'x86',
                'productName': 'foo layered',
                'buildId': 169,
                'baseBuildId' : 69,
                'buildName': 'foo layered',
                'buildDescription': 'foo layered description',
                'productDescription': 'foo layered product description',
                'createdBy': 'Bob Loblaw',
                'role': 'developer',
                'imageType' : 'DEFERRED_IMAGE',
                'isPrivate': 0,
                'baseFileName' : 'some-file-6-1-x86',
                'files' : [
                  dict(
                    sha1 = 'sha1ForOvf091111111111111111111111111111',
                    fileName = 'some-file-6-1-x86-ovf.tar.gz',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=692',
                    fileId = 692,
                    uniqueImageId = 169,
                    targetImages = []),
                  dict(
                    sha1 = 'sha1ForOvf101111111111111111111111111111',
                    fileName = 'some-file-6-1-x86.ova',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=693',
                    fileId = 693,
                    uniqueImageId = 169,
                    targetImages = []),
                ],
                'buildPageUrl': 'http://test.rpath.local2/project/foo/build?id=169',
                'imageData' : {
                    'vmMemory' : 512,
                    'vmCPUs' : 2,
                },
            },
            ],
        'VMWARE_OVF_IMAGE': [
            {
                'architecture' : 'x86',
                'productName': 'foo project',
                'buildId': 6,
                'buildName': 'foo project',
                'buildDescription': 'just words and stuff',
                'productDescription': 'words words SPARKY words',
                'createdBy': 'Bob Loblaw',
                'role': 'developer',
                'isPrivate': 0,
                'baseFileName' : 'some-file-6-1-x86',
                'files' : [dict(
                    sha1 = 'aaaaaabbbbbbbbbcccccccccccddddddddeeeeee',
                    fileName = 'some-file-6-1-x86.tar.gz',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=7',
                    targetImages = [],
                    fileId = 7,
                )],
                'buildPageUrl': 'http://test.rpath.local2/project/foo/build?id=7',
                'imageData' : {
                    'vmMemory' : 512,
                    'vmCPUs' : 2,
                },
            }
            ],
        'AMI' : [
            {
                'architecture' : 'x86',
                'productName': 'foo project',
                'buildId': 6,
                'buildName': 'foo project',
                'buildDescription': 'just words and stuff',
                'productDescription': 'words words SPARKY words',
                'createdBy': 'Bob Loblaw',
                'role': 'developer',
                'isPrivate': 0,
                'baseFileName' : 'some-file-6-1-x86',
                'files' : [dict(
                    sha1 = 'aaaaaabbbbbbbbbcccccccccccddddddddeeeeee',
                    fileName = 'some-file-6-1-x86.tar.gz',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=7',
                    targetImages = [],
                    fileId = 7,
                )],
                'buildPageUrl': 'http://test.rpath.local2/project/foo/build?id=7',
                'imageData' : {
                    'freespace' : 143515414,
                    'attributes.installed_size' : 234290583,
                },
            },
        ],
        'RAW_FS_IMAGE' : [
            {
                'architecture' : 'x86',
                'productName': 'foo project',
                'buildId': 6,
                'buildName': 'foo project',
                'buildDescription': 'just words and stuff',
                'productDescription': 'words words SPARKY words',
                'createdBy': 'Bob Loblaw',
                'role': 'developer',
                'isPrivate': 0,
                'baseFileName' : 'some-file-6-1-x86',
                'files' : [dict(
                    sha1 = '361d7fa1d99431e16a3a438c8d4ebaa79aea075a',
                    fileName = 'some-file-6-1-x86.tar.gz',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=6',
                    targetImages = [],
                    fileId = 6,
                )],
                'buildPageUrl': 'http://test.rpath.local2/project/foo/build?id=6',
                'imageData' : {
                },
            },
            {
                'productName': 'bar project',
                'buildId': 8,
                'buildName': 'bar project',
                'buildDescription': 'build description for bar 8',
                'productDescription': 'product description for bar',
                'createdBy': 'Bob Loblaw',
                'role': 'developer',
                'isPrivate': 0,
                'baseFileName' : 'some-file-8-1-x86',
                'files' : [dict(
                    sha1 = '0000000000000000000000000000000000000001',
                    fileName = 'some-file-8-1-x86.tar.gz',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=8',
                    targetImages = [
                        ('eucalyptus', 'euca1.eng.rpath.com', 'emi-0435d06d'),
                    ],
                    fileId = 8,
                )],
                'buildPageUrl': 'http://test.rpath.local2/project/bar/build?id=8',
            },
        ],
        'RAW_HD_IMAGE' : [
            {
                'architecture' : 'x86',
                'productName': 'foo project',
                'buildId': 96,
                'buildName': 'foo project',
                'buildDescription': 'just words and stuff',
                'productDescription': 'words words SPARKY words',
                'createdBy': 'Bob Loblaw',
                'role': 'developer',
                'isPrivate': 0,
                'baseFileName' : 'some-file-96-1-x86',
                'files' : [dict(
                    sha1 = 'a00000000000000000000000000000000000000a',
                    fileName = 'some-file-96-1-x86.tar.gz',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=196',
                    targetImages = [],
                    fileId = 196,
                )],
                'buildPageUrl': 'http://test.rpath.local2/project/foo/build?id=96',
            },
            {
                'productName': 'bar project',
                'buildId': 98,
                'buildName': 'bar project',
                'buildDescription': 'build description for bar 98',
                'productDescription': 'product description for bar',
                'createdBy': 'Bob Loblaw',
                'role': 'developer',
                'isPrivate': 0,
                'baseFileName' : 'some-file-98-1-x86',
                'files' : [dict(
                    sha1 = '0000000000000000000000000000000000000001',
                    fileName = 'some-file-98-1-x86.tar.gz',
                    downloadUrl = 'http://test.rpath.local2/downloadImage?id=198',
                    targetImages = [
                        ('openstack', 'openstack1.eng.rpath.com', '2'),
                    ],
                    fileId = 198,
                )],
                'buildPageUrl': 'http://test.rpath.local2/project/bar/build?id=98',
            },
        ],
    }

class TestCase(testcase.TestCaseWithWorkDir):
    testDirName = 'catalog-service-test-'
    _basePath = '/TOPLEVEL'
    TARGETS = []
    MINT_CFG = [
        ('basePath', '/'),
        ('dataPath', '/tmp'),
    ]
    USERS = [
        ('JeanValjean', 'secretPassword', 'Jean Valjean',),
    ]
    USER_TARGETS = [
    ]
    BUILD_DATA = [
    ]
    targetSystemIds = [ "0xABC" ]

    def setUp(self):
        testcase.TestCaseWithWorkDir.setUp(self)
        helpDir = os.path.join(
            os.environ['CATALOG_SERVICE_PATH'],
            'catalogService',
            'rest')

        buildData = BuildData.buildData.copy()
        buildData.update(self.BUILD_DATA)
        # Fix up imageType
        for imageType, images in buildData.items():
            for img in images:
                img.setdefault('imageType', imageType)

        dbpath = os.path.join(self.workDir, "db.sqlite")
        # Stub mint config file
        mintCfgPath = self.mintCfgPath = os.path.join(self.workDir, 'mint.conf')
        mintCfgDict = dict(self.MINT_CFG)
        mintCfgDict['dataPath'] = self.storagePath = os.path.join(self.workDir, "data")
        mintCfgDict['dbPath'] = dbpath
        mintCfgDict['basePath'] = self._basePath
        file(mintCfgPath, "w").write('\n'.join(' '.join(x)
            for x in mintCfgDict.items()))
        mintcfg = self.mintcfg = config.getConfig(mintCfgPath)

        mintdb = Database(mintcfg)

        restdb = self.restdb = RestDatabase(mintcfg, mintdb)
        setupbase.createSchema(mintdb.db)
        mintdb.db._buildData = buildData

        for targetType, targetName, targetData in self.TARGETS:
            restdb.targetMgr.addTarget(targetType, targetName, targetData)
        for username, password, fullName in self.USERS:
            restdb.db.users.registerNewUser(username, password, fullName,
                'email@address.com', 'Y', 'blurb', 1)
        for username, targetType, targetName, credentials in self.USER_TARGETS:
            restdb.targetMgr.setTargetCredentialsForUser(targetType,
                targetName, username, credentials)
        self.setUpJobs()
        restdb.commit()

        if os.path.isdir(helpDir):
            handler.Request._helpDir = helpDir
            handler.Request._driverHelpDir = "drivers/%(driverName)s/help"
        self.services = []
        self.inventoryManager = rbuildermanager.RbuilderManager(self.mintcfg, 1)
        self.systemMgr = self.inventoryManager.sysMgr

        RESTHandler.updateHandler(restdb)

        from rpath_job import api1 as rpath_job

        # We need to slow down addHistoryEntry a bit
        origAddHistoryEntry = rpath_job.HistoryBaseJob.addHistoryEntry
        def fakeAddHistoryEntry(slf, *args, **kwargs):
            time.sleep(0.002)
            return origAddHistoryEntry(slf, *args, **kwargs)
        self.mock(rpath_job.HistoryBaseJob, 'addHistoryEntry', fakeAddHistoryEntry)

        # Mock postFork, we don't want to reopen the db, or we lose the mock
        # data
        def mockPostFork(slf):
            slf.zoneAddresses = [ '1.2.3.4:5678', '2.3.4.5:6789' ]
        self.mock(baseDriver.BaseDriver, 'postFork', mockPostFork)

        self.setUpSystemManager()
        self.setUpSchemaDir()

    def setUpSystemManager(self):
        self.systemMgr.CREDS.clear()
        self.systemMgr.VERSIONS.clear()

    def setUpSchemaDir(self):
        self.schemaDir = ""
        from smartform import descriptor
        schemaFile = "descriptor-%s.xsd" % descriptor.BaseDescriptor.version
        schemaDir = os.path.join(os.environ['SMARTFORM_PATH'], 'xsd')
        if not os.path.exists(os.path.join(schemaDir, schemaFile)):
            # Not running from a checkout
            schemaDir = descriptor._BaseClass.schemaDir
            assert(os.path.exists(os.path.join(schemaDir, schemaFile)))
        self.schemaDir = schemaDir
        self.mock(descriptor.BaseDescriptor, 'schemaDir', schemaDir)
        self.mock(descriptor.DescriptorData, 'schemaDir', schemaDir)

    def setUpJobs(self):
        self.restdb.auth.userId = 1
        targetId = self.restdb.targetMgr.getTargetId(self.cloudType,
            self.cloudName)

        # Add instance
        cu = self.restdb.cursor()
        for targetSystemId in self.targetSystemIds:
            cu.execute("INSERT INTO inventory_managed_system (registration_date) VALUES (datetime('now'))")
            managedSystemId = cu.lastid()
            cu.execute("INSERT INTO inventory_system_target (target_id, managed_system_id, target_system_id) VALUES (?, ?, ?)",
                targetId, managedSystemId, targetSystemId)

    def getMintDb(self):
        return shimclient.ShimMintClient.db

    def getTargetData(self, targetType, targetName):
        return self.restdb.targetMgr.getTargetData(targetType, targetName)

    def deleteTarget(self, targetType, targetName):
        ret = self.restdb.targetMgr.deleteTarget(targetType, targetName)
        self.restdb.commit()
        return ret

    def setTargetData(self, targetType, targetName, dataDict):
        self.restdb.targetMgr.addTarget(targetType, targetName, dataDict)
        self.restdb.commit()

    def setAdmin(self, isAdmin = False):
        db = self.restdb
        cu = db.cursor()
        isAdmin = (isAdmin and 1) or 0
        cu.execute("UPDATE Users SET admin = ? WHERE username = ?",
            isAdmin, "JeanValjean")
        db.commit()


    def tearDown(self):
        testcase.TestCaseWithWorkDir.tearDown(self)
        shimclient.MintClient.db = None
        for srv in self.services:
            srv.close()
        del self.services[:]

    def newClient(self, srv, uri, username = 'JeanValjean',
            password = 'secretPassword', headers = None, **kwargs):
        if username is not None:
            kwargs['username'] = username
            kwargs['password'] = password
        uri = self._makeUri(uri, port = srv.port, **kwargs)
        client = Client(uri, headers)
        if username is not None:
            client.setUserPassword(username, password)
        client.connect()
        return client

    def newService(self):
        logFile = os.path.join(self.workDir, "server.log")
        RESTHandler._logFile = logFile
        srv = rephelp.HTTPServerController(RESTHandler)
        self.services.append(srv)
        return srv

    def _makeUri(self, uri, **kwargs):
        if uri.startswith('http://'):
            return uri
        if 'hostport' not in kwargs and 'port' in kwargs:
            kwargs['hostport'] = "localhost:%s" % kwargs["port"]
        uri = 'http://%(hostport)s' + '%s/%s' % (self._basePath, uri)
        return uri % kwargs

    def makeUri(self, client, uri):
        return self._makeUri(uri, username = client.user,
            hostport = client.hostport)

    @classmethod
    def getJobFromResponse(cls, response):
        job = jobmodels.Job()
        job.parseStream(response)
        return job

    def waitForJob(self, srv, jobUrl, states):
        client = self.newClient(srv, jobUrl)
        if not isinstance(states, (list, set, tuple)):
            states = [states]
        states = set(states)
        for i in range(20):
            resp = client.request('GET')
            job = self.getJobFromResponse(resp)
            status = job.get_status()
            if status in states:
                return job
            if status not in [ 'Queued', 'Running' ]:
                self.fail("Unexpected state: %s" % status)
            time.sleep(.2)
        raise TimeoutError(job)

class RESTHandler(handler.BaseRESTHandler):
    pass

class TimeoutError(Exception):
    def __init__(self, job):
        Exception.__init__(self)
        self.job = job
