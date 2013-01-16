#
# Copyright (c) 2010 rPath, Inc.  All Rights Reserved.
#

# vim: set fileencoding=utf-8 :

import os
from boto.s3 import connection as s3connection
from boto.ec2.regioninfo import RegionInfo

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

    PermittedS3Users = None

    class Cloud(ec2client.EC2_Cloud):
        pass
    class Image(ec2client.EC2_Image):
        pass
    class Instance(ec2client.EC2_Instance):
        pass

    _configNameMap = []

    class _ImageMap(ec2client.EC2Client._ImageMap):
        def __init__(self, imageList):
            ec2client.EC2Client._ImageMap.__init__(self, imageList)
            for img in imageList:
                # Hash images by target image id too
                if img._targetImageId is not None:
                    self._ids[img._targetImageId] = img

    def drvCreateCloud(self, descriptorData):
        return ec2client.baseDriver.BaseDriver.drvCreateCloud(self,
            descriptorData)

    def drvVerifyCloudConfiguration(self, config):
        certificateData = config.get('certificateData')
        certificateKeyData = config.get('certificateKeyData')
        config.update(certificateData=certificateData,
            certificateKeyData=certificateKeyData)
        config.update((k, self._strip(v)) for k, v in config.items())

        # Seed the target configuration
        self._targetConfig = config
        # Validate credentials
        cli = self.drvCreateCloudClient(config)
        # Do a call to force cred validation
        try:
            cli.get_all_regions()
        except ec2client.EC2ResponseError, e:
            raise errors.ResponseError(e.status, self._getErrorMessage(e), e.body)
        self._targetConfig = None

    @classmethod
    def _fixConfig(cls, config):
        # Fix PEM fields
        for field in ['certificateData', 'certificateKeyData', 'cloudX509Cert']:
            config[field] = ec2client.fixPEM(config[field])
        return config

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
        self.kernelMap = {}
        return (RegionInfo(name=self.cloudName, endpoint=self.cloudName),
            port, '/services/Eucalyptus', False)

    def _getS3ConnectionInfo(self, credentials):
        targetConfiguration = self.getTargetConfiguration()
        port = targetConfiguration['port']
        return (self.cloudName, port, '/services/Walrus', False,
            self.CallingFormat, None)

    getImageIdFromMintImage = ec2client.baseDriver.BaseDriver._getImageIdFromMintImage_local

    @classmethod
    def setImageNamesFromMintData(cls, image, mintImageData):
        ec2client.baseDriver.BaseDriver.setImageNamesFromMintData(image,
            mintImageData)
        targetImageId = image._targetImageId
        if targetImageId:
            image.setShortName("%s (%s)" % (image.getShortName(), targetImageId))
            image.setLongName("%s (%s)" % (image.getLongName(), targetImageId))

    def addExtraImagesFromMint(self, imageList, mintImages, cloudAlias):
        # We do want to expose mint images in the list
        return ec2client.baseDriver.BaseDriver.addExtraImagesFromMint(
            self, imageList, mintImages, cloudAlias)

    def _productCodesForImage(self, image):
        return None

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

    def drvLaunchDescriptorCommonFields(self, descr):
        descr = ec2client.baseDriver.BaseDriver.drvLaunchDescriptorCommonFields(
            self, descr)
        return descr

    def launchInstanceProcess(self, job, image, auth, **launchParams):
        if not image.getIsDeployed():
            imageId = self._deployImage(job, image, auth)
            launchParams.update(imageId=imageId)
        elif image._targetImageId is not None:
            imageId = image._targetImageId
            launchParams.update(imageId=imageId)
        instanceIds = self._launchInstances(job, image, launchParams)
        return instanceIds

    def _getFilesystemImage(self, job, image, dlpath):
        fileExtensions = [ '.ext3' ]
        self._msg(job, "Uncompressing image")
        workdir = self.extractImage(dlpath)
        # XXX make this more robust
        imageFileDir, imageFileName = self.findFile(workdir, fileExtensions)
        if imageFileDir is None:
            raise RuntimeError("No file(s) found: %s" %
                ', '.join("*%s" % x for x in fileExtensions))
        imageFilePath = os.path.join(imageFileDir, imageFileName)
        return imageFilePath
