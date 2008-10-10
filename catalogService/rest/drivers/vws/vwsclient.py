
import os
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
    _constructorOverrides = dict(cloudType = 'vws')

class VWS_Image(images.BaseImage):
    "Globus Virtual Workspaces Image"

    __slots__ = images.BaseImage.__slots__ + ['isDeployed', 'buildId',
                                              'downloadUrl', 'buildPageUrl']
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

    def __init__(self, *args, **kwargs):
        baseDriver.BaseDriver.__init__(self, *args, **kwargs)
        self.client = {}
        self._instanceStore = None

    def _getCloudClient(self, cloudName):
        cloudCred = self._getCredentialsForCloudName(cloudName)
        if cloudName in self.client:
            return self.client[cloudName]

        props = globuslib.WorkspaceCloudProperties()
        props.set('vws.factory', cloudCred['factory'])
        props.set('vws.repository', cloudCred['repository'])
        props.set('vws.factory.identity', cloudCred['factoryIdentity'])
        props.set('vws.repository.identity', cloudCred['repositoryIdentity'])
        cli = globuslib.WorkspaceCloudClient(props, cloudCred['caCert'],
            cloudCred['userCert'], cloudCred['userKey'],
            cloudCred['sshPubKey'], cloudCred['alias'])
        self.client[cloudName] = cli

        keyPrefix = "%s/%s" % (cloudName.replace('/', '_'), cli.userCertHash)
        self._instanceStore = self._getInstanceStore(cloudName, keyPrefix)
        return cli

    def isValidCloudName(self, cloudName):
        try:
            creds = self._getCredentialsForCloudName(cloudName)
        except HttpNotFound:
            return False
        return True
        # XXX We have to scan the list of available clouds here
        return cloudName == 'aws'

    def listClouds(self):
        ret = clouds.BaseClouds()
        for cloudCred in self._getCredentials():
            cName = cloudCred['factory']
            cld = self._nodeFactory.newCloud(cloudName = cName,
                             description = cloudCred['description'],
                             cloudAlias = cloudCred['alias'])
            ret.append(cld)
        return ret

    def cloudParameters(self):
        return CloudParameters()

    def createCloud(self, parameters):
        parameters = CloudParameters(parameters)

    def updateCloud(self, cloudId, parameters):
        parameters = CloudParameters(parameters)
        pass

    def publishImage(self, cloudId, image):
        self.cloudClient.transferInstance(fileName)
        pass

    def launchInstance(self, cloudName, xmlString, requestIPAddress):
        client = self._getCloudClient(cloudName)
        parameters = LaunchInstanceParameters(xmlString)
        imageId = parameters.imageId

        image = self.getImage(cloudName, imageId)
        instanceId = self._instanceStore.newKey(imageId = imageId)
        self._daemonize(self._launchInstance,
                        cloudName, imageId, instanceId, image,
                        duration=parameters.duration,
                        instanceType=parameters.instanceType)
        cloudAlias = client.getCloudAlias()
        instanceList = instances.BaseInstances()
        instance = self._nodeFactory.newInstance(id=instanceId,
                                        instanceId=instanceId,
                                        imageId=imageId,
                                        cloudName=cloudName,
                                        cloudAlias=cloudAlias)
        instanceList.append(instance)
        return instanceList

    def terminateInstances(self, cloudName, instanceIds):
        client = self._getCloudClient(cloudName)
        client.terminateInstances(instanceId)

    def terminateInstance(self, cloudName, instanceId):
        return self.terminateInstances(cloudName, [instanceId])

    def getAllImages(self, cloudId):
        return self.getImages(cloudId, None)

    def getImages(self, cloudName, imageIds):
        imageList = self._getImagesFromGrid(cloudName)
        imageList = self._addMintDataToImageList(cloudName, imageList)

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

    def getImage(self, cloudName, imageId):
        return self.getImages(cloudName, [imageId])[0]

    def getEnvironment(self):
        instTypeNodes = self._getInstanceTypes()

        cloudName = self._nodeFactory.urlParams['cloudName']
        cloud = self._nodeFactory.newEnvironmentCloud(
            instanceTypes = instTypeNodes, cloudName = cloudName)

        env = self._nodeFactory.newEnvironment()
        env.append(cloud)
        return env

    def getInstanceTypes(self):
        return self._getInstanceTypes()

    def getAllInstances(self, cloudId):
        return self.getInstances(cloudId, None)

    def getInstances(self, cloudName, instanceIds):
        client = self._getCloudClient(cloudName)
        cloudAlias = client.getCloudAlias()
        globusInsts  = client.listInstances()
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

        instanceList = instances.BaseInstances()

        for storeKey, imageId, instObj in gInsts:
            instId = str(os.path.basename(storeKey))
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
                cloudName = cloudName,
                cloudAlias = cloudAlias)

            instanceList.append(inst)
        return instanceList

    def _daemonize(self, function, *args, **kw):
        pid = os.fork()
        if pid:
            os.waitpid(pid, 0)
        try:
            try:
                pid = os.fork()
                if pid:
                    # The first child exits and is waited by the parent
                    os._exit(0)
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


    def _launchInstance(self, cloudId, imageId, instanceId, image,
                        duration, instanceType):
        try:
            self._instanceStore.setPid(instanceId)
            if not img.getIsDeployed():
                self._instanceStore.setState(instanceId, 'Downloading image')
                dlImagePath = self._downloadImage(img, imageExtraData)
                self._instanceStore.setState(instanceId, 'Preparing image')
                imgFile = self._prepareImage(dlImagePath)
                self._instanceStore.setState(instanceId, 'Publishing image')
                self._publishImage(imgFile)
            imageId = img.getImageId()

            def callback(realId):
                self._instanceStore.setId(instanceId, realId)
                # We no longer manage the state ourselves
                self._instanceStore.setState(instanceId, None)
            self._instanceStore.setState(instanceId, 'Launching')

            realId = self.cloudClient.launchInstances([imageId],
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

    def _prepareImage(self, cloudName, downloadFilePath):
        client = self._getCloudClient(cloudName)
        retfile = client._repackageImage(downloadFilePath)
        os.unlink(downloadFilePath)
        return retfile

    def _publishImage(self, cloudId, fileName):
        client = self._getCloudClient(cloudName)
        client.transferInstance(fileName)

    def _getImagesFromGrid(self, cloudName):
        client = self._getCloudClient(cloudName)
        cloudAlias = client.getCloudAlias()

        imageIds = client.listImages()
        imageList = images.BaseImages()

        for imageId in imageIds:
            imageName = imageId
            image = self._nodeFactory.newImage(id = imageId,
                    imageId = imageId, isDeployed = True,
                    is_rBuilderImage = False,
                    shortName = os.path.basename(imageName),
                    longName = imageName,
                    cloudName = cloudName,
                    cloudAlias = cloudAlias)
            imageList.append(image)
        return imageList

    def _addMintDataToImageList(self, cloudName, imageList):
        client = self._getCloudClient(cloudName)
        cloudAlias = client.getCloudAlias()

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
                    cloudName = cloudName,
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

    def _getInstanceStore(self, cloudName, keyPrefix):
        client = self._getCloudClient(cloudName)
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
