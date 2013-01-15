#
# Copyright (c) rPath, Inc.
#

from xobj import xobj2
from lxml import etree
import sys
import StringIO
import weakref

from rmake3.core import handler

from conary import conarycfg
from conary.lib.formattrace import formatTrace

from catalogService import errors
from catalogService import storage

from catalogService.rest.models import xmlNode

from rpath_repeater import models
from rpath_repeater.codes import Codes as C
from rpath_repeater.codes import NS
from rpath_repeater.utils import base_forwarding_plugin as bfp

class Authorization(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class TargetsPlugin(bfp.BaseForwardingPlugin):
    """
    Setup dispatcher side of the interface detection.
    """

    def dispatcher_pre_setup(self, dispatcher):
        handler.registerHandler(TargetsTestCreateHandler)
        handler.registerHandler(TargetsTestCredentialsHandler)
        handler.registerHandler(TargetsImageListHandler)
        handler.registerHandler(TargetsInstanceListHandler)
        handler.registerHandler(TargetsInstanceCaptureHandler)
        handler.registerHandler(TargetsImageDeployHandler)
        handler.registerHandler(TargetsSystemLaunchHandler)
        handler.registerHandler(TargetsImageDeployDescriptorHandler)
        handler.registerHandler(TargetsSystemLaunchDescriptorHandler)

    def worker_get_task_types(self):
        return {
            NS.TARGET_TEST_CREATE: TargetsTestCreate,
            NS.TARGET_TEST_CREDENTIALS: TargetsTestCredentials,
            NS.TARGET_IMAGES_LIST: TargetsImageListTask,
            NS.TARGET_INSTANCES_LIST: TargetsInstanceListTask,
            NS.TARGET_SYSTEM_CAPTURE: TargetsInstanceCaptureTask,
            NS.TARGET_IMAGE_DEPLOY: TargetsImageDeployTask,
            NS.TARGET_SYSTEM_LAUNCH: TargetsSystemLaunchTask,
            NS.TARGET_IMAGE_DEPLOY_DESCRIPTOR: TargetsImageDeployDescriptorTask,
            NS.TARGET_SYSTEM_LAUNCH_DESCRIPTOR: TargetsSystemLaunchDescriptorTask,
        }


class BaseHandler(bfp.BaseHandler):
    firstState = 'callRun'
    # using the system launch task should be good enough, it's deployed
    # where the reg one is deployed
    RegistrationTaskNS = NS.TARGET_SYSTEM_LAUNCH

    def setup(self):
        bfp.BaseHandler.setup(self)

    def callRun(self):
        self.initCall()
        return self._run()

    def initCall(self):
        bfp.BaseHandler.initCall(self)
        if not self.zone:
            self.setStatus(C.ERR_ZONE_MISSING, 'Required argument zone missing')
            self.postFailure()
            return
        # Add IP addresses for all nodes in this zone
        self.data['params'].zoneAddresses = self.zoneAddresses

    def _run(self):
        self.setStatus(C.MSG_NEW_TASK, 'Creating task')
        task = self.newTask(self.jobType, self.jobType, self.data, zone=self.zone)
        return self._handleTask(task)

    def getResultsUrl(self):
        return self.jobUrl

    def postprocessXmlNode(self, elt):
        job = self.newJobElement()
        self.addJobResults(job, elt)
        return job

class TargetsTestCreateHandler(BaseHandler):
    jobType = NS.TARGET_TEST_CREATE

class TargetsTestCredentialsHandler(BaseHandler):
    jobType = NS.TARGET_TEST_CREDENTIALS

class TargetsImageListHandler(BaseHandler):
    jobType = NS.TARGET_IMAGES_LIST

class TargetsInstanceListHandler(BaseHandler):
    jobType = NS.TARGET_INSTANCES_LIST

class TargetsInstanceCaptureHandler(BaseHandler):
    jobType = NS.TARGET_SYSTEM_CAPTURE

class TargetsImageDeployHandler(BaseHandler):
    jobType = NS.TARGET_IMAGE_DEPLOY

    def setup(self):
        BaseHandler.setup(self)
        self.addTaskStatusCodeWatcher(C.PART_RESULT_1,
            self.linkImage)

    def linkImage(self, task):
        params = self.data['params'].args['params']
        targetImageXmlTemplate = params['targetImageXmlTemplate']
        response = task.task_data.thaw().getObject()
        imageXml = response.response
        targetImageXml = targetImageXmlTemplate % dict(image=imageXml)
        imageFileUpdateUrl = params['imageFileUpdateUrl']
        location = models.URL.fromString(imageFileUpdateUrl, port=80)
        self.postResults(targetImageXml, location=location)

class TargetsSystemLaunchHandler(TargetsImageDeployHandler):
    jobType = NS.TARGET_SYSTEM_LAUNCH

    def setup(self):
        TargetsImageDeployHandler.setup(self)
        self.addTaskStatusCodeWatcher(C.PART_RESULT_2,
            self.uploadSystems)

    def uploadSystems(self, task):
        params = self.data['params'].args['params']
        systemsCreateUrl = params['systemsCreateUrl']
        response = task.task_data.thaw().getObject()
        systemsXml = response.response
        location = models.URL.fromString(systemsCreateUrl, port=80)
        self.postResults(systemsXml, method='POST', location=location)

class TargetsImageDeployDescriptorHandler(BaseHandler):
    jobType = NS.TARGET_IMAGE_DEPLOY_DESCRIPTOR

class TargetsSystemLaunchDescriptorHandler(BaseHandler):
    jobType = NS.TARGET_SYSTEM_LAUNCH_DESCRIPTOR

class RestDatabase(object):
    __slots__ = [ 'auth', 'taskHandler', 'targetMgr', ]
    class Auth(object):
        __slots__ = [ 'auth', ]

    class TargetManager(object):
        def __init__(self, taskHandler):
            self.taskHandler = taskHandler

        def linkTargetImageToImage(self, targetTypeName, targetName,
                rbuilderImageId, targetImageId):
            self.taskHandler.linkTargetImageToImage(rbuilderImageId, targetImageId)

    # Class attribute. We only want to read the conary config once, when
    # the module is loaded.
    cfg = conarycfg.ConaryConfiguration(readConfigFiles=True)

    def __init__(self, taskHandler):
        self.taskHandler = weakref.proxy(taskHandler)
        self.auth = self.Auth()
        self.targetMgr = self.TargetManager(self.taskHandler)

class BaseTaskHandler(bfp.BaseTaskHandler):
    """
    Task that runs on the rUS to query the target systems.
    """
    RestDatabaseClass = RestDatabase

    def run(self):
        self._initConfig()
        try:
            self._initTarget()
            self._run()
        except:
            typ, value, tb = sys.exc_info()
            out = StringIO.StringIO()
            formatTrace(typ, value, tb, stream = out, withLocals = False)
            out.write("\nFull stack:\n")
            formatTrace(typ, value, tb, stream = out, withLocals = True)

            self.sendStatus(C.ERR_GENERIC,
                "Error in target call: %s"
                    % str(value), out.getvalue())

    def _initConfig(self):
        self.data = self.getData()
        params = self.data.pop('params')
        self.targetConfig = params.targetConfiguration
        self.userCredentials = params.targetUserCredentials
        self.allUserCredentials = params.targetAllUserCredentials
        self.cmdArgs = params.args
        self.zoneAddresses = params.zoneAddresses

    def _initTarget(self):
        driverName = self.targetConfig.targetType
        # xen enterprise is a one-off
        if driverName == 'xen-enterprise':
            driverName = 'xenent'

        moduleName = "catalogService.rest.drivers.%s" % driverName
        BaseDriverClass = __import__(moduleName, {}, {}, '.driver').driver

        class Driver(BaseDriverClass):
            def __init__(slf, userCredentials, *args, **kwargs):
                super(Driver, slf).__init__(*args, **kwargs)
                slf.setUserCredentials(userCredentials)
            def setUserCredentials(slf, userCredentials):
                slf._userCredentials = userCredentials
                slf.reset()
            def _getCloudCredentialsForUser(slf):
                return slf._userCredentials.credentials
            def _getStoredTargetConfiguration(slf):
                config = self.targetConfig.config.copy()
                config.update(alias=self.targetConfig.alias)
                return config
            def _checkAuth(slf):
                return True
            def _getMintImagesByType(slf, imageType):
                "Overridden, no access to mint"
                return []

        restDb = self._createRestDatabase()
        scfg = storage.StorageConfig(storagePath="/srv/rbuilder/catalog")
        self.driver = Driver(self.userCredentials, scfg, driverName, cloudName=self.targetConfig.targetName,
            db=restDb, inventoryHandler=InventoryHandler(weakref.ref(self)),
            zoneAddresses=self.zoneAddresses)
        self.driver._nodeFactory.baseUrl = '/'

    def finishCall(self, node, msg, code=C.OK):
        if node is not None:
            xml = self.toXml(node)
            data = models.Response(response=xml)
            self.setData(data)
        self.sendStatus(code, msg)

    @classmethod
    def toXml(cls, node):
        if hasattr(node, 'toXml'):
            return node.toXml()
        hndlr = xmlNode.Handler()
        return hndlr.toXml(node)

    def _createRestDatabase(self):
        db = self.RestDatabaseClass(self)
        if self.userCredentials is not None:
            db.auth.auth = Authorization(authorized=True,
                userId=self.userCredentials.rbUserId,
                admin=bool(self.userCredentials.isAdmin))
        return db

class TargetsTestCreate(BaseTaskHandler):
    def _run(self):
        """
        Validate we can talk to the target (if the driver supports that)
        """
        try:
            self.driver.drvVerifyCloudConfiguration(self.targetConfig.config)
        except errors.PermissionDenied:
            return self.finishCall(None, "Invalid target configuration",
                code=C.ERR_BAD_ARGS)
        target = models.Target()
        self.finishCall(target, "Target validated")

class TargetsTestCredentials(BaseTaskHandler):
    def _run(self):
        """
        Validate we can talk to the target using these credentials
        """
        try:
            self.driver.drvValidateCredentials(self.userCredentials.credentials)
        except errors.PermissionDenied:
            return self.finishCall(None, "Invalid target credentials",
                code=C.ERR_AUTHENTICATION)
        target = models.Target()
        self.finishCall(target, "Target credentials validated")

class TargetsImageListTask(BaseTaskHandler):
    def _run(self):
        """
        List target images
        """
        images = self.driver.getImagesFromTarget(None)
        self.finishCall(images, "Retrieved list of images")

class TargetsInstanceListTask(BaseTaskHandler):
    def _run(self):
        """
        List target instances
        """
        instancesMap = {}
        for creds in self.allUserCredentials:
            self.driver.setUserCredentials(creds)
            credId = creds.opaqueCredentialsId
            instances = self.driver.getAllInstances()
            for inst in instances:
                instId = inst.getInstanceId()
                # Append current credentials to this instance
                instancesMap.setdefault(instId, (inst, []))[1].append(credId)
        instances = self.driver.Instances()
        for _, (inst, credIds) in sorted(instancesMap.items()):
            inst.setCredentials(credIds)
            instances.append(inst)
        self.finishCall(instances, "Retrieved list of instances")

class JobProgressTaskHandler(BaseTaskHandler):
    class Job(object):
        def __init__(self, msgMethod):
            self.msgMethod = msgMethod

        def addHistoryEntry(self, *args):
            self.msgMethod(C.MSG_PROGRESS, ' '.join(args))

class TargetsInstanceCaptureTask(JobProgressTaskHandler):
    def _run(self):
        """
        List target instances
        """
        instanceId = self.cmdArgs['instanceId']
        params = self.cmdArgs['params']
        # Look at captureSystem to figure out which params are really
        # used
        job = self.Job(self.sendStatus)
        self.driver.captureSystem(job, instanceId, params)
        imageRef = models.ImageRef(params['image_id'])
        self.finishCall(imageRef, "Instance captured")

class TargetsImageDeployTask(JobProgressTaskHandler):
    def _run(self):
        job = self.Job(self.sendStatus)
        img, descriptorData = self._getImageInfo()
        img = self.driver.deployImageFromUrl(job, img, descriptorData)
        self.finishCall(img, "Image deployed")

    def _getImageInfo(self):
        params = self.cmdArgs['params']
        imageFileInfo = params['imageFileInfo']
        descriptorData = params['descriptorData']
        imageDownloadUrl = params['imageDownloadUrl']
        imageData = params['imageData']
        img = self._isImageDeployed()
        if img is None:
            img = self.driver.imageFromFileInfo(imageFileInfo, imageDownloadUrl,
                    imageData=imageData)
        else:
            self.driver.updateImageFromFileInfo(img, imageFileInfo,
                    imageData=imageData)
        self.image = img
        return img, descriptorData

    def linkTargetImageToImage(self, rbuilderImageId, targetImageId):
        if not self.image.getShortName():
            self.image.setShortName(targetImageId)
        imageXml = etree.tostring(self.image.getElementTree(),
            xml_declaration=False)

        io = XmlStringIO(imageXml)
        self.finishCall(io, "Linking image", C.PART_RESULT_1)

    def _isImageDeployed(self):
        targetImageIdList = self.cmdArgs['params']['targetImageIdList']
        if not targetImageIdList:
            return None
        images = self.driver.getImagesFromTarget(targetImageIdList)
        if images:
            return images[0]
        return None


class System(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class Systems(object):
    _xobjMeta = xobj2.XObjMetadata(
        tag = 'systems',
        elements = [ xobj2.Field("system", [ System ]) ])

class InventoryHandler(object):
    System = System
    Systems = Systems

    def __init__(self, parent):
        self.parent = parent
        self.systems = self.Systems()
        self.systems.system = []
        # The driver is not yet initialized, so don't try to access it
        # in the constructor

    @property
    def log_info(self):
        return self.parent().log_info

    def addSystem(self, systemFields, dnsName=None, withNetwork=True):
        parent = self.parent()
        system = self.System(**systemFields)
        system.dnsName = dnsName
        system.targetName = parent.driver.cloudName
        system.targetType = parent.driver.cloudType
        self.systems.system.append(system)

    def reset(self):
        del self.systems.system[:]

    def commit(self):
        taskHandler = self.parent()
        if taskHandler is None:
            return
        doc = xobj2.Document(root=self.systems)
        io = XmlStringIO(doc.toxml())
        taskHandler.finishCall(io, "Systems created", C.PART_RESULT_2)

class TargetsSystemLaunchTask(TargetsImageDeployTask):
    def _run(self):
        job = self.Job(self.sendStatus)
        img, descriptorData = self._getImageInfo()
        instanceIdList = self.driver.launchSystemSynchronously(job, img, descriptorData)
        io = XmlStringIO(xobj2.Document.serialize(self.driver.inventoryHandler.systems))
        self.finishCall(io, "Systems launched")

class XmlStringIO(StringIO.StringIO):
    def toXml(self):
        return self.getvalue()

class TargetsImageDeployDescriptorTask(BaseTaskHandler):
    def _run(self):
        """
        Fetch image deployment descriptor
        """
        descr = self.driver.getImageDeploymentDescriptor()
        io = XmlStringIO(etree.tounicode(descr.getElementTree()))
        self.finishCall(io, "Descriptor generated")

class TargetsSystemLaunchDescriptorTask(BaseTaskHandler):
    def _run(self):
        """
        Fetch system launch descriptor
        """
        descr = self.driver.getLaunchDescriptor()
        io = XmlStringIO()
        descr.serialize(io)
        self.finishCall(io, "Descriptor generated")
