#
# Copyright (c) 2010 rPath, Inc.  All Rights Reserved.
#

# vim: set fileencoding=utf-8 :

import os
import subprocess
import tempfile
from boto.s3 import connection as s3connection
from boto.ec2.regioninfo import RegionInfo

from conary.lib import util
from mint import ec2

from catalogService import errors
from catalogService.rest.drivers.ec2 import ec2client


_configurationDescriptorXmlData = r"""<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>Eucalyptus Configuration</displayName>
    <descriptions>
      <desc>Configure Eucalyptus</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>name</name>
      <descriptions>
        <desc>Eucalyptus Server Address</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/serverName.html'/>
    </field>
    <field>
      <name>port</name>
      <descriptions>
        <desc>Eucalyptus Server Port</desc>
      </descriptions>
      <type>int</type>
      <required>true</required>
      <default>8773</default>
      <help href='configuration/serverPort.html'/>
    </field>
    <field>
      <name>alias</name>
      <descriptions>
        <desc>Descriptive Name</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/alias.html'/>
    </field>
    <field>
      <name>description</name>
      <descriptions>
        <desc>Full Description</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/description.html'/>
    </field>
    <field>
      <name>publicAccessKeyId</name>
      <descriptions>
        <desc>Access Key ID</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Field must contain between 1 and 100 characters</desc>
        </descriptions>
        <length>100</length>
      </constraints>
      <required>true</required>
      <help href='configuration/accessKey.html'/>
    </field>
    <field>
      <name>secretAccessKey</name>
      <descriptions>
        <desc>Secret Access Key</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Field must contain between 1 and 256 characters</desc>
        </descriptions>
        <length>256</length>
      </constraints>
      <required>true</required>
      <help href='configuration/secretAccessKey.html'/>
    </field>
    <field>
      <name>certificateData</name>
      <descriptions>
        <desc>X.509 Certificate</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>The certificate must start with '-----BEGIN CERTIFICATE-----', end with '-----END CERTIFICATE-----', and have a maximum length of 16384 characters.</desc>
        </descriptions>
        <regexp>^\s*-----BEGIN CERTIFICATE-----.*-----END CERTIFICATE-----\s*$</regexp>
        <length>16384</length>
      </constraints>
      <required>true</required>
      <allowFileContent>true</allowFileContent>
      <help href='configuration/certificateData.html'/>
    </field>
    <field>
      <name>certificateKeyData</name>
      <descriptions>
        <desc>X.509 Private Key</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>The key must start with '-----BEGIN PRIVATE KEY-----', end with '----END PRIVATE KEY-----', and have a maximum length of 16384 characters.</desc>
        </descriptions>
        <regexp>^\s*-----BEGIN (\S+ )?PRIVATE KEY-----.*-----END (\S+ )?PRIVATE KEY-----\s*$</regexp>
        <length>16384</length>
      </constraints>
      <required>true</required>
      <allowFileContent>true</allowFileContent>
      <help href='configuration/certificateKeyData.html'/>
    </field>
    <field>
      <name>cloudX509Cert</name>
      <descriptions>
        <desc>Cloud X.509 Certificate</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>The certificate must start with '-----BEGIN CERTIFICATE-----', end with '-----END CERTIFICATE-----', and have a maximum length of 16384 characters.</desc>
        </descriptions>
        <regexp>^\s*-----BEGIN CERTIFICATE-----.*-----END CERTIFICATE-----\s*$</regexp>
        <length>16384</length>
      </constraints>
      <required>true</required>
      <allowFileContent>true</allowFileContent>
      <help href='configuration/cloudX509Cert.html'/>
    </field>
    <field>
      <name>s3Bucket</name>
      <descriptions>
        <desc>Storage (Walrus) Bucket</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Field must contain between 1 and 32 characters</desc>
        </descriptions>
        <length>32</length>
      </constraints>
      <required>true</required>
      <help href='configuration/s3Bucket.html'/>
    </field>
  </dataFields>
</descriptor>"""

_credentialsDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>Eucalyptus User Credentials</displayName>
    <descriptions>
      <desc>User Credentials for Eucalyptus</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>publicAccessKeyId</name>
      <descriptions>
        <desc>Access Key ID</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Field must contain between 1 and 100 characters</desc>
        </descriptions>
        <length>100</length>
      </constraints>
      <required>true</required>
    </field>
    <field>
      <name>secretAccessKey</name>
      <descriptions>
        <desc>Secret Access Key</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Field must contain between 1 and 256 characters</desc>
        </descriptions>
        <length>256</length>
      </constraints>
      <required>true</required>
    </field>
  </dataFields>
</descriptor>
"""


class EucalyptusClient(ec2client.EC2Client):
    cloudType = 'eucalyptus'
    # XXX will need their own image type
    RBUILDER_BUILD_TYPE = 'RAW_FS_IMAGE'
    ImagePrefix = 'emi-'
    CallingFormat = s3connection.OrdinaryCallingFormat()

    configurationDescriptorXmlData = _configurationDescriptorXmlData
    credentialsDescriptorXmlData = _credentialsDescriptorXmlData

    _credNameMap = [
        ('publicAccessKeyId', 'publicAccessKeyId'),
        ('secretAccessKey', 'secretAccessKey'),
     ]

    class Cloud(ec2client.EC2_Cloud):
        _constructorOverrides = {}
    class Image(ec2client.EC2_Image):
        _constructorOverrides = {}
    class Instance(ec2client.EC2_Instance):
        _constructorOverrides = {}

    def drvCreateCloud(self, descriptorData):
        return ec2client.baseDriver.BaseDriver.drvCreateCloud(self,
            descriptorData)

    def drvVerifyCloudConfiguration(self, config):
        certificateData = ec2client.fixPEM(config.get('certificateData'))
        certificateKeyData = ec2client.fixPEM(config.get('certificateKeyData'))
        config.update(certificateData=certificateData,
            certificateKeyData=certificateKeyData)
        config.update((k, self._strip(v)) for k, v in config.items())

        # Validate credentials
        cli = self.drvCreateCloudClient(config)
        # Do a call to force cred validation
        try:
            cli.get_all_regions()
        except ec2client.EC2ResponseError, e:
            raise errors.ResponseError(e.status, self._getErrorMessage(e), e.body)

    def drvGetTargetConfiguration(self, targetData, isAdmin = False):
        publicAccessKeyId = targetData.get('publicAccessKeyId')
        if not publicAccessKeyId:
            # Not configured
            return {}
        ret = dict(name = self.cloudName,
            alias = targetData.get('alias'),
            cloudAlias = targetData.get('alias'),
            fullDescription = targetData.get('description'),
            description = targetData.get('description'),
            port = targetData.get('port'),
            )
        if isAdmin:
            ret.update(
                publicAccessKeyId = publicAccessKeyId,
                secretAccessKey = targetData.get('secretAccessKey'),
                certificateData = ec2client.fixPEM(targetData.get('certificateData'), error=False),
                certificateKeyData = ec2client.fixPEM(targetData.get('certificateKeyData'), error=False),
                cloudX509Cert = targetData.get('cloudX509Cert'),
                s3Bucket = targetData.get('s3Bucket'))
        return ret

    def isValidCloudName(self, cloudName):
        return ec2client.baseDriver.BaseDriver.isValidCloudName(self,
            cloudName)

    def _getEC2ConnectionInfo(self, credentials):
        targetConfiguration = self.getTargetConfiguration()
        port = targetConfiguration['port']
        return (RegionInfo(name=self.cloudName, endpoint=self.cloudName),
            port, '/services/Eucalyptus', False)

    def _getS3ConnectionInfo(self, credentials):
        targetConfiguration = self.getTargetConfiguration()
        port = targetConfiguration['port']
        return (self.cloudName, port, '/services/Walrus', False,
            self.CallingFormat)

    def getImageIdFromMintImage(self, imageData):
        return ec2client.baseDriver.BaseDriver.getImageIdFromMintImage(imageData)

    def addExtraImagesFromMint(self, imageList, mintImages, cloudAlias):
        # We do want to expose mint images in the list
        return ec2client.baseDriver.BaseDriver.addExtraImagesFromMint(
            self, imageList, mintImages, cloudAlias)

    def _getProxyInfo(self, https = True):
        # We are going to assume there's no need to talk to an external proxy
        # to get access to eucalyptus. This may not always be true
        return None, None, None, None

    def _cliGetSecurityGroups(self, groupNames = None):
        # For now we won't create the default catalog group, the way we do it
        # in ec2
        sGroups = self._getUnfilteredSecurityGroups(groupNames = groupNames)
        return sGroups

    def drvPopulateLaunchDescriptor(self, descr):
        ec2client.EC2Client.drvPopulateLaunchDescriptor(self, descr)
        descr.setDisplayName("Eucalyptus Launch Parameters")
        descr.addDescription("Eucalyptus Launch Parameters")
        return descr

    def launchInstanceProcess(self, job, image, auth, **launchParams):
        if not image.getIsDeployed():
            imageId = self._deployImage(job, image, auth, launchParams)
            launchParams.update(imageId=imageId)
        instanceIds = self._launchInstances(job, image, launchParams)
        return instanceIds

    @classmethod
    def _tempfile(self, contents):
        f = tempfile.NamedTemporaryFile(dir="/dev/shm")
        f.write(contents)
        f.flush()
        f.seek(0)
        return f

    def _deployImage(self, job, image, auth, launchParams):
        tmpDir = tempfile.mkdtemp(prefix="euca-download-")
        tconf = self.getTargetConfiguration(forceAdmin=True)
        x509CertFile = self._tempfile(tconf['certificateData'])
        x509KeyFile = self._tempfile(tconf['certificateKeyData'])
        cloudX509CertFile = self._tempfile(tconf['cloudX509Cert'])
        # The account does not matter for euca
        accountId = '0' * 12
        bucketName = tconf['s3Bucket']

        try:
            self._msg(job, "Downloading image")
            dlpath = self._downloadImage(image, tmpDir, auth = auth)
        except errors.CatalogError, e:
            util.rmtree(tmpDir, ignore_errors=True)
            raise

        try:
            self._msg(job, "Uncompressing image")
            workdir = self.extractImage(dlpath)
            extractedDir = os.path.join(workdir, image.getBaseFileName())
            # XXX make this more robust
            imageFileName = [ x for x in os.listdir(extractedDir)
                if x.endswith('.ext3') ][0]
            imageFilePath = os.path.join(extractedDir, imageFileName)
            bundlePath = os.path.join(workdir, "bundled")
            util.mkdirChain(bundlePath)
            imagePrefix = "%s_%s" % (image.getBaseFileName(), image.getBuildId())
            architecture = "x86_64" # XXX
            self._msg(job, "Bundling image")
            self._bundleImage(imageFilePath, accountId,
                x509CertFile.name, x509KeyFile.name,
                bundlePath, imagePrefix, architecture,
                cloudX509CertFile=cloudX509CertFile.name)
            manifestName = self._uploadBundle(job, bundlePath, bucketName, tconf)
            emiId = self._registerImage(job, bucketName, manifestName, tconf)
            self._msg(job, "Registered %s" % emiId)
            return emiId
        finally:
            # clean up our mess
            util.rmtree(tmpDir, ignore_errors=True)
            util.rmtree(dlpath, ignore_errors=True)

    @classmethod
    def _bundleImage(cls, inputFSImage, accountId, x509CertFile, x509KeyFile,
            bundlePath, imagePrefix, architecture, kernelImage=None,
            ramdiskImage=None, cloudX509CertFile=None):
        cmd = [ '/usr/bin/ec2-bundle-image',
            '-i', inputFSImage,
            '-u', accountId,
            '-c', x509CertFile,
            '-k', x509KeyFile,
            '-d', bundlePath,
            '-p', imagePrefix,
            '-r', architecture,
        ]
        if kernelImage:
            cmd.extend(['--kernel', kernelImage,])
        if ramdiskImage:
            cmd.extend(['--ramdisk', ramdiskImage])
        if cloudX509CertFile:
            cmd.extend(['--ec2cert', cloudX509CertFile])
        p = subprocess.Popen(cmd)
        p.wait()

    @classmethod
    def _bundleItem(cls, bundlePath, fileName):
        fpath = os.path.join(bundlePath, fileName)
        fobj = file(fpath)
        fobj.seek(0, 2)
        fsize = fobj.tell()
        fobj.seek(0, 0)
        return fileName, fsize, fobj

    def _uploadBundle(self, job, bundlePath, bucketName, targetConfiguration):
        self._msg(job, "Uploading bundle")
        bundleItemGen = [ self._bundleItem(bundlePath, x)
            for x in os.listdir(bundlePath) ]
        fileCount = len(bundleItemGen)
        totalSize = sum(x[1] for x in bundleItemGen)

        cb = self.UploadCallback(job, self._msg).callback
        s3conn = self._getS3Connection(targetConfiguration)
        policy = None
        bucket = ec2.S3Wrapper.createBucketBackend(s3conn, bucketName,
            policy=policy)
        ec2.S3Wrapper.uploadBundleBackend(bundleItemGen, fileCount, totalSize,
            bucket, callback=cb, policy=policy)
        manifests = [ os.path.basename(x[0]) for x in bundleItemGen
                            if x[0].endswith('.manifest.xml') ]

        return manifests[0]

    def _registerImage(self, job, bucketName, manifestName, targetConfiguration):
        self._msg(job, "Registering image")
        ec2conn = self._getEC2Connection(targetConfiguration)
        loc = "%s/%s" % (bucketName, os.path.basename(manifestName))
        return ec2conn.register_image(image_location=loc)

    class UploadCallback(object):
        def __init__(self, job, msg):
            self.job = job
            self.msg = msg

        def callback(self, fileName, fileIdx, fileTotal,
                currentFileBytes, totalFileBytes, sizeCurrent, sizeTotal):
            # Nice percentages
            if sizeTotal == 0:
                sizeTotal = 1024
            pct = sizeCurrent * 100.0 / sizeTotal
            message = "Uploading bundle: %d%%" % (pct, )

            self.msg(self.job, message)
