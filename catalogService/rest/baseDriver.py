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


import os
import subprocess
import tarfile
import tempfile
import time
import traceback
import urllib
import urllib2
import weakref
import gzip
from StringIO import StringIO

from conary.lib import magic, util, sha1helper

from catalogService import errors
from catalogService import instanceStore
from catalogService import nodeFactory as nodeFactoryMod
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
from catalogService.utils.progress import StreamWithProgress, PercentageCallback

from mint.mint_error import TargetExists, TargetMissing

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
    Instances        = instances.BaseInstances
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

    # Timeout for waiting for an instance to show up as running
    LAUNCH_TIMEOUT = 600
    LAUNCH_NETWORK_TIMEOUT = 1200 # windows reboots, etc.
    PENDING_STATES = set([ 'pending' ])
    RUNNING_STATES = set([ 'running' ])
    FAILED_STATES = set([ 'terminated' ])
    WAIT_RUNNING_STATE_SLEEP = 2
    WAIT_NETWORK_SLEEP = 10

    ImageDownloadUrlMapFile = "/srv/rbuilder/imageDownloadUrlMap"

    def __init__(self, cfg, driverName=None, cloudName=None,
                 nodeFactory=None, userId = None, db = None,
                 inventoryHandler=None,
                 zoneAddresses=None):
        if driverName is None:
            driverName = self.__class__.__module__.rsplit('.', 2)[-2]
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
        self._instanceLaunchJobStore = jobs.LaunchJobSqlStore(self.db)
        self._imageDeploymentJobStore = jobs.DeployImageJobSqlStore(self.db)
        self._instanceUpdateJobStore = jobs.ApplianceUpdateJobSqlStore(self.db)
        self._x509Cert = None
        self._x509Key = None
        self._bootUuid = None
        self._rootSshKeys = None
        self._targetConfig = None

        if inventoryHandler is None:
            inventoryHandler = self.InventoryHandler(weakref.ref(self))
        self.inventoryHandler = inventoryHandler
        self.zoneAddresses = zoneAddresses
        self._postInit()

    class InventoryHandler(object):
        """
        Interface to the rbuilder inventory service, replaced in case of rmake3
        """
        def __init__(self, parent):
            self.parent = parent
            self.cloudType = parent().cloudType
            self.cloudName = parent().cloudName
            from mint.django_rest.rbuilder.manager import rbuildermanager
            self.inventoryManager = rbuildermanager.RbuilderManager(
                cfg=parent().db.cfg,
                userName=parent().userId)

        @property
        def log_info(self):
            return self.parent().log_info

        def addSystem(self, systemFields, dnsName=None, withNetwork=True):
            from mint.django_rest.rbuilder.inventory import models as inventorymodels
            system = inventorymodels.System(**systemFields)
            self.inventoryManager.addLaunchedSystem(system, dnsName=dnsName,
                targetType=self.cloudType, targetName=self.cloudName)
            self.log_info("System id %s added to inventory for instance %s." % \
                (system.pk, system.target_system_id))

        def reset(self):
            pass

        def commit(self):
            pass

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

    def _postInit(self):
        pass

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

    @classmethod
    def isDriverFunctional(cls):
        return True

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
                              db = self.db, zoneAddresses=self.zoneAddresses)
        drv.setLogger(request.logger)
        drv.request = request
        return drv

    def _createNodeFactory(self):
        factory = nodeFactoryMod.NodeFactory(
            cloudName = self.cloudName,
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
            baseUrl = '',
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
        # The image identifiers in the filter may not match exactly the
        # image IDs from the target, so we need to fetch everything
        # here.
        imageList = self.getImagesFromTarget(None)
        imageList = self.addMintDataToImageList(imageList,
            self.RBUILDER_BUILD_TYPE)
        return self.filterImages(imageIdsFilter, imageList)

    def filterImages(self, imageIdsFilter, imageList):
        if imageIdsFilter is None:
            # no filtering required. We'll make the filter contain everything
            imageIdsFilter = sorted(str(x.getImageId()) for x in imageList)

        # filter the images to those requested
        imagesById = self._ImageMap(imageList)
        newImageList = images.BaseImages()
        for imageId in imageIdsFilter:
            img = imagesById.get(imageId)
            if img is None:
                continue
            newImageList.append(img)
        return newImageList

    class _ImageMap(object):
        def __init__(self, imageList):
            self._ids = dict((str(x.getImageId()), x) for x in imageList)
            self._ids.update((x._targetImageId, x) for x in imageList
                if getattr(x, '_targetImageId', None))

        def get(self, imageId):
            return self._ids.get(imageId)

    def getAllInstances(self):
        return self.getInstances(None)

    def getInstances(self, instanceIds):
        if self.client is None:
            raise errors.MissingCredentials("Target credentials not set for user")
        instances = self.drvGetInstances(instanceIds)
        return instances

    def _msg(self, job, msg):
        job.addHistoryEntry(msg)
        self.log_debug(msg)

    @classmethod
    def _toStr(cls, obj):
        if obj is None:
            return None
        return unicode(obj).encode("utf-8")

    def updateInventory(self, instanceIdList, x509Cert,
                        x509Key, launchParams, sourceImage, withNetwork=True):
        self.inventoryHandler.reset()
        for instanceId in instanceIdList:
            self._updateInventory(instanceId, x509Cert,
                x509Key, launchParams, sourceImage,
                withNetwork=withNetwork)
            self.inventoryHandler.commit()

    def _updateInventory(self, instanceId, x509Cert, x509Key,
                         launchParams, sourceImage, withNetwork=True):
        self.log_info("Adding launched instance %s to system inventory. " % \
            instanceId)
        instance = self.getInstance(instanceId)
        instanceDnsName = self._toStr(instance.getPublicDnsName())
        systemName = self._toStr(launchParams['instanceName'])
        systemDescription = self._toStr(launchParams['instanceDescription'])
        instanceName = self._toStr(instance.getInstanceName())
        instanceDescription = self._toStr(instance.getInstanceDescription())
        instanceState = self._toStr(instance.getState())

        systemFields = dict(
            name=systemName,
            description=systemDescription,
            target_system_id=instanceId,
            target_system_name=instanceName,
            target_system_description=instanceDescription,
            target_system_state=instanceState,
            ssl_client_certificate = x509Cert,
            ssl_client_key = x509Key,
            source_image_id = sourceImage.getBuildId(),
            boot_uuid = self.getBootUuid(),
        )
        self.inventoryHandler.addSystem(systemFields,
            dnsName=instanceDnsName, withNetwork=True)

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
            self._cloudCredentials = self.protectCredentials(
                self._getCloudCredentialsForUser())
        return self._cloudCredentials

    credentials = property(drvGetCloudCredentialsForUser)

    def protectCredentials(self, credentials):
        cm = dict(self._credNameMap)
        ret = {}
        for field in self.getCredentialsDescriptor().getDataFields():
            fieldName = field.name
            key = cm.get(fieldName, fieldName)
            if key not in credentials:
                continue
            value = credentials[key]
            if not field.password or value is None:
                ret[key] = value
            else:
                ret[key] = descriptor.ProtectedUnicode(value)
        return ret

    def _getCloudCredentialsForUser(self):
        return self.db.targetMgr.getTargetCredentialsForUser(self.cloudType,
            self.cloudName, self.userId)

    def drvGetCredentialsFromDescriptor(self, descrData):
        cm = dict(self._credNameMap)
        ret = {}
        for field in descrData.getFields():
            fieldName = field.getName()
            key = cm.get(fieldName, fieldName)
            ret[key] = str(field.getValue())
        return ret

    def reset(self):
        self._cloudClient = None
        self._cloudCredentials = None
        self._bootUuid = None
        self._x509Cert = None
        self._x509Key = None

    def drvGetCloudClient(self):
        """
        Authenticate the user, cache the cloud credentials and the client
        """
        if self._cloudClient is None:
            cred = self.drvGetCloudCredentialsForUser()
            if not cred:
                return None
            self._cloudClient = self.drvCreateCloudClient(cred)
        return self._cloudClient

    client = property(drvGetCloudClient)

    def drvValidateCredentials(self, creds):
        self.drvCreateCloudClient(creds)
        return True

    def drvCreateCloud(self, descriptorData):
        cloudName = self.getCloudNameFromDescriptorData(descriptorData)
        self.cloudName = cloudName
        config = self.getTargetConfigFromDescriptorData(descriptorData)
        self.drvVerifyCloudConfiguration(config)
        self.saveTarget(config)
        return self._createCloudNode(cloudName, config)

    @classmethod
    def getTargetConfigFromDescriptorData(cls, descriptorData):
        config = dict((k.getName(), k.getValue())
            for k in descriptorData.getFields())
        ret = dict()
        for descriptorFieldName, configFieldName in cls._configNameMap:
            descrFieldData = config.pop(descriptorFieldName)
            ret[configFieldName] = descrFieldData
        # The rest of the descriptor fields go in unchanged
        ret.update(config)
        return ret

    @classmethod
    def getCloudNameFromDescriptorData(cls, descriptorData):
        return descriptorData.getField('name')

    def drvVerifyCloudConfiguration(self, config):
        pass

    @classmethod
    def _strip(cls, obj):
        if not isinstance(obj, basestring):
            return obj
        return obj.strip()

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
        cm = dict(self._credNameMap)
        for descrField in descr.getDataFields():
            descrName = descrField.name
            localName = cm.get(descrName, descrName)
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
        descr = self._nodeFactory.newCloudConfigurationDescriptor(descr)
        return descr

    def getCloudConfigurationDescriptor(self):
        descr = descriptor.ConfigurationDescriptor(
            fromStream = self.configurationDescriptorXmlData)
        descr = self._nodeFactory.newCloudConfigurationDescriptor(descr)
        return descr

    def getLaunchDescriptor(self, extraArgs=None):
        cred = self.credentials
        if not cred:
            raise errors.HttpNotFound(message = "User has no credentials set")
        descr = descriptor.LaunchDescriptor()
        descr.setRootElement('newInstance')
        # We require an image ID
        descr.addDataField("imageId",
            descriptions = "Image ID",
            hidden = True, required = True, type = "str",
            constraints = dict(constraintName = 'range',
                               min = 1, max = 32))

        self.drvPopulateLaunchDescriptor(descr, extraArgs=extraArgs)
        descr = self._nodeFactory.newLaunchDescriptor(descr)
        return descr

    def getImageDeploymentDescriptor(self, extraArgs=None):
        cred = self.credentials
        if not cred:
            raise errors.HttpNotFound(message = "User has no credentials set")
        descr = descriptor.LaunchDescriptor()
        descr.setRootElement('newImage')
        # We require an image ID
        descr.addDataField("imageId",
            descriptions = "Image ID",
            hidden = True, required = True, type = "str",
            constraints = dict(constraintName = 'range',
                               min = 1, max = 32))

        self.drvPopulateImageDeploymentDescriptor(descr, extraArgs=extraArgs)
        descr = self._nodeFactory.newLaunchDescriptor(descr)
        return descr

    def drvPopulateImageDeploymentDescriptor(self, descr, extraArgs=None):
        # By default, image deployment does not work
        raise errors.HttpNotFound()

    def drvLaunchDescriptorCommonFields(self, descr):
        descr.addDataField('instanceName',
                           descriptions = 'Instance Name',
                           type = 'str',
                           required = True,
                           help = [
                               ('launch/instanceName.html', None)
                           ],
                           constraints = dict(constraintName = 'length',
                                              value = 32))

        descr.addDataField('instanceDescription',
                           descriptions = 'Instance Description',
                           type = 'str',
                           help = [
                               ('launch/instanceDescription.html', None)
                           ],
                           constraints = dict(constraintName = 'length',
                                              value = 128))
        return descr

    def drvImageDeploymentDescriptorCommonFields(self, descr):
        descr.addDataField('imageName',
                           descriptions = 'Image Name',
                           type = 'str',
                           required = True,
                           help = [
                               ('launch/imageName.html', None)
                           ],
                           # RCE-1781; image names can be up to 80
                           # chars, leave a few chars to add -1 at the
                           # end
                           constraints = dict(constraintName = 'length',
                                              value = 76))

        descr.addDataField('imageDescription',
                           descriptions = 'Image Description',
                           type = 'str',
                           help = [
                               ('launch/imageDescription.html', None)
                           ],
                           constraints = dict(constraintName = 'length',
                                              value = 128))
        return descr

    class ImageData(object):
        __slots__ = []
        def __init__(self, **kwargs):
            for slot in self.__slots__:
                setattr(self, slot, kwargs.get(slot))

    def _getImageData(self, extraArgs):
        if extraArgs is None:
            imageDataDict = {}
        else:
            imageDataDict = extraArgs.get('imageData', {})
        return self.ImageData(**imageDataDict)

    def deployImage(self, xmlString, auth):
        # Grab descriptor
        descr = self.getImageDeploymentDescriptor()
        # Parse the XML string into descriptor data
        descrData = descriptor.DescriptorData(fromStream = xmlString,
            descriptor = descr)
        return self.deployImageFromDescriptorData(descrData, auth, xmlString)

    def imageFromFileInfo(self, imageFileInfo, imageDownloadUrl,
            imageData=None):
        imageId = imageFileInfo['fileId']
        image = self._nodeFactory.newImage(id=imageId,
            imageId=imageId, isDeployed=False,
            buildId=imageId,
            is_rBuilderImage=True,
            cloudName=self.cloudName)
        self.updateImageFromFileInfo(image, imageFileInfo,
                imageDownloadUrl, imageData=imageData)
        return image

    def updateImageFromFileInfo(self, image, imageFileInfo,
            imageDownloadUrl=None, imageData=None):
        image.setBaseFileName(imageFileInfo['baseFileName'])
        image.setChecksum(imageFileInfo.get('sha1'))
        image.setSize(imageFileInfo.get('size'))
        image.setArchitecture(imageFileInfo.get('architecture'))
        image.setDownloadUrl(imageDownloadUrl)
        image._fileId = imageFileInfo['fileId']
        image._imageData = imageData
        return image

    def deployImageFromUrl(self, job, image, descriptorDataXml):
        """Only invoked via rmake"""
        # Grab descriptor
        descr = self.getImageDeploymentDescriptor(
                extraArgs=dict(imageData=image._imageData))
        descr.setRootElement("descriptor_data")
        # Parse the XML string into descriptor data
        descriptorData = descriptor.DescriptorData(
            fromStream=descriptorDataXml, descriptor=descr)

        params = self.getDeployImageParameters(image, descriptorData)
        self.deployImageProcess(job, image, auth=None, **params)
        return image

    def launchSystemSynchronously(self, job, image, descriptorDataXml):
        """Only invoked via rmake"""
        # Grab descriptor
        descr = self.getLaunchDescriptor(
                extraArgs=dict(imageData=image._imageData))
        descr.setRootElement("descriptor_data")
        # Parse the XML string into descriptor data
        descriptorData = descriptor.DescriptorData(
            fromStream=descriptorDataXml, descriptor=descr)

        params = self.getLaunchInstanceParameters(image, descriptorData)
        instanceIdList = self.launchInstanceWrapper(job, image, auth=None, **params)
        return instanceIdList


    def launchInstance(self, xmlString, auth):
        # Grab the launch descriptor
        descr = self.getLaunchDescriptor()
        # Parse the XML string into descriptor data
        descrData = descriptor.DescriptorData(fromStream = xmlString,
            descriptor = descr)
        return self.launchInstanceFromDescriptorData(descrData, auth, xmlString)

    def launchInstanceWrapper(self, *args, **kwargs):
        try:
            return self._launchInstanceWrapper(*args, **kwargs)
        finally:
            self.cleanUpX509()

    def _launchInstanceWrapper(self, job, image, auth, **launchParams):
        realInstanceId = self.launchInstanceProcess(job, image, auth,
            **launchParams)
        if not realInstanceId:
            job.addHistoryEntry('Launch failed, no instance was created')
            return
        # Some drivers (like ec2) may have the ability to launch
        # multiple instances with the same call.
        instanceIdList = realInstanceId
        if not isinstance(instanceIdList, list):
            instanceIdList = [ instanceIdList ]
        x509Cert, x509Key = self.getWbemX509()
        # Read the cert files
        x509Cert = file(x509Cert).read()
        x509Key = file(x509Key).read()
        self.updateInventory(instanceIdList, x509Cert, x509Key, launchParams,
            image, withNetwork=True)
        self.waitForRunningState(job, instanceIdList)
        self.waitForNetwork(job, instanceIdList)
        self.updateInventory(instanceIdList, x509Cert, x509Key, launchParams,
            image, withNetwork=False)
        return instanceIdList

    def launchInstanceInBackground(self, jobId, image, auth, **params):
        job = self._instanceLaunchJobStore.get(jobId, commitAfterChange = True)
        job.setFields([('pid', os.getpid()), ('status', job.STATUS_RUNNING) ])
        self._msg(job, "Launching instance from image %s (type %s)" % (
            image.getImageId(), image._imageType))
        try:
            try:
                instanceIds = self._launchInstanceWrapper(job, image, auth, **params)
                if instanceIds is None:
                    job.status = job.STATUS_FAILED
                    return
                job.addResults(instanceIds)
                job.addHistoryEntry('Done')
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

    def deployImageInBackground(self, jobId, image, auth, **params):
        job = self._imageDeploymentJobStore.get(jobId, commitAfterChange = True)
        job.setFields([('pid', os.getpid()), ('status', job.STATUS_RUNNING) ])
        job.addHistoryEntry('Running')
        try:
            try:
                realImageId = self.deployImageProcess(job, image, auth, **params)
                if not realImageId:
                    job.addHistoryEntry('Image deployment failed, no image was uploaded')
                    job.status = job.STATUS_FAILED
                    return
                if not isinstance(realImageId, list):
                    realImageId = [realImageId]
                job.addResults(realImageId)
                job.addHistoryEntry('Done')
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
            self.deployImageInBackgroundCleanup(image, **params)

    def waitForRunningState(self, job, instanceIds):
        # Wait until all instances get out of the PENDING state
        expired = time.time() + self.LAUNCH_TIMEOUT
        first = True
        while time.time() < expired:
            instances = self.drvGetInstances(instanceIds, force=True)
            states = set(x.getState().lower() for x in instances)
            instanceIds = sorted(x.getInstanceId() for x in instances)
            msg = ', '.join(instanceIds)
            if not states.intersection(self.PENDING_STATES):
                self._msg(job, "Instance(s) running: %s" % msg)
                return
            if first:
                self._msg(job, "Instance(s): %s" % msg)
                first = False
            else:
                self._msg(job, "Waiting for a running state...")
            time.sleep(self.WAIT_RUNNING_STATE_SLEEP)
        results = [ (x.getInstanceId(), x.getState()) for x in instances ]
        msg = '; '.join("Instance %s state: %s" % r for r in results)
        self._msg(job, msg)

    def waitForNetwork(self, job, instanceIds):
        # Wait until all instances have a network
        expired = time.time() + self.LAUNCH_NETWORK_TIMEOUT
        while time.time() < expired:
            instances = self.drvGetInstances(instanceIds, force=True)
            imaps = [ (x, x.getPublicDnsName()) for x in instances ]
            withNetworks = [ x for (x, y) in imaps if y is not None ]
            withoutNetworks = [ x for (x, y) in imaps if y is None ]
            for inst in withNetworks:
                self._msg(job, "Instance %s: %s" % (
                    inst.getInstanceId(), inst.getPublicDnsName()))
            if not withoutNetworks:
                return
            instanceIds = sorted(x.getInstanceId() for x in withoutNetworks)
            msg = ', '.join(instanceIds)
            self._msg(job, "Waiting for network information for %s" % msg)
            time.sleep(self.WAIT_NETWORK_SLEEP)

    def launchInstanceInBackgroundCleanup(self, image, **params):
        self.cleanUpX509()

    def deployImageInBackgroundCleanup(self, image, **params):
        pass

    def deployImageFromDescriptorData(self, descriptorData, auth, descrXml):
        client = self.client
        cloudConfig = self.getTargetConfiguration()

        imageId = os.path.basename(descriptorData.getField('imageId'))

        images = self.getImages([imageId])
        if not images:
            raise errors.HttpNotFound()
        image = images[0]

        params = self.getDeployImageParameters(image, descriptorData)

        job = self._imageDeploymentJobStore.create(cloudName = self.cloudName,
            cloudType = self.cloudType, restArgs = descrXml,
            jobUuid = self.getBootUuid())
        job.commit()
        jobId = job.id
        launchJobRunner = CatalogJobRunner(
                                self.deployImageInBackground,
                                self._logger,
                                postFork=self.postFork)
        launchJobRunner.job = job
        launchJobRunner(jobId, image, auth, **params)

        newImageParams = self.getNewImageParameters(job, image,
            descriptorData, params)
        newImageParams['createdBy'] = self.userId
        job = jobmodels.Job(**newImageParams)
        return self._nodeFactory.newImageDeploymentJob(job)

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
        params = self._descriptorDataAsDict(descriptorData)
        if params.get('instanceName') is None:
            params['instanceName'] = self.getInstanceNameFromImage(image)
        if params.get('instanceDescription') is None:
            params['instanceDescription'] = self.getInstanceDescriptionFromImage(image) or params['instanceName']
        # Make sure we use the right image id
        params.update(imageId = image.getImageId())
        return params

    def getDeployImageParameters(self, image, descriptorData):
        params = self._descriptorDataAsDict(descriptorData)
        # Make sure we use the right image id
        params.update(imageId = image.getImageId())
        return params

    @classmethod
    def _descriptorDataAsDict(cls, descriptorData):
        params = {}
        fields = descriptorData.getFields()
        for field in fields:
            if hasattr(field, 'getValue'):
                fieldName = field.getName()
                params[fieldName] = field.getValue()
            else:
                fieldName = field._nodeDescriptor.name
                vals = params[fieldName] = []
                vals.extend(cls._descriptorDataAsDict(x) for x in field)
        return params

    def getNewInstanceParameters(self, job, image, descriptorData, launchParams):
        imageId = launchParams['imageId']
        return dict(
            id = job.id,
            imageId = imageId,
            cloudName = self.cloudName,
            type_ = 'instance-launch',
            status = job.status,
        )

    def getNewImageParameters(self, job, image, descriptorData, launchParams):
        ret = self.getNewInstanceParameters(job, image, descriptorData, launchParams)
        ret.update(type_='image-deployment')
        return ret

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

        validFields = set(x.name for x in descr.getDataFields())
        for k, v in sorted(cloudConfig.items()):
            if k not in validFields:
                continue
            descrData.addField(k, value = v, checkConstraints=False)
        return self._nodeFactory.newCloudConfigurationDescriptorData(descrData)

    def _getStoredTargetConfiguration(self):
        try:
            targetData = self.db.targetMgr.getTargetData(self.cloudType,
                                                         self.cloudName)
        except TargetMissing:
            targetData = {}

        targetData = self.remapTargetConfigurationFields(targetData)
        return targetData

    @classmethod
    def remapTargetConfigurationFields(cls, targetConfig):
        ret = targetConfig.copy()
        undef = object()
        for nameDescr, nameDb in cls._configNameMap:
            val = ret.pop(nameDb, undef)
            if val is undef:
                continue
            ret[nameDescr] = val
        return ret

    def getTargetConfiguration(self, isAdmin = False, forceAdmin = False):
        # We can't set both isAdmin and forceAdmin at the same time
        assert int(bool(isAdmin)) + int(bool(forceAdmin)) != 2
        if not self.db:
            return {}
        if isAdmin and not self.db.auth.auth.admin:
            raise errors.PermissionDenied("Permission Denied - user is not adminstrator")
        if not forceAdmin and bool(self._targetConfig):
            return self._targetConfig
        targetData = self._getStoredTargetConfiguration()

        # If we force admin, don't pollute _targetConfig
        ret = self.drvGetTargetConfiguration(targetData,
            isAdmin = (isAdmin or forceAdmin))
        if not forceAdmin:
            self._targetConfig = ret
        return ret

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

    def linkTargetImageToImage(self, image):
        targetImageId = image.getImageId()
        rbuilderImageId = image._fileId
        self.db.targetMgr.linkTargetImageToImage(self.cloudType,
            self.cloudName, rbuilderImageId, targetImageId)

    def _deployImage(self, job, image, auth, *args, **kwargs):
        # This is really OO spaghetti.
        # deployImageProcess in sublcasses calls _deployImage in the
        # base class, which calls _deployImageFromFile from the subclass
        # again.
        stream = self.openImage(image, auth=auth)
        vmRef = self._deployImageFromStream(job, image, stream, *args, **kwargs)
        targetImageId = self.getImageIdFromTargetImageRef(vmRef)
        image.setId(targetImageId)
        image.setImageId(targetImageId)
        image.setInternalTargetId(targetImageId)
        self.linkTargetImageToImage(image)
        return vmRef

    def _deployImageFromStream(self, job, image, stream, *args, **kwargs):
        # By default, save image to file then deploy from the file. Subclasses
        # might be able to use the stream more efficiently.
        stream = self.streamProgressWrapper(job, stream)
        tmpDir = tempfile.mkdtemp(prefix="%s-download-" % self.cloudType)
        try:
            imageId = os.path.basename(image.getId())
            extension = '.tgz'
            path = os.path.join(tmpDir, '%s%s' % (imageId, extension))
            with open(path, 'w') as outf:
                util.copyfileobj(stream, outf)
            return self._deployImageFromFile(job, image, path, *args, **kwargs)
        finally:
            # clean up our mess
            util.rmtree(tmpDir, ignore_errors=True)

    def getImageIdFromTargetImageRef(self, vmRef):
        # Default implementation is fairly dumb
        return vmRef

    @classmethod
    def findFile(cls, topdir, extensions):
        for (dirPath, dirNames, fileNames) in os.walk(topdir):
            for fileName in fileNames:
                for extension in extensions:
                    if fileName.endswith(extension):
                        return dirPath, fileName
        return None, None

    def openUrl(self, url, headers):
        req = urllib2.Request(url, headers = headers or {})
        resp = urllib2.urlopen(req)
        if resp.headers['Content-Type'].startswith("text/html"):
            # We should not get HTML content out of rbuilder - most likely
            # a private project to which we don't have access
            raise errors.DownloadError("Unable to download file")
        return resp

    def downloadImage(self, job, image, tmpDir, auth=None, extension='.tgz'):
        imageId = os.path.basename(image.getId())
        downloadFilePath = os.path.join(tmpDir, '%s%s' % (imageId, extension))
        try:
            inf = self.openImage(image, auth)
            inf = self.streamProgressWrapper(job, inf)
            with open(downloadFilePath, 'wb') as outf:
                util.copyfileobj(inf, outf)
        except Exception:
            util.rmtree(tmpDir, ignore_errors=True)
            raise
        return downloadFilePath

    def openImage(self, image, auth=None):
        downloadUrl = image.getDownloadUrl()
        downloadUrl = self._remapDownloadUrl(downloadUrl)
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
        return self.openUrl(downloadUrl, headers)

    def streamProgressWrapper(self, job, fobj, message='Downloading image'):
        if hasattr(fobj, 'headers'):
            size = long(fobj.headers['content-length'])
        elif hasattr(fobj, 'fileno'):
            size = os.fstat(fobj.fileno()).st_size
        elif isinstance(fobj, StringIO):
            # testsuite
            size = len(fobj.getvalue())
        else:
            raise TypeError("Can't determine size of file object")
        def callback(percent):
            self._msg(job, "%s: %d%%" % (message, percent))
        callback = PercentageCallback(size, callback)
        return StreamWithProgress(fobj, callback)

    def _remapDownloadUrl(self, downloadUrl):
        if not os.path.exists(self.ImageDownloadUrlMapFile):
            return downloadUrl
        try:
            f = file(self.ImageDownloadUrlMapFile)
        except IOError:
            return downloadUrl
        splitUrl = util.urlSplit(downloadUrl)
        for line in f:
            line = line.strip()
            if line.startswith('#'):
                continue
            arr = line.split()
            if len(arr) != 2:
                continue
            if self._urlMatch(util.urlSplit(arr[0]), splitUrl):
                return self._urlMap(splitUrl, util.urlSplit(arr[1]))
        return downloadUrl

    @classmethod
    def _urlMatch(cls, url1, url2):
        for idx in [0, 3, 4]:
            if url1[idx] != url2[idx]:
                return False
        return True

    @classmethod
    def _urlMap(cls, urlOld, urlNew):
        comps = list(urlOld)
        for idx in [0, 3, 4]:
            comps[idx] = urlNew[idx]
        return util.urlUnsplit(comps)

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

    def hashMintImages(self, mintImageList, imageList):
        targetImageIds = set(x.getImageId() for x in imageList)
        return dict((self.getImageIdFromMintImage(x, targetImageIds), x)
            for x in mintImageList)

    def addMintDataToImageList(self, imageList, imageType):
        cloudAlias = self.getCloudAlias()

        mintImages = self._getMintImagesByType(imageType)
        # Convert the list into a map keyed on the sha1 converted into
        # uuid format
        mintImages = self.hashMintImages(mintImages, imageList)

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
    def getImageIdFromMintImage(cls, image, targetImageIds):
        files = image.get('files', [])
        if not files:
            return None
        ffile = files[0]
        # If uniqueImageId is present, use that.
        return ffile.get('uniqueImageId', ffile['sha1'])

    def _getImageIdFromMintImage_local(self, imageData, targetImageIds):
        """
        A variant of getImageIdFromMintImage that records the image IDs
        in the local database, as opposed to annotating the image on the
        target with the mint image id.
        """
        files = imageData.get('files', [])
        if not files:
            return None
        # Look for image ids that match this target
        fdata = files[0]
        targetImageIdsFromMint = set(x[2] for x in fdata['targetImages']
            if x[0] == self.cloudType and x[1] == self.cloudName)
        # Some of them may have been removed, so only look for the overlapping
        # ones
        inters = targetImageIdsFromMint.intersection(targetImageIds)
        mintImageId = imageData['_mintImageId'] = fdata.get('uniqueImageId',
            fdata['sha1'])
        if inters:
            imageId = imageData['_targetImageId'] = inters.pop()
            return imageId
        return mintImageId

    @classmethod
    def setImageNamesFromMintData(cls, image, mintImageData):
        buildId = mintImageData.get('buildId')
        baseFileName = mintImageData.get('baseFileName')
        if baseFileName:
            shortName = os.path.basename(baseFileName)
            longName = "%s/%s" % (buildId, shortName)
            image.setShortName(shortName)
            image.setLongName(longName)
            image.setBaseFileName(baseFileName)
        imageId = image.getImageId()
        targetImageId = mintImageData.get('_targetImageId')
        image._targetImageId = targetImageId
        if targetImageId:
            # The image ID gets replaced, we want to keep the ID from mint
            # in the list
            mintImageId = mintImageData.get('_mintImageId')
            image.setImageId(mintImageId)
            oldImageId = image.getId()
            image.setId("%s%s" % (oldImageId[:-len(imageId)], mintImageId))

    @classmethod
    def addImageDataFromMintData(cls, image, mintImageData, methodMap):
        imageFiles = mintImageData.get('files', [])
        buildId = mintImageData.get('buildId')
        cls.setImageNamesFromMintData(image, mintImageData)
        # XXX this overly simplifies the fact that there may be more than one
        # file associated with a build
        if imageFiles:
            imgf = imageFiles[0]
            image.setDownloadUrl(imgf.get('downloadUrl'))
            image._fileId = imgf.get('fileId')
        image.setBuildPageUrl(mintImageData.get('buildPageUrl'))
        image.setBuildId(buildId)
        image._imageType = mintImageData['imageType']
        image._imageData = mintImageData.get('imageData')

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
        fd, isoFile = tempfile.mkstemp(dir = isoDir,
             prefix = 'credentials-', suffix = '.iso')
        os.close(fd)

        # Create an empty file for our signature
        empty = os.path.join(certDir, "EMPTY")
        file(empty, "w")

        # Load the cert, we need the hash
        certHash = self.computeX509CertHash(certFile)

        bootUuidFile = tempfile.NamedTemporaryFile()
        bootUuidFile.write(self.getBootUuid())
        bootUuidFile.flush()

        rootSshKeyFile = None
        rootSshKeys = self._rootSshKeys
        if rootSshKeys:
            rootSshKeyFile = tempfile.NamedTemporaryFile()
            rootSshKeyFile.write(rootSshKeys)
            rootSshKeyFile.flush()

        directMethodFile = None
        conaryProxyFile = None
        if self.zoneAddresses:
            directMethodFile = tempfile.NamedTemporaryFile()
            tmpl = "directMethod %s\n"
            directMethodFile.write(tmpl % "[]")
            for za in self.zoneAddresses:
                directMethodFile.write(tmpl % za)
            directMethodFile.flush()
            conaryProxyFile = tempfile.NamedTemporaryFile()
            # zone addresses may have the port embedded, need to strip
            # that out
            conaryProxyFile.write(
                "proxyMap * %s\n" % " ".join(
                    "conarys://" + x.split(':', 1)[0]
                        for x in self.zoneAddresses))
            conaryProxyFile.flush()

        graftList = [
            "SECURITY-CONTEXT-BOOTSTRAP=%s" % empty,
            "etc/sfcb/clients/%s.0=%s" % (certHash, certFile),
            "etc/conary/rpath-tools/boot-uuid=%s" % bootUuidFile.name,
        ]

        if directMethodFile:
            graftList.append("etc/conary/rpath-tools/config.d/directMethod=%s"
                % directMethodFile.name)
        if conaryProxyFile:
            graftList.append("etc/conary/config.d/rpath-tools-conaryProxy=%s"
                % conaryProxyFile.name)
        if rootSshKeyFile:
            graftList.append("etc/ssh/keys.d/root/key.pub=%s" % rootSshKeyFile.name)

        # Make ISO, if it doesn't exist already
        cmd = [ "/usr/bin/mkisofs", "-r", "-J", "-graft-points",
            "-o", isoFile,
        ] + graftList

        devnull = file(os.devnull, "w")
        p = subprocess.Popen(cmd, shell = False, stdout=devnull,
            stderr = devnull)
        p.wait()
        return isoFile

    @classmethod
    def utctime(cls, timestr, timeFormat = None):
        if timeFormat is None:
            timeFormat = cls.detectTimeFormat(timestr)
        return timeutils.utctime(timestr, timeFormat)

    @classmethod
    def detectTimeFormat(cls, timestr):
        if not isinstance(timestr, basestring):
            return "%Y-%m-%dT%H:%M:%S.000Z"
        if len(timestr) == 20:
            return "%Y-%m-%dT%H:%M:%SZ"
        # This is trying to get rid of the milliseconds part
        timeFormat = "%Y-%m-%dT%H:%M:%S." + timestr.rsplit('.', 1)[-1]
        # The last 4 chars should normally be milliseconds and Z
        if not timeFormat.endswith('Z'):
            raise ValueError("Invalid time string %s" % (timestr, ))
        return timeFormat

    @classmethod
    def _uuid(cls, s):
        return '-'.join((s[:8], s[8:12], s[12:16], s[16:20], s[20:32]))

    @classmethod
    def uuidgen(cls):
        hex = sha1helper.md5ToString(sha1helper.md5String(os.urandom(128)))
        return cls._uuid(hex)


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

def _wrap_method(methodName):
    def _method(slf, *args, **kwargs):
        slf._open()
        method = getattr(slf._fileobj, methodName)
        return method(*args, **kwargs)
    _method.__name__ = methodName
    return _method

class Archive(object):
    """
    Generic implementation for an archive.
    You can iterate over the archive, and you can extract a member of the archive.
    A member has the following properties:
        * name
        * size
    You can extract a member from the using archive.extractfile(member)
    The object returned is guaranteed to have:
        * name
        * size
        * read()
        * seek()
        * tell()
    """
    class CommandArchive(object):
        """
        Archive that needs to be exploded in order to inspect it
        """
        class File(object):
            "An abstract File object, with name and size"
            __slots__ = [ 'name', '_stat', '_topdir', '_fileobj' ]
            def __init__(self, name, topdir):
                self.name = name
                self._stat = None
                self._topdir = topdir
                self._fileobj = None
            @property
            def size(self):
                return self.stat.st_size
            @property
            def _filename(self):
                return os.path.join(self._topdir, self.name)
            @property
            def stat(self):
                if self._stat is None:
                    self._stat = os.stat(self._filename)
                return self._stat
            seek = _wrap_method('seek')
            tell = _wrap_method('tell')
            read = _wrap_method('read')
            def close(self):
                if self._fileobj:
                    self._fileobj.close()
                    self._fileobj = None
            def _open(self):
                if self._fileobj is None:
                    self._fileobj = file(self._filename)
            def _reset(self):
                self._fileobj = None

        def __init__(self, parent, workdir, cmd):
            self.parent = parent
            self.workdir = workdir
            self.cmd = cmd

        def run(self):
            self.parent().log("Exploding archive")
            util.mkdirChain(self.workdir)
            p = subprocess.Popen(self.cmd, stderr = file(os.devnull, 'w'))
            p.wait()

        def __iter__(self):
            for (dirPath, dirNames, fileNames) in os.walk(self.workdir):
                # We need to strip out self.workdir from the path
                reldir = dirPath[len(self.workdir) + 1:]
                for fileName in fileNames:
                    yield self.File(os.path.join(reldir, fileName), self.workdir)
        def extractfile(self, member):
            # Instantiate a new member, so we don't mistakenly trip over
            # ourselves by extracting the same file twice
            ret = member.__class__(member.name, member._topdir)
            ret._stat = member._stat
            return ret

    class TarArchive(object):
        "A tar file"
        def __init__(self, parent, path):
            self.parent = parent
            self.tarfile = tarfile.open(path)
        def run(self):
            pass
        def __iter__(self):
            return (x for x in self.tarfile if x.isfile())
        def extractfile(self, member):
            return self.tarfile.extractfile(member)

    class GzipArchive(object):
        "A gzip file"
        def __init__(self, parent, path):
            self.parent = parent
            self.path = path
            self.workdir = os.path.join(os.path.dirname(path), 'subdir')
            util.mkdirChain(self.workdir)
            fname = os.path.basename(self.path)
            if fname.lower().endswith('.gz'):
                fname = fname[:-3]
            self._fname = os.path.join(self.workdir, fname)
            self._fobj = file(self._fname, "w")
        def run(self):
            fsrc = gzip.open(self.path, "r")
            util.copyfileobj(fsrc, self._fobj)
            self._fobj.close()
        def __iter__(self):
            return iter([ Archive.CommandArchive.File(
                os.path.basename(self._fname),
                self.workdir) ])
        def extractfile(self, member):
            return member

    def __init__(self, path, log):
        self.path = path
        self.archive = None
        self.identify()
        self.log = log
        # baseDir is a directory to which other paths are relative of
        self.baseDir = None

    def identify(self):
        wself = weakref.ref(self)
        workdir = os.path.join(os.path.dirname(self.path), 'subdir')
        mg = magic.magic(self.path)
        cmd = None
        if isinstance(mg, magic.ZIP):
            cmd = [ 'unzip', '-d', workdir, self.path ]
        elif isinstance(mg, magic.tar_gz):
            cmd = [ 'tar', 'zxSf', self.path, '-C', workdir ]
        elif isinstance(mg, magic.tar):
            self.archive = self.TarArchive(wself, self.path)
        elif isinstance(mg, magic.gzip):
            self.archive = self.GzipArchive(wself, self.path)
        else:
            raise errors.CatalogError('unsupported rBuilder image archive format')
        if cmd is not None:
            self.archive = self.CommandArchive(wself, workdir, cmd)

    def extract(self):
        return self.archive.run()

    def __iter__(self):
        return iter(self.archive)

    def extractfile(self, member):
        return self.archive.extractfile(member)

    def iterFileWithExtensions(self, extensions):
        for member in self.archive:
            for extension in extensions:
                if member.name.endswith(extension):
                    yield member


BaseDriver.Archive = Archive
