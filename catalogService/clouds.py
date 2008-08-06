#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

import xmlNode

class BaseCloud(xmlNode.BaseNode):
    tag = 'cloud'
    __slots__ = [ 'id', 'cloudName', 'description', 'cloudType', 'cloudAlias' ]

class BaseClouds(xmlNode.BaseNodeCollection):
    tag = "clouds"

class Handler(xmllib.DataBinder):
    cloudClass = BaseCloud
    cloudsClass = BaseClouds
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.cloudClass, self.cloudClass.tag)
        self.registerType(self.cloudsClass, self.cloudsClass.tag)
