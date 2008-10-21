
import os
import signal
import time
import urllib

from conary.lib import util

from catalogService import clouds
from catalogService import environment
from catalogService import images
from catalogService import instances
from catalogService import instanceStore
from catalogService import storage
from catalogService.rest import baseDriver

import globuslib

# XXX should be pushed to errors
class HttpNotFound(Exception):
    pass

class VWS_Cloud(clouds.BaseCloud):
    "Clobus Virtual Workspaces Cloud"

class VWS_Image(images.BaseImage):
    "Globus Virtual Workspaces Image"

    __slots__ = images.BaseImage.__slots__ + ['isDeployed', 'buildId',
                                              'downloadUrl', 'buildPageUrl',
                                              'baseFileName']
    _slotTypeMap = images.BaseImage._slotTypeMap.copy()
    _slotTypeMap.update(dict(isDeployed = bool))
    _constructorOverrides = VWS_Cloud._constructorOverrides.copy()

class VWS_Instance(instances.BaseInstance):
    "Globus Virtual Workspaces Instance"
    _constructorOverrides = VWS_Cloud._constructorOverrides.copy()

class VWS_EnvironmentCloud(environment.BaseCloud):
    "Globus Virtual Workspaces Environment Cloud"
    _constructorOverrides = VWS_Image._constructorOverrides.copy()

class VWS_InstanceTypes(instances.InstanceTypes):
    "Globus Virtual Workspaces Instance Types"

    idMap = [
        ('vws.small', "Small"),
        ('vws.medium', "Medium"),
        ('vws.large', "Large"),
        ('vws.xlarge', "Extra Large"),
    ]

class VWS_ImageHandler(images.Handler):
    imageClass = VWS_Image

class VWSClient(baseDriver.BaseDriver):
    Cloud = VWS_Cloud
    EnvironmentCloud = VWS_EnvironmentCloud
    Image = VWS_Image
    Instance = VWS_Instance

    _cloudType = 'vws'

    _credNameMap = [
        ('userCert', 'userCert'),
        ('userKey', 'userKey'),
        ('sshPubKey', 'sshPubKey'),
    ]

    def __init__(self, *args, **kwargs):
        baseDriver.BaseDriver.__init__(self, *args, **kwargs)
        self._instanceStore = None

    def _getCloudCredentialsForUser(self):
        return self._getCredentialsForCloudName(self.cloudName)

    def drvCreateCloudClient(self, credentials):
        props = globuslib.WorkspaceCloudProperties()
        props.set('vws.factory', credentials['factory'])
        props.set('vws.repository', credentials['repository'])
        props.set('vws.factory.identity', credentials['factoryIdentity'])
        props.set('vws.repository.identity', credentials['repositoryIdentity'])
        cli = globuslib.WorkspaceCloudClient(props, credentials['caCert'],
            credentials['userCert'], credentials['userKey'],
            credentials['sshPubKey'], credentials['alias'])
        keyPrefix = "%s/%s" % (self.cloudName.replace('/', '_'),
                               cli.userCertHash)
        self._instanceStore = self._getInstanceStore(keyPrefix)
        return cli

    def isValidCloudName(self, cloudName):
        try:
            creds = self._getCredentialsForCloudName(cloudName)
        except HttpNotFound:
            return False
        return True

    def setUserCredentials(self, fields):
        # We will not implement this yet, we need to differentiate between
        # config data and credentials
        valid = True
        node = self._nodeFactory.newCredentials(valid)
        return node

    def listClouds(self):
        ret = clouds.BaseClouds()
        for cloudCred in self._getCredentials():
            cName = cloudCred['factory']
            cld = self._nodeFactory.newCloud(cloudName = cName,
                             description = cloudCred['description'],
                             cloudAlias = cloudCred['alias'])
            ret.append(cld)
        return ret

    def launchInstance(self, xmlString, requestIPAddress):
        client = self.client
        parameters = LaunchInstanceParameters(xmlString)
        imageId = parameters.imageId

        image = self.getImage(imageId)
        if not image:
            raise errors.HttpNotFound()

        instanceId = self._instanceStore.newKey(imageId = imageId)
        self._daemonize(self._launchInstance,
                        instanceId, image,
                        duration=parameters.duration,
                        instanceType=parameters.instanceType)
        cloudAlias = client.getCloudAlias()
        instanceList = instances.BaseInstances()
        instance = self._nodeFactory.newInstance(id=instanceId,
                                        instanceId=instanceId,
                                        imageId=imageId,
                                        cloudName=self.cloudName,
                                        cloudAlias=cloudAlias)
        instanceList.append(instance)
        return instanceList

    def terminateInstances(self, instanceIds):
        client = self.client

        instIdSet = set(os.path.basename(x) for x in instanceIds)
        runningInsts = self.getInstances(instanceIds)

        # Separate the ones that really exist in globus
        nonGlobusInstIds = [ x.getInstanceId() for x in runningInsts
            if x.getReservationId() is None ]

        globusInstIds = [ x.getReservationId() for x in runningInsts
            if x.getReservationId() is not None ]

        if globusInstIds:
            client.terminateInstances(globusInstIds)
            # Don't bother to remove the instances from the store,
            # getInstances() should take care of that

        self._killRunningProcessesForInstances(nonGlobusInstIds)

        insts = instances.BaseInstances()
        insts.extend(runningInsts)
        # Set state
        for inst in insts:
            inst.setState("Terminating")
        return insts

    def terminateInstance(self, instanceId):
        return self.terminateInstances([instanceId])

    def getAllImages(self):
        return self.getImages(None)

    def getImages(self, imageIds):
        imageList = self._getImagesFromGrid()
        imageList = self._addMintDataToImageList(imageList)

        # now that we've grabbed all the images, we can return only the one
        # we want.  This is horribly inefficient, but neither the mint call
        # nor the grid call allow us to filter by image, at least for now
        if imageIds is not None:
            imagesById = dict((x.getImageId(), x) for x in imageList )
            newImageList = images.BaseImages()
            for imageId in imageIds:
                if imageId.endswith('.gz') and imageId not in imagesById:
                    imageId = imageId[:-3]
                if imageId not in imagesById:
                    continue
                newImageList.append(imagesById[imageId])
            imageList = newImageList
        return imageList

    def getImage(self, imageId):
        return self.getImages([imageId])[0]

    def getEnvironment(self):
        instTypeNodes = self._getInstanceTypes()

        cloud = self._nodeFactory.newEnvironmentCloud(
            instanceTypes = instTypeNodes, cloudName = self.cloudName)

        env = self._nodeFactory.newEnvironment()
        env.append(cloud)
        return env

    def getInstanceTypes(self):
        return self._getInstanceTypes()

    def getAllInstances(self):
        return self.getInstances(None)

    def getInstances(self, instanceIds):
        cloudAlias = self.client.getCloudAlias()
        globusInsts  = self.client.listInstances()
        globusInstsDict = dict((x.getId(), x) for x in globusInsts)
        storeInstanceKeys = self._instanceStore.enumerate()
        reservIdHash = {}
        tmpInstanceKeys = {}
        for storeKey in storeInstanceKeys:
            instanceId = os.path.basename(storeKey)
            reservationId = self._instanceStore.getId(storeKey)
            expiration = self._instanceStore.getExpiration(storeKey)
            if reservationId is None and (expiration is None
                                     or time.time() > float(expiration)):
                # This instance exists only in the store, and expired
                self._instanceStore.delete(storeKey)
                continue
            imageId = self._instanceStore.getImageId(storeKey)

            # Did we find this instance in our store already?
            if reservationId in reservIdHash:
                # If the previously found instance already has an image ID,
                # prefer it. Also, if neither this instance nor the other one
                # have an image ID, prefer the first (i.e. not this one)
                otherInstKey, otherInstImageId = reservIdHash[reservationId]
                if otherInstImageId is not None or imageId is None:
                    self._instanceStore.delete(storeKey)
                    continue

                # We prefer this instance over the one we previously found
                del reservIdHash[reservationId]
                del tmpInstanceKeys[(otherInstKey, reservationId)]

            if reservationId is not None:
                reservIdHash[reservationId] = (storeKey, imageId)
            tmpInstanceKeys[(storeKey, reservationId)] = imageId

        # Done with the preference selection
        del reservIdHash

        gInsts = []

        # Walk through the list again
        for (storeKey, reservationId), imageId in tmpInstanceKeys.iteritems():
            if reservationId is None:
                # The child process hasn't updated the reservation id yet (or
                # it died but the instance hasn't expired yet).
                # Synthesize a globuslib.Instance with not much info in it
                state = self._instanceStore.getState(storeKey)
                inst = globuslib.Instance(_id = reservationId, _state = state)
                gInsts.append((storeKey, imageId, inst))
                continue

            reservationId = int(reservationId)
            if reservationId not in globusInstsDict:
                # We no longer have this instance, get rid of it
                self._instanceStore.delete(storeKey)
                continue
            # Instance exists both in the store and in globus
            inst = globusInstsDict.pop(reservationId)
            gInsts.append((storeKey, imageId, inst))
            # If a state file exists, get rid of it, we are getting the state
            # from globus
            self._instanceStore.setState(storeKey, None)

        # For everything else, create an instance ID
        for reservationId, inst in globusInstsDict.iteritems():
            nkey = self._instanceStore.newKey(realId = reservationId)
            gInsts.append((nkey, None, inst))

        gInsts.sort(key = lambda x: x[1])

        # Set up the filter for instances the client requested
        if instanceIds is not None:
            instanceIds = set(os.path.basename(x) for x in instanceIds)

        instanceList = instances.BaseInstances()

        for storeKey, imageId, instObj in gInsts:
            instId = str(os.path.basename(storeKey))
            if instanceIds and instId not in instanceIds:
                continue

            reservationId = instObj.getId()
            if reservationId is not None:
                reservationId = str(reservationId)
            inst = self._nodeFactory.newInstance(id = instId,
                imageId = imageId,
                instanceId = instId,
                reservationId = reservationId,
                dnsName = instObj.getName(),
                publicDnsName = instObj.getIp(), state = instObj.getState(),
                launchTime = instObj.getStartTime(),
                cloudName = self.cloudName,
                cloudAlias = cloudAlias)

            instanceList.append(inst)
        return instanceList

    def _daemonize(self, function, *args, **kw):
        pid = os.fork()
        if pid:
            os.waitpid(pid, 0)
            return
        try:
            try:
                pid = os.fork()
                if pid:
                    # The first child exits and is waited by the parent
                    # the finally part will do the os._exit
                    return
                # Redirect stdin, stdout, stderr
                fd = os.open(os.devnull, os.O_RDWR)
                os.dup2(fd, 0)
                os.dup2(fd, 1)
                os.dup2(fd, 2)
                os.close(fd)
                # Create new process group
                os.setsid()

                os.chdir('/')
                function(*args, **kw)
            except Exception:
                os._exit(1)
        finally:
            os._exit(0)

    def _setState(self, instanceId, state):
        return self._instanceStore.setState(instanceId, state)

    def _launchInstance(self, instanceId, image, duration,
                        instanceType):
        try:
            self._instanceStore.setPid(instanceId)
            if not image.getIsDeployed():
                self._setState(instanceId, 'Downloading image')
                dlImagePath = self._downloadImage(img, imageExtraData)
                self._setState(instanceId, 'Preparing image')
                imgFile = self._prepareImage(dlImagePath)
                self._setState(instanceId, 'Publishing image')
                self._publishImage(imgFile)
            imageId = image.getImageId()

            def callback(realId):
                self._instanceStore.setId(instanceId, realId)
                # We no longer manage the state ourselves
                self._setState(instanceId, None)
            self._setState(instanceId, 'Launching')

            realId = self.client.launchInstances([imageId],
                duration = duration, callback = callback)

        finally:
            self._instanceStore.deletePid(instanceId)

    def _downloadImage(self, image, imageExtraData):
        imageId = image.getImageId()
        # Get rid of the trailing .gz
        assert(imageId.endswith('.gz'))
        imageSha1 = imageId[:-3]
        build = self._mintClient.getBuild(image.getBuildId())

        downloadUrl = imageExtraData['downloadUrl']

        # XXX follow redirects
        uobj = urllib.urlopen(downloadUrl)
        # Create temp file
        downloadFilePath = os.path.join(self.cloudClient._tmpDir,
            '%s.tgz' % imageSha1)
        util.copyfileobj(uobj, file(downloadFilePath, "w"))
        return downloadFilePath

    def _prepareImage(self, downloadFilePath):
        retfile = self.client._repackageImage(downloadFilePath)
        os.unlink(downloadFilePath)
        return retfile

    def _publishImage(self, fileName):
        self.client.transferInstance(fileName)

    def _getImagesFromGrid(self):
        cloudAlias = self.client.getCloudAlias()

        imageIds = self.client.listImages()
        imageList = images.BaseImages()

        for imageId in imageIds:
            imageName = imageId
            image = self._nodeFactory.newImage(id = imageId,
                    imageId = imageId, isDeployed = True,
                    is_rBuilderImage = False,
                    shortName = os.path.basename(imageName),
                    longName = imageName,
                    cloudName = self.cloudName,
                    cloudAlias = cloudAlias)
            imageList.append(image)
        return imageList

    def _addMintDataToImageList(self, imageList):
        cloudAlias = self.client.getCloudAlias()

        imageDataLookup = self._mintClient.getAllVwsBuilds()
        # Convert the images coming from rbuilder to .gz, to match what we're
        # storing in globus
        imageDataLookup = dict((x + '.gz', y)
            for x, y in imageDataLookup.iteritems())
        for image in imageList:
            imageId = image.getImageId()
            mintImageData = imageDataLookup.pop(imageId, {})
            image.setIs_rBuilderImage(bool(mintImageData))
            image.setIsDeployed(True)
            if not mintImageData:
                continue
            self._addImageDataFromMintData(image, mintImageData)

        # Add the rest of the images coming from mint
        for imageId, mintImageData in sorted(imageDataLookup.iteritems()):
            image = self._nodeFactory.newImage(id = imageId,
                    imageId = imageId, isDeployed = False,
                    is_rBuilderImage = True,
                    cloudName = self.cloudName,
                    cloudAlias = cloudAlias)
            self._addImageDataFromMintData(image, mintImageData)
            imageList.append(image)
        return imageList

    @classmethod
    def _addImageDataFromMintData(cls, image, mintImageData):
        shortName = os.path.basename(mintImageData['baseFileName'])
        longName = "%s/%s" % (mintImageData['buildId'], shortName)
        image.setShortName(shortName)
        image.setLongName(longName)
        image.setDownloadUrl(mintImageData['downloadUrl'])
        image.setBuildPageUrl(mintImageData['buildPageUrl'])
        image.setBaseFileName(mintImageData['baseFileName'])
        image.setBuildId(mintImageData['buildId'])

        for key, methodName in images.buildToNodeFieldMap.iteritems():
            getattr(image, methodName)(mintImageData.get(key))

    def _getCredentials(self):
        if not globuslib.WorkspaceCloudClient.isFunctional():
            return []

        store = self._getCredentialsDataStore()

        # XXX in the future we'll have the credentials split by user
        user = "demo"
        clouds = store.enumerate(user)
        keys = ['alias', 'factory', 'repository', 'factoryIdentity',
            'repositoryIdentity', 'caCert', 'userCert', 'userKey',
            'sshPubKey', 'description', ]
        ret = []
        for cloud in clouds:
            d = dict((k, store.get("%s/%s" % (cloud, k)))
                for k in keys)
            ret.append(d)
        return ret

    def _getCredentialsForCloudName(self, cloudName):
        creds = [ x for x in self._getCredentials()
            if x['factory'] == cloudName ]
        if creds:
            return creds[0]
        raise errors.HttpNotFound

    def _getCredentialsDataStore(self):
        path = self._cfg.storagePath + '/credentials'
        cfg = storage.StorageConfig(storagePath = path)
        return storage.DiskStorage(cfg)

    def _getInstanceStore(self, keyPrefix):
        path = self._cfg.storagePath + '/instances'
        cfg = storage.StorageConfig(storagePath = path)

        dstore = storage.DiskStorage(cfg)
        return instanceStore.InstanceStore(dstore, keyPrefix)

    def _getInstanceTypes(self):
        ret = VWS_InstanceTypes()
        ret.extend(self._nodeFactory.newInstanceType(
                id = x, instanceTypeId = x, description = y)
            for (x, y) in VWS_InstanceTypes.idMap)
        return ret

    def _killRunningProcessesForInstances(self, nonGlobusInstIds):
        # For non-globus instances, try to kill the pid
        for instId in nonGlobusInstIds:
            pid = self._instanceStore.getPid(instId)
            if pid is not None:
                # try to kill the child process
                pid = int(pid)
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError, e:
                    if e.errno != 3: # no such process
                        raise
            # At this point the instance doesn't exist anymore
            self._instanceStore.delete(instId)


class LaunchInstanceParameters(object):
    __slots__ = [
        'duration', 'imageId', 'instanceType',
    ]

    def __init__(self, xmlString=None):
        if xmlString:
            self.load(xmlString)

    def load(self, xmlString):
        from catalogService import newInstance
        node = newInstance.Handler().parseString(xmlString)
        image = node.getImage()
        imageId = image.getId()
        self.imageId = self._extractId(imageId)
        self.duration = node.getDuration()
        if self.duration is None:
            raise errors.ParameterError('duration was not specified')

        instanceType = node.getInstanceType()
        if instanceType is None:
            instanceType = 'vws.small'
        else:
            instanceType = instanceType.getId() or 'vws.small'
            instanceType = self._extractId(instanceType)
        self.instanceType = instanceType

    @staticmethod
    def _extractId(value):
        if value is None:
            return None
        return urllib.unquote(os.path.basename(value))
