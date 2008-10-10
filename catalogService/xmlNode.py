#
# Copyright (c) 2008 rPath, Inc.
#

import urllib
import sha

from rpath_common import xmllib

class BaseNode(xmllib.BaseNode):
    tag = None
    # Hint for a slot's type
    _slotTypeMap = {}

    # Overrides for whatever was provided in the constructor
    # This is useful, for instance, for providing some quasi-immutable
    # defaults
    _constructorOverrides = {}


    def __init__(self, attrs=None, nsMap = None, **kwargs):
        xmllib.BaseNode.__init__(self, attrs, nsMap = nsMap)
        for slot in self.__slots__:
            setattr(self, slot, None)

        kwargs.update(self._constructorOverrides)
        for k in self.__slots__:
            if k.startswith('_'):
                # Private variable, do not set
                continue
            method = getattr(self, "set%s%s" % (k[0].upper(), k[1:]))
            method(kwargs.get(k))

    def setName(self, name):
        pass

    def getName(self):
        return self.tag

    _getName = getName

    def getAbsoluteName(self):
        return self.tag

    def _iterChildren(self):
        for fName in self.__slots__:
            if fName.startswith('_'):
                continue
            fVal = getattr(self, fName)
            if hasattr(fVal, "getElementTree"):
                yield fVal

    def _iterAttributes(self):
        return {}

    def addChild(self, node):
        nodeName = node.getName()
        if nodeName in self.__slots__:
            setattr(self, nodeName, node)

    def getElementTree(self, *args, **kwargs):
        eltree = xmllib.BaseNode.getElementTree(self, *args, **kwargs)
        if '_xmlNodeHash' not in self.__slots__ or self._xmlNodeHash is not None:
            return eltree
        # Compute the checksum
        csum = sha.new()
        csum.update(xmllib.etree.tostring(eltree, pretty_print = False,
                    xml_declaration = False, encoding = 'UTF-8'))
        self._xmlNodeHash = csum.hexdigest()
        eltree.attrib['xmlNodeHash'] = self._xmlNodeHash
        return eltree

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
        if hasattr(value, 'getElementTree') and value._getName() == key:
            # This catches the case where we have a list defined as one of the
            # sub-nodes for this object
            setattr(self, key, value)
            return self
        slotType = self._slotTypeMap.get(key)
        if slotType == bool or isinstance(slotType, xmllib.BooleanNode):
            cls = xmllib.BooleanNode
            value = cls.toString(value)
        elif slotType == int or isinstance(value, int):
            cls = xmllib.IntegerNode
            value = str(value)
        else:
            cls = xmllib.GenericNode
        setattr(self, key, cls().setName(key).characters(value))
        return self

    def _get(self, key):
        val = getattr(self, key)
        if val is None:
            return None
        slotType = self._slotTypeMap.get(key)
        if slotType == bool:
            return xmllib.BooleanNode.fromString(val.getText())
        if isinstance(val, xmllib.IntegerNode):
            return val.finalize()
        if isinstance(val, BaseNode) and val.__slots__:
            return val
        if hasattr(val, 'getText'):
            return val.getText()
        # Well, this may be a list of values. Just return it
        return val

    @classmethod
    def urlquote(cls, data):
        return urllib.quote(data, safe = "")

    def __repr__(self):
         return "<%s:id=%s at %#x>" % (self.__class__.__name__, self.getId(),
            id(self))


class BaseNodeCollection(xmllib.SerializableList):
    "Base class for node collections"

    def __init__(self, attrs = None, nsMap = None):
        xmllib.SerializableList.__init__(self)
        self._attrs = attrs or {}
        self._nsMap = nsMap or {}

    def setName(self, name):
        "No-op, it should be defined by the class"

    def getNamespaceMap(self):
        return self._nsMap.copy()

    def finalize(self):
        return self

    def characters(self, data):
        return self

    addChild = xmllib.SerializableList.append
    getName = xmllib.SerializableList._getName

class Handler(xmllib.DataBinder):
    "Base xml handler"
