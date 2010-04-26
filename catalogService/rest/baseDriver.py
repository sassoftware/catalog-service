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
from catalogService.utils import cimupdater
from catalogService.utils import timeutils
from catalogService.utils import x509

from mint.mint_error import TargetExists, TargetMissing
from mint.rest import errors as mint_rest_errors
from mint.django_rest.rbuilder import inventory
from mint.django_rest.rbuilder.inventory import systemdbmgr

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

        self.systemMgr = systemdbmgr.SystemDBManager(cfg, userId)

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

    def _addSoftwareVersionInfo(self, instance, force=False):
        self._updateInstalledSoftwareList(instance, force)
        self._getAvailableUpdates(instance)
        self._setVersionAndStage(instance)
        self._nodeFactory.refreshInstance(instance)

    def getInstances(self, instanceIds):
        if self.client is None:
            raise errors.MissingCredentials("Target credentials not set for user")
        instances = self.drvGetInstances(instanceIds)
        for instance in instances:
            self._addSoftwareVersionInfo(instance)
        return instances

    def _getSoftwareVersionsForInstance(self, instanceId):
        softwareVersions = self.systemMgr.getSoftwareVersionsForInstanceId(instanceId)
        if not softwareVersions:
            return []
        ret = [ self._getNVF(x) for x in softwareVersions.split('\n') ]
        return [ x for x in ret if x is not None ]

    @classmethod
    def _getNVF(cls, troveSpec):
        name, version, flavor = conaryclient.cmdline.parseTroveSpec(troveSpec)
        try:
            version = versions.ThawVersion(version)
        except ValueError:
            # We may need to catch additional exceptions here.
            # This was for the change from VersionToString to ThawVersion
            return None
        return (name, version, flavor)

    def _updateInventory(self, instanceId, cloudType, cloudName, x509Cert,
                         x509Key):
        system = inventory.System(target_system_id=instanceId, target_type=cloudType,
                    target_name=cloudName, ssl_client_certificate=x509Cert, 
                    ssl_client_key=x509Key, registration_date=datetime.datetime.now())
        self.systemMgr.createSystem(system)

    def _fullSpec(self, nvf):
        flavor = nvf[2]
        if flavor is None:
            flavor = ''
        else:
            flavor = str(flavor)
        return "%s=%s[%s]" % (nvf[0], nvf[1].freeze(), flavor)

    def _quoteSpec(self, spec):
        return urllib.quote(urllib.quote(spec, safe = ''))

    def _updateInstalledSoftwareList(self, instance, force):
        state = instance.getState()
        # XXX we really should normalize the states across drivers
        if not state or state.lower() not in ['running', 'poweredon']:
            return
        instanceId = instance.getInstanceId()
        softwareVersions = self._getSoftwareVersionsForInstance(instanceId)
        if softwareVersions:
            troveList = [self._troveFactoryFromTroveTuple(c)
                for c in softwareVersions]
            versions = []
            for (nvf, t) in zip(softwareVersions, troveList):
                isTopLevel = self._isTopLevelGroup(nvf)
                fullSpec = self._fullSpec(nvf)
                installedSoftware = instances.InstalledSoftware()
                installedSoftware.setTrove(t)
                if isTopLevel:
                    installedSoftware.setIsTopLevel(isTopLevel)
                sanitizedFullSpec = self._quoteSpec(fullSpec)
                installedSoftware.setId(sanitizedFullSpec)
                installedSoftware.setTroveChangesHref(sanitizedFullSpec)

                installedSoftware.setTroveChangeNode(fromVersion = nvf[1].freeze(),
                    fromFlavor = str(nvf[2]))
                versions.append(installedSoftware)
            instance.setInstalledSoftware(versions)
        nextCheck = self._instanceStore.getSoftwareVersionNextCheck(instanceId)
        lastChecked = self._instanceStore.getSoftwareVersionLastChecked(instanceId)
        jobId = self._instanceStore.getSoftwareVersionJobId(instanceId)
        jobStatus = self._instanceStore.getSoftwareVersionJobStatus(instanceId)
        instance.setSoftwareVersionNextCheck(nextCheck)
        instance.setSoftwareVersionLastChecked(lastChecked)
        instance.setSoftwareVersionJobStatus(jobStatus)
        if jobId:
            instance.setSoftwareVersionJobId(
                self._nodeFactory.getJobIdUrl(jobId, 'software-version-refresh'))

        if nextCheck and time.time() < nextCheck and not force:
            return

        if jobStatus == 'Running':
            # XXX Verify if process still exists
            return

        system = self.systemMgr.getSystemByInstanceId(instanceId)
        if not system.is_manageable:
            return
        assert system.ssl_client_key is not None \
            and system.ssl_client_certificate is not None
        assert os.path.exists(system.ssl_client_key) and \
                os.path.exists(system.ssl_client_certificate)
        # Do we have an IP address/DNS name for this instance?
        ipAddr = instance.getPublicDnsName()
        if not ipAddr:
            return

        job = self._jobsStore.create(cloudType = self.cloudType,
            cloudName = self.cloudName, instanceId = instanceId)
        self._jobsStore.commit()
        self.versionJobRunner = CatalogJobRunner(self.runUpdateSoftwareVersion)
        self.versionJobRunner.job = job
        self.versionJobRunner(instance, job.id)

        instance.setSoftwareVersionJobId(self._nodeFactory.getJobIdUrl(job.id,
                    'software-version-refresh'))
        jobStatus = 'Running'
        instance.setSoftwareVersionJobStatus(jobStatus)

    def _troveFactoryFromTroveTuple(self, (name, version, flavor)):
        return self._troveModelFactory(name, version, flavor)

    def _setVersionAndStage(self, instance):
        # XXX: we can only look up version/stage info if there's one top
        # level
        instanceId = instance.getInstanceId()
        softwareVersions = self._getSoftwareVersionsForInstance(instanceId)

        for softwareVersion in softwareVersions:
            self._addVersionAndStage(instance, softwareVersion)

    def _isTopLevelGroup(self, nvf):
        name = nvf[0]
        return name.startswith('group-') and name.endswith('-appliance')

    def _addVersionAndStage(self, instance, nvf):
        if not self._isTopLevelGroup(nvf):
            return
        version, stage = self._getProductVersionAndStage(nvf)
        if not (version and stage):
            return
        versionModel = instances.VersionHref(href=self._buildUrl(version))
        versionModel.characters(version.name)
        stageModel = instances.StageHref(href=self._buildUrl(stage))
        stageModel.characters(stage.name)

        instance.setVersion(versionModel)
        instance.setStage(stageModel)

    def _getProductVersionAndStage(self, nvf):
        name, version, flavor = nvf
        label = version.trailingLabel()
        try:
            product = self.db.productMgr.getProduct(label.getHost())
        except mint_rest_errors.ProductNotFound:
            # Not a product that lives on this rba
            return None, None

        prodVersions = self.db.listProductVersions(product.hostname)
        for version in prodVersions.versions:
            stages = self.db.getProductVersionStages(product.hostname, version.name)
            for stage in stages.stages:
                if stage.label == label.asString():
                    return version, stage

        return None, None

    def _getRepositoryUrl(self, host):
        schemeUrl = self._nodeFactory.baseUrl.strip('/catalog')
        return '/'.join([schemeUrl, 'repos', host, 'api'])

    def _buildUrl(self, model):
        absUrl = model.get_absolute_url()
        parts = absUrl[0].split('.')
        vals = absUrl[1:]
        url = '/'.join(['/'.join((parts[i], vals[i])) for i in range(len(parts))]) 
        schemeUrl = self._nodeFactory.baseUrl.strip('/catalog')
        url = '/'.join([schemeUrl, 'api', url])
        
        return url

    def _troveModelFactory(self, name, version, flavor):
        schemeUrl = self._nodeFactory.baseUrl.strip('/catalog')
        label = version.trailingLabel()
        revision = version.trailingRevision()
        versionModel = instances.AvailableUpdateVersion(
                                    full=version.asString(),
                                    label=str(label),
                                    ordering=str(version.versions[-1].timeStamp),
                                    revision=str(version.trailingRevision()))
        trove = instances._Trove(name=name, version=versionModel,
                                 flavor=str(flavor))
        try:
            product = self.db.productMgr.getProduct(label.getHost())
            id = "repos/%s/api/trove/%s=/%s/%s[%s]" % \
                         (product.shortname, name, label.asString(),
                          revision.asString(), str(flavor))
            trove.id = "%s/%s" % (schemeUrl, urllib.quote(id))
        except mint_rest_errors.ProductNotFound:
            # Not a product that lives on this rba
            pass

        return trove

    def _getConaryClient(self):
        return self.db.productMgr.reposMgr.getUserClient()

    def _getAvailableUpdates(self, instance):
        # need to access this property as it sets user information and sets up
        # the instance store under the hood.
        client = self.client

        instanceId = instance.getInstanceId()
        softwareVersions = self._getSoftwareVersionsForInstance(instanceId)
        cclient = self._getConaryClient()
        content = []

        for trvName, trvVersion, trvFlavor in softwareVersions:
            fullSpec = self._fullSpec((trvName, trvVersion, trvFlavor))
            sanitizedFullSpec = self._quoteSpec(fullSpec)

            # trvName and trvVersion are str's, trvFlavor is a
            # conary.deps.deps.Flavor.
            label = trvVersion.trailingLabel()
            revision = trvVersion.trailingRevision()

            # Search the label for the trove of the top level item.  It should
            # only (hopefully) return 1 result.
            troves = cclient.repos.findTroves(label,
                [(trvName, trvVersion, trvFlavor)])
            assert(len(troves) == 1)

            # findTroves returns a {} with keys of (name, version, flavor), values
            # of [(name, repoVersion, repoFlavor)], where repoVersion and
            # repoFlavor are rich objects with the repository metadata.
            repoVersion = troves[(trvName, trvVersion, trvFlavor)][0][1]
            repoFlavors = [f[0][2] for f in troves.values()]
            # We only asked for 1 flavor, only 1 should be returned.
            assert(len(repoFlavors) == 1)

            # getTroveVersionList searches a repository (NOT by label), for a
            # given name/flavor combination.
            allVersions = cclient.repos.getTroveVersionList(
                trvVersion.getHost(), {trvName:repoFlavors})
            # We only asked for 1 name/flavor, so we should have only gotten 1
            # back.
            assert(len(allVersions) == 1)
            # getTroveVersionList returns a dict with keys of name, values of
            # (version, [flavors]).
            allVersions = allVersions[trvName]

            newerVersions = {}
            for v, fs in allVersions.iteritems():
                # getTroveVersionList doesn't search by label, so we need to
                # compare the results to the label we're interested in, and make
                # sure the version is newer.
                if v.trailingLabel() == label and v > repoVersion:

                    # Check that at least one of the flavors found satisfies the
                    # flavor we're interested in.
                    satisfiedFlavors = []
                    for f in fs:
                        # XXX: do we want to use flavor or repoFlavor here?
                        # XXX: do we want to use stronglySatisfies here?
                        if f.satisfies(trvFlavor):
                            satisfiedFlavors.append(f)
                    if satisfiedFlavors:
                        newerVersions[v] = satisfiedFlavors

            if newerVersions:
                for ver, fs in newerVersions.iteritems():
                    for flv in fs:
                        trove = self._troveModelFactory(trvName, ver, f)
                        update = instances.AvailableUpdate()
                        update.setTrove(trove)
                        update.setInstalledSoftwareHref(sanitizedFullSpec)
                        updateFullSpec = self._quoteSpec(self._fullSpec(
                            (trvName, ver, flv)))
                        update.setId(updateFullSpec)
                        update.setTroveChangesHref(updateFullSpec)
                        update.setTroveChangeNode(fromVersion = ver.freeze(),
                            fromFlavor = str(flv))
                        content.append(update)

                instance.setOutOfDate(True)

            # Add the current version as well.
            trove = self._troveModelFactory(trvName, repoVersion, trvFlavor)
            update = instances.AvailableUpdate()
            update.setTrove(trove)
            update.setInstalledSoftwareHref(sanitizedFullSpec)
            update.setId(sanitizedFullSpec)
            update.setTroveChangesHref(sanitizedFullSpec)
            update.setTroveChangeNode(fromVersion = trvVersion.freeze(),
                fromFlavor = str(trvFlavor))
            content.append(update)

            # Can only have one repositoryUrl set on the instance, so set it
            # if this is a top level group.
            if self._isTopLevelGroup([trvName,]):
                instance.setRepositoryUrl(
                    self._getRepositoryUrl(repoVersion.getHost()))

        instance.setAvailableUpdate(content)

        return instance

    def runUpdateSoftwareVersion(self, instance, jobId):
        self.db.db.reopen_fork()

        job = self._jobsStore.get(jobId, commitAfterChange = True)

        # RBL-5979 fix race condition. just because the instance is in the
        # 'running' state, doesn't mean sfcb is started.  If the instance was
        # launched within the last minute, wait 5 seconds.
        if (time.time() - instance.getLaunchTime()) < 60:
            time.sleep(5)

        instanceId = instance.getInstanceId()

        job.setFields([('pid', os.getpid()), ('status', job.STATUS_RUNNING) ])
        job.addHistoryEntry('Running')

        self._instanceStore.setSoftwareVersionJobId(instanceId, job.id)
        self._instanceStore.setSoftwareVersionJobStatus(instanceId,
                                                        "Running")
        self._instanceStore.setSoftwareVersionLastChecked(instanceId)
        self._instanceStore.setSoftwareVersionNextCheck(instanceId)
        try:
            self.runUpdateSoftwareVersionJob(instanceId, instance, job)
        finally:
            job.pid = None
            self._instanceStore.setSoftwareVersionJobStatus(instanceId,
                                                            "Done")
            self._instanceStore.setSoftwareVersionLastChecked(instanceId)
            self._instanceStore.setSoftwareVersionNextCheck(instanceId)

    def runUpdateSoftwareVersionJob(self, instanceId, instance, job):
        ipAddr = instance.getPublicDnsName()
        port = 5989
        self.log_debug("software version: probing %s:%s" % (ipAddr, port))

        try:
            self._probeHost(ipAddr, port)
        except self.ProbeHostError, e:
            job.addHistoryEntry("Error contacting system %s: %s" % (ipAddr, str(e)))
            raise

        job.addHistoryEntry("Successfully probed %s:%s" % (ipAddr, port))
        system = self.systemMgr.getSystemByInstanceId(instanceId)
        self.log_debug("Querying %s using cert %s, key %s", ipAddr,
                       system.ssl_client_certificate, system.ssl_client_key)

        # We know we can contact the appliance.
        x509Dict = dict(cert_file=system.ssl_client_certificate, 
                        key_file=system.ssl_client_key)
        wbemUrl = "https://%s" % ipAddr
        try:
            updater = cimupdater.CIMUpdater(wbemUrl, x509Dict)
            installedGroups = updater.getInstalledGroups()
            job.addResults(installedGroups)
            groups = [self._getNVF(g) for g in installedGroups]
            self.systemMgr.setSoftwareVersionForInstanceId(instanceId, groups)
        except Exception, e:
            job.addHistoryEntry("Error retrieving software version for %s: %s" %
                (ipAddr, str(e)))
            raise
        job.status = job.STATUS_COMPLETED

    def _probeHost(self, host, port):
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        try:
            s.connect((host, port))
        except socket.error, e:
            raise self.ProbeHostError(str(e))
        s.close()
        return True

    def getInstance(self, instanceId, force=False):
        if self.client is None:
            raise errors.MissingCredentials("Target credentials not set for user")
        instance = self.drvGetInstance(instanceId)
        self._addSoftwareVersionInfo(instance, force)
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
        # We need to reopen the db, so we don't share a cursor with the parent
        # process
        self.db.db.reopen_fork()
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
                for instanceId in realInstanceId:
                    x509CertPath, x509KeyPath = self._instanceStore.storeX509(
                                                    instanceId, x509Cert, x509Key)
                    self._updateInventory(instanceId, job.cloudType,
                        job.cloudName, x509CertPath, x509KeyPath)
                job.addResults(realInstanceId)
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
            cloudType = self.cloudType, restArgs = descrXml)
        job.commit()
        jobId = job.id
        self.launchJobRunner = CatalogJobRunner(self.launchInstanceInBackground)
        self.launchJobRunner.job = job
        self.launchJobRunner(jobId, image, auth, **params)

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

    def updateInstance(self, instanceXml):
        hdlr = instances.Handler()
        instance = hdlr.parseString(instanceXml)
        return self._updateInstance(instance)

    def _updateInstance(self, instance):
        dnsName = instance.getPublicDnsName()
        if not dnsName:
            # We can't do anything unless we know how to contact the box
            return

        troveSpecs = []
        for sw in instance.getInstalledSoftware():
            trove = sw.getTrove()
            n = trove.name.getText()
            f = deps.parseFlavor(trove.getFlavor())

            version = trove.getVersion()
            v = versions.VersionFromString(version.getFull())
            v.versions[-1].timeStamp = float(version.getOrdering())
            v = v.freeze()

            troveSpecs.append(conaryclient.cmdline.toTroveSpec(n, v, f))

        instanceId = instance.getInstanceId()
        system = self.systemMgr.getSystemByInstanceId(instanceId)

        if system.is_manageable:
            job = self._instanceUpdateJobStore.create(cloudType=self.cloudType,
                cloudName=self.cloudName, instanceId=instanceId)
            self._jobsStore.commit()

            self.updateJobRunner = CatalogJobRunner(self._updateInstanceJob)
            self.updateJobRunner.job = job

            newState = self.updateStatusStateUpdating
            # TODO comment this out for now until it's in the db.
            # self._setInstanceUpdateStatus(instance, newState)
            self.updateJobRunner(instance, dnsName,
                    troveSpecs, system.ssl_client_certificate,
                    system.ssl_client_key, job)
        else:
            # system is not manageable
            pass

        return instance

    def _updateInstanceJob(self, instanceId, dnsName, troveList, certFile,
                        keyFile, job):
        try:
            host = 'https://%s' % dnsName
            self.log_debug("Updating instance %s (%s))", instanceId, dnsName)
            self.log_debug("Updating %s: cert %s, key %s", instanceId, certFile, keyFile)
            x509Dict = dict(cert_file = certFile, key_file = keyFile)
            updater = cimupdater.CIMUpdater(host, x509Dict, self._logger)
            updater.checkAndApplyUpdate()
        except Exception, e:
            newState = self.updateStatusStateException
            raise
        else:
            # Mark the update status as done.
            newState = self.updateStatusStateDone
            job.status = job.STATUS_COMPLETED
        finally:
            self._setInstanceUpdateStatus(instance, newState)

    def _setInstanceUpdateStatus(self, instance, newState, newTime = None):
        if newTime is None:
            newTime = int(time.time())
        instance.getUpdateStatus().setState(newState)
        instance.getUpdateStatus().setTime(newTime)
        # Save the update status in the instance store
        instanceId = instance.getId()
        self._instanceStore.setUpdateStatusState(instanceId, newState)
        self._instanceStore.setUpdateStatusTime(instanceId, newTime)
        # Set the expiration to 3 hours for now.
        self._instanceStore.setExpiration(instanceId, 10800)

    def addMintDataToImageList(self, imageList, imageType):
        cloudAlias = self.getCloudAlias()

        mintImages = self.db.imageMgr.getAllImagesByType(imageType)
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
            getattr(image, methodName)(mintImageData.get(key))

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

        # Make ISO, if it doesn't exist already
        cmd = [ "/usr/bin/mkisofs", "-r", "-J", "-graft-points",
            "-o", isoFile,
            "SECURITY-CONTEXT-BOOTSTRAP=%s" % empty,
            "etc/sfcb/clients/%s.0=%s" % (certHash, certFile) ]

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
    def __init__(self, function, logger=None):
        self.logger = logger
        rpath_job.BackgroundRunner.__init__(self, function)

    def preFork(self):
        # Setting this to None forces the child to re-open the connection.
        self._cloudClient = None

    def log_error(self, msg, ei):
        if self.logger is not None:
            self.logger.error(msg, ei)

    def handleError(self, ei):
        self.job.addHistoryEntry('\n'.join(traceback.format_tb(ei[2])))
        self.job.status = self.job.STATUS_FAILED
        self.job.commit()
