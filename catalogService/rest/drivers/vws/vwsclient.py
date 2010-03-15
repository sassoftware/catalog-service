
import os
import signal
import tempfile
import time
import urllib

from conary.lib import util

from catalogService import errors
from catalogService import storage
from catalogService.rest import baseDriver
from catalogService.rest.models import clouds
from catalogService.rest.models import images
from catalogService.rest.models import instances

import globuslib

class VWS_Cloud(clouds.BaseCloud):
    "Clobus Virtual Workspaces Cloud"

class VWS_Image(images.BaseImage):
    "Globus Virtual Workspaces Image"
    _constructorOverrides = VWS_Cloud._constructorOverrides.copy()

class VWS_Instance(instances.BaseInstance):
    "Globus Virtual Workspaces Instance"
    _constructorOverrides = VWS_Cloud._constructorOverrides.copy()

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

_configurationDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>Globus Workspaces Cloud Configuration</displayName>
    <descriptions>
      <desc>Configure Globus Workspaces Cloud</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>alias</name>
      <descriptions>
        <desc>Cloud Alias</desc>
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
      <name>factory</name>
      <descriptions>
        <desc>Factory Name</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/factoryName.html'/>
    </field>
    <field>
      <name>factoryIdentity</name>
      <descriptions>
        <desc>Factory Identity (x509 subject)</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/factoryIdentity.html'/>
    </field>
    <field>
      <name>repository</name>
      <descriptions>
        <desc>GridFTP Repository Name</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/repository.html'/>
    </field>
    <field>
      <name>repositoryIdentity</name>
      <descriptions>
        <desc>GridFTP Repository Identity (x509 subject)</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/repositoryIdentity.html'/>
    </field>
    <field>
      <name>repositoryBaseDir</name>
      <descriptions>
        <desc>GridFTP Base Directory</desc>
      </descriptions>
      <type>str</type>
      <required>false</required>
      <help href='configuration/repositoryBaseDir.html'/>
    </field>  
    <field>
      <name>caCert</name>
      <descriptions>
        <desc>Certificate Authority (x509) Public Key</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Maximum Length</desc>
        </descriptions>
        <length>4096</length>
      </constraints>
      <required>true</required>
      <help href='configuration/caCert.html'/>
    </field>
  </dataFields>
</descriptor>"""

_credentialsDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>Globus Workspaces User Credentials</displayName>
    <descriptions>
      <desc>User Credentials for Globus Workspaces</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>userCert</name>
      <descriptions>
        <desc>X509 User Certificate</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Maximum Characters</desc>
        </descriptions>
        <length>4096</length>
      </constraints>
      <required>true</required>
    </field>
    <field>
      <name>userKey</name>
      <descriptions>
        <desc>X509 User Key</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Maximum Characters</desc>
        </descriptions>
        <length>4096</length>
      </constraints>
      <required>true</required>
    </field>
    <field>
      <name>sshPubKey</name>
      <descriptions>
        <desc>SSH Public Key</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Maximum Characters</desc>
        </descriptions>
        <length>4096</length>
      </constraints>
      <required>true</required>
    </field>
  </dataFields>
</descriptor>
"""

class VWSClient(baseDriver.BaseDriver):
    Cloud = VWS_Cloud
    Image = VWS_Image
    Instance = VWS_Instance

    cloudType = 'vws'

    _credNameMap = [
        ('userCert', 'userCert'),
        ('userKey', 'userKey'),
        ('sshPubKey', 'sshPubKey'),
    ]

    _configNameMap = [
        ('factory', 'name'),
    ]

    configurationDescriptorXmlData = _configurationDescriptorXmlData
    credentialsDescriptorXmlData = _credentialsDescriptorXmlData

    RBUILDER_BUILD_TYPE = 'VWS'

    @classmethod
    def isDriverFunctional(cls):
        return globuslib.WorkspaceCloudClient.isFunctional()

    def drvCreateCloudClient(self, credentials):
        cloudConfig = self.getTargetConfiguration()
        props = globuslib.WorkspaceCloudProperties()
        userCredentials = credentials
        props.set('vws.factory', self.cloudName)
        props.set('vws.repository', cloudConfig['repository'])
        props.set('vws.factory.identity', cloudConfig['factoryIdentity'])
        props.set('vws.repository.identity', cloudConfig['repositoryIdentity'])
        props.set('vws.repository.basedir', cloudConfig['repositoryBaseDir'])
        try:
            cli = globuslib.WorkspaceCloudClient(props, cloudConfig['caCert'],
                userCredentials['userCert'], userCredentials['userKey'],
                userCredentials['sshPubKey'], cloudConfig['alias'])
        except globuslib.Error, e:
            raise errors.PermissionDenied(message = str(e))
        return cli

    def _getUserIdForInstanceStore(self):
        return self._cloudClient.userCertHash

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

    def drvPopulateLaunchDescriptor(self, descr):
        descr.setDisplayName("Globus Workspaces Launch Parameters")
        descr.addDescription("Globus Workspaces Launch Parameters")
        descr.addDataField("instanceType",
            descriptions = "Instance Size", required = True,
            type = descr.EnumeratedType(
                descr.ValueWithDescription(x,
                    descriptions = y)
                  for (x, y) in VWS_InstanceTypes.idMap),
            help = [
                ("launch/instanceSize.html", None)
            ]
        )
        descr.addDataField("minCount",
            descriptions = "Minimum Number of Instances",
            type = "int", required = True, default = 1,
            help = [
                ("launch/minInstances.html", None)
            ],
            constraints = dict(constraintName = 'range',
                               min = 1, max = 100))
        descr.addDataField("maxCount", required = True,
            descriptions = "Maximum Number of Instances",
            type = "int", default = 1,
            help = [
                ("launch/maxInstances.html", None)
            ],
            constraints = dict(constraintName = 'range',
                               min = 1, max = 100))
        descr.addDataField("duration", required = True,
            descriptions = "Duration (minutes)",
            type = "int",
            help = [
                ("launch/duration.html", None)
            ],
            constraints = dict(constraintName = 'range',
                               min = 1, max = 1440))
        return descr


    def getImage(self, imageId):
        return self.getImages([imageId])[0]

    def drvGetInstances(self, instanceIds):
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

    def getLaunchInstanceParameters(self, image, descriptorData):
        params = baseDriver.BaseDriver.getLaunchInstanceParameters(self,
            image, descriptorData)
        getField = descriptorData.getField
        duration = getField('duration')
        params['duration'] = duration
        return params

    def launchInstanceProcess(self, job, image, auth, **launchParams):
        duration = launchParams.pop('duration')
        if not image.getIsDeployed():
            tmpDir = os.path.join(self.client._tmpDir, 'downloads')
            util.mkdirChain(tmpDir)
            try:
                job.addLog(self.LogEntry('Downloading image'))
                dlImagePath = self._downloadImage(image, tmpDir, auth = auth)
                job.addLog(self.LogEntry('Preparing image'))
                imgFile = self._prepareImage(dlImagePath)
                job.addLog(self.LogEntry('Publishing image'))
                self._publishImage(imgFile)
            finally:
                util.rmtree(tmpDir, ignore_errors = True)
        imageId = image.getImageId()

        def callback(realId):
            pass

        job.addLog(self.LogEntry('Launching'))
        realId = self.client.launchInstances([imageId],
            duration = duration, callback = callback)
        return str(realId)

    def _prepareImage(self, downloadFilePath):
        retfile = self.client._repackageImage(downloadFilePath)
        os.unlink(downloadFilePath)
        return retfile

    def _publishImage(self, fileName):
        self.client.transferInstance(fileName)

    def getImagesFromTarget(self, imageIds):
        cloudAlias = self.client.getCloudAlias()

        targetImageIds = self.client.listImages()
        imageList = images.BaseImages()

        for imageId in targetImageIds:
            if imageIds is not None and imageId not in imageIds:
                continue
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

    def _imageIdInMap(self, imageId, imageIdMap):
        # Images in mint have no .gz, but we have to store them with a .gz in
        # the grid. This normalizes the 
        if imageId is None:
            return None
        if imageId.endswith('.gz') and imageId not in imageIdMap:
            imageId = imageId[:-3]
        return (imageId in imageIdMap and imageId) or None

    @classmethod
    def getImageIdFromMintImage(cls, image):
        imageSha1 = baseDriver.BaseDriver.getImageIdFromMintImage(image)
        if imageSha1 is None:
            return imageSha1
        return imageSha1 + '.gz'

    @classmethod
    def _readCredentialsFromStore(cls, store, userId, cloudName):
        userId = userId.replace('/', '_')
        return dict(
            (os.path.basename(k), store.get(k))
                for k in store.enumerate("%s/%s" % (userId, cloudName)))

    @classmethod
    def _writeCredentialsToStore(cls, store, userId, cloudName, credentials):
        userId = userId.replace('/', '_')
        for k, v in credentials.iteritems():
            key = "%s/%s/%s" % (userId, cloudName, k)
            store.set(key, v)

    @classmethod
    def getCloudNameFromDescriptorData(cls, descriptorData):
        return descriptorData.getField('factory')

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
