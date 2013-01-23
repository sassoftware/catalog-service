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

import os
import StringIO
import time
import tempfile

from catalogService.rest import baseDriver
from catalogService.rest.drivers import ec2 as d_ec2
from catalogService.rest.models import instances

from catalogService_test import testbase
import mockedData

class EC2Test(testbase.TestCase):
    TARGETS = [
        ('ec2', 'aws', dict(
            alias = 'aws-us-east',
            description = 'Amazon Elastic Compute Cloud - US East Region',
            ec2PublicKey = 'Public Key',
            ec2PrivateKey = 'Private Key',
            ec2AccountId = '867530900000',
            ec2S3Bucket = 'Bucket',
            ec2Certificate = mockedData.tmp_userCert,
            ec2CertificateKey = mockedData.tmp_userKey,
            ec2LaunchUsers = ['user1', 'user2'],
            ec2LaunchGroups = ['group1', 'group2'],
        )),
    ]

    USER_TARGETS = [
        ('JeanValjean', 'ec2', 'aws', dict(
                accountId = '867-5309-jv',
                publicAccessKeyId = 'User public key',
                secretAccessKey = 'User private key',
            )),
    ]
    cloudType = 'ec2'
    cloudName = 'aws'
    targetSystemIds = [ "i-e2df098b", "i-e5df098c" ]

    def setUp(self):
        testbase.TestCase.setUp(self)
        baseDriver.CatalogJobRunner.preFork = lambda *args: None
        os.makedirs(os.path.join(self.workDir, "data"))
 
    def _createNodeFactory(self):
        return self._createDriver()._nodeFactory

    def _createDriver(self):
        rBuilderUrl = "http://mumbo.jumbo.com"
        from catalogService import config
        cfg = config.BaseConfig()
        cfg.rBuilderUrl = 'http://adf'
        cfg.storagePath = "%s/storage" % self.workDir
        driver = d_ec2.ec2client.EC2Client(cfg, 'ec2', db=self.restdb)
        class Request(object):pass

        class Authorization(object):
            authorized = True
        self.restdb.auth.auth = Authorization()

        request = Request()
        request.auth = ('JeanValjean', 'sekrit')
        request.baseUrl = 'http://mumbo.jumbo.com/bottom'
        request.logger = None
        driver = driver(request, 'aws')
        driver.db = self.restdb
        # Initialize client
        client = driver.client
        driver.drvCreateCloudClient = lambda x: client
        return driver

    def _fakeMakeRequest(self, drv, **kw):
        def fakeMakeRequest(methodName, params, *args, **kwargs):
            #response = origMakeRequest(methodName, params, *args, **kwargs)
            data = kw[methodName]
            if isinstance(data, mockedData.MultiResponse):
                return data.getData()
            resp = mockedData.MockedResponse(data)
            return resp
        self.mock(drv.client, 'make_request', fakeMakeRequest)

    def testCloud(self):

        # Try to create a cloud with id, name, type that are not the default
        # ones
        drv = self._createDriver()
        x = drv._nodeFactory.newCloud(id = 'aaa', cloudName = 'bbb',
            description = 'Cloud Description', cloudAlias='ccc')

        self.failUnlessEqual(x.getId(), 'http://mumbo.jumbo.com/bottom/clouds/ec2/instances/bbb')
        self.failUnlessEqual(x.getType().getText(), 'ec2')
        self.failUnlessEqual(x.getType().getHref(), 'http://mumbo.jumbo.com/bottom/clouds/ec2')
        self.failUnlessEqual(x.getCloudName(), 'bbb')
        self.failUnlessEqual(x.getCloudAlias(), 'ccc')
        self.failUnlessEqual(x.getDescription(), 'Cloud Description')

    def testGetAllImages(self):
        drv = self._createDriver()

        self._fakeMakeRequest(drv, DescribeImages = mockedData.xml_getAllImages1)

        expected = [
            { 'state': None, 'isPublic': None,
                'id': 'http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/images/aaaaaabbbbbbbbbcccccccccccddddddddeeeeee',
                'longName': '6/some-file-6-1-x86'},
            { 'state': 'available', 'isPublic': True,
              'longName': 'rbuilder-online/reviewboard-1.0-x86_13964.img (ami-0435d06d)',
              'id': 'http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/images/ami-0435d06d'}
        ]

        data = drv.getAllImages()
        self.failUnlessEqual([
            dict(id=x.getId(), longName=x.getLongName(), state = x.getState(),
                 isPublic = x.getIsPublic()) for x in data], expected)

    def testGetAllInstances(self):
        drv = self._createDriver()

        self._fakeMakeRequest(drv,
            DescribeInstances = mockedData.xml_getAllInstances1,
            DescribeImages = mockedData.xml_getAllImages3)

        expected = [
            {
                'id': 'http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/instances/i-1639fe7f',
                'imageId': 'ami-3675905f',
                'ramdisk': None, 'kernel': None,
                'privateDnsName': 'domU-12-31-35-00-4D-84.z-2.compute-1.internal',
                'keyName': 'tgerla',
                'reservationId': 'r-698a7500',
                'previousState': None,
                'placement': 'us-east-1c',
                'publicDnsName': 'ec2-75-101-210-216.compute-1.amazonaws.com',
                'instanceType': 'm1.small', 'state': 'running',
                'dnsName': 'ec2-75-101-210-216.compute-1.amazonaws.com',
                'launchTime': 1207592569,
                'stateCode': 16, 'shutdownState': None,
                'ownerId': '941766519978',
                'launchIndex' : 0,
                'cloudName' : 'aws',
                'cloudType' : 'ec2',
                'cloudAlias' : 'aws-us-east',
            },
            {
                'id': 'http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/instances/i-805f98e9',
                'imageId': 'ami-957590fc',
                'ramdisk': None, 'kernel': None,
                'privateDnsName': 'domU-12-31-39-00-5C-E6.compute-1.internal',
                'keyName': 'tgerla',
                'reservationId': 'r-0af30c63',
                'previousState': None,
                'placement': 'imperial-russia',
                'publicDnsName': 'ec2-67-202-54-84.compute-1.amazonaws.com',
                'instanceType': 'm1.small',
                'state': 'running',
                'dnsName': 'ec2-67-202-54-84.compute-1.amazonaws.com',
                'launchTime': 1207665151,
                'stateCode': 16,
                'shutdownState': None,
                'ownerId': '941766519978',
                'launchIndex' : 1,
                'cloudName' : 'aws',
                'cloudType' : 'ec2',
                'cloudAlias' : 'aws-us-east',
            }
        ]

        data = drv.getAllInstances()
        dataList = [
            dict(id=x.getId(), dnsName=x.getDnsName(),
                 publicDnsName=x.getPublicDnsName(),
                 privateDnsName=x.getPrivateDnsName(),
                 state=x.getState(), stateCode=x.getStateCode(),
                 keyName=x.getKeyName(), shutdownState=x.getShutdownState(),
                 previousState=x.getPreviousState(),
                 instanceType=x.getInstanceType(), launchTime=x.getLaunchTime(),
                 imageId=x.getImageId(), placement=x.getPlacement().strip(),
                 kernel=x.getKernel(), ramdisk=x.getRamdisk(),
                 reservationId=x.getReservationId(),
                 ownerId=x.getOwnerId(),
                 launchIndex = x.getLaunchIndex(),
                 cloudName = x.getCloudName(),
                 cloudType = x.getCloudType(),
                 cloudAlias = x.getCloudAlias()) for x in data] 
        self.failUnlessEqual(dataList, expected)

    def testNewInstance(self):

        drv = self._createDriver()

        self._fakeMakeRequest(drv, RunInstances = mockedData.xml_runInstances1,
            DescribeKeyPairs = mockedData.xml_getAllKeyPairs1,
            DescribeSecurityGroups = mockedData.xml_getAllSecurityGroups1,
            DescribeImages = mockedData.xml_getAllImages2,
            DescribeInstances = mockedData.xml_getAllInstances3,
            DescribeAvailabilityZones = mockedData.xml_getAllZones1,
            CreateTags = mockedData.xml_ec2CreateTags,
            )

        job = drv.launchInstance(mockedData.xml_newInstance7, None)
        jobId = 'instance-launch/%s' % os.path.basename(job.get_id())
        for i in range(20):
            job = drv._instanceLaunchJobStore.get(jobId, readOnly = True)
            if job.getResults():
                break
            time.sleep(.2)
        else:
            self.fail("No instances produced")
        self.failUnlessEqual(job.getResults(), [ "i-e2df098b", "i-e5df098c"])

        data = drv.getAllInstances()
        self.failUnlessEqual(len(data), 2)
        self.failUnlessEqual(
            [(x.getId(), x.getKeyName(), x.getLaunchIndex()) for x in data],
            [
                ('http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/instances/i-e2df098b', 'tgerla', 0),
                ('http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/instances/i-e5df098c', 'tgerla', 1)
            ])
        self.failUnlessEqual(
            [(x.getCloudName(), x.getCloudType(), x.getCloudAlias()) for x in data],
            [('aws', 'ec2', 'aws-us-east')] * 2)

    class Job(object):
        def __init__(self, accumulator):
            self._accumulator = accumulator

        def addHistoryEntry(self, *args):
            self._accumulator.append(args)


    def _setupMocking(self, mockedCalls=None):
        drv = self._createDriver()
        # Test URL rewrites too
        urlMapFile = drv._urlMapFile = tempfile.NamedTemporaryFile()
        urlMapFile.write("# http://commented\n")
        urlMapFile.write("ignored\n")
        urlMapFile.write("http://something https://somethingelse\n")
        urlMapFile.write("http://localhost https://localhost:1234\n")
        urlMapFile.flush()
        drv.ImageDownloadUrlMapFile = urlMapFile.name

        mockedCallsArgs = dict(
            DescribeKeyPairs = mockedData.xml_getAllKeyPairs1,
            DescribeSecurityGroups = mockedData.xml_getAllSecurityGroups1,
            DescribeImages = mockedData.xml_getAllImages2,
            DescribeInstances = mockedData.xml_ec2GetMyInstance,
            DescribeAvailabilityZones = mockedData.xml_getAllZones1,
            CreateVolume=mockedData.xml_ec2CreateVolume,
            AttachVolume=mockedData.xml_ec2AttachVolume,
            CreateSnapshot=mockedData.xml_ec2CreateSnapshot,
            DescribeSnapshots=mockedData.MultiResponse([
                mockedData.xml_ec2DescribeSnapshots1,
                mockedData.xml_ec2DescribeSnapshots2, ]),
            RegisterImage=mockedData.xml_ec2RegisterImage,
            DetachVolume=mockedData.xml_ec2DetachVolume,
            DescribeVolumes=mockedData.MultiResponse([
                mockedData.xml_ec2DescribeVolumes1,
                mockedData.xml_ec2DescribeVolumes2, ]),
            DeleteVolume=mockedData.xml_ec2DeleteVolume,
            CreateTags=mockedData.xml_ec2CreateTags,
            )
        if mockedCalls is not None:
            mockedCallsArgs.update(mockedCalls)
        self._fakeMakeRequest(drv, **mockedCallsArgs)

        _downloadUrls = []
        def fakeDownloadFile(url, destFile, headers = None):
            file(destFile, "w").write(url)
            _downloadUrls.append(url)

        self.mock(drv, "downloadFile", fakeDownloadFile)
        drv._downloadUrls = _downloadUrls

        def getFilesystemImageFunc(job, image, dlpath):
            npath = dlpath + '-image'
            f = file(npath, "w")
            f.seek(1024 * 1024 - 1)
            f.write('\0')
            f.close()
            return npath

        self.mock(drv, '_getFilesystemImage', getFilesystemImageFunc)

        self.mock(drv, '_findMyInstanceId', lambda *args: 'i-decafbad')

        # Fake dev file so we can test formatting etc
        devFile = tempfile.NamedTemporaryFile()
        devFile.seek(10 * 1024 * 1024 - 1)
        devFile.write('\0')
        devFile.flush()

        orig_findOpenBlockDevice = drv._findOpenBlockDevice
        def mock_findOpenBlockDevice(*args, **kwargs):
            ret = orig_findOpenBlockDevice(*args, **kwargs)
            return ret[0], devFile.name
        self.mock(drv, '_findOpenBlockDevice', mock_findOpenBlockDevice)

        self.mock(drv, '_writeFilesystemImage', lambda *args: None)
        drv.TIMEOUT_BLOCKDEV = 0.1
        drv.TIMEOUT_SNAPSHOT = 0.1
        drv.TIMEOUT_VOLUME = 0.1

        return drv

    def testDeployImageEBS(self):
        drv = self._setupMocking()
        job = self.Job(list())
        imageFileInfo = dict(fileId=5145, baseFileName="img-64bit",
            architecture='x86')
        imageDownloadUrl = "http://localhost/blah"
        imageData = dict(freespace=1234, ebsBacked=True)
        imageData['attributes.installed_size'] = 14554925
        img = drv.imageFromFileInfo(imageFileInfo, imageDownloadUrl,
                                    imageData=imageData)
        self.assertEquals(img.getArchitecture(), 'x86')
        descriptorDataXml = """\
<descriptor_data>
  <imageId>5145</imageId>
  <imageName>ignoreme1</imageName>
</descriptor_data>
"""
        ret = drv.deployImageFromUrl(job, img, descriptorDataXml)
        self.assertEquals(ret.id, "ami-decafbad")
        self.failUnlessEqual(job._accumulator, [
            ('Downloading image',),
            ('Creating EBS volume',),
            ('Created EBS volume vol-decafbad',),
            ('Attaching EBS volume',),
            ('Created snapshot snap-decafbad',),
            ('Snapshot status: pending',),
            ('Snapshot status: pending',),
            ('Registering EBS-backed image',),
            ('Registered image ami-decafbad',),
            ('Cleaning up',),
            ('Detaching volume vol-decafbad',),
            ('Waiting for volume to be detached',),
        ])

        # Make sure URL remap worked
        self.assertEquals(drv._downloadUrls, ['https://localhost:1234/blah'])

    def testLaunchInstanceEBS(self):
        drv = self._setupMocking(mockedCalls=dict(
            DescribeImages = mockedData.xml_ec2DescribeImages,
            CreateSecurityGroup=mockedData.xml_createSecurityGroupSuccess,
            RunInstances=mockedData.xml_ec2RunInstances,
        ))
        job = self.Job(list())
        imageFileInfo = dict(fileId=5145, baseFileName="img-64bit",
            architecture='x86')
        imageDownloadUrl = "http://localhost/blah"
        imageData = dict(freespace=1234, ebsBacked=True)
        imageData['attributes.installed_size'] = 14554925
        img = drv.imageFromFileInfo(imageFileInfo, imageDownloadUrl,
                                    imageData=imageData)
        descriptorDataXml = """\
<descriptor_data>
  <imageId>5145</imageId>
  <instanceName>instance prefix</instanceName>
  <minCount>2</minCount>
  <maxCount>2</maxCount>
  <freeSpace>20</freeSpace>
</descriptor_data>
"""
        ret = drv.launchSystemSynchronously(job, img, descriptorDataXml)
        self.assertEquals(ret, ["i-decafbad0", "i-decafbad1", ])
        self.failUnlessEqual(job._accumulator, [
            ('Downloading image',),
            ('Creating EBS volume',),
            ('Created EBS volume vol-decafbad',),
            ('Attaching EBS volume',),
            ('Created snapshot snap-decafbad',),
            ('Snapshot status: pending',),
            ('Snapshot status: pending',),
            ('Registering EBS-backed image',),
            ('Registered image ami-decafbad',),
            ('Cleaning up',),
            ('Detaching volume vol-decafbad',),
            ('Waiting for volume to be detached',),
            ('Launching instance ami-decafbad',),
            ('Tagging instances',),
            ('Instance(s) running: i-decafbad',),
            ('Instance i-decafbad: ec2-54-245-172-197.us-west-2.compute.amazonaws.com',)
        ])

        # Make sure URL remap worked
        self.assertEquals(drv._downloadUrls, ['https://localhost:1234/blah'])


    def testTerminateInstance(self):
        drv = self._createDriver()

        self._fakeMakeRequest(drv,
            TerminateInstances = mockedData.xml_awsTerminateInstances1,
            DescribeImages = mockedData.xml_getAllImages1)

        instanceId = 'i-60f12709'
        node = drv.terminateInstance(instanceId)
        self.failUnless(isinstance(node, instances.BaseInstance), node)
        self.failUnlessEqual(node.getId(), 'http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/instances/' + instanceId)

    def test_getExternalIp(self):
        drv = self._createDriver()
        def fakeOpenUrl(url):
            return StringIO.StringIO("""\
1.2.3.4 \n""")
        self.mock(drv, '_openUrl', fakeOpenUrl)
        self.failUnlessEqual(drv._getExternalIp(), '1.2.3.4')

    def testGetImageDeploymentDescriptor(self):
        drv = self._createDriver()
        descr = drv.getImageDeploymentDescriptor()
        self.failUnlessEqual(descr.getDisplayName(),
                'Amazon EC2 Image Deployment Parameters')
        descr = drv.getImageDeploymentDescriptor(extraArgs=dict(
            imageData=dict(ebsBacked=True, ignored=True)))
        self.failUnlessEqual(descr.getDisplayName(),
                'Amazon EC2 Image Deployment Parameters (EBS-backed)')

    def testGetLaunchDescriptor(self):
        drv = self._createDriver()
        self._fakeMakeRequest(drv,
            DescribeKeyPairs = mockedData.xml_getAllKeyPairs1,
            DescribeRegions = mockedData.xml_getAllRegions1,
            DescribeAvailabilityZones = mockedData.xml_getAllZones1,
            DescribeSecurityGroups = mockedData.xml_getAllSecurityGroups1,
        )

        descr = drv.getLaunchDescriptor()
        self.failUnlessEqual(descr.getDisplayName(),
                'Amazon EC2 System Launch Parameters')

        descr = drv.getLaunchDescriptor(extraArgs=dict(
            imageData=dict(ebsBacked=True, ignored=True, freespace=51459)))
        self.failUnlessEqual(descr.getDisplayName(),
                'Amazon EC2 System Launch Parameters (EBS-backed)')
        field = descr.getDataField('freeSpace')
        self.failUnlessEqual(field.getDefault(), 51)

if __name__ == "__main__":
    testsuite.main()
