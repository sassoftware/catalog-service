#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

import xmlNode

class BaseInstance(xmlNode.BaseNode):
    tag = 'instance'
    __slots__ = [ 'id', 'instanceId',
                  'dnsName', 'publicDnsName', 'privateDnsName',
                  'state', 'stateCode', 'keyName', 'shutdownState',
                  'previousState', 'instanceType', 'launchTime',
                  'imageId', 'placement', 'kernel', 'ramdisk',
                  'reservationId', 'ownerId']

class BaseInstances(xmlNode.BaseNodeCollection):
    tag = "instances"

class Handler(xmllib.DataBinder):
    instanceClass = BaseInstance
    instancesClass = BaseInstances
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.instanceClass, self.instanceClass.tag)
        self.registerType(self.instancesClass, self.instancesClass.tag)
