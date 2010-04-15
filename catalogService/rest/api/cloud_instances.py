#!/usr/bin/python
#
# Copyright (c) 2008-2010 rPath, Inc.  All Rights Reserved.
#

import os
import urllib

from catalogService.errors import InvalidCloudName

from catalogService.rest.database import commitafter
from catalogService.rest.api.base import BaseCloudController
from catalogService.rest.api import trove_change
from catalogService.rest.middleware.response import XmlResponse, XmlStringResponse, XmlSerializableObjectResponse

class ImagesController(BaseCloudController):
    modelName = 'imageId'

    def index(self, request, cloudName):
        imgNodes = self.driver(request, cloudName).getAllImages()
        return XmlResponse(imgNodes)

    def get(self, request, cloudName, imageId):
        images = self.driver(request, cloudName).getImages([imageId])
        return XmlResponse(images)

class InstancesUpdateController(BaseCloudController):
    modelName = 'instanceUpdateId'

    def create(self, request, cloudName, instanceId):
        insts = self.driver(request, cloudName).updateInstance(instanceId)
        return XmlResponse(insts)

class SecurityGroupsController(BaseCloudController):
    modelName = 'securityGroup'

    def index(self, request, cloudName, instanceId):
        return self._getMethod(request, cloudName, instanceId,
            "getSecurityGroups")

    def get(self, request, cloudName, instanceId, securityGroup):
        return self._getMethod(request, cloudName, instanceId,
            "getSecurityGroup", securityGroup)

    def update(self, request, cloudName, instanceId, securityGroup):
        requestData = request.read()
        return self._getMethod(request, cloudName, instanceId,
            "updateSecurityGroup", securityGroup, requestData)

    def _getMethod(self, request, cloudName, instanceId, methodName, *args):
        meth = getattr(self.driver(request, cloudName), methodName, None)
        if meth is None:
            return XmlStringResponse("", status = 404)
        return XmlResponse(meth(instanceId, *args))

class AvailableUpdatesController(BaseCloudController):
    modelName = 'troveSpec'

    urls = dict(troveChanges=trove_change.TroveChangesController)

class InstancesForceUpdateController(BaseCloudController):
    def index(self, request, cloudName, instanceId):
        insts = self.driver(request, cloudName).getInstance(instanceId, True)
        return XmlResponse(insts)

class InstancesController(BaseCloudController):
    urls = dict(updates=InstancesUpdateController,
                securityGroups=SecurityGroupsController,
                availableUpdates=AvailableUpdatesController,
                forceUpdate=InstancesForceUpdateController,)

    modelName = 'instanceId'
    def index(self, request, cloudName):
        insts = self.driver(request, cloudName).getAllInstances()
        return XmlResponse(insts)

    def get(self, request, cloudName, instanceId):
        insts = self.driver(request, cloudName).getInstance(instanceId)
        return XmlResponse(insts)

    def create(self, request, cloudName):
        "launch a new instance"
        request.logger.info("User %s: launching instance in %s/%s" % (
            request.auth[0], self.driver.cloudType, cloudName))
        # We need to pass in authentication information, downloading private
        # images requires that.
        job = self.driver(request, cloudName).launchInstance(request.read(),
                request.auth)
        request.logger.info("User %s: %s/%s: launched job %s with image %s"
            % ( request.auth[0], self.driver.cloudType, cloudName,
            job.getId(), os.path.basename(job.getImageId())))
        return XmlResponse(job)

    def destroy(self, request, cloudName, instanceId):
        insts = self.driver(request, cloudName).terminateInstance(instanceId)
        return XmlResponse(insts)


class UserEnvironmentController(BaseCloudController):
    def index(self, request, cloudName, userName):
        if userName != request.auth[0]:
            return self.PermissionDenied(request)
        return XmlResponse(self.driver(request, cloudName).getEnvironment())

class CredentialsController(BaseCloudController):
    def index(self, request, cloudName, userName):
        if userName != request.auth[0]:
            return self.PermissionDenied(request)
        ddata = self.driver(request, cloudName).getUserCredentials()
        return XmlSerializableObjectResponse(ddata)

    @commitafter
    def update(self, request, cloudName, userName):
        if userName != request.auth[0]:
            return self.PermissionDenied(request)
        dataLen = request.getContentLength()
        data = request.read(dataLen)

        return XmlResponse(self.driver(request, cloudName).setUserCredentials(
            data))

class ConfigurationController(BaseCloudController):
    def index(self, request, cloudName):
        ddata = self.driver(request, cloudName).getConfiguration()
        return XmlSerializableObjectResponse(ddata)

class LaunchDescriptorController(BaseCloudController):
    def index(self, request, cloudName):
        descr = self.driver(request, cloudName).getLaunchDescriptor()
        return XmlSerializableObjectResponse(descr)

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
                users = UsersController)

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

    @commitafter
    def create(self, request):
        return XmlResponse(self.driver(request).createCloud(request.read()))

    @commitafter
    def destroy(self, request, cloudName):
        return XmlResponse(self.driver(request, cloudName).removeCloud())
