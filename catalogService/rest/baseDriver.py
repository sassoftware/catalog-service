#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import datetime
import os
import sys
import subprocess
import time
import traceback
import urllib
import urllib2

from conary import conaryclient
from conary import versions
from conary.deps import deps
from conary.lib import util, sha1helper

from catalogService import errors
from catalogService import instanceStore
from catalogService import nodeFactory
from catalogService import instanceStore
from catalogService import jobs
from catalogService import storage
from catalogService.rest.models import clouds
from catalogService.rest.models import cloud_types
from catalogService.rest.models import credentials
from catalogService.rest.models import descriptor
from catalogService.rest.models import images
from catalogService.rest.models import instances
from catalogService.rest.models import jobs as jobmodels
from catalogService.rest.models import keypairs
from catalogService.rest.models import securityGroups
from catalogService.utils import timeutils
from catalogService.utils import x509

from mint.mint_error import TargetExists, TargetMissing
from mint.django_rest.rbuilder import models as rbuildermodels
from mint.django_rest.rbuilder.inventory import manager
from mint.django_rest.rbuilder.inventory import models as inventorymodels

from rpath_job import api1 as rpath_job

class BaseDriver(object):
    # Enumerate the factories we support.
    CloudConfigurationDescriptor = descriptor.ConfigurationDescriptor
    CredentialsDescriptor = descriptor.CredentialsDescriptor
    Cloud            = clouds.BaseCloud
    CloudType        = cloud_types.CloudType
    Credentials      = credentials.BaseCredentials
    CredentialsField = credentials.BaseField
    CredentialsFields = credentials.BaseFields
    Image            = images.BaseImage
    Instance         = instances.BaseInstance
    InstanceUpdateStatus = instances.BaseInstanceUpdateStatus
    InstanceType     = instances.InstanceType
    KeyPair          = keypairs.BaseKeyPair
    SecurityGroup    = securityGroups.BaseSecurityGroup

    # Map descriptor field name to name in internal storage field
    _credNameMap = []
    # Map descriptor field name to name in internal storage field
    _configNameMap = []
    cloudType = None

    updateStatusStateUpdating = 'updating'
    updateStatusStateDone = 'done'
    updateStatusStateException = 'error'

    instanceStorageClass = storage.DiskStorage

    HistoryEntry = jobs.HistoryEntry

    def __init__(self, cfg, driverName, cloudName=None,
                 nodeFactory=None, userId = None, db = None):
        self.userId = userId
        self.cloudName = cloudName
        self.driverName = driverName
        self._cfg = cfg
        self._cloudClient = None
        self._cloudCredentials = None
        self.db = db
        if nodeFactory is None:
            nodeFactory = self._createNodeFactory()
        self._nodeFactory = nodeFactory
        self._nodeFactory.userId = userId
        self._logger = None
        self._instanceStore = None
        self._jobsStore = jobs.ApplianceVersionUpdateJobSqlStore(self.db)
        self._instanceLaunchJobStore = jobs.LaunchJobSqlStore(self.db)
        self._instanceUpdateJobStore = jobs.ApplianceUpdateJobSqlStore(self.db)
        self._x509Cert = None
        self._x509Key = None
        self._bootUuid = None

        self.inventoryManager = manager.Manager(cfg=self.db.cfg, userName=userId)

    def _getInstanceStore(self):
        keyPrefix = '%s/%s' % (self._sanitizeKey(self.cloudName),
                               self._getUserIdForInstanceStore())
        path = os.path.join(self._cfg.storagePath, 'instances',
            self.cloudType)
        cfg = storage.StorageConfig(storagePath = path)

        dstore = self.instanceStorageClass(cfg)
        return instanceStore.InstanceStore(dstore, keyPrefix)

    def _getUserIdForInstanceStore(self):
        return self._sanitizeKey(self.userId)

    @classmethod
    def _sanitizeKey(cls, key):
        return key.replace('/', '_')

    def setLogger(self, logger):
        self._logger = logger

    def log_debug(self, *args, **kwargs):
        if self._logger:
            return self._logger.debug(*args, **kwargs)

    def log_info(self, *args, **kwargs):
        if self._logger:
            return self._logger.info(*args, **kwargs)

    def log_error(self, *args, **kwargs):
        if self._logger:
            return self._logger.error(*args, **kwargs)

    def log_exception(self, *args, **kwargs):
        if self._logger:
            return self._logger.exception(*args, **kwargs)

    def isValidCloudName(self, cloudName):
        if self.db is None:
            return True
        self.cloudName = cloudName
        return bool(self.getTargetConfiguration())

    def __call__(self, request, cloudName=None):
        # This is a bit of a hack - basically, we're turning this class
        # into a factory w/o doing all the work of splitting out
        # a factory.  Call the instance with a request passed in, and you
        # get an instance that is specific to this particular request.
        self._nodeFactory.baseUrl = request.baseUrl
        self._nodeFactory.cloudName = cloudName
        drv =  self.__class__(self._cfg, self.driverName, cloudName,
                              self._nodeFactory,
                              userId = request.auth[0],
                              db = self.db)
        drv.setLogger(request.logger)
        drv.request = request
        return drv

    def _createNodeFactory(self):
        factory = nodeFactory.NodeFactory(
            cloudType = self.cloudType,
            cloudConfigurationDescriptorFactory = self.CloudConfigurationDescriptor,
            credentialsDescriptorFactory = self.CredentialsDescriptor,
            cloudTypeFactory = self.CloudType,
            cloudFactory = self.Cloud,
            credentialsFactory = self.Credentials,
            credentialsFieldFactory = self.CredentialsField,
            credentialsFieldsFactory = self.CredentialsFields,
            imageFactory = self.Image,
            instanceFactory = self.Instance,
            instanceUpdateStatusFactory = self.InstanceUpdateStatus,
            instanceTypeFactory = self.InstanceType,
            keyPairFactory = self.KeyPair,
            securityGroupFactory = self.SecurityGroup,
        )
        return factory

    def listClouds(self):
        self._checkAuth()
        ret = clouds.BaseClouds()
        if not self.isDriverFunctional():
            return ret
        for targetName, cloudConfig, userConfig in self._enumerateClouds():
            cloudNode = self._createCloudNode(targetName, cloudConfig)
            # RBL-4055: no longer erase launch descriptor if the credentials
            # are not set
            ret.append(cloudNode)
        return ret

    def _enumerateClouds(self):
        return self.db.targetMgr.getTargetsForUser(self.cloudType, self.userId)

    def _createCloudNode(self, cloudName, cloudConfig):
        cld = self._nodeFactory.newCloud(cloudName = cloudName,
                         description = cloudConfig['description'],
                         cloudAlias = cloudConfig['alias'])
        return cld

    def getCloud(self, cloudName):
        ret = clouds.BaseClouds()
        if not self.isDriverFunctional():
            return ret
        for cloud in self.listClouds():
            if cloud.getCloudName() == cloudName:
                ret.append(cloud)
                return ret
        return ret

    def getAllImages(self):
        return self.getImages(None)

    def getImages(self, imageIds):
        if self.client is None:
            raise errors.MissingCredentials("Target credentials not set for user")
        return self.drvGetImages(imageIds)

    def drvGetImages(self, imageIdsFilter):
        imageList = self.getImagesFromTarget(imageIdsFilter)
        imageList = self.addMintDataToImageList(imageList,
            self.RBUILDER_BUILD_TYPE)

        # now that we've grabbed all the images, we can return only the one
        # we want.  This is horribly inefficient, but neither the mint call
        # nor the grid call allow us to filter by image, at least for now
        if imageIdsFilter is None:
            # no filtering required. We'll make the filter contain everything
            imageIdsFilter = sorted(x.getImageId() for x in imageList)

        # filter the images to those requested
        imagesById = dict((x.getImageId(), x) for x in imageList)
        newImageList = images.BaseImages()
        for imageId in imageIdsFilter:
            imageId = self._imageIdInMap(imageId, imagesById)
            if imageId is None:
                continue
            newImageList.append(imagesById[imageId])
        return newImageList

    def _imageIdInMap(self, imageId, imageIdMap):
        if imageId is None:
            return None
        return (imageId in imageIdMap and imageId) or None

    def getAllInstances(self):
        return self.getInstances(None)

    def getInstances(self, instanceIds):
        if self.client is None:
            raise errors.MissingCredentials("Target credentials not set for user")
        instances = self.drvGetInstances(instanceIds)
        return instances

    @classmethod
    def _toStr(cls, obj):
        if obj is None:
            return None
        return unicode(obj).encode("utf-8")

    def _updateInventory(self, instanceId, cloudType, cloudName, x509Cert,
                         x509Key):
        self.log_info("Adding launched instance %s to system inventory. " % \
            instanceId)
        instance = self.getInstance(instanceId)
        instanceDnsName = self._toStr(instance.getPublicDnsName())
        instanceName = self._toStr(instance.getInstanceName())
        instanceDescription = self._toStr(instance.getInstanceDescription())
        instanceState = self._toStr(instance.getState())
        system = inventorymodels.System(
            target_system_id=instanceId,
            target_system_name=instanceName,
            target_system_description=instanceDescription,
            target_system_state=instanceState,
            ssl_client_certificate = x509Cert,
            ssl_client_key = x509Key,
        )
        self.inventoryManager.addLaunchedSystem(system, dnsName=instanceDnsName,
            targetType=cloudType, targetName=cloudName)
        self.log_info("System id %s added to inventory for instance %s." % \
            (system.pk, instanceId))
        return system

    def getInstance(self, instanceId, force=False):
        if self.client is None:
            raise errors.MissingCredentials("Target credentials not set for user")
        instance = self.drvGetInstance(instanceId)
        return instance

    def drvGetInstance(self, instanceId):
        ret = self.drvGetInstances([instanceId])
        if ret:
            return ret[0]
        raise errors.HttpNotFound()

    def filterInstances(self, instanceIds, instanceList):
        if not instanceIds:
            return instanceList

        instanceIds = set(os.path.basename(x) for x in instanceIds)
        ret = instances.BaseInstances()
        ret.extend(x for x in instanceList
            if x.getInstanceId() in instanceIds)
        return ret

    def drvGetCloudCredentialsForUser(self):
        """
        Authenticate the user and cache the cloud credentials
        """
        if self._cloudCredentials is None:
            self._checkAuth()
            self._cloudCredentials = self._getCloudCredentialsForUser()
        return self._cloudCredentials

    credentials = property(drvGetCloudCredentialsForUser)

    def _getCloudCredentialsForUser(self):
        return self.db.targetMgr.getTargetCredentialsForUser(self.cloudType,
            self.cloudName, self.userId)

    def drvGetCredentialsFromDescriptor(self, fields):
        ret = {}
        for field, key in self._credNameMap:
            ret[key] = str(fields.getField(field))
        return ret

    def drvGetCloudClient(self):
        """
        Authenticate the user, cache the cloud credentials and the client
        """
        if self._cloudClient is None:
            cred = self.drvGetCloudCredentialsForUser()
            if not cred:
                return None
            self._cloudClient = self.drvCreateCloudClient(cred)
            self._instanceStore = self._getInstanceStore()
        return self._cloudClient

    client = property(drvGetCloudClient)

    def drvValidateCredentials(self, creds):
        self.drvCreateCloudClient(creds)
        return True

    def drvCreateCloud(self, descriptorData):
        cloudName = self.getCloudNameFromDescriptorData(descriptorData)
        config = dict((k.getName(), k.getValue())
            for k in descriptorData.getFields())
        self.cloudName = cloudName
        self.drvVerifyCloudConfiguration(config)
        self.saveTarget(config)
        return self._createCloudNode(cloudName, config)

    @classmethod
    def getCloudNameFromDescriptorData(cls, descriptorData):
        return descriptorData.getField('name')

    def drvVerifyCloudConfiguration(self, config):
        pass

    def saveTarget(self, dataDict):
        try:
            self.db.targetMgr.addTarget(self.cloudType, self.cloudName, dataDict)
        except TargetExists:
            raise errors.CloudExists()

    def getCloudAlias(self):
        cloudConfig = self.getTargetConfiguration()
        return cloudConfig['alias']

    def _checkAuth(self):
        """rBuilder authentication"""
        if not self.db.auth.auth.authorized:
            raise errors.PermissionDenied

    def getUserCredentials(self):
        cred = self.credentials
        # XXX We should validate the credentials too
        descr = self.getCredentialsDescriptor()
        descrData = descriptor.DescriptorData(descriptor = descr)
        if not cred:
            raise errors.MissingCredentials(status = 404,
                message = "User credentials not configured")
        for descrName, localName in self._credNameMap:
            descrData.addField(descrName, value = cred[localName])
        descrData.checkConstraints()
        return self._nodeFactory.newCredentialsDescriptorData(descrData)

    def getCloudType(self):
        node = self._createCloudTypeNode(self.cloudType)
        return node

    def _createCloudTypeNode(self, cloudTypeName):
        node = self._nodeFactory.newCloudType(
            id = cloudTypeName,
            cloudTypeName = cloudTypeName)
        return node

    def getCredentialsDescriptor(self):
        descr = descriptor.ConfigurationDescriptor(
            fromStream = self.credentialsDescriptorXmlData)
        return descr

    def getCloudConfigurationDescriptor(self):
        descr = descriptor.ConfigurationDescriptor(
            fromStream = self.configurationDescriptorXmlData)
        descr = self._nodeFactory.newCloudConfigurationDescriptor(descr)
        return descr

    def getLaunchDescriptor(self):
        cred = self.credentials
        if not cred:
            raise errors.HttpNotFound(message = "User has no credentials set")
        descr = descriptor.LaunchDescriptor()
        # We require an image ID
        descr.addDataField("imageId",
            descriptions = "Image ID",
            hidden = True, required = True, type = "str",
            constraints = dict(constraintName = 'range',
                               min = 1, max = 32))

        self.drvPopulateLaunchDescriptor(descr)
        descr = self._nodeFactory.newLaunchDescriptor(descr)
        return descr

    def launchInstance(self, xmlString, auth):
        # Grab the launch descriptor
        descr = self.getLaunchDescriptor()
        descr.setRootElement('newInstance')
        # Parse the XML string into descriptor data
        descrData = descriptor.DescriptorData(fromStream = xmlString,
            descriptor = descr)
        return self.launchInstanceFromDescriptorData(descrData, auth, xmlString)

    def launchInstanceInBackground(self, jobId, image, auth, **params):
        job = self._instanceLaunchJobStore.get(jobId, commitAfterChange = True)
        job.setFields([('pid', os.getpid()), ('status', job.STATUS_RUNNING) ])
        job.addHistoryEntry('Running')
        try:
            try:
                realInstanceId = self.launchInstanceProcess(job, image, auth, **params)
                if not realInstanceId:
                    job.addHistoryEntry('Launch failed, no instance was created')
                    job.status = job.STATUS_FAILED
                    return
                # Some drivers (like ec2) may have the ability to launch
                # multiple instances with the same call.
                if not isinstance(realInstanceId, list):
                    realInstanceId = [ realInstanceId ]
                x509Cert, x509Key = self.getWbemX509()
                # Read the cert files
                x509Cert = file(x509Cert).read()
                x509Key = file(x509Key).read()
                for instanceId in realInstanceId:
                    system = self._updateInventory(instanceId, job.cloudType,
                        job.cloudName, x509Cert, x509Key)
                job.addResults(realInstanceId)
                job.addHistoryEntry('Done')
                job.system = system.pk
                job.status = job.STATUS_COMPLETED
            except errors.CatalogError, e:
                err = errors.CatalogErrorResponse(e.status,
                    message = e.msg, tracebackData = e.tracebackData,
                    productCodeData = e.productCodeData)
                job.addHistoryEntry(e.msg)
                job.setFields([('errorResponse', err.response[0]),
                    ('status', job.STATUS_FAILED)])
            except Exception, e:
                job.addHistoryEntry(str(e))
                job.status = job.STATUS_FAILED
                raise
        finally:
            job.pid = None
            job.commit()
            self.launchInstanceInBackgroundCleanup(image, **params)

    def launchInstanceInBackgroundCleanup(self, image, **params):
        self.cleanUpX509()

    def launchInstanceFromDescriptorData(self, descriptorData, auth, descrXml):
        client = self.client
        cloudConfig = self.getTargetConfiguration()

        imageId = os.path.basename(descriptorData.getField('imageId'))

        images = self.getImages([imageId])
        if not images:
            raise errors.HttpNotFound()
        image = images[0]

        params = self.getLaunchInstanceParameters(image, descriptorData)

        job = self._instanceLaunchJobStore.create(cloudName = self.cloudName,
            cloudType = self.cloudType, restArgs = descrXml,
            jobUuid = self.getBootUuid())
        job.commit()
        jobId = job.id
        launchJobRunner = CatalogJobRunner(
                                self.launchInstanceInBackground,
                                self._logger,
                                postFork=self.postFork)
        launchJobRunner.job = job
        launchJobRunner(jobId, image, auth, **params)

        newInstanceParams = self.getNewInstanceParameters(job, image,
            descriptorData, params)
        newInstanceParams['createdBy'] = self.userId
        job = jobmodels.Job(**newInstanceParams)
        return self._nodeFactory.newInstanceLaunchJob(job)

    def getLaunchInstanceParameters(self, image, descriptorData):
        getField = descriptorData.getField
        imageId = image.getImageId()
        instanceName = getField('instanceName')
        instanceName = instanceName or self.getInstanceNameFromImage(image)
        instanceDescription = getField('instanceDescription')
        instanceDescription = (instanceDescription
                               or self.getInstanceDescriptionFromImage(image)
                               or instanceName)
        return dict(
            imageId = imageId,
            instanceName = instanceName,
            instanceDescription = instanceDescription,
            instanceType = getField('instanceType'),
        )

    def getNewInstanceParameters(self, job, image, descriptorData, launchParams):
        imageId = launchParams['imageId']
        return dict(
            id = job.id,
            imageId = imageId,
            cloudName = self.cloudName,
            type_ = 'instance-launch',
            status = job.status,
        )

    def createCloud(self, cloudConfigurationData):
        # Grab the configuration descriptor
        descr = self.getCloudConfigurationDescriptor()
        # Instantiate the descriptor data
        try:
            descrData = descriptor.DescriptorData(
                fromStream = cloudConfigurationData,
                descriptor = descr)
        except descriptor.errors.InvalidXML:
            # XXX
            raise
        return self.drvCreateCloud(descrData)

    def removeCloud(self):
        cloudConfig = self.getTargetConfiguration()
        if not cloudConfig:
            # Cloud does not exist
            raise errors.InvalidCloudName(self.cloudName)
        self.drvRemoveCloud()
        return clouds.BaseClouds()

    def drvRemoveCloud(self):
        try:
            self.db.targetMgr.deleteTarget(self.cloudType, self.cloudName)
        except TargetMissing:
            pass

    def setUserCredentials(self, credentialsData):
        # Authenticate
        _ = self.credentials

        # Grab the configuration descriptor
        descr = self.getCredentialsDescriptor()
        # Instantiate the descriptor data
        try:
            descrData = descriptor.DescriptorData(
                fromStream = credentialsData,
                descriptor = descr)
        except descriptor.errors.InvalidXML:
            # XXX
            raise
        creds = self.drvGetCredentialsFromDescriptor(descrData)
        if not self.drvValidateCredentials(creds):
            raise errors.PermissionDenied(
                message = "The supplied credentials are invalid")
        self._setUserCredentials(creds)
        return self._nodeFactory.newCredentials(valid = True)

    def _setUserCredentials(self, creds):
        self.db.targetMgr.setTargetCredentialsForUser(
            self.cloudType, self.cloudName, self.userId, creds)

    def getConfiguration(self):
        # Authenticate
        _ = self.credentials

        # Grab the configuration descriptor
        descr = self.getCloudConfigurationDescriptor()
        descrData = descriptor.DescriptorData(descriptor = descr)

        cloudConfig = self.getTargetConfiguration(isAdmin = True)
        kvlist = []
        for k, v in cloudConfig.items():
            df = descr.getDataField(k)
            if df is None:
                continue
            # We add all field names and values to the list first, so we can
            # sort them after adding the extra maps
            kvlist.append((k, v))
        for field, k in self._configNameMap:
            kvlist.append((field, cloudConfig.get(k)))
        kvlist.sort()

        for k, v in kvlist:
            descrData.addField(k, value = v, checkConstraints=False)
        return self._nodeFactory.newCloudConfigurationDescriptorData(descrData)

    def getTargetConfiguration(self, isAdmin = False):
        if not self.db:
            return {}
        if isAdmin and not self.db.auth.auth.admin:
            raise errors.PermissionDenied("Permission Denied - user is not adminstrator")
        try:
            targetData = self.db.targetMgr.getTargetData(self.cloudType,
                                                         self.cloudName)
        except TargetMissing:
            targetData = {}

        return self.drvGetTargetConfiguration(targetData, isAdmin = isAdmin)

    def drvGetTargetConfiguration(self, targetData, isAdmin = False):
        if not targetData:
            return targetData
        # Add the target name, we don't have to persist it in the target data
        # section
        targetData['name'] = self.cloudName
        return targetData

    def getInstanceNameFromImage(self, imageNode):
        if imageNode is None:
            return None
        for method in [ imageNode.getBuildName, imageNode.getProductName,
                        imageNode.getShortName ]:
            val = method()
            if val is not None:
                return val
        return None

    def extractImage(self, path):
        if path.endswith('.zip'):
            workdir = path[:-4]
            util.mkdirChain(workdir)
            cmd = 'unzip -d %s %s' % (workdir, path)
        elif path.endswith('.tgz'):
            workdir = path[:-4]
            util.mkdirChain(workdir)
            cmd = 'tar zxSf %s -C %s' % (path, workdir)
        else:
            raise errors.CatalogError('unsupported rBuilder image archive format')
        p = subprocess.Popen(cmd, shell = True, stderr = file(os.devnull, 'w'))
        p.wait()
        return workdir

    @classmethod
    def downloadFile(cls, url, destFile, headers = None):
        """Download the contents of the url into a file"""
        req = urllib2.Request(url, headers = headers or {})
        resp = urllib2.urlopen(req)
        if resp.headers['Content-Type'].startswith("text/html"):
            # We should not get HTML content out of rbuilder - most likely
            # a private project to which we don't have access
            raise errors.DownloadError("Unable to download file")
        util.copyfileobj(resp, file(destFile, 'w'))

    def _downloadImage(self, image, tmpDir, auth = None, extension = '.tgz'):
        imageId = image.getImageId()

        downloadUrl = image.getDownloadUrl()
        imageId = os.path.basename(image.getId())
        downloadFilePath = os.path.join(tmpDir, '%s%s' % (imageId, extension))

        headers = {}
        if image.getIsPrivate_rBuilder() and auth:
            # We need to acquire a pysid cookie
            netloc = urllib2.urlparse.urlparse(downloadUrl)[1]
            # XXX we don't allow for weird port numbers
            host, port = urllib.splitnport(netloc)
            pysid = CookieClient(host, auth[0], auth[1]).getCookie()
            if pysid is not None:
                headers['Cookie'] = pysid
            # If we could not fetch the pysid, we'll still try to download
        self.downloadFile(downloadUrl, downloadFilePath, headers = headers)
        return downloadFilePath

    def getInstanceDescriptionFromImage(self, imageNode):
        if imageNode is None:
            return None
        for method in [ imageNode.getBuildDescription,
                        imageNode.getProductDescription, ]:
            val = method()
            if val is not None:
                return val
        return None

    def postFork(self):
        # Force the client to reopen the connection to the cloud
        self._cloudClient = None
        # We need to reopen the db, so we don't share a cursor with the parent
        # process
        self.db.db.reopen_fork()

    def _getMintImagesByType(self, imageType):
        return self.db.imageMgr.getAllImagesByType(imageType)

    def addMintDataToImageList(self, imageList, imageType):
        cloudAlias = self.getCloudAlias()

        mintImages = self._getMintImagesByType(imageType)
        # Convert the list into a map keyed on the sha1 converted into
        # uuid format
        mintImages = dict((self.getImageIdFromMintImage(x), x) for x in mintImages)

        for image in imageList:
            imageId = image.getImageId()
            mintImageData = mintImages.pop(imageId, {})
            image.setIs_rBuilderImage(bool(mintImageData))
            image.setIsDeployed(True)
            if not mintImageData:
                continue
            self.addImageDataFromMintData(image, mintImageData,
                images.buildToNodeFieldMap)

        self.addExtraImagesFromMint(imageList, mintImages.iteritems(),
            cloudAlias)
        return imageList

    @classmethod
    def getImageIdFromMintImage(cls, image):
        files = image.get('files', [])
        if not files:
            return None
        return files[0]['sha1']

    @classmethod
    def addImageDataFromMintData(cls, image, mintImageData, methodMap):
        imageFiles = mintImageData.get('files', [])
        baseFileName = mintImageData.get('baseFileName')
        buildId = mintImageData.get('buildId')
        if baseFileName:
            shortName = os.path.basename(baseFileName)
            longName = "%s/%s" % (buildId, shortName)
            image.setShortName(shortName)
            image.setLongName(longName)
            image.setBaseFileName(baseFileName)
        # XXX this overly simplifies the fact that there may be more than one
        # file associated with a build
        if imageFiles:
            image.setDownloadUrl(imageFiles[0].get('downloadUrl'))
        image.setBuildPageUrl(mintImageData.get('buildPageUrl'))
        image.setBuildId(buildId)

        for key, methodName in methodMap.iteritems():
            value = mintImageData.get(key)
            if isinstance(value, str):
                value = value.decode('utf-8')
            getattr(image, methodName)(value)

    def addExtraImagesFromMint(self, imageList, mintImages, cloudAlias):
        # Add the rest of the images coming from mint
        for uuid, mintImageData in sorted(mintImages):
            image = self._nodeFactory.newImage(id=uuid,
                    imageId=uuid, isDeployed=False,
                    is_rBuilderImage=True,
                    cloudName=self.cloudName,
                    cloudAlias=cloudAlias)
            self.addImageDataFromMintData(image, mintImageData,
                images.buildToNodeFieldMap)
            imageList.append(image)

    def getWbemClientCert(self):
        return self.getWbemX509()[0]

    def getWbemX509(self):
        if self._x509Cert:
            # Already generated for this instance
            return self._x509Cert, self._x509Key
        certDir = os.path.join(self._cfg.storagePath, 'x509')
        self._x509Cert, self._x509Key = self.newX509(certDir)
        return self._x509Cert, self._x509Key

    def getBootUuid(self):
        if self._bootUuid is None:
            self._bootUuid = self._getBootUuid()
        return self._bootUuid

    def _getBootUuid(self):
        return self.uuidgen()

    def cleanUpX509(self):
        if not self._x509Cert:
            return
        certs = self.getWbemX509()
        for c in certs:
            try:
                os.unlink(c)
            except OSError:
                pass

    def computeX509CertHash(self, certFile):
        return x509.X509.computeHash(certFile)

    def newX509(self, certDir):
        netloc = urllib2.urlparse.urlparse(self._nodeFactory.baseUrl)[1]
        host, port = urllib.splitnport(netloc)

        byteCount = 4
        ident = ("%02x" * byteCount) % tuple(ord(x)
            for x in file('/dev/urandom').read(byteCount))
        commonName = 'Client certificate for %s, id: %s' % (host, ident)
        util.mkdirChain(certDir)
        return x509.X509.new(commonName, certDir = certDir)

    def getCredentialsIsoFile(self):
        certFile = self.getWbemClientCert()
        certDir = os.path.dirname(certFile)
        util.mkdirChain(certDir)
        isoDir = os.path.join(self._cfg.storagePath, 'credentials')
        util.mkdirChain(isoDir)
        fd, isoFile = x509.tempfile.mkstemp(dir = isoDir,
             prefix = 'credentials-', suffix = '.iso')
        os.close(fd)

        # Create an empty file for our signature
        empty = os.path.join(certDir, "EMPTY")
        file(empty, "w")

        # Load the cert, we need the hash
        certHash = self.computeX509CertHash(certFile)

        bootUuidFile = x509.tempfile.NamedTemporaryFile()
        bootUuidFile.write(self.getBootUuid())
        bootUuidFile.flush()

        # Make ISO, if it doesn't exist already
        cmd = [ "/usr/bin/mkisofs", "-r", "-J", "-graft-points",
            "-o", isoFile,
            "SECURITY-CONTEXT-BOOTSTRAP=%s" % empty,
            "etc/sfcb/clients/%s.0=%s" % (certHash, certFile),
            "etc/conary/rpath-tools/boot-uuid=%s" % bootUuidFile.name,
        ]

        devnull = file(os.devnull, "w")
        p = subprocess.Popen(cmd, shell = False, stdout=devnull,
            stderr = devnull)
        p.wait()
        return isoFile

    @classmethod
    def utctime(cls, timestr, timeFormat = None):
        if timeFormat is None:
            timeFormat = "%Y-%m-%dT%H:%M:%S.000Z"
        return timeutils.utctime(timestr, timeFormat)

    @classmethod
    def _uuid(cls, s):
        return '-'.join((s[:8], s[8:12], s[12:16], s[16:20], s[20:32]))

    @classmethod
    def uuidgen(cls):
        hex = sha1helper.md5ToString(sha1helper.md5String(os.urandom(128)))
        return cls._uuid(hex)

    class ProbeHostError(Exception):
        pass

class CookieClient(object):
    def __init__(self, server, username, password):
        self.server = server
        self.username = username
        self.password = password

        self.opener = urllib2.OpenerDirector()
        self.opener.add_handler(urllib2.HTTPSHandler())
        self.opener.add_handler(urllib2.HTTPHandler())
        self._cookie = None

    def getCookie(self):
        if self._cookie is not None:
            return self._cookie

        loginUrl = "https://%s/processLogin" % self.server
        data = urllib.urlencode([
            ('username', self.username),
            ('password', self.password),
            ('rememberMe', "1"),
            ('to', urllib.quote('http://%s/' % self.server)),
        ])
        ret = self.makeRequest(loginUrl, data, {})
        cookie = ret.headers.get('set-cookie')
        if not cookie or not cookie.startswith('pysid'):
            return None
        self._cookie = cookie.split(';', 1)[0]
        return self._cookie

    def makeRequest(self, loginUrl, data, headers):
        req = urllib2.Request(loginUrl, data = data, headers = headers)
        ret = self.opener.open(req)
        # Junk the response
        ret.read()
        return ret

class CatalogJobRunner(rpath_job.BackgroundRunner):
    def __init__(self, function, logger=None, preFork=None, postFork=None):
        self.logger = logger
        self._preFork = preFork
        self._postFork = postFork
        rpath_job.BackgroundRunner.__init__(self, function)

    def preFork(self):
        from django import db
        db.close_connection()
        if self._preFork is None:
            return None
        return self._preFork()

    def postFork(self):
        if self._postFork is None:
            return None
        return self._postFork()

    def log_error(self, msg, ei):
        if self.logger is not None:
            self.logger.error(msg)
            self.logger.error(str(ei[0]))
            self.logger.error(str(ei[1]))
            self.logger.error(''.join(traceback.format_tb(ei[2])))

    def handleError(self, ei):
        self.job.addHistoryEntry(str(ei[0]))
        self.job.addHistoryEntry(str(ei[1]))
        self.job.addHistoryEntry(''.join(traceback.format_tb(ei[2])))
        self.job.status = self.job.STATUS_FAILED
        self.job.commit()
