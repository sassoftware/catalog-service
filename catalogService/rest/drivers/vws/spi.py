
LaunchInstanceParameters = {'InstanceType' : Enumerate({'large' : 'Large',
                                                    'Extra Large' : 'x-large',
                                                    'small' : 'small'},
                                                    default='small'),
                            'Security groups' : SecurityGroups }

class VWSCloudManager(CloudManager):
    def __init__(self, handle, client):
        self.handle = handle

    def launchCloudParameters(self):
        return LaunchCloudParameters()

    def createCloud(self, parameters):
        parameters = LaunchCloudParmaeters(parameters)
        cloudId = self.client.createCloud(parameters)
        return cloudId

    def updateCloud(self, cloudId, parameters)
        parameters = LaunchCloudParameters(parameters)
        self.client.updateCloud(cloudId, parameters)

    def listCloudIds(self, parameters):
        self.client.listCloudIds()

class VWSCloud(Cloud):
    def __init__(self, cloudId, handle, mintClient):
        """
        @param handle: handle to set callback info.
        """
        self.client = VWSClient()
        self.handle = handle
        self.mintClient = mintClient

    def launchInstanceParameters(self):
        """
        @returns: {field : QuestionItem} dict where field is the piece
        of launchData that needs to be filled in and QuestionItem is the
        question that needs to be asked.
        """
        return LaunchInstanceParameters()

    def launchInstance(self, cloud, params):
        """
        @param cloud: Cloud in which to launch the  instance
        @param params: dictionary of parameters required to launch this image type
        @return: instanceId
        """
        params = LaunchInstanceParameters(params)
        image = self.client.getImage(params.imageId)
        instanceId = self.handle.newInstanceId(imageId)
        pid = os.fork()
        if not pid:
            if needToUploadImage:
                self.handle.setState(instanceId, 'Downloading Image')
                self._downloadImage(image)
                self.handle.setState(instanceId, 'Preparing Image')
                self._prepareImage(image)
                self.handle.setState(instanceId, 'Publishing Image')
                self.client.publishImage(cloudId, image)
            self.handle.setState(instanceId, 'Launching')
            realId = self.cloudClient.launchInstances(self.cloudId, [imageId],
                                         duration = params.duration)
            return realId
        else:
            os.waitpid(pid, 0)
            return instanceId


    def terminateInstances(self, instanceIds):
        for instanceId in instanceIds:
            self.client.terminateInstance(cloudId, instanceId):
            self.handle.setTerminated(cloudId, instanceId)

    def getInstances(self, instanceIds):
        instances = []
        for instanceData in self.client.getInstances(instanceIds)
            inst = VWSInstance(instanceData.instanceId,
                               startTime=instanceData.startTime,
                               ipAddress=instanceData.getIP(),
                               hostname=instanceData.getName(),
                               cloudName=self.cloudId)
            instances.append(inst)
        return instances

    def listInstanceIds(self):
        return self.client.getAllInstanceIds()

    def listImageIds(self):
        return self.client.getAllImageIds()

    def getImages(self, imageIds):
        images = []
        for imageData in  self.client.getImages(imageIds):
            shortName = os.path.baseName(imageData.imageId)
            extra = dict(isDeployed=imageData.isDeployed,
                         is_rbuilderImage=imageData.isRbuilderImage)
            i =  VWSImage(imageData.imageId,
                          shortName=shortName,
                          longName=imageData.imageId,
                          cloudId=self.cloudId,
                          parameters = extra)
            images.append(i)
        return images
