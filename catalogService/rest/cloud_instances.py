#!/usr/bin/python2.4
#
# Copyright (c) 2008 rPath, Inc.  All Rights Reserved.
#

import os
import urllib

from catalogService import credentials
from catalogService.errors import InvalidCloudName

from catalogService.rest.base import BaseCloudController
from catalogService.rest.response import XmlResponse, XmlStringResponse

class ImagesController(BaseCloudController):
    modelName = 'imageId'

    def index(self, request, cloudName):
        imgNodes = self.driver(request, cloudName).getAllImages()
        return XmlResponse(imgNodes)

class InstancesUpdateController(BaseCloudController):
    modelName = 'instanceUpdateId'

    def create(self, request, cloudName, instanceId):
        insts = self.driver(request, cloudName).updateInstance(instanceId)
        return XmlResponse(insts)


class InstancesController(BaseCloudController):
    urls = dict(updates=InstancesUpdateController)

    modelName = 'instanceId'
    def index(self, request, cloudName):
        insts = self.driver(request, cloudName).getAllInstances()
        return XmlResponse(insts)

    def create(self, request, cloudName):
        "launch a new instance"
        request.logger.info("User %s: launching instance in %s/%s" % (
            request.auth[0], self.driver.cloudType, cloudName))
        insts = self.driver(request, cloudName).launchInstance(request.read(),
                                                               request.host)
        request.logger.info("User %s: launched instance %s/%s/%s with image %s"
            % ( request.auth[0], self.driver.cloudType, cloudName,
            ','.join([os.path.basename(x.getInstanceId()) for x in insts]),
            ','.join([os.path.basename(x.getImageId()) for x in insts])))
        return XmlResponse(insts)

    def destroy(self, request, cloudName, instanceId):
        insts = self.driver(request, cloudName).terminateInstance(instanceId)
        return XmlResponse(insts)


class InstanceTypesController(BaseCloudController):
    modelName = 'instanceTypeId'

    def index(self, request, cloudName):
        return XmlResponse(self.driver(request, cloudName).getInstanceTypes())

class UserEnvironmentController(BaseCloudController):
    def index(self, request, cloudName, userName):
        if userName != request.auth[0]:
            return XmlStringResponse("", status = 403)
        return XmlResponse(self.driver(request, cloudName).getEnvironment())

class CredentialsController(BaseCloudController):
    def index(self, request, cloudName, userName):
        if userName != request.auth[0]:
            return XmlStringResponse("", status = 403)
        return XmlResponse(self.driver(request, cloudName).getUserCredentials())

    def update(self, request, cloudName, userName):
        if userName != request.auth[0]:
            return XmlStringResponse("", status = 403)
        dataLen = request.getContentLength()
        data = request.read(dataLen)

        return XmlResponse(self.driver(request, cloudName).setUserCredentials(
            data))

class ConfigurationController(BaseCloudController):
    def index(self, request, cloudName):
        return XmlResponse(self.driver(request, cloudName).getConfiguration())

class LaunchDescriptorController(BaseCloudController):
    def index(self, request, cloudName):
        return XmlResponse(self.driver(request, cloudName).getLaunchDescriptor())

class DescriptorController(BaseCloudController):
    urls = dict(launch = LaunchDescriptorController)

class UsersController(BaseCloudController):
    modelName = 'userName'

    urls = dict(environment = UserEnvironmentController,
                credentials = CredentialsController)


class CloudTypeModelController(BaseCloudController):

    modelName = 'cloudName'

    urls = dict(configuration = ConfigurationController,
                descriptor = DescriptorController,
                images = ImagesController,
                instances = InstancesController,
                users = UsersController,
                instanceTypes = InstanceTypesController)

    def splitId(self, url):
        cloudName, rest = BaseCloudController.splitId(self, url)
        cloudName = urllib.unquote(cloudName)
        # note - may want to do further validation at the time of
        # passing the cloud name into the function...
        if not self.driver.isValidCloudName(cloudName):
            raise InvalidCloudName(cloudName)
        return cloudName, rest

    def index(self, request):
        'iterate available clouds'
        return XmlResponse(self.driver(request).listClouds())

    def get(self, request, cloudName):
        return XmlResponse(self.driver(request).getCloud(cloudName))

    def create(self, request):
        return XmlResponse(self.driver(request).createCloud(request.read()))

    def destroy(self, request, cloudName):
        return XmlResponse(self.driver(request, cloudName).removeCloud())
