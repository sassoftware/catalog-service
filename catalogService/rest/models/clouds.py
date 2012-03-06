#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import rpath_xmllib as xmllib

from catalogService.rest.models import instances
import xmlNode

class BaseCloud(xmlNode.BaseNode):
    tag = 'cloud'
    __slots__ = [ 'id', 'cloudName', 'description', 'cloudAlias',
        'type', 'images', 'instances', 'userCredentials', 'configuration',
        'descriptorLaunch', 'descriptorDeploy', 'activeJobs', ]
    _slotAttributes = set(['id'])

class BaseClouds(xmlNode.BaseNodeCollection):
    tag = "clouds"

class BaseHrefNode(xmlNode.BaseNode):
    __slots__ = [ 'href' ]
    _slotAttributes = set(__slots__)

    def __repr__(self):
         return "<%s:href=%s at %#x>" % (self.__class__.__name__,
            self.getHref(), id(self))

class Type(BaseHrefNode):
    tag = 'type'

class Images(BaseHrefNode):
    tag = 'images'

class Instances(BaseHrefNode):
    tag = 'instances'

class UserCredentials(BaseHrefNode):
    tag = 'userCredentials'

class Configuration(BaseHrefNode):
    tag = 'configuration'

class DescriptorLaunch(BaseHrefNode):
    tag = 'descriptorLaunch'

class DescriptorDeploy(BaseHrefNode):
    tag = 'descriptorDeploy'

class ActiveJobs(BaseHrefNode):
    tag = "activeJobs"

class Handler(xmllib.DataBinder):
    cloudClass = BaseCloud
    cloudsClass = BaseClouds
    typeClass = Type
    imagesClass = Images
    instancesClass = Instances
    userCredentialsClass = UserCredentials
    configurationClass = Configuration
    descriptorLaunchClass = DescriptorLaunch
    descriptorDeployClass = DescriptorDeploy
    activeJobsClass = ActiveJobs
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        for cls in [ self.cloudClass, self.cloudsClass, self.typeClass,
                     self.imagesClass, self.instancesClass,
                     self.userCredentialsClass, self.configurationClass,
                     self.descriptorLaunchClass, self.descriptorDeployClass, self.activeJobsClass ]:
            self.registerType(cls, cls.tag)
