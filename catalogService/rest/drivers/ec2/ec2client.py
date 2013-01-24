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


import base64
import gzip
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib2
from boto import ec2 as bec2
from boto.ec2 import EC2Connection
from boto.s3.connection import S3Connection, Location
from boto.exception import EC2ResponseError, S3CreateError, S3ResponseError
from conary.lib import util

from mint import ec2, helperfuncs

from catalogService import errors
from catalogService.rest import baseDriver
from catalogService.rest.models import clouds
from catalogService.rest.models import images
from catalogService.rest.models import instances
from catalogService.rest.models import securityGroups

CATALOG_DYN_SECURITY_GROUP = 'dynamic'
CATALOG_DYN_SECURITY_GROUP_DESC = 'Generated Security Group'
CATALOG_DEF_SECURITY_GROUP = 'catalog-default'
CATALOG_DEF_SECURITY_GROUP_DESC = 'Default EC2 Catalog Security Group'
CATALOG_DEF_SECURITY_GROUP_PERMS = (
        # proto  start_port  end_port
        ('tcp',  22,         22),
        ('tcp',  80,         80),
        ('tcp',  443,        443),
        ('tcp',  8003 ,      8003),
)
CATALOG_DEF_SECURITY_GROUP_WBEM_PORTS = (
        ('tcp',  5989,       5989),
)

EC2_DEVPAY_OFFERING_BASE_URL = "https://aws-portal.amazon.com/gp/aws/user/subscription/index.html?productCode=%s"

class EC2_IPRange(instances.xmlNode.BaseMultiNode):
    tag = 'ipRange'

class EC2_Permissions(instances.xmlNode.BaseMultiNode):
    tag = 'permission'
    __slots__ = ['ipRange', 'ipProtocol', 'fromPort', 'toPort']
    _slotTypeMap = instances.xmlNode.BaseMultiNode._slotTypeMap.copy()
    _slotTypeMap['ipRange'] = EC2_IPRange

class EC2_SecurityGroup(securityGroups.BaseSecurityGroup):
    multiple = True
    _slotTypeMap = securityGroups.BaseSecurityGroup._slotTypeMap.copy()
    _slotTypeMap['permission'] = EC2_Permissions

class EC2_Image(images.BaseImage):
    "EC2 Image"

class EC2_Instance(instances.BaseInstance):
    "EC2 Instance"

    __slots__ = instances.BaseInstance.__slots__ + [
                'keyName', 'securityGroup', ]

    _slotTypeMap = instances.BaseInstance._slotTypeMap.copy()
    _slotTypeMap['securityGroup'] = EC2_SecurityGroup

class EC2_Cloud(clouds.BaseCloud):
    "EC2 Cloud"

class EC2_InstanceTypes(instances.InstanceTypes):
    "EC2 Instance Types"

    idMap = [
        ('m1.small', "Small"),
        ('m1.large', "Large"),
        ('m1.xlarge', "Extra Large"),
        ('c1.medium', "High-CPU Medium"),
        ('c1.xlarge', "High-CPU Extra Large"),
    ]

class XRegionInfo(bec2.regioninfo.RegionInfo):
    def __init__(self, name=None, endpoint=None, s3Endpoint=None,
            s3Location=None, description=None, kernelMap=None):
        super(XRegionInfo, self).__init__(name=name, endpoint=endpoint)
        self.s3Endpoint = s3Endpoint
        self.s3Location = s3Location
        self.description = description
        self.kernelMap = kernelMap

class Regions(object):
    """
    A cache of the region info, with a more descriptive text.
    Can be regenerated with data from boto's get_all_regions()
    """
    _regions = [
        XRegionInfo(name="us-east-1", endpoint="ec2.us-east-1.amazonaws.com",
            s3Endpoint="s3.amazonaws.com", s3Location=Location.DEFAULT,
            description="US East 1 (Northern Virginia) Region",
            kernelMap={'x86_64': 'aki-88aa75e1', 'i386': 'aki-b6aa75df'}),
        XRegionInfo(name="us-west-1", endpoint="ec2.us-west-1.amazonaws.com",
            s3Endpoint="s3-us-west-1.amazonaws.com", s3Location='us-west-1',
            description="US West 1 (Northern California)",
            kernelMap={'x86_64': 'aki-f77e26b2', 'i386': 'aki-f57e26b0'}),
        XRegionInfo(name="us-west-2", endpoint="ec2.us-west-2.amazonaws.com",
            s3Endpoint="s3-us-west-2.amazonaws.com", s3Location='us-west-2',
            description="US West 2 (Oregon)",
            kernelMap={'x86_64': 'aki-fc37bacc', 'i386': 'aki-fa37baca'}),
        XRegionInfo(name="eu-west-1", endpoint="ec2.eu-west-1.amazonaws.com",
            s3Endpoint="s3-eu-west-1.amazonaws.com", s3Location='EU',
            description="EU (Ireland)",
            kernelMap={'x86_64': 'aki-71665e05', 'i386': 'aki-75665e01'}),
        XRegionInfo(name="sa-east-1", endpoint="ec2.sa-east-1.amazonaws.com",
            s3Endpoint="s3-sa-east-1.amazonaws.com", s3Location='sa-east-1',
            description="South America (Sao Paulo)",
            kernelMap={'x86_64': 'aki-c48f51d9', 'i386': 'aki-ca8f51d7'}),
        XRegionInfo(name="ap-northeast-1", endpoint="ec2.ap-northeast-1.amazonaws.com",
            s3Endpoint="s3-ap-northeast-1.amazonaws.com",
            s3Location='ap-northeast-1',
            description="Asia Pacific NorthEast (Tokyo)",
            kernelMap={'x86_64': 'aki-44992845', 'i386': 'aki-42992843'}),
        XRegionInfo(name="ap-southeast-1", endpoint="ec2.ap-southeast-1.amazonaws.com",
            s3Endpoint="s3-ap-southeast-1.amazonaws.com",
            s3Location='ap-southeast-1',
            description="Asia Pacific 1 (Singapore)",
            kernelMap={'x86_64': 'aki-fe1354ac', 'i386': 'aki-f81354aa'}),
        XRegionInfo(name="ap-southeast-2", endpoint="ec2.ap-southeast-2.amazonaws.com",
            s3Endpoint="s3-ap-southeast-2.amazonaws.com",
            s3Location='ap-southeast-2',
            description="Asia Pacific 2 (Sydney)",
            kernelMap={'x86_64': 'aki-31990e0b', 'i386': 'aki-33990e09'}),
    ]

    @classmethod
    def get(cls, name):
        if name is None:
            return None
        for region in cls._regions:
            if region.name == name:
                return region
        raise KeyError(name)

    @classmethod
    def asEnumeratedType(cls):
        tmpl = "<enumeratedType>%s</enumeratedType>"
        tmpl2 = "<describedValue><descriptions><desc>%s</desc></descriptions><key>%s</key></describedValue>"
        return tmpl % ''.join(
            tmpl2 % (regInfo.description, regInfo.name)
                for regInfo in cls._regions)

_configurationDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>EC2 Cloud Configuration</displayName>
    <descriptions>
      <desc>Configure Amazon EC2</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>name</name>
      <descriptions>
        <desc>Name</desc>
      </descriptions>
      <type>str</type>
      <default>aws</default>
    </field>
    <field>
      <name>alias</name>
      <descriptions>
        <desc>Alias</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
    </field>
    <field>
      <name>description</name>
      <descriptions>
        <desc>Description</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
    </field>
    <field>
      <name>region</name>
      <descriptions>
        <desc>Region</desc>
      </descriptions>
      <type>enumeratedType</type>
%s
      <default>us-east-1</default>
      <required>true</required>
    </field>
    <field>
      <name>accountId</name>
      <descriptions>
        <desc>AWS Account Number</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Field must contain between 1 and 12 characters and cannot contain hyphens</desc>
        </descriptions>
        <regexp>^[^-]+$</regexp>
        <length>12</length>
      </constraints>
      <required>true</required>
      <help href='configuration/accountNumber.html'/>
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
      <name>s3Bucket</name>
      <descriptions>
        <desc>S3 Bucket</desc>
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
</descriptor>""" % Regions.asEnumeratedType()

_credentialsDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>EC2 User Credentials</displayName>
    <descriptions>
      <desc>User Credentials for Amazon EC2</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>accountId</name>
      <descriptions>
        <desc>Amazon Account Number</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Field must contain between 1 and 14 characters</desc>
        </descriptions>
        <length>14</length>
      </constraints>
      <required>true</required>
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

class EC2Client(baseDriver.BaseDriver):
    cloudType = 'ec2'

    Cloud = EC2_Cloud
    Image = EC2_Image
    Instance = EC2_Instance
    SecurityGroup = EC2_SecurityGroup

    _instanceBotoMap = dict(
                dnsName = 'dns_name',
                imageId = 'image_id',
                instanceType = 'instance_type',
                kernel = 'kernel',
                keyName = 'key_name',
                launchTime = 'launch_time',
                placement = 'placement',
                previousState = 'previous_state',
                productCodes = 'product_codes',
                privateDnsName = 'private_dns_name',
                publicDnsName = 'public_dns_name',
                ramdisk = 'ramdisk',
                shutdownState = 'shutdown_state',
                stateCode = 'state_code',
                state = 'state',
    )

    _configNameMap = [
        ('accountId', 'ec2AccountId'),
        ('certificateData', 'ec2Certificate'),
        ('certificateKeyData', 'ec2CertificateKey'),
        ('publicAccessKeyId', 'ec2PublicKey'),
        ('s3Bucket', 'ec2S3Bucket'),
        ('secretAccessKey', 'ec2PrivateKey'),
    ]

    configurationDescriptorXmlData = _configurationDescriptorXmlData
    credentialsDescriptorXmlData = _credentialsDescriptorXmlData

    dynamicSecurityGroupPattern = re.compile(baseDriver.BaseDriver._uuid('.' * 32))

    RBUILDER_BUILD_TYPE = 'AMI'

    PermittedS3Users = [ ec2.S3Wrapper.amazonEC2UserId ]

    class SecurityGroupHandler(securityGroups.Handler):
        securityGroupClass = EC2_SecurityGroup

    ImagePrefix = 'ami-'

    TIMEOUT_BLOCKDEV = 1
    TIMEOUT_SNAPSHOT = 2
    TIMEOUT_VOLUME = 3

    def _getProxyInfo(self, https = True):
        proto = (https and "https") or "http"
        proxyUrl = self.db.cfg.proxy.get(proto)
        if not proxyUrl:
            return None, None, None, None
        splitUrl = helperfuncs.urlSplit(proxyUrl)
        proxyUser, proxyPass, proxy, proxyPort = splitUrl[1:5]
        return proxyUser, proxyPass, proxy, proxyPort

    def _openUrl(self, url):
        proxyUser, proxyPass, proxy, proxyPort = self._getProxyInfo(https = False)
        opener = urllib2.OpenerDirector()
        if proxy:
            proxy = helperfuncs.urlUnsplit(("http", proxyUser, proxyPass,
                proxy, proxyPort, '', '', ''))
            opener.add_handler(urllib2.ProxyHandler(dict(http = proxy)))
        opener.add_handler(urllib2.HTTPHandler())
        ret = opener.open(url)
        return ret

    def _getExternalIp(self):
        # RCE-1310
        url = "http://automation.whatismyip.com/n09230945.asp"
        resp = self._openUrl(url)
        data = resp.read().strip()
        if len(data) > 16:
            return None
        return data

    def drvCreateCloudClient(self, credentials):
        for key in ('publicAccessKeyId', 'secretAccessKey'):
            if key not in credentials or not credentials[key]:
                raise errors.MissingCredentials()
        return self._getEC2Connection(credentials)

    def _getEC2Connection(self, credentials):
        publicAccessKeyId = credentials['publicAccessKeyId']
        secretAccessKey = credentials['secretAccessKey']
        proxyUser, proxyPass, proxy, proxyPort = self._getProxyInfo()
        region, port, path, isSecure = self._getEC2ConnectionInfo(
            credentials)
        kw = dict(
                             proxy_user = proxyUser,
                             proxy_pass = proxyPass,
                             proxy = proxy,
                             proxy_port = proxyPort,
                             region = region,
                             port = port,
                             path = path,
                             is_secure = isSecure,
        )
        kwargs = self._updateDict({}, kw)
        return EC2Connection(self._strip(publicAccessKeyId),
                             self._strip(secretAccessKey),
                             **kwargs)

    def _getEC2ConnectionInfo(self, credentials):
        cloudConfig = self.getTargetConfiguration()
        regionName = cloudConfig.get('region')
        region = Regions.get(regionName)
        if region is not None:
            self.kernelMap = region.kernelMap
        else:
            self.kernelMap = {}
        return region, None, None, True

    def _getS3ConnectionInfo(self, credentials):
        cloudConfig = self.getTargetConfiguration()
        regionName = cloudConfig.get('region')
        region = Regions.get(regionName)
        if region is None:
            s3Endpoint, s3Location = S3Connection.DefaultHost, Location.DEFAULT
        else:
            s3Endpoint, s3Location = region.s3Endpoint, region.s3Location
        return s3Endpoint, None, None, True, None, s3Location

    def _getS3Connection(self, credentials):
        publicAccessKeyId = credentials['publicAccessKeyId']
        secretAccessKey = credentials['secretAccessKey']
        proxyUser, proxyPass, proxy, proxyPort = self._getProxyInfo(https=True)
        botoHost, botoPort, path, isSecure, callingFormat, location = self._getS3ConnectionInfo(credentials)
        kw = dict(
                            proxy_user = proxyUser,
                            proxy_pass = proxyPass,
                            proxy = proxy,
                            proxy_port = proxyPort,
                            host = botoHost,
                            port = botoPort,
                            is_secure = isSecure,
                            path = path,
                            calling_format = callingFormat,
        )
        kwargs = self._updateDict({}, kw)
        return S3Connection(self._strip(publicAccessKeyId),
                            self._strip(secretAccessKey),
                            **kwargs), location

    @classmethod
    def _updateDict(cls, dst, src):
        """
        Update dictionary dst with items from src for which the value is not
        None
        """
        dst.update((x, y) for (x, y) in src.iteritems() if y is not None)
        return dst

    def _createRandomKey(self):
        return base64.b64encode(file("/dev/urandom").read(8))

    def _validateS3Bucket(self, publicAccessKeyId, secretAccessKey, bucket):
        conn, location = self._getS3Connection(credentials=dict(
            publicAccessKeyId=publicAccessKeyId,
            secretAccessKey=secretAccessKey))
        # boto 2.0 enforces that bucket names don't have upper case
        bucket = bucket.lower()

        try:
            conn.create_bucket(bucket, location=location)
        except S3CreateError, e:
            # Bucket already exists
            pass
        except S3ResponseError, e:
            # Bad auth data
            raise errors.ResponseError(e.status, self._getErrorMessage(e), e.body)
        else:
            return True

        # Can we still write to it?
        try:
            bucket = conn.get_bucket(bucket)
        except S3ResponseError:
            raise errors.ResponseError(e.status, self._getErrorMessage(e), e.body)

        keyName = self._createRandomKey()
        key = bucket.new_key(keyName)
        try:
            key.set_contents_from_string("")
        except S3ResponseError:
            raise errors.ResponseError(e.status, self._getErrorMessage(e), e.body)
        else:
            # Clean up
            bucket.delete_key(keyName)
        return True

    def drvValidateCredentials(self, creds):
        cli = self.drvCreateCloudClient(creds)
        # Do a call to force cred validation
        try:
            cli.get_all_regions()
        except EC2ResponseError, e:
            return False
        return True

    @classmethod
    def getTargetConfigFromDescriptorData(cls, descriptorData):
        config = super(EC2Client, cls).getTargetConfigFromDescriptorData(descriptorData)
        # Strip whitespaces that could cause problems
        config = dict((x, cls._strip(y)) for (x, y) in config.items())

        config = cls._fixConfig(config)
        return config

    @classmethod
    def _fixConfig(cls, config):
        # Fix PEM fields
        for field in ['ec2Certificate', 'ec2CertificateKey']:
            config[field] = fixPEM(config[field])
        return config

    def drvVerifyCloudConfiguration(self, dataDict):
        ec2PublicKey = dataDict['ec2PublicKey']
        ec2PrivateKey = dataDict['ec2PrivateKey']
        ec2S3Bucket = dataDict['ec2S3Bucket']
        self._validateS3Bucket(ec2PublicKey, ec2PrivateKey, ec2S3Bucket)
        # Validate credentials
        cli = self.drvCreateCloudClient(dict(publicAccessKeyId=ec2PublicKey,
            secretAccessKey=ec2PrivateKey))
        # Do a call to force cred validation
        try:
            cli.get_all_regions()
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, self._getErrorMessage(e), e.body)

    @classmethod
    def _getErrorCode(cls, err):
        fname = hasattr(err, 'error_code') and 'error_code' or 'code'
        return getattr(err, fname)

    @classmethod
    def _getErrorMessage(cls, err):
        fname = hasattr(err, 'error_message') and 'error_message' or 'message'
        return getattr(err, fname)

    def drvGetCredentialsFromDescriptor(self, fields):
        accountId = str(fields.getField('accountId'))
        publicAccessKeyId = str(fields.getField('publicAccessKeyId'))
        secretAccessKey = str(fields.getField('secretAccessKey'))
        return dict(accountId = accountId,
            publicAccessKeyId = publicAccessKeyId,
            secretAccessKey = secretAccessKey)

    def createUserData(self, userData):
        templ = """\
[sfcb-client-setup]
x509-cert-hash=%s
x509-cert(base64)=%s
boot-uuid=%s
"""
        certPath = self.getWbemClientCert()
        try:
            certData = file(certPath).read()
        except IOError:
            return userData

        certHash = self.computeX509CertHash(certPath)
        certData = base64.b64encode(certData)
        bootUuid = self.getBootUuid()

        sect = templ % (certHash, certData, bootUuid)
        if not userData:
            return sect
        return userData + '\n' + sect

    def getLaunchInstanceParameters(self, image, descriptorData):
        params = baseDriver.BaseDriver.getLaunchInstanceParameters(self, image,
            descriptorData)
        getField = descriptorData.getField
        params['remoteIp'] = getField('remoteIp')
        params['securityGroups'] = getField('securityGroups')
        params['minCount'] = getField('minCount')
        params['maxCount'] = getField('maxCount')
        params['keyName'] = getField('keyName')
        params['userData'] = getField('userData')
        params['instanceType'] = getField('instanceType')
        params['availabilityZone'] = getField('availabilityZone')

        return params

    def deployImageProcess(self, job, image, auth, **params):
        if image.getIsDeployed():
            self._msg(job, "Image is already deployed")
            return image.getImageId()
        self._deployImage(job, image, auth, extraParams=params)
        return image.getImageId()


    def launchInstanceProcess(self, job, image, auth, **launchParams):
        if not image.getIsDeployed():
            imageId = self._deployImage(job, image, auth, extraParams=launchParams)
            launchParams.update(imageId=imageId)
        elif image._targetImageId is not None:
            imageId = image._targetImageId
            launchParams.update(imageId=imageId)

        remoteIp = launchParams.pop('remoteIp')
        # If the UI did not send us an IP, don't try to guess, it's going to
        # be wrong anyway.
        securityGroups = launchParams.pop('securityGroups')
        if CATALOG_DEF_SECURITY_GROUP in securityGroups:
            # Create/update the default security group that opens TCP
            # ports 80, 443, and 8003 for traffic from the requesting IP address
            self._updateCatalogDefaultSecurityGroup(remoteIp)
        if CATALOG_DYN_SECURITY_GROUP in securityGroups:
            dynSecurityGroup = self._updateCatalogDefaultSecurityGroup(remoteIp, dynamic = True)
            # Replace placeholder dynamic security group with generated security group
            securityGroups.remove(CATALOG_DYN_SECURITY_GROUP)
            securityGroups.append(dynSecurityGroup)
        launchParams.update(securityGroups=securityGroups)

        return self._launchInstances(job, image, launchParams)

    def _launchInstances(self, job, image, launchParams):
        imageId = launchParams.pop('imageId')
        self._msg(job, "Launching instance %s" % imageId)
        try:
            reservation = self.client.run_instances(imageId,
                    min_count=launchParams.get('minCount'),
                    max_count=launchParams.get('maxCount'),
                    key_name=launchParams.get('keyName'),
                    security_groups=launchParams.get('securityGroups'),
                    user_data=self.createUserData(launchParams.get('userData')),
                    instance_type=launchParams.get('instanceType'),
                    placement=launchParams.get('availabilityZone'))
        except EC2ResponseError, e:
            # is this a product code error?
            errorMsg = self._getErrorMessage(e)
            pcData = self._processProductCodeError(errorMsg)
            raise errors.ResponseError, (e.status, errorMsg, e.body, pcData), sys.exc_info()[2]

        return [ x.id for x in reservation.instances ]

    def terminateInstances(self, instanceIds):
        resultSet = self.client.terminate_instances(instance_ids=instanceIds)
        return self._getInstancesFromResult(resultSet)

    def terminateInstance(self, instanceId):
        return self.terminateInstances([instanceId])[0]

    def drvGetInstances(self, instanceIds, force=False):
        try:
            resultSet = self.client.get_all_instances(instance_ids = instanceIds)
        except EC2ResponseError, e:
            if self._getErrorCode(e) in ['InvalidInstanceID.NotFound',
                                         'InvalidInstanceID.Malformed']:
                raise errors.HttpNotFound()
            raise errors.ResponseError(e.status, self._getErrorMessage(e), e.body)

        insts = instances.BaseInstances()
        for reservation in resultSet:
            insts.extend(self._getInstancesFromReservation(reservation))
        return insts

    def getImagesFromTarget(self, imageIds):
        targetConfiguration = self.getTargetConfiguration()
        ownerId = targetConfiguration.get('accountId')
        if ownerId:
            ownerIds = [ ownerId ]
        else:
            ownerIds = None
        rs = self.client.get_all_images(image_ids = imageIds, owners = ownerIds)
        # avoid returning amazon kernel images.
        rs = [ x for x in rs if x.id.startswith(self.ImagePrefix) ]

        cloudAlias = targetConfiguration.get('cloudAlias')
        imageList = images.BaseImages()
        for image in rs:
            productCodes = self._productCodesForImage(image)
            if image.location:
                iloc = image.location.replace(".manifest.xml", "")
                longName = "%s (%s)" % (iloc, image.id)
            else:
                longName = None
            i = self._nodeFactory.newImage(id=image.id, imageId=image.id,
                                           ownerId=image.ownerId,
                                           longName=longName,
                                           state=image.state,
                                           isPublic=image.is_public,
                                           productCode=productCodes,
                                           cloudAlias=cloudAlias,
                                           cloudName=self.cloudName,
                                           cloudType=self.cloudType,
                                           isDeployed = True,
                                           is_rBuilderImage = False,
                                           )
            imageList.append(i)
        return imageList

    def _productCodesForImage(self, image):
        return [ (x, EC2_DEVPAY_OFFERING_BASE_URL % x)
            for x in image.product_codes ]

    def drvLaunchDescriptorCommonFields(self, descr):
        pass

    def drvPopulateLaunchDescriptor(self, descr, extraArgs=None):
        imageData = self._getImageData(extraArgs)
        title = "Amazon EC2 System Launch Parameters"
        if imageData.ebsBacked:
            title += " (EBS-backed)"
        freeSpace = imageData.freespace or 256

        descr.setDisplayName(title)
        descr.addDescription(title)
        self.drvLaunchDescriptorCommonFields(descr)
        descr.addDataField("instanceType",
            descriptions = [
                ("Instance Type", None),
                ("Type de l'instance", "fr_FR")],
            help = [
                ("launch/instanceTypes.html", None)
            ],
            required = True,
            type = descr.EnumeratedType(
                descr.ValueWithDescription(x,
                    descriptions = y)
                  for (x, y) in EC2_InstanceTypes.idMap),
            default = EC2_InstanceTypes.idMap[0][0],
            )
        if imageData.ebsBacked:
            descr.addDataField("freeSpace",
                descriptions = [ ("Free Space (Megabytes)", None) ],
                required = True,
                type = "int",
                default = freeSpace,
                )
        descr.addDataField("availabilityZone",
            descriptions = [
                ("Availability Zone", None),
                (u"Zone de disponibilit\u00e9", "fr_FR")],
            help = [
                ("launch/availabilityZones.html", None)],
            type = descr.EnumeratedType(
                descr.ValueWithDescription(x[0], descriptions = x[0])
                for x in self._cliGetAvailabilityZones()
            ))

        descr.addDataField("minCount",
            descriptions = [
                ("Minimum Number of Instances", None),
                ("Nombre minimal d'instances", "fr_FR")],
            help = [
                ("launch/minInstances.html", None)
            ],
            type = "int", required = True, default = 1,
            constraints = dict(constraintName = 'range',
                               min = 1, max = 100))
        descr.addDataField("maxCount",
            descriptions = [
                ("Maximum Number of Instances", None),
                ("Nombre maximal d'instances", "fr_FR")],
            help = [
                ("launch/maxInstances.html", None)
            ],
            type = "int", required = True, default = 1,
            constraints = dict(constraintName = 'range',
                               min = 1, max = 100))
        descr.addDataField("keyName",
            descriptions = [ ("SSH Key Pair", None), ("Paire de clefs", "fr_FR") ],
            help = [
                ("launch/keyPair.html", None)
            ],
            type = descr.EnumeratedType(
                descr.ValueWithDescription(x[0], descriptions = x[0])
                for x in self._cliGetKeyPairs()
            ))
        sgList = self._cliGetSecurityGroups()
        descr.addDataField("securityGroups",
            descriptions = [("Security Groups", None),
                (u"Groupes de sécurité", "fr_FR")],
            help = [
                ("launch/securityGroups.html", None)
            ],
            required = True, multiple = True,
            type = descr.EnumeratedType(
                descr.ValueWithDescription(x[0], descriptions = x[1])
                for x in sgList),
            default = sgList[0][0],
            )
        descr.addDataField("remoteIp",
            descriptions = "Remote IP address allowed to connect (if security group is catalog-default)",
            type = "str", hidden = True,
            constraints = dict(constraintName = 'length', value = 128))
        descr.addDataField("userData",
            descriptions = [("User Data", None),
                ("Data utilisateur", "fr_FR")],
            help = [
                ("launch/userData.html", None)
            ],
            type = "str",
            constraints = dict(constraintName = 'length', value = 256))
        return descr

    def drvPopulateImageDeploymentDescriptor(self, descr, extraArgs=None):
        imageData = self._getImageData(extraArgs)
        title = "Amazon EC2 Image Deployment Parameters"
        if imageData.ebsBacked:
            title += ' (EBS-backed)'
        descr.setDisplayName(title)
        descr.addDescription(title)
        self.drvImageDeploymentDescriptorCommonFields(descr)
        return descr

    class ImageData(object):
        __slots__ = [ 'ebsBacked', 'freespace', 'amiHugeDiskMountpoint', ]
        def __init__(self, **kwargs):
            for slot in self.__slots__:
                setattr(self, slot, kwargs.get(slot))

    def _getImageData(self, extraArgs):
        if extraArgs is None:
            imageDataDict = {}
        else:
            imageDataDict = extraArgs.get('imageData', {})
        return self.ImageData(**imageDataDict)

    def _updateCatalogDefaultSecurityGroup(self, remoteIPAddress, dynamic = False):
        # add the security group if it's not present already
        if dynamic:
            securityGroup = self.uuidgen()
            securityGroupDesc = CATALOG_DYN_SECURITY_GROUP_DESC
        else:
            securityGroup = CATALOG_DEF_SECURITY_GROUP
            securityGroupDesc = CATALOG_DEF_SECURITY_GROUP_DESC

        try:
            self.client.create_security_group(securityGroup,
                    securityGroupDesc)
        except EC2ResponseError, e:
            if e.status == 400 and self._getErrorCode(e) == 'InvalidGroup.Duplicate':
                pass # ignore this error
            else:
                raise errors.ResponseError(e.status, e.message, e.body)

        self._updateCatalogSecurityGroup(remoteIPAddress, securityGroup)

        return securityGroup

    def _updateCatalogSecurityGroup(self, remoteIPAddress, securityGroup):

        serviceIp = self._getExternalIp()
        if not remoteIPAddress and not serviceIp:
            return

        allowed = []
        # open ingress for ports 80, 443, and 8003 on TCP
        # for the IP address
        if remoteIPAddress:
            allowed.extend(dict(from_port=from_port, to_port=to_port,
                                ip_protocol=proto,
                                cidr_ip='%s/32' % remoteIPAddress)
                for proto, from_port, to_port in CATALOG_DEF_SECURITY_GROUP_PERMS)
        if serviceIp:
            allowed.extend(dict(from_port=from_port, to_port=to_port,
                                ip_protocol=proto, cidr_ip='%s/32' % serviceIp)
                for proto, from_port, to_port in CATALOG_DEF_SECURITY_GROUP_WBEM_PORTS)
        for pdict in allowed:
            try:
                self.client.authorize_security_group(securityGroup,
                        **pdict)
            except EC2ResponseError, e:
                if e.status == 400 and self._getErrorCode(e) == 'InvalidPermission.Duplicate':
                    pass # ignore this error
                else:
                    raise errors.ResponseError(e.status, e.message, e.body)
        return securityGroup

    def _getInstancesFromResult(self, resultSet):
        instanceList = instances.BaseInstances()
        instanceList.extend(self._getInstances(resultSet))
        return instanceList

    def _getInstancesFromReservation(self, reservation):
        insts = instances.BaseInstances()
        insts.extend(self._getInstances(reservation.instances, reservation))
        sGroups = []
        for grp in reservation.groups:
            sGroups.append(self.SecurityGroup(id = grp.id,
                groupName = grp.id))
        for inst in insts:
            inst.setSecurityGroup(sGroups)
        return insts

    def _getInstances(self, instancesIterable, reservation=None):
        # Grab images first
        imageIds = set(x.image_id for x in instancesIterable
            if x.image_id is not None)
        imageIdToImageMap = self._ImageMap(
            self.drvGetImages(list(imageIds)))

        properties = dict(cloudAlias = self.getCloudAlias())
        if reservation:
            properties.update(ownerId=reservation.owner_id,
                              reservationId=reservation.id)
        ret = []
        for instance in instancesIterable:
            # Technically it is possible for someone to launch an instance,
            # turn it off and remove the image; amazon will keep that around
            # for a while, which means we may not have the image available.
            imageNode = imageIdToImageMap.get(instance.image_id)
            ret.append(self._getSingleInstance(instance, imageNode,
                       properties.copy()))
        return ret

    def _getSingleInstance(self, instance, imageNode, properties):
        launchIndex = getattr(instance, 'ami_launch_index', None)
        if launchIndex is not None:
            properties['launchIndex'] = int(launchIndex)
        for attr, botoAttr in self._instanceBotoMap.items():
            properties[attr] = getattr(instance, botoAttr, None)
        # come up with a sane name

        instanceName = self.getInstanceNameFromImage(imageNode)
        instanceDescription = self.getInstanceDescriptionFromImage(imageNode) \
            or instanceName

        properties['instanceName'] = instanceName
        properties['instanceDescription'] = instanceDescription
        if properties['launchTime']:
            properties['launchTime'] = self.utctime(properties['launchTime'])

        productCodes = self._productCodesForImage(instance)
        properties['productCode'] = productCodes

        i = self._nodeFactory.newInstance(id=instance.id,
                                          instanceId=instance.id,
                                          **properties)
        return i

    def _cliGetKeyPairs(self, keynames = None):
        try:
            rs = self.client.get_all_key_pairs(keynames = keynames)
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, self._getErrorMessage(e), e.body)
        return [ (x.name, x.fingerprint) for x in rs ]

    def _cliGetAvailabilityZones(self):
        try:
            rs = self.client.get_all_zones()
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, self._getErrorMessage(e), e.body)
        return [ (x.name, getattr(x, 'regionName', x.name)) for x in rs ]

    def _getUnfilteredSecurityGroups(self, groupNames = None):
        ret = []
        try:
            rs = self.client.get_all_security_groups(groupnames = groupNames)
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, self._getErrorMessage(e),
                e.body)

        for sg in rs:
            rules = [(x.grants, x.ip_protocol, x.from_port, x.to_port) for x in sg.rules]
            entry =(sg.name, sg.description, sg.owner_id, rules)
            ret.append(entry)
        return ret

    def _cliGetSecurityGroups(self, groupNames = None):
        sGroups = self._getUnfilteredSecurityGroups(groupNames = groupNames)
        dynSecurityGroup = (CATALOG_DYN_SECURITY_GROUP,
                            CATALOG_DYN_SECURITY_GROUP_DESC,
                            None,
                            [])
        ret = [ dynSecurityGroup ]
        defSecurityGroup = None
        for entry in sGroups:
            sgName = entry[0]
            if sgName == CATALOG_DEF_SECURITY_GROUP:
                # We will add this group as the first one
                defSecurityGroup = entry
                continue
            # Filter out any security groups that match the UUID pattern
            if self.dynamicSecurityGroupPattern.match(sgName):
                continue
            ret.append(entry)
        if defSecurityGroup is None:
            defSecurityGroup = (CATALOG_DEF_SECURITY_GROUP,
                                CATALOG_DEF_SECURITY_GROUP_DESC,
                                None,
                                [([], x[0], x[1], x[2]) for x in
                                    CATALOG_DEF_SECURITY_GROUP_PERMS])
        ret.insert(0, defSecurityGroup)
        return ret

    def _processProductCodeError(self, message):
        if "subscription to productcode" in message.lower():
            return self._getProductCodeData(message)
        return None

    def _getProductCodeData(self, message):
        """
        Get the proper product code entry based on the message
        @return: a dict in the form of {'code': <code>, 'url': <url'}
        """
        # get the product code from the message
        parts = message.strip().split(' ')
        if parts and len(parts) >= 3:
            code = parts[3]
            return self._getProductCodeMap(code)
        return None

    def _getProductCodeMap(self, productCode):
        return dict(code = productCode,
                    url = EC2_DEVPAY_OFFERING_BASE_URL % productCode)

    def getSecurityGroups(self, instanceId):
        instance = self.getInstance(instanceId)
        groupNames = [ x.getGroupName() for x in instance.getSecurityGroup() ]
        if not groupNames:
            raise errors.ResponseError(404)
        sGroups = self._getUnfilteredSecurityGroups(
            groupNames = groupNames)
        ret = securityGroups.BaseSecurityGroups()
        for sg in sGroups:
            ret.append(self._createSecurityGroupNode(instanceId, sg))
        return ret

    def getSecurityGroup(self, instanceId, securityGroup):
        instance = self.getInstance(instanceId)
        groupNames = [ x.getGroupName() for x in instance.getSecurityGroup() ]
        if not groupNames or securityGroup not in groupNames:
            raise errors.ResponseError(404)
        # XXX can the security group disappear?
        sGroup = self._getUnfilteredSecurityGroups(
            groupNames = [ securityGroup ] )[0]
        return self._createSecurityGroupNode(instanceId, sGroup)

    def updateSecurityGroup(self, instanceId, securityGroup, xmlContent):
        instance = self.getInstance(instanceId)
        groupNames = [ x.getGroupName() for x in instance.getSecurityGroup() ]
        if not groupNames or securityGroup not in groupNames:
            raise errors.ResponseError(404)
        # XXX exception handling
        sgObject = self.SecurityGroupHandler().parseString(xmlContent)
        newRules = [
            ( [ y.getText() for y in x.getIpRange() ],
              x.getIpProtocol(), x.getFromPort(), x.getToPort())
            for x in sgObject.getPermission() ]
        # Hash the rules
        newRulesSet = self._buildRuleSet(newRules)
        sGroup = self._getUnfilteredSecurityGroups(
            groupNames = [ securityGroup ] )[0]
        oldRulesSet = self._buildRuleSet(sGroup[3])
        toAuthorize = newRulesSet.difference(oldRulesSet)
        for cidr_ip, ip_protocol, from_port, to_port in toAuthorize:
            try:
                self.client.authorize_security_group(securityGroup,
                    cidr_ip = cidr_ip, ip_protocol = ip_protocol,
                    from_port = from_port, to_port = to_port)
            except EC2ResponseError, e:
                if e.status == 400 and self._getErrorCode(e) == 'InvalidPermission.Duplicate':
                    pass # ignore this error
                else:
                    raise errors.ResponseError(e.status, e.message, e.body)
        toRevoke = oldRulesSet.difference(newRulesSet)
        for cidr_ip, ip_protocol, from_port, to_port in toRevoke:
            try:
                self.client.revoke_security_group(securityGroup,
                    cidr_ip = cidr_ip, ip_protocol = ip_protocol,
                    from_port = from_port, to_port = to_port)
            except EC2ResponseError, e:
                pass # ignore this error, at least for now
        return self.getSecurityGroup(instanceId, securityGroup)

    @classmethod
    def _buildRuleSet(cls, rules):
        ruleSet = set()
        for ipRange, ipProto, fromPort, toPort in rules:
            ipProto = str(ipProto)
            fromPort = str(fromPort)
            toPort = str(toPort)
            for ip in ipRange:
                ruleSet.add((str(ip), ipProto, fromPort, toPort))
        return ruleSet

    def _createSecurityGroupNode(self, instanceId, sg):
        permissions = []
        for perm in sg[3]:
            p = EC2_Permissions()
            p.setIpRange([ EC2_IPRange(item = x) for x in perm[0]])
            p.setIpProtocol(perm[1])
            p.setFromPort(perm[2])
            p.setToPort(perm[3])
            permissions.append(p)
        ret = self._nodeFactory.newSecurityGroup(instanceId,
            self.SecurityGroup(id = sg[0],
                groupName = sg[0],
                description = sg[1],
                ownerId = sg[2],
                permission = permissions))
        return ret

    @classmethod
    def _tempfile(cls, contents):
        f = tempfile.NamedTemporaryFile(dir="/dev/shm")
        f.write(contents)
        f.flush()
        f.seek(0)
        return f

    def _deployImageFromFile(self, job, image, filePath, extraParams=None):
        amiId = self._deployImageHelper(job, image, filePath)
        img = self.client.get_all_images([amiId])[0]
        imageName = extraParams.get('imageName', None)
        if imageName is None:
            imageName = "%s_%s" % (image.getBaseFileName(), image.getBuildId())
        img.add_tag('Name', imageName)
        return amiId

    def _deployImageHelper(self, job, image, filePath):
        tconf = self.getTargetConfiguration(forceAdmin=True)
        # Force creation of client
        self._getEC2Connection(tconf)

        if image._imageData.get('ebsBacked'):
            return self._deployImageFromFile_EBS(job, image, filePath)

        bucketName = tconf['s3Bucket']
        tmpDir = os.path.dirname(filePath)
        imageFilePath = self._getFilesystemImage(job, image, filePath)
        bundlePath = os.path.join(tmpDir, "bundled")
        util.mkdirChain(bundlePath)
        imagePrefix = "%s_%s" % (image.getBaseFileName(), image.getBuildId())
        architecture = image.getArchitecture() or "x86"
        if architecture == 'x86':
            architecture = 'i386'
        self._msg(job, "Bundling image")
        aki = self.kernelMap.get(architecture)
        self._bundleImage(imageFilePath, bundlePath, imagePrefix,
                architecture, targetConfiguration=tconf, kernelImage=aki)
        manifestName = self._uploadBundle(job, bundlePath, bucketName, tconf)
        emiId = self._registerImage(job, bucketName, manifestName, tconf)
        return emiId

    def _deployImageFromFile_EBS(self, job, image, filePath):
        imageData = image._imageData
        fsSize = imageData.get('attributes.installed_size')
        # Moderate amount of free space necessary, we'll resize at
        # launch time
        totalSize = 64 * 1024 * 1024 + self._extFilesystemSize(fsSize)
        # EBS volumes come in 1G increments
        GiB = 1024 * 1024 * 1024
        totalSize += self._computePadding(totalSize, GiB)
        volumeSize = int(totalSize / GiB)

        conn = self.client
        myInstanceId = self._findMyInstanceId()
        # Fetch my own instance
        instances = conn.get_all_instances(instance_ids=[myInstanceId])
        instance = instances[0].instances[0]

        devName, internalDev = self._findOpenBlockDevice(instance)
        self._msg(job, "Creating EBS volume")
        vol = conn.create_volume(size=volumeSize, zone=instance.placement)
        self._msg(job, "Created EBS volume %s" % vol.id)
        try:
            self._msg(job, "Attaching EBS volume")
            vol.attach(instance.id, devName)

            self._waitForBlockDevice(job, internalDev)
            self._writeFilesystemImage(internalDev, filePath)
            snapshot = self._createSnapshot(job, vol)
            amiId = self._registerEBSBackedImage(job, image, snapshot)
            return amiId
        finally:
            self._msg(job, 'Cleaning up')
            self._detachVolume(job, vol)
            conn.delete_volume(vol.id)

    def _registerEBSBackedImage(self, job, image, snapshot):
        self._msg(job, "Registering EBS-backed image")
        conn = self.client
        bdm = bec2.blockdevicemapping.BlockDeviceMapping()
        devName = "/dev/sda"
        # Add snapshot hash to image name as well, in case we want to
        # re-register later
        snapshotHash = snapshot.id.rsplit('-', 1)[-1]
        name = "%s_%s-%s" % (image.getBaseFileName(), image.getBuildId(),
                snapshotHash)
        bdm[devName] = bec2.blockdevicemapping.BlockDeviceType(
                snapshot_id=snapshot.id, delete_on_termination=True)
        architecture = image.getArchitecture() or "x86"
        if architecture == 'x86':
            architecture = 'i386'
        aki = self.kernelMap.get(architecture)
        amiId = conn.register_image(name=name, description=name,
                kernel_id=aki,  block_device_map=bdm,
                root_device_name=devName, architecture=architecture)
        self._msg(job, "Registered image %s" % amiId)
        return amiId

    def _waitForBlockDevice(self, job, internalDev):
        for i in range(120):
            if os.path.exists(internalDev):
                return
            self._msg(job, "Waiting for volume to become available")
            time.sleep(self.TIMEOUT_BLOCKDEV)
        raise RuntimeError("Block device unavailable")

    def _createSnapshot(self, job, volume):
        conn = self.client
        snapshot = volume.create_snapshot()
        snapshotId = snapshot.id
        self._msg(job, "Created snapshot %s" % snapshotId)
        for i in range(120):
            if snapshot.status == 'completed':
                return snapshot
            self._msg(job, "Snapshot status: %s" % snapshot.status)
            time.sleep(self.TIMEOUT_SNAPSHOT)
            snapshot.update(validate=True)
        conn.delete_snapshot(snapshotId)
        raise RuntimeError("Timed out waiting for snapshot operation")

    def _detachVolume(self, job, volume):
        volumeId = volume.id
        conn = self.client
        self._msg(job, "Detaching volume %s" % volumeId)
        conn.detach_volume(volumeId)
        for i in range(120):
            if volume.status == "available":
                return True
            self._msg(job, "Waiting for volume to be detached")
            time.sleep(self.TIMEOUT_VOLUME)
            volume.update(validate=True)
        return None

    def _findMyInstanceId(self):
        from amiconfig import ami
        ac = ami.AMIConfig()
        instanceId = ac.id.getInstanceId()
        return instanceId

    @classmethod
    def _findOpenBlockDevice(cls, instance):
        bmap = instance.block_device_mapping
        for i in range(15):
            devName = "/dev/sd%s" % chr(ord('f') + i)
            if devName not in bmap:
                return devName, '/dev/xvd%s' % chr(ord('j') + i)
        return None, None

    def _getFilesystemImage(self, job, image, dlpath):
        imageData = image._imageData
        fsSize = imageData.get('attributes.installed_size')
        if fsSize is None:
            # Hopefully we won't have to do this
            self._msg(job, "Computing filesystem image size")
            gf = gzip.open(dlpath)
            fsSize = 0
            blockSize = 1024 * 1024
            while 1:
                gf.seek(blockSize, 1)
                pos = gf.tell()
                if fsSize == pos:
                    break
                fsSize = pos
            gf.close()
        imageFilePath = os.path.join(os.path.dirname(dlpath),
            "%s.ext3" % image.getBaseFileName())

        freeSpace = image._imageData.get('freespace', 256) * 1024 * 1024

        totalSize = self._extFilesystemSize(fsSize + freeSpace)
        # ext3 hides 5% of the space for root's own usage. To avoid
        # having people come screaming they didn't get all their free
        # space, let's pad things a bit.
        totalSize = int((fsSize + freeSpace) * 1.09)

        # Round filesystem size to a multiple of FS_BLK_SIZE
        FS_BLK_SIZE = 4096

        padding = self._computePadding(totalSize, FS_BLK_SIZE)
        imageF = file(imageFilePath, "w")
        imageF.seek(totalSize + padding - 1)
        imageF.write('\0')
        imageF.close()

        self._msg(job, "Creating filesystem image")
        self._writeFilesystemImage(imageFilePath, dlpath)

        return imageFilePath

    @classmethod
    def _extFilesystemSize(cls, fsSize):
        # ext3 hides 5% of the space for root's own usage. To avoid
        # having people come screaming they didn't get all their free
        # space, let's pad things a bit.
        totalSize = int(fsSize * 1.09)
        return totalSize

    @classmethod
    def _computePadding(cls, actualSize, blockSize):
        # ((a + x - 1) % x + 1) is equal to a % x, except for the
        # a == x case, where it is x instead of 0.
        padding = blockSize - (( actualSize + blockSize - 1) % blockSize) - 1
        return padding

    def _writeFilesystemImage(self, fsImage, tarFile):
        from jobslave.generators import bootable_image
        fs = bootable_image.Filesystem(fsImage, fsType='ext3', size=0, fsLabel='root')
        fs.format()
        mountPoint = os.path.join(os.path.dirname(fsImage), "mounted")
        util.mkdirChain(mountPoint)
        fs.mount(mountPoint)
        cmd = [ 'tar', 'zxf', tarFile, '--directory', mountPoint, '--sparse', ]
        p = subprocess.Popen(cmd)
        p.wait()

        self._fixGrub(mountPoint)
        grubConfF = file(os.path.join(mountPoint, 'etc', 'grub.conf'), "r+")
        grubData = grubConfF.read()
        grubData = grubData.replace('(hd0,0)', '(hd0)')
        grubData = grubData.replace('timeout=5', 'timeout=1')
        grubConfF.seek(0)
        grubConfF.truncate()
        grubConfF.write(grubData)
        grubConfF.close()

        fs.umount()
        util.rmtree(mountPoint)

    def _fixGrub(self, mountPoint):
        confFiles = [ 'grub.conf', 'menu.lst' ]
        for fname in confFiles:
            fpath = os.path.join(mountPoint, 'boot', fname)
            if not os.path.exists(fpath):
                continue
            f = file(fpath, "r+")
            grubData = f.read()
            grubData = grubData.replace('(hd0,0)', '(hd0)')
            grubData = grubData.replace('timeout=5', 'timeout=1')
            f.seek(0)
            f.truncate()
            f.write(grubData)
            f.close()

    @classmethod
    def _bundleImage(cls, inputFSImage, bundlePath, imagePrefix, architecture,
            kernelImage=None, ramdiskImage=None, targetConfiguration=None):
        tconf = targetConfiguration
        x509CertFile = cls._tempfile(tconf['certificateData'])
        x509KeyFile = cls._tempfile(tconf['certificateKeyData'])
        cloudX509CertFile = tconf.get('cloudX509Cert')
        if cloudX509CertFile is not None:
            cloudX509CertFile = cls._tempfile(cloudX509CertFile)
        # The account does not matter for euca
        accountId = tconf.get('accountId', '0' * 12)
        cmd = [ '/usr/bin/ec2-bundle-image',
            '-i', inputFSImage,
            '-u', accountId,
            '-c', x509CertFile.name,
            '-k', x509KeyFile.name,
            '-d', bundlePath,
            '-p', imagePrefix,
            '-r', architecture,
        ]
        if kernelImage:
            cmd.extend(['--kernel', kernelImage,])
        if ramdiskImage:
            cmd.extend(['--ramdisk', ramdiskImage])
        if cloudX509CertFile:
            cmd.extend(['--ec2cert', cloudX509CertFile.name])
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
        s3conn, location = self._getS3Connection(targetConfiguration)
        policy = None
        bucket = ec2.S3Wrapper.createBucketBackend(s3conn, bucketName,
            policy=policy)
        ec2.S3Wrapper.uploadBundleBackend(bundleItemGen, fileCount, totalSize,
            bucket, permittedUsers=self.PermittedS3Users,
            callback=cb, policy=policy)
        manifests = [ os.path.basename(x[0]) for x in bundleItemGen
                            if x[0].endswith('.manifest.xml') ]

        return manifests[0]

    def _registerImage(self, job, bucketName, manifestName, targetConfiguration):
        self._msg(job, "Registering image")
        ec2conn = self._getEC2Connection(targetConfiguration)
        loc = "%s/%s" % (bucketName, os.path.basename(manifestName))
        emiId = ec2conn.register_image(image_location=loc)
        self._msg(job, "Registered %s" % emiId)
        return emiId

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

PEM_LINE = 76
PEM_HEADER = '-{2,5}(BEGIN [A-Z0-9 ]+?\s*)-{2,5}'
PEM_TRAILER = '-{2,5}(END [A-Z0-9 ]+?\s*)-{2,5}'
PEM_BODY = '([a-zA-Z0-9/+= \t\r\n]+)'

PEM = re.compile('^%s$' % (PEM_HEADER + PEM_BODY + PEM_TRAILER), re.M)
WHITESPACE = re.compile('\s+')

def fixPEM(pem, error=True):
    """
    Normalize a blob C{pem}, which may contain one or more
    PEM-like sections (e.g. a certificate and private key).
    """
    out = ''
    for header, body, trailer in PEM.findall(pem):
        body = WHITESPACE.sub('', body)
        out += '-----' + header + '-----\n'
        while body:
            chunk, body = body[:PEM_LINE], body[PEM_LINE:]
            out += chunk + '\n'
        out += '-----' + trailer + '-----\n'
    if error and not out:
        raise RuntimeError("No PEM blocks found in blob")
    return out
