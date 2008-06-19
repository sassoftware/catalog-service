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
    def __init__(self, attrs = None, nsMap = None, **kwargs):
        xmlNode.BaseNode.__init__(self, attrs = attrs, nsMap = nsMap)

        for k in self.__slots__:
            method = getattr(self, "set%s%s" % (k[0].upper(), k[1:]))
            method(kwargs.get(k))

    # Magic function mapper
    def __getattr__(self, name):
        if name[:3] not in ['get', 'set']:
            raise AttributeError(name)
        slot = "%s%s" % (name[3].lower(), name[4:])
        if slot not in self.__slots__:
            raise AttributeError(name)
        if name[:3] == 'get':
            return lambda: self._get(slot)
        return lambda x: self._set(slot, x)

    def _set(self, key, value):
        setattr(self, key, None)
        if value is None:
            return self
        setattr(self, key, xmllib.GenericNode().setName(key).characters(value))
        return self

    def _get(self, key):
        val = getattr(self, key)
        if val is None:
            return None
        return val.getText()

class BaseInstances(xmlNode.BaseNodeCollection):
    tag = "instances"

class Handler(xmllib.DataBinder):
    instanceClass = BaseInstance
    instancesClass = BaseInstances
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.instanceClass, self.instanceClass.tag)
        self.registerType(self.instancesClass, self.instancesClass.tag)
