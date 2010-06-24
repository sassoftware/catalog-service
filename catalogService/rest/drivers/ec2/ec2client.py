# vim: set fileencoding=utf-8 :

import base64
import os
import re
import sys
import time
import urllib
import urllib2
from boto.ec2.connection import EC2Connection
from boto.s3.connection import S3Connection
from boto.exception import EC2ResponseError, S3CreateError, S3ResponseError

from mint import helperfuncs
from mint.mint_error import EC2Exception as MintEC2Exception
from mint.mint_error import TargetExists, TargetMissing, PermissionDenied

from catalogService import errors
from catalogService import storage
from catalogService.rest import baseDriver
from catalogService.rest.models import clouds
from catalogService.rest.models import images
from catalogService.rest.models import instances
from catalogService.rest.models import keypairs
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

EC2_ALIAS = 'ec2'
EC2_DESCRIPTION = "Amazon Elastic Compute Cloud"

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

    _constructorOverrides = dict(cloudName = 'aws', cloudAlias = 'ec2')

class EC2_Instance(instances.BaseInstance):
    "EC2 Instance"

    __slots__ = instances.BaseInstance.__slots__ + [
                'keyName', 'securityGroup', ]

    _constructorOverrides = EC2_Image._constructorOverrides.copy()
    _slotTypeMap = instances.BaseInstance._slotTypeMap.copy()
    _slotTypeMap['securityGroup'] = EC2_SecurityGroup

class EC2_Cloud(clouds.BaseCloud):
    "EC2 Cloud"

    _constructorOverrides = EC2_Image._constructorOverrides.copy()
    _constructorOverrides['description'] = EC2_DESCRIPTION

class EC2_InstanceTypes(instances.InstanceTypes):
    "EC2 Instance Types"

    idMap = [
        ('m1.small', "Small"),
        ('m1.large', "Large"),
        ('m1.xlarge', "Extra Large"),
        ('c1.medium', "High-CPU Medium"),
        ('c1.xlarge', "High-CPU Extra Large"),
    ]

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
      <hidden>true</hidden>
    </field>
    <field>
      <name>cloudAlias</name>
      <descriptions>
        <desc>Cloud Alias</desc>
      </descriptions>
      <type>str</type>
      <default>ec2</default>
      <hidden>true</hidden>
    </field>
    <field>
      <name>fullDescription</name>
      <descriptions>
        <desc>Full Description</desc>
      </descriptions>
      <type>str</type>
      <default>Amazon Elastic Compute Cloud</default>
      <hidden>true</hidden>
    </field>
    <field>
      <name>accountId</name>
      <descriptions>
        <desc>AWS Account Number</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Field must contain between 1 and 12 characters</desc>
        </descriptions>
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
</descriptor>"""

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
      <password>true</password>
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

    _credNameMap = [
        ('accountId', 'accountId'),
        ('publicAccessKeyId', 'publicAccessKeyId'),
        ('secretAccessKey', 'secretAccessKey'),
     ]

    configurationDescriptorXmlData = _configurationDescriptorXmlData
    credentialsDescriptorXmlData = _credentialsDescriptorXmlData

    dynamicSecurityGroupPattern = re.compile(baseDriver.BaseDriver._uuid('.' * 32))

    RBUILDER_BUILD_TYPE = 'AMI'

    class SecurityGroupHandler(securityGroups.Handler):
        securityGroupClass = EC2_SecurityGroup

    DefaultCloudName = 'aws'

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
        url = "http://rpath.com/clientinfo/"
        resp = self._openUrl(url)
        return self._parseXml(resp.read())

    def _parseXml(self, response):
        from xml.dom import minidom
        dom = minidom.parseString(response)
        nodes = dom.getElementsByTagName('remoteIp')
        if not nodes:
            return None
        return nodes[0].firstChild.wholeText

    def drvCreateCloudClient(self, credentials):
        for key in ('publicAccessKeyId', 'secretAccessKey'):
            if key not in credentials or not credentials[key]:
                raise errors.MissingCredentials()
        proxyUser, proxyPass, proxy, proxyPort = self._getProxyInfo()
        return EC2Connection(self._strip(credentials['publicAccessKeyId']),
                             self._strip(credentials['secretAccessKey']),
                             proxy_user = proxyUser,
                             proxy_pass = proxyPass,
                             proxy = proxy,
                             proxy_port = proxyPort)

    def drvGetTargetConfiguration(self, targetData, isAdmin = False):
        if 'ec2PublicKey' not in targetData:
            # Not configured
            return {}
        ret = dict(name = self.DefaultCloudName,
            alias = targetData.get('alias', EC2_ALIAS),
            cloudAlias = targetData.get('alias', EC2_ALIAS),
            fullDescription = targetData.get('description', EC2_DESCRIPTION),
            description = targetData.get('description', EC2_DESCRIPTION),
            accountId = targetData.get('ec2AccountId', ''),
            )
        if isAdmin:
            ret.update(dict(
                publicAccessKeyId = targetData.get('ec2PublicKey', ''),
                secretAccessKey = targetData.get('ec2PrivateKey', ''),
                certificateData = fixPEM(targetData.get('ec2Certificate', ''),
                    error=False),
                certificateKeyData = fixPEM(targetData.get('ec2CertificateKey',
                    ''), error=False),
                s3Bucket = targetData.get('ec2S3Bucket', '')))
        return ret

    @classmethod
    def _strip(cls, obj):
        if not isinstance(obj, basestring):
            return obj
        return obj.strip()

    def _getS3Connection(self, publicAccessKeyId, secretAccessKey):
        proxyUrl = self.db.cfg.proxy.get('https')
        if proxyUrl:
            splitUrl = helperfuncs.urlSplit(proxyUrl)
            proxyUser, proxyPass, proxy, proxyPort = splitUrl[1:5]
        else:
            proxyUser, proxyPass, proxy, proxyPort = None, None, None, None
        return S3Connection(publicAccessKeyId, secretAccessKey,
                            proxy_user = proxyUser,
                            proxy_pass = proxyPass,
                            proxy = proxy,
                            proxy_port = proxyPort)

    def _createRandomKey(self):
        return base64.b64encode(file("/dev/urandom").read(8))

    def _validateS3Bucket(self, publicAccessKeyId, secretAccessKey, bucket):
        conn = self._getS3Connection(publicAccessKeyId, secretAccessKey)

        try:
            conn.create_bucket(bucket)
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

    def drvCreateCloud(self, descriptorData):
        self.cloudName = self.DefaultCloudName
        clouds = self.listClouds()
        if clouds:
            raise errors.CloudExists()

        getField = descriptorData.getField

        ec2PublicKey = str(self._strip(getField('publicAccessKeyId')))
        ec2PrivateKey = str(self._strip(getField('secretAccessKey')))
        ec2S3Bucket = self._strip(getField('s3Bucket'))
        self._validateS3Bucket(ec2PublicKey, ec2PrivateKey, ec2S3Bucket)

        # Nothing fancy, just reenable the cloud
        launchUsers = getField('launchUsers')
        if launchUsers:
            launchUsers = [ x.strip() for x in launchUsers.split(',') ]
        launchGroups = getField('launchGroups')
        if launchGroups:
            launchGroups = [ x.strip() for x in launchGroups.split(',') ]
        dataDict = dict(
            alias = getField('cloudAlias') or EC2_ALIAS,
            description = getField('fullDescription') or EC2_DESCRIPTION,
            ec2AccountId = getField('accountId'),
            ec2PublicKey = ec2PublicKey,
            ec2PrivateKey = ec2PrivateKey,
            ec2S3Bucket = ec2S3Bucket,
            ec2Certificate = fixPEM(getField('certificateData')),
            ec2CertificateKey = fixPEM(getField('certificateKeyData')),
            ec2LaunchUsers = launchUsers,
            ec2LaunchGroups = launchGroups)
        dataDict = dict((x, self._strip(y)) for (x, y) in dataDict.items())
        # Validate credentials
        creds = {
           'publicAccessKeyId' : dataDict['ec2PublicKey'],
           'secretAccessKey' : dataDict['ec2PrivateKey']}
        cli = self.drvCreateCloudClient(creds)
        # Do a call to force cred validation
        try:
            cli.get_all_regions()
        except EC2ResponseError, e:
            raise errors.ResponseError(e.status, self._getErrorMessage(e), e.body)
        self.saveTarget(dataDict)
        return self.listClouds()[0]

    @classmethod
    def _getErrorCode(cls, err):
        fname = hasattr(err, 'error_code') and 'error_code' or 'code'
        return getattr(err, fname)

    @classmethod
    def _getErrorMessage(cls, err):
        fname = hasattr(err, 'error_message') and 'error_message' or 'message'
        return getattr(err, fname)

    def isDriverFunctional(self):
        return True

    def isValidCloudName(self, cloudName):
        if cloudName != 'aws':
            return False
        return baseDriver.BaseDriver.isValidCloudName(self, cloudName)

    def drvGetCredentialsFromDescriptor(self, fields):
        accountId = str(fields.getField('accountId'))
        publicAccessKeyId = str(fields.getField('publicAccessKeyId'))
        secretAccessKey = str(fields.getField('secretAccessKey'))
        return dict(accountId = accountId,
            publicAccessKeyId = publicAccessKeyId,
            secretAccessKey = secretAccessKey)

    def updateCloud(self, parameters):
        parameters = CloudParameters(parameters)
        pass

    def createUserData(self, userData):
        templ = """\
[sfcb-client-setup]
x509-cert-hash=%s
x509-cert(base64)=%s
"""
        certPath = self.getWbemClientCert()
        try:
            certData = file(certPath).read()
        except IOError:
            return userData

        certHash = self.computeX509CertHash(certPath)
        certData = base64.b64encode(certData)

        sect = templ % (certHash, certData)
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

    def launchInstanceProcess(self, job, image, auth, **launchParams):
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

        imageId = launchParams.pop('imageId')
        try:
            reservation = self.client.run_instances(imageId,
                    min_count=launchParams.get('minCount'),
                    max_count=launchParams.get('maxCount'),
                    key_name=launchParams.get('keyName'),
                    security_groups=securityGroups,
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

    def drvGetInstances(self, instanceIds):
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
        ownerId = self.getTargetConfiguration()['accountId']
        if ownerId:
            ownerIds = [ ownerId ]
        else:
            ownerIds = None
        rs = self.client.get_all_images(image_ids = imageIds, owners = ownerIds)
        # avoid returning amazon kernel images.
        rs = [ x for x in rs if x.id.startswith('ami-') ]

        imageList = images.BaseImages()
        for image in rs:
            productCodes = [ (x, EC2_DEVPAY_OFFERING_BASE_URL % x)
                for x in image.product_codes ]
            i = self._nodeFactory.newImage(id=image.id, imageId=image.id,
                                           ownerId=image.ownerId,
                                           longName=image.location,
                                           state=image.state,
                                           isPublic=image.is_public,
                                           productCode=productCodes)
            imageList.append(i)
        return imageList

    def getImageIdFromMintImage(self, imageData):
        return imageData.get('amiId')

    def addExtraImagesFromMint(self, imageList, mintImages, cloudAlias):
        pass

    def drvPopulateLaunchDescriptor(self, descr):
        descr.setDisplayName("Amazon EC2 Launch Parameters")
        descr.addDescription("Amazon EC2 Launch Parameters")
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
        imageIdToImageMap = dict((x.getImageId(), x)
            for x in self.drvGetImages(list(imageIds)))

        properties = {}
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

        productCodes = [ (x, EC2_DEVPAY_OFFERING_BASE_URL % x)
            for x in instance.product_codes ]
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
        return [ (x.name, x.regionName) for x in rs ]

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
