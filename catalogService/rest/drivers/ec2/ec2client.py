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


import base64
import gzip
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from amiconfig import AMIConfig, errors as amierrors
from boto import ec2 as bec2
from boto.ec2 import networkinterface
from boto.vpc import VPCConnection as EC2Connection
from boto.s3.connection import S3Connection, Location
from boto.exception import EC2ResponseError, S3CreateError, S3ResponseError
from conary.lib import util

from mint import ec2, helperfuncs
from jobsubordinate.util import logCall
from jobsubordinate.generators import bootable_image

from catalogService import errors
from catalogService.rest import baseDriver
from catalogService.rest.models import clouds
from catalogService.rest.models import images
from catalogService.rest.models import instances
from catalogService.rest.models import securityGroups
from catalogService.utils import vmdk_extract
from catalogService.utils.progress import PercentageCallback

log = logging.getLogger(__name__)

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
        ('m3.medium', 'M3 Medium'),
        ('m3.large', 'M3 Large'),
        ('m3.xlarge', 'M3 Extra Large'),
        ('m3.2xlarge', 'M3 Double Extra Large'),
        ('c3.large', 'C3 Compute Optimized Large'),
        ('c3.xlarge', 'C3 Compute Optimized Extra Large'),
        ('c3.2xlarge', 'C3 Compute Optimized Double Extra Large'),
        ('c3.4xlarge', 'C3 Compute Optimized Quadruple Extra Large'),
        ('c3.8xlarge', 'C3 Compute Optimized Eight Extra Large'),
        ('g2.2xlarge', 'G2 GPU-Optimized Double Extra Large'),
        ('r3.xlarge', 'R3 Memory Optimized Extra Large'),
        ('r3.2xlarge', 'R3 Memory Optimized Double Extra Large'),
        ('r3.4xlarge', 'R3 Memory Optimized Quadruple Extra Large'),
        ('r3.8xlarge', 'R3 Memory Optimized Eight Extra Large'),
        ('i2.xlarge', 'I2 Storage Optimized Extra Large'),
        ('i2.2xlarge', 'I2 Storage Optimized Double Extra Large'),
        ('i2.4xlarge', 'I2 Storage Optimized Quadruple Extra Large'),
        ('i2.8xlarge', 'I2 Storage Optimized Eight Extra Large'),
        ('hs1.8xlarge', "High Storage Eight Extra Large"),
        ('m1.small', "(OLD) M1 Small"),
        ('m1.medium', "(OLD) M1 Medium"),
        ('m1.large', "(OLD) M1 Large"),
        ('m1.xlarge', "(OLD) M1 Extra Large"),
        ('m2.xlarge', "(OLD) M2 High Memory Extra Large"),
        ('m2.2xlarge', "(OLD) M2 High Memory Double Extra Large"),
        ('m2.4xlarge', "(OLD) M2 High Memory Quadruple Extra Large"),
        ('c1.medium', "(OLD) C1 High-CPU Medium"),
        ('c1.xlarge', "(OLD) C1 High-CPU Extra Large"),
        ('hi1.4xlarge', "(OLD) High I/O Quadruple Extra Large"),
    ]
    idMapEBS = [
            ('t2.micro', "T2 Micro"),
            ('t2.small', "T2 Small"),
            ('t2.medium', "T2 Medium"),
            ('t1.micro', "T1 Micro"),
            ('c4.large', 'C4 Compute Optimized Large'),
            ('c4.xlarge', 'C4 Compute Optimized Extra Large'),
            ('c4.2xlarge', 'C4 Compute Optimized Double Extra Large'),
            ('c4.4xlarge', 'C4 Compute Optimized Quadruple Extra Large'),
            ('c4.8xlarge', 'C4 Compute Optimized Eight Extra Large'),
            ] + idMap

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
            kernelMap={'x86_64': 'aki-919dcaf8', 'i386': 'aki-8f9dcae6'}),
        XRegionInfo(name="us-west-1", endpoint="ec2.us-west-1.amazonaws.com",
            s3Endpoint="s3-us-west-1.amazonaws.com", s3Location='us-west-1',
            description="US West 1 (Northern California)",
            kernelMap={'x86_64': 'aki-880531cd', 'i386': 'aki-8e0531cb'}),
        XRegionInfo(name="us-west-2", endpoint="ec2.us-west-2.amazonaws.com",
            s3Endpoint="s3-us-west-2.amazonaws.com", s3Location='us-west-2',
            description="US West 2 (Oregon)",
            kernelMap={'x86_64': 'aki-fc8f11cc', 'i386': 'aki-f08f11c0'}),
        XRegionInfo(name="eu-central-1", endpoint="ec2.eu-central-1.amazonaws.com",
            s3Endpoint="s3-eu-central-1.amazonaws.com", s3Location='eu-central-1',
            description="EU (Frankfurt)",
            kernelMap={'x86_64': 'aki-184c7a05', 'i386': 'aki-3e4c7a23'}),
        XRegionInfo(name="eu-west-1", endpoint="ec2.eu-west-1.amazonaws.com",
            s3Endpoint="s3-eu-west-1.amazonaws.com", s3Location='eu-west-1',
            description="EU (Ireland)",
            kernelMap={'x86_64': 'aki-52a34525', 'i386': 'aki-68a3451f'}),
        XRegionInfo(name="sa-east-1", endpoint="ec2.sa-east-1.amazonaws.com",
            s3Endpoint="s3-sa-east-1.amazonaws.com", s3Location='sa-east-1',
            description="South America (Sao Paulo)",
            kernelMap={'x86_64': 'aki-5553f448', 'i386': 'aki-5b53f446'}),
        XRegionInfo(name="ap-northeast-1", endpoint="ec2.ap-northeast-1.amazonaws.com",
            s3Endpoint="s3-ap-northeast-1.amazonaws.com",
            s3Location='ap-northeast-1',
            description="Asia Pacific NorthEast (Tokyo)",
            kernelMap={'x86_64': 'aki-176bf516', 'i386': 'aki-136bf512'}),
        XRegionInfo(name="ap-southeast-1", endpoint="ec2.ap-southeast-1.amazonaws.com",
            s3Endpoint="s3-ap-southeast-1.amazonaws.com",
            s3Location='ap-southeast-1',
            description="Asia Pacific 1 (Singapore)",
            kernelMap={'x86_64': 'aki-503e7402', 'i386': 'aki-ae3973fc'}),
        XRegionInfo(name="ap-southeast-2", endpoint="ec2.ap-southeast-2.amazonaws.com",
            s3Endpoint="s3-ap-southeast-2.amazonaws.com",
            s3Location='ap-southeast-2',
            description="Asia Pacific 2 (Sydney)",
            kernelMap={'x86_64': 'aki-c362fff9', 'i386': 'aki-cd62fff7'}),
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
      <multiline>true</multiline>
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
      <multiline>true</multiline>
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
    imageListPattern = re.compile(r'.*\[([^]]*)\].*')

    RBUILDER_BUILD_TYPE = 'AMI'

    PermittedS3Users = [ ec2.S3Wrapper.amazonEC2UserId ]

    class SecurityGroupHandler(securityGroups.Handler):
        securityGroupClass = EC2_SecurityGroup

    ImagePrefix = 'ami-'

    TIMEOUT_BLOCKDEV = 1
    TIMEOUT_SNAPSHOT = 2
    TIMEOUT_VOLUME = 3

    ShutdownBehavior = [
        ('stop', 'Stop'),
        ('terminate', 'Terminate'),
    ]

    def _getProxyInfo(self, https = True):
        proto = (https and "https") or "http"
        proxyUrl = self.db.cfg.proxy.get(proto)
        if not proxyUrl:
            return None, None, None, None
        splitUrl = helperfuncs.urlSplit(proxyUrl)
        proxyUser, proxyPass, proxy, proxyPort = splitUrl[1:5]
        return proxyUser, proxyPass, proxy, proxyPort

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
        except EC2ResponseError:
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
[amiconfig]
plugins = rpath sfcb-client-setup
[sfcb-client-setup]
x509-cert-hash=%s
x509-cert(base64)=%s
[rpath-tools]
boot-uuid=%s
zone-addresses=%s
conary-proxies=%s
"""
        certPath = self.getWbemClientCert()
        try:
            certData = file(certPath).read()
        except IOError:
            return userData

        certHash = self.computeX509CertHash(certPath)
        certData = base64.b64encode(certData)
        bootUuid = self.getBootUuid()

        zoneAddresses = ' '.join(self.zoneAddresses)
        conaryProxies = ' '.join(x.split(':', 1)[0] for x in self.zoneAddresses)

        sect = templ % (certHash, certData, bootUuid, zoneAddresses,
            conaryProxies)
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
        if hasattr(image, '_imageData') and image._imageData.get('ebsBacked'):
            params['vpc'] = vpcId = getField('network')
            params['subnet'] = subnetId = getField('subnet-%s' % vpcId)
            val = getField('autoAssignPublicIp-%s' % subnetId)
            if val.startswith('subnet-'):
                val = val[7:]
            params['autoAssignPublicIp'] = True if val == 'Enable' else False
            params['securityGroups'] = getField('securityGroups-%s' % vpcId)
            netif = networkinterface.NetworkInterfaceSpecification(
                    subnet_id=subnetId,
                    associate_public_ip_address=params['autoAssignPublicIp'],
                    groups=params['securityGroups'],
                    )
            params['networkInterfaces'] =  networkinterface.NetworkInterfaceCollection(netif)

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
        instanceIds = self._launchInstancesHelper(job, image, launchParams)
        self._tagInstances(job, image, launchParams, instanceIds)
        return instanceIds

    def _tagInstances(self, job, image, launchParams, instanceIds):
        self._msg(job, "Tagging instances")
        reqInstName = launchParams.get('instanceName')
        reqInstDescription = launchParams.get('instanceDescription')
        for i in range(60):
            try:
                reservations = self._getInstanceReservations(instanceIds)
            except errors.HttpNotFound:
                self._msg(job, "Waiting for reservation")
                time.sleep(1)
            else:
                break
        instCount = len(instanceIds)
        suffix = ""
        # All instances should be part of the same reservation
        for inst in reservations[0].instances:
            idx = int(inst.ami_launch_index)
            if instCount > 1:
                suffix = " (%s/%s)" % (idx + 1, instCount)
            if reqInstName:
                self._tagResource(job, inst, 'Name',
                        reqInstName + suffix)
            if reqInstDescription:
                self._tagResource(job, inst, 'Description',
                        reqInstDescription + suffix)
            for tagDict in launchParams.get('tags', []):
                self._tagResource(job, inst, tagDict['name'], tagDict['value'])

    def _launchInstancesHelper(self, job, image, launchParams):
        imageId = launchParams.pop('imageId')
        self._msg(job, "Launching instance %s" % imageId)
        runInstancesParams = dict(
                min_count=launchParams.get('minCount'),
                max_count=launchParams.get('maxCount'),
                key_name=launchParams.get('keyName'),
                user_data=self.createUserData(launchParams.get('userData')),
                instance_type=launchParams.get('instanceType'),
                placement=launchParams.get('availabilityZone'))
        # The hasattr below is because the testsuite insists on testing
        # old codepaths. All images should have _imageData
        if hasattr(image, '_imageData') and image._imageData.get('ebsBacked'):
            img = self.client.get_all_images([imageId])[0]
            # Reuse the block device definition from the image object
            rootDevice = img.block_device_mapping[img.root_device_name]
            rootDevice.size += launchParams.get('freeSpace')
            rootDevice.delete_on_termination = launchParams.get('deleteRootVolumeOnTermination')
            runInstancesParams.update(
                instance_initiated_shutdown_behavior=launchParams.get('shutdownBehavior'),
                block_device_map=img.block_device_mapping,
                network_interfaces=launchParams.get('networkInterfaces'),
            )
        else:
            runInstancesParams.update(security_groups=launchParams.get('securityGroups'))
        try:
            reservation = self.client.run_instances(imageId, **runInstancesParams)
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

    def _getInstanceReservations(self, instanceIds):
        try:
            resultSet = self.client.get_all_instances(instance_ids=instanceIds)
        except EC2ResponseError, e:
            if self._getErrorCode(e) in ['InvalidInstanceID.NotFound',
                                         'InvalidInstanceID.Malformed']:
                raise errors.HttpNotFound()
            raise errors.ResponseError(e.status, self._getErrorMessage(e), e.body)
        return resultSet

    def drvGetInstances(self, instanceIds, force=False):
        resultSet = self._getInstanceReservations(instanceIds)
        insts = instances.BaseInstances()
        for reservation in resultSet:
            insts.extend(self._getInstancesFromReservation(reservation))
        return insts

    def getImagesFromTarget(self, imageIds):
        imageList = images.BaseImages()
        targetConfiguration = self.getTargetConfiguration()
        ownerId = targetConfiguration.get('accountId')
        if ownerId:
            ownerIds = [ ownerId ]
        else:
            ownerIds = None
        imageIds = set(imageIds or [])
        try:
            rs = self.client.get_all_images(image_ids = list(imageIds), owners = ownerIds)
        except EC2ResponseError, e:
            errorCode = self._getErrorCode(e)
            errorMsg = self._getErrorMessage(e)
            if errorCode != 'InvalidAMIID.NotFound':
                raise
            # Identify the non-existing images
            missingImageIds = self._processInvalidAMIID(errorMsg)
            imageIds = imageIds.difference(missingImageIds)
            if not imageIds:
                return imageList
            rs = self.client.get_all_images(image_ids = list(imageIds), owners = ownerIds)

        # avoid returning amazon kernel images.
        rs = [ x for x in rs if x.id.startswith(self.ImagePrefix) ]

        cloudAlias = targetConfiguration.get('cloudAlias')
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

    @classmethod
    def _formatVPC(cls, obj):
        tmpl = [obj.id, "(%s)" % obj.cidr_block]
        name = obj.tags.get('Name')
        if name:
            tmpl.append('|')
            tmpl.append(name)
        return ' '.join(tmpl)

    @classmethod
    def _formatSubnet(cls, obj):
        tmpl = [obj.id, "(%s)" % obj.cidr_block]
        name = obj.tags.get('Name')
        if name:
            tmpl.append('|')
            tmpl.append(name)
        tmpl.append('|')
        tmpl.append(obj.availability_zone)
        tmpl.append('|')
        tmpl.append("(%s IP addresses available)" %
                obj.available_ip_address_count)
        return ' '.join(tmpl)

    @classmethod
    def _formatSecurityGroup(cls, obj):
        return "%s | %s (%s)" % (obj.id, obj.name, obj.description)

    def drvPopulateLaunchDescriptor(self, descr, extraArgs=None):
        imageData = self._getImageData(extraArgs)
        title = "Amazon EC2 System Launch Parameters"
        if imageData.ebsBacked:
            title += " (EBS-backed)"
        freeSpace = imageData.freespace or 256

        descr.setDisplayName(title)
        descr.addDescription(title)
        self.drvLaunchDescriptorCommonFields(descr)
        if imageData.ebsBacked:
            instanceTypeMap = EC2_InstanceTypes.idMapEBS
        else:
            instanceTypeMap = EC2_InstanceTypes.idMap
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
                  for (x, y) in instanceTypeMap),
            default = instanceTypeMap[0][0],
            )
        if imageData.ebsBacked:
            subnets = self.client.get_all_subnets()
            vpcToSubnet = {}
            for subnet in subnets:
                if not subnet.available_ip_address_count:
                    continue
                vpcToSubnet.setdefault(subnet.vpc_id, []).append(subnet)
            vpcToSecurityGroups = {}
            for sg in self._getAllSecurityGroups():
                vpcToSecurityGroups.setdefault(sg.vpc_id, []).append(sg)
            vpcs = self.client.get_all_vpcs()
            vpcList = [ (x.id, self._formatVPC(x)) for x in vpcs
                    if x.id in vpcToSubnet ]
            descr.addDataField("network",
                descriptions = [
                    ("Network", None),
                    ],
                help = [
                    ("launch/network_vpc.html", None)],
                default = vpcList[0][0],
                required = True,
                type = descr.EnumeratedType(
                    descr.ValueWithDescription(x[0], descriptions = x[1])
                    for x in vpcList
                ))
            for vpc in vpcs:
                subnetList = [ (x.id, self._formatSubnet(x))
                        for x in vpcToSubnet[vpc.id] ]
                descr.addDataField("subnet-%s" % vpc.id,
                    descriptions = [
                        ("Subnet", None),
                        ],
                    help = [
                        ("launch/subnet.html", None)],
                    required = True,
                    type = descr.EnumeratedType(
                        descr.ValueWithDescription(x[0], descriptions = x[1])
                        for x in subnetList
                    ),
                    default=subnetList[0][0],
                    conditional = descr.Conditional(
                        fieldName='network',
                        operator='eq',
                        fieldValue=vpc.id),
                    )
                for subnet in vpcToSubnet[vpc.id]:
                    subnetDefault = "Enable" if subnet.mapPublicIpOnLaunch == "true" else "Disable"
                    label = "Use subnet setting (%s)" % subnetDefault
                    autoAssignPublicIPOptions = [
                            ("subnet-%s" % subnetDefault, label),
                            ("Enable", "Enable"),
                            ("Disable", "Disable"),]
                    descr.addDataField("autoAssignPublicIp-%s" % subnet.id,
                        descriptions = [
                            ("Auto-assign Public IP", None),
                            ],
                        help = [
                            ("launch/auto_assign_public_ip.html", None)],
                        required = True,
                        type = descr.EnumeratedType(
                            descr.ValueWithDescription(x[0], descriptions = x[1])
                            for x in autoAssignPublicIPOptions
                        ),
                        default=autoAssignPublicIPOptions[0][0],
                        conditional = descr.Conditional(
                            fieldName='subnet-%s' % vpc.id,
                            operator='eq',
                            fieldValue=subnet.id),
                        )

                sgList = [ (x.id, self._formatSecurityGroup(x))
                        for x in vpcToSecurityGroups[vpc.id] ]
                descr.addDataField("securityGroups-%s" % vpc.id,
                    descriptions = [("Security Groups", None),
                        (u"Groupes de sécurité", "fr_FR")],
                    help = [
                        ("launch/securityGroups.html", None)
                    ],
                    required = True, multiple = True,
                    type = descr.EnumeratedType(
                        descr.ValueWithDescription(x[0], descriptions = x[1])
                        for x in sgList),
                    conditional = descr.Conditional(
                        fieldName='network',
                        operator='eq',
                        fieldValue=vpc.id),
                    )
            defaultFreeSpace = int(
                (freeSpace +  self._computePadding(freeSpace, 1024)) / 1024)
            descr.addDataField("freeSpace",
                descriptions = [ ("Addtional Space on Root Volume (Gigabytes)", None) ],
                required = True,
                type = "int",
                default = defaultFreeSpace,
                constraints = dict(constraintName = 'range',
                                   min = 0, max = 1024),
                )
            descr.addDataField("deleteRootVolumeOnTermination",
                descriptions = [ ("Delete Root Volume on Termination", None) ],
                required = True,
                type = "bool",
                default = True)
            descr.addDataField("shutdownBehavior",
                descriptions = [ ("Instance-initiated Shutdown Behavior", None) ],
                required = True,
                type = descr.EnumeratedType(
                    descr.ValueWithDescription(x[0], descriptions = x[1])
                    for x in self.ShutdownBehavior
                ),
                default = self.ShutdownBehavior[-1][0])
        if not imageData.ebsBacked:
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
        if not imageData.ebsBacked:
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
        self.addTagsDescriptor(descr)
        return descr

    def drvPopulateImageDeploymentDescriptor(self, descr, extraArgs=None):
        imageData = self._getImageData(extraArgs)
        title = "Amazon EC2 Image Deployment Parameters"
        if imageData.ebsBacked:
            title += ' (EBS-backed)'
        descr.setDisplayName(title)
        descr.addDescription(title)
        self.drvImageDeploymentDescriptorCommonFields(descr)
        self.addTagsDescriptor(descr)
        return descr

    def addTagsDescriptor(self, descr):
        kvdesc = descr.__class__()
        kvdesc.setId("tag")
        # XXX there is a bug in the UI, it looks like it hardcodes
        # 'item' here
        #kvdesc.setRootElement('tag')
        kvdesc.setRootElement('item')
        kvdesc.setDisplayName("Additional tag")
        kvdesc.addDescription("Additional tag")
        # Constraints documented here:
        # http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Using_Tags.html
        kvdesc.addDataField('name', type="str", required=True,
                descriptions="Tag name",
                constraints=[
                    dict(constraintName='length', value=127)
                    ])
        kvdesc.addDataField('value', type="str", required=True,
                descriptions="Tag value",
                constraints=[
                    dict(constraintName='length', value=255)
                    ])
        descr.addDataField('tags', type=descr.ListType(kvdesc),
                descriptions="Additional tags",
                constraints=[
                    dict(constraintName="uniqueKey", value="name"),
                    dict(constraintName="maxLength", value="9"),
                    ])
        return descr

    class ImageData(baseDriver.BaseDriver.ImageData):
        __slots__ = [ 'ebsBacked', 'freespace', 'amiHugeDiskMountpoint', ]

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
        allowed = []
        # open ingress for ports 80, 443, and 8003 on TCP
        # for the IP address
        remoteNet = '%s/32' % remoteIPAddress if remoteIPAddress else '0.0.0.0/0'
        allowed.extend(dict(from_port=from_port, to_port=to_port,
                            ip_protocol=proto, cidr_ip=remoteNet)
            for proto, from_port, to_port in CATALOG_DEF_SECURITY_GROUP_PERMS)
        allowed.extend(dict(from_port=from_port, to_port=to_port,
                            ip_protocol=proto, cidr_ip='0.0.0.0/0')
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

    def _getAllSecurityGroups(self, groupNames=None):
        try:
            rs = self.client.get_all_security_groups(groupnames = groupNames)
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, self._getErrorMessage(e),
                e.body)
        return rs

    def _getUnfilteredSecurityGroups(self, groupNames = None):
        ret = []
        for sg in self._getAllSecurityGroups(groupNames=groupNames):
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

    def _processInvalidAMIID(self, errorMsg):
        match = self.imageListPattern.match(errorMsg)
        if not match:
            return []
        imageList = match.group(1)
        return [ x.strip() for x in imageList.split(',') ]

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

    def _deployImageFromStream(self, job, image, stream, extraParams=None):
        amiId = self._deployImageHelper(job, image, stream)
        for i in range(60):
            imgs = self.client.get_all_images([amiId])
            if imgs:
                break
            self._msg(job, "Waiting for image to become available")
            time.sleep(1)
        else:
            raise Exception("Timeout waiting for image to become available")
        img = imgs[0]
        imageName = extraParams.get('imageName', None)
        if imageName is None:
            imageName = "%s_%s" % (image.getBaseFileName(), image.getBuildId())
        self._tagResource(job, img, 'Name', imageName)
        for tagDict in extraParams.get('tags', []):
            self._tagResource(job, img, tagDict['name'], tagDict['value'])
        return amiId

    def _tagResource(self, job, resource, tagName, tagValue):
        for i in range(10):
            try:
                return resource.add_tag(tagName, tagValue)
            except EC2ResponseError, e:
                self._msg(job, "Error tagging resource: %s" % e)
            resource.update(validate=True)
            time.sleep(1)

    def _deployImageHelper(self, job, image, stream):
        tconf = self.getTargetConfiguration(forceAdmin=True)
        # Force creation of client
        self._getEC2Connection(tconf)

        if image._imageData.get('ebsBacked'):
            return self._deployImageFromStream_EBS(job, image, stream)
        else:
            return self._deployImageFromStream_S3(job, image, stream, tconf)

    def _deployImageFromStream_S3(self, job, image, stream, tconf):
        # RCE-1354: we create the bucket as lowercase, so we need to
        # register the image with the lowercase bucket name too
        bucketName = tconf['s3Bucket'].lower()
        imagePrefix = "%s_%s" % (image.getBaseFileName(), image.getBuildId())
        architecture = image.getArchitecture() or "x86"
        if architecture == 'x86':
            architecture = 'i386'
        aki = self.kernelMap.get(architecture)

        imageFilePath = self._getFilesystemImage(job, image, stream)
        try:
            self._msg(job, "Bundling image")
            bundlePath = tempfile.mkdtemp(prefix='bundle-')
            try:
                self._bundleImage(imageFilePath, bundlePath, imagePrefix,
                        architecture,
                        targetConfiguration=tconf,
                        kernelImage=aki,
                        )
                manifestName = self._uploadBundle(job, bundlePath, bucketName,
                        tconf)
            finally:
                util.rmtree(bundlePath)
        finally:
            os.unlink(imageFilePath)
        emiId = self._registerImage(job, bucketName, manifestName, tconf)
        return emiId

    def _deployImageFromStream_EBS(self, job, image, stream):
        imageData = image._imageData

        fsSize = imageData.get('attributes.uncompressed_size')
        if not fsSize:
            raise RuntimeError('Please rebuild EBS-backed image')
        if image.getImageSuffix() != 'vmdk':
            raise RuntimeError('Please rebuild EBS-backed image')

        totalSize = fsSize
        GiB = 1024 * 1024 * 1024
        totalSize += self._computePadding(totalSize, GiB)
        volumeSize = int(totalSize / GiB)

        conn = self.client
        myInstanceId = self._findMyInstanceId()
        # Fetch my own instance
        instances = conn.get_all_instances(instance_ids=[myInstanceId])
        instance = instances[0].instances[0]

        vol = self._createVolume(job, size=volumeSize, zone=instance.placement)
        self._tagResource(job, vol, 'Name',
                'appeng-image-deployment-%s' % myInstanceId)
        self._msg(job, "Created EBS volume %s" % vol.id)
        try:
            internalDev = self._attachVolume(job, instance, vol)
            stream = self.streamProgressWrapper(job, stream,
                    "Downloading compressed disk image")
            try:
                self._waitForBlockDevice(job, internalDev)
                self._writeDiskImage(job, internalDev, stream, fsSize)
            finally:
                self._detachVolume(job, vol, internalDev)
            snapshot = self._createSnapshot(job, vol)
            amiId = self._registerEBSBackedImage(job, image, snapshot)
            return amiId
        finally:
            self._msg(job, 'Deleting volume %s' % vol.id)
            conn.delete_volume(vol.id)

    def _attachVolume(self, job, instance, vol):
        timeout = 4
        devNum = 0
        while 1:
            try:
                devName, internalDev, devNum = self._findOpenBlockDevice(
                        instance, devNum)
                if devName is not None:
                    self._msg(job, "Attaching EBS volume as %s" % devName)
                    vol.attach(instance.id, devName)
                    return internalDev
                # This will queue up image deployments
                self._msg(job, "No available device found; waiting %s seconds" % timeout)
                time.sleep(timeout)
                if timeout < 128:
                    timeout *= 2
                instance = self.client.get_all_instances(
                        instance_ids=[instance.id])[0].instances[0]
                devNum = 0
                continue
            except EC2ResponseError, e:
                # APPENG-2951: we may attempt to use a device already in use
                if self._getErrorCode(e) != 'InvalidParameterValue':
                    raise
                devNum += 1
                continue

    def _registerEBSBackedImage(self, job, image, snapshot):
        self._msg(job, "Registering EBS-backed image")
        conn = self.client
        bdm = bec2.blockdevicemapping.BlockDeviceMapping()
        devName = "/dev/sda1"
        # Add snapshot hash to image name as well, in case we want to
        # re-register later
        snapshotHash = snapshot.id.rsplit('-', 1)[-1]
        name = "%s-%s_%s-%s" % (image.getBaseFileName(),
                time.strftime("%Y%m%d%H%M", time.gmtime()),
                image.getBuildId(), snapshotHash)
        bdm[devName] = bec2.blockdevicemapping.BlockDeviceType(
                snapshot_id=snapshot.id, delete_on_termination=True)
        architecture = image.getArchitecture() or "x86"
        if architecture == 'x86':
            architecture = 'i386'
        amiId = conn.register_image(name=name, description=name,
                block_device_map=bdm,
                root_device_name=devName, architecture=architecture,
                virtualization_type='hvm')
        self._msg(job, "Registered image %s" % amiId)
        return amiId

    def _createVolume(self, job, size, zone):
        self._msg(job, "Creating EBS volume of %d GiB" % size)
        # io1 has a min size of 4G and 30 IOPS/G
        if size < 4:
            volType = 'gp2'
            iops = None
        else:
            volType = 'io1'
            iops = size * 25
        vol = self.client.create_volume(size=size, zone=zone,
            volume_type=volType, iops=iops)
        while vol.status == 'creating':
            time.sleep(self.TIMEOUT_BLOCKDEV)
            vol.update(validate=True)
        if vol.status == 'available':
            return vol
        else:
            self.client.delete_volume(vol.id)
            raise RuntimeError("Failed to create volume")

    def _waitForBlockDevice(self, job, internalDev):
        for i in range(1000):
            if os.path.exists(internalDev):
                return
            self._msg(job, "Waiting for volume to become available")
            time.sleep(self.TIMEOUT_BLOCKDEV)
        raise RuntimeError("Block device unavailable")

    def _createSnapshot(self, job, volume):
        conn = self.client
        snapshot = volume.create_snapshot()
        snapshotId = snapshot.id
        while True:
            if snapshot.status != 'pending':
                break
            progress = str(snapshot.progress) if snapshot.progress else '0'
            if not progress.endswith('%'):
                progress += '%'
            self._msg(job, "Creating snapshot: %s" % (progress,))
            time.sleep(self.TIMEOUT_SNAPSHOT)
            snapshot.update(validate=True)
        if snapshot.status == 'completed':
            self._msg(job, "Snapshot created")
            return snapshot
        else:
            conn.delete_snapshot(snapshotId)
            raise RuntimeError("Failed to create snapshot")

    def _detachVolume(self, job, volume, dev):
        volumeId = volume.id
        conn = self.client
        self._flushDevice(dev)
        self._msg(job, "Detaching volume %s" % volumeId)
        conn.detach_volume(volumeId)
        volume.update(validate=True)
        for i in range(1000):
            if volume.status == "available":
                return True
            self._msg(job, "Waiting for volume to be detached; state=%s" % volume.status)
            time.sleep(self.TIMEOUT_VOLUME)
            volume.update(validate=True)
        return None

    def _flushDevice(self, dev):
        subprocess.call(['/sbin/blockdev', '--flushbufs', dev])

    def _findMyInstanceId(self):
        ac = AMIConfig()
        try:
            instanceId = ac.id.getInstanceId()
        except amierrors.EC2DataRetrievalError, e:
            raise errors.ResponseError(400,
                "Attempted AWS operation from outside a non-AWS endpoint",
                "The management endpoint was unable to talk to AWS' metadata service. Is it running in EC2? Error: %s" % e)
        return instanceId

    @classmethod
    def _findOpenBlockDevice(cls, instance, start):
        bmap = instance.block_device_mapping
        for i in range(start, 5):
            devName = "/dev/sd%s" % chr(ord('f') + i)
            if devName not in bmap:
                return devName, '/dev/xvd%s' % chr(ord('j') + i), i
        return None, None, None

    def _getFilesystemImage(self, job, image, stream):
        compressed = 'z'
        imageData = image._imageData
        fsSize = imageData.get('attributes.installed_size')
        if fsSize is None:
            # Hopefully we won't have to do this
            stream = self.streamProgressWrapper(job, stream,
                    "Computing filesystem image size")
            imageFile = tempfile.TemporaryFile()
            blockSize = 1024 * 1024
            fsSize = util.copyfileobj(gzip.GzipFile(fileobj=stream), imageFile)
            fsSize = (fsSize + blockSize - 1) / blockSize * blockSize
            imageFile.seek(0)
            stream = imageFile
            compressed = ''

        freeSpace = image._imageData.get('freespace', 256) * 1024 * 1024
        totalSize = self._extFilesystemSize(fsSize + freeSpace)
        # Round filesystem size to a multiple of FS_BLK_SIZE
        FS_BLK_SIZE = 4096
        padding = self._computePadding(totalSize, FS_BLK_SIZE)

        imageF = tempfile.NamedTemporaryFile(prefix=image.getBaseFileName(),
                suffix='.ext4', delete=False)
        imageF.seek(totalSize + padding - 1)
        imageF.write('\0')
        imageF.close()

        stream = self.streamProgressWrapper(job, stream,
                "Creating filesystem image")
        try:
            self._writeFilesystemImage(imageF.name, stream, compressed)
        except:
            os.unlink(imageF.name)
            raise

        return imageF.name

    def _writeDiskImage(self, job, internalDev, stream, diskSize):
        def callback(percent):
            self._msg(job, "%s: %d%%" % ("Uncompressing image", percent))
        callback = PercentageCallback(diskSize, callback)

        with open(internalDev, 'wb') as f_dev:
            reader = vmdk_extract.VMDKReader(stream, f_dev)
            reader.process()
            finalSize = reader.header.capacity * 512
        if reader.header.capacity * 512 != diskSize:
            raise RuntimeError("Expected an image of %s bytes; got %s" % (
                diskSize, finalSize))

    @classmethod
    def isZero(cls, block):
        for b in block:
            if b != '\0':
                return False
        return True

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

    def _writeFilesystemImage(self, fsImage, stream, compressed=''):
        fs = bootable_image.Filesystem(fsImage, fsType='ext4', size=0,
                fsLabel='root')
        fs.format()
        mountPoint = tempfile.mkdtemp(prefix='mount-')
        fs.mount(mountPoint)
        try:
            cmd = [ 'tar', '-x' + compressed,
                    '--directory', mountPoint,
                    '--sparse',
                    ]
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            util.copyfileobj(stream, p.stdin)
            p.stdin.close()
            if p.wait():
                raise RuntimeError("tar exited with status %s" % p.returncode)

            self._fixGrub(mountPoint)
            grubConfF = file(os.path.join(mountPoint, 'etc', 'grub.conf'), "r+")
            grubData = grubConfF.read()
            grubData = grubData.replace('(hd0,0)', '(hd0)')
            grubData = grubData.replace('timeout=5', 'timeout=1')
            grubConfF.seek(0)
            grubConfF.truncate()
            grubConfF.write(grubData)
            grubConfF.close()

        finally:
            try:
                fs.umount()
                os.rmdir(mountPoint)
            except Exception:
                log.exception("Error in unmount:")

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
        logCall(cmd)

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
