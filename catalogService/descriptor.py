#!/usr/bin/python2.4
#
# Copyright (c) 2008 rPath, Inc.
#
# This program is distributed under the terms of the Common Public License,
# version 1.0. A copy of this license should have been distributed with this
# source file in a file called LICENSE. If it is not present, the license
# is always available at http://www.rpath.com/permanent/licenses/CPL-1.0.
#
# This program is distributed in the hope that it will be useful, but
# without any warranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the Common Public License for
# full details.
#

import os
import re
import StringIO

from rpath_common.xmllib import api1 as xmllib

from catalogService import descriptor_errors as errors

InvalidXML = xmllib.InvalidXML

class _BaseClass(xmllib.SerializableObject):
    defaultNamespace = ''
    xmlSchemaNamespace = 'http://www.w3.org/2001/XMLSchema-instance'
    schemaDir = '/usr/share/factory/schemas'

    xmlSchemaLocation = 'http://www.rpath.org/permanent/descriptor-1.0.xsd' \
                        ' descriptor-1.0.xsd'

    def __init__(self, fromStream = None, validate = False, schemaDir = None):
        xmllib.SerializableObject.__init__(self)
        self._initFields()

        if fromStream:
            if isinstance(fromStream, (str, unicode)):
                fromStream = StringIO.StringIO(fromStream)
            self.parseStream(fromStream, validate = validate,
                             schemaDir = schemaDir)

    def parseStream(self, stream, validate = False, schemaDir = None):
        """
        Initialize the current object from an XML stream.
        @param stream: An XML stream
        @type stream: C{file}
        """
        self._initFields()

        binder = self._createBinder()
        try:
            xmlObj = binder.parseFile(stream, validate = validate,
                                      schemaDir = schemaDir)
        except xmllib.SchemaValidationError, e:
            raise errors.SchemaValidationError(str(e))
        self._postprocess(xmlObj)

    def serialize(self, stream):
        binder = xmllib.DataBinder()
        stream.write(binder.toXml(self))

    def _getLocalNamespaces(self):
        return {'xsi' : self.xmlSchemaNamespace}

    def _iterAttributes(self):
        yield ("{%s}schemaLocation" % self.xmlSchemaNamespace,
               self.xmlSchemaLocation)

class ConfigurationDescriptor(_BaseClass):
    "Class for representing the factory definition"

    xmlSchemaLocation = 'http://www.rpath.org/permanent/descriptor-1.0.xsd' \
                        ' descriptor-1.0.xsd'

    def _createBinder(self):
        binder = xmllib.DataBinder()
        stack = [ (_DescriptorNode, None) ]
        while stack:
            nodeClass, nodeClassName = stack.pop()
            binder.registerType(nodeClass, nodeClassName)
            scList = getattr(nodeClass, '_nodeDescription', [])
            for subClass, subClassName in scList:
                stack.append((subClass, subClassName))
        return binder

    def _postprocess(self, xmlObj):
        if isinstance(xmlObj, _DescriptorNode):
            self._metadata = xmlObj.metadata
            self._dataFields.extend(xmlObj.dataFields.iterChildren())
            self._dataFieldsHash.update(dict((x.name, x)
                for x in xmlObj.dataFields.iterChildren()))

    def getMetadata(self):
        """
        @return: the metadata associated with this object
        @rtype: C{_MetadataNode}
        """
        return self._metadata

    def getDisplayName(self):
        return self._metadata.displayName

    def setDisplayName(self, displayName):
        self._metadata.displayName = displayName

    def getDataFields(self):
        """
        @return: the data fields associated with this object
        @rtype: C{list} of C{_DataFieldNode}
        """
        return [ PresentationField(x) for x in self._dataFields ]

    def addDataField(self, name, **kwargs):
        nodeType = kwargs.get('type')
        constraints = kwargs.get('constraints', [])
        descriptions = kwargs.get('descriptions', [])
        constraintsDescriptions = kwargs.get('constraintsDescriptions', [])
        default = None
        if 'default' in kwargs:
            default = str(kwargs['default'])
        df = _DataFieldNode()
        df.name = name
        df.type = nodeType
        df.multiple = kwargs.get('multiple', None)
        df.descriptions = _Descriptions()
        df.descriptions.extend(
            [ _DescriptionNode.fromData(x.description, x.lang)
                for x in descriptions ])
        df.constraints = _ConstraintsNode.fromData(constraints)
        if df.constraints:
            df.constraints.descriptions = _Descriptions()
            # descriptions come first per XML schema. _ConstraintsNode.fromData
            # already defined the _children attribute, so we'll insert this
            # value in the front
            df.constraints._children.insert(0, df.constraints.descriptions)
            df.constraints.descriptions.extend([
                _DescriptionNode.fromData(x.description, x.lang) \
                    for x in constraintsDescriptions])
        df.default = default
        df.required = kwargs.get('required')
        self._dataFields.extend([ df ])
        self._dataFieldsHash[df.name] = df

    def getDataField(self, name):
        if name not in self._dataFieldsHash:
            return None
        return PresentationField(self._dataFieldsHash[name])

    def getDescriptions(self):
        """
        @return: the description fields associated with this object
        @rtype: C{list} of C{_DescriptionNode}
        """
        return self._metadata.descriptions.getDescriptions()

    def addDescription(self, description, lang=None):
        dn = _DescriptionNode.fromData(description, lang)
        if self._metadata.descriptions is None:
            self._metadata.descriptions = _Descriptions()
        self._metadata.descriptions.extend([dn])

    def _initFields(self):
        self._metadata = _MetadataNode()
        self._dataFields = _DataFieldsNode()
        self._dataFieldsHash = {}

    @staticmethod
    def _getName():
        return 'factory'

    def _iterChildren(self):
        yield self._metadata
        yield self._dataFields

class Description(object):
    __slots__ = [ 'description', 'lang' ]
    def __init__(self, description = None, lang = None, node = None):
        if node is None:
            self.description = description
            self.lang = lang
        else:
            self.description = node.getText()
            self.lang = node.getAttribute('lang')

class PresentationField(object):
    __slots__ = [ 'name', 'descriptions', 'type', 'multiple', 'default',
                  'constraints', 'constraintsDescriptions', 'required' ]
    def __init__(self, node):
        self.name = node.name
        self.descriptions = node.descriptions.getDescriptions()
        self.type = node.type
        self.multiple = node.multiple
        self.default = node.default
        self.required = node.required
        self.constraintsDescriptions = {}
        if node.constraints:
            self.constraints = node.constraints.presentation()
            self.constraintsDescriptions = node.constraints.getDescriptions()
        else:
            self.constraints = []

class _NodeDescriptorMixin(object):
    """
    @cvar _nodeDescription: a mapping between node classes and attribute
    names. If the attribute name is the same as the class' name class
    variable, it can be passed in as C{None}.
    @type _nodeDescription: C{list} of (nodeClass, attributeName) tuples
    """
    _nodeDescription = []

    @classmethod
    def _setMapping(cls):
        if hasattr(cls, '_mapping'):
            return
        mapping = cls._mapping = {}
        for nodeClass, attrName in cls._nodeDescription:
            # If no attribute name is set, use the class' name
            if attrName is None:
                attrName = nodeClass.name
            mapping[nodeClass] = attrName

    def __init__(self):
        self.__class__._setMapping()
        if not hasattr(self, 'extend'):
            for nodeClass, attrName in self._mapping.items():
                setattr(self, attrName, None)

    def addChild(self, child):
        if child.__class__ not in self._mapping:
            return
        attrName = self._mapping[child.__class__]
        if hasattr(self, 'extend'):
            self.extend([child.finalize()])
        else:
            setattr(self, attrName, child.finalize())

    def _iterChildren(self):
        if hasattr(self, 'extend'):
            for y in self.iterChildren():
                yield y
        else:
            for nodeClass, attrName in self._nodeDescription:
                if attrName is None:
                    attrName = nodeClass.name
                val = getattr(self, attrName)
                if val is None and not issubclass(nodeClass, xmllib.NullNode):
                    # The value was not set
                    continue
                if issubclass(nodeClass, xmllib.IntegerNode):
                    val = xmllib.IntegerNode(name = attrName).characters(
                                             str(val))
                elif issubclass(nodeClass, xmllib.StringNode):
                    val = xmllib.StringNode(name = attrName).characters(val)
                elif issubclass(nodeClass, xmllib.BooleanNode):
                    val = xmllib.BooleanNode(name = attrName).characters(
                        xmllib.BooleanNode.toString(val))
                elif issubclass(nodeClass, xmllib.NullNode):
                    val = xmllib.NullNode(name = attrName)
                yield val

    def _getName(self):
        return self.__class__.name

class _ExtendEnabledMixin(object):
    def extend(self, iterable):
        self._children.extend(iterable)

    def __iter__(self):
        return self.iterChildren()

    def _getName(self):
        return self.name

    def _iterChildren(self):
        for val in self.iterChildren():
            if not isinstance(val, (int, str, unicode, bool)):
                yield val
                continue
            # We need to determine the class type - it should be the same
            nodeClass, attrName = self._nodeDescription[0]
            if attrName is None:
                attrName = nodeClass.name
            if isinstance(val, int):
                val = xmllib.IntegerNode(name = attrName).characters(
                                         str(val))
            elif isinstance(val, (str, unicode)):
                val = xmllib.StringNode(name = attrName).characters(val)
            elif isinstance(val, bool):
                val = xmllib.BooleanNode(name = attrName).characters(
                    xmllib.BooleanNode.toString(val))
            yield val

class _NoCharDataNode(_NodeDescriptorMixin, xmllib.BaseNode):
    def __init__(self, attributes = None, nsMap = None, name = None):
        xmllib.BaseNode.__init__(self, attributes = attributes, nsMap = nsMap,
                        name = name)
        _NodeDescriptorMixin.__init__(self)

    def characters(self, ch):
        pass

class _DisplayName(xmllib.StringNode):
    name = 'displayName'

class _DescriptionNode(xmllib.BaseNode):
    name = 'desc'

    @classmethod
    def fromData(cls, description, lang = None):
        attrs = {}
        if lang is not None:
            attrs['lang'] = lang
        dn = cls(attrs, name = cls.name)
        dn.characters(description)
        return dn

class _Descriptions(_ExtendEnabledMixin, _NoCharDataNode):
    name = 'descriptions'

    _nodeDescription = [(_DescriptionNode, None)]

    def getDescriptions(self):
        return dict((x.getAttribute('lang'), x.getText()) for x in self)

class _SupportedFile(xmllib.StringNode):
    name = 'file'

class _MetadataNode(_NoCharDataNode):
    name = 'metadata'

    _nodeDescription = [
        (_DisplayName, None),
        (_Descriptions, None),
    ]

class _NameNode(xmllib.StringNode):
    name = 'name'

class _TypeNode(xmllib.StringNode):
    name = 'type'

class _MultipleNode(xmllib.BooleanNode):
    name = 'multiple'

class _DefaultNode(xmllib.StringNode):
    name = 'default'

class _MinNode(xmllib.IntegerNode):
    name = 'min'

class _MaxNode(xmllib.IntegerNode):
    name = 'max'

class _RequiredNode(xmllib.BooleanNode):
    name = 'required'

class _RangeNode(_NoCharDataNode):
    name = 'range'

    _nodeDescription = [
        (_MinNode, None),
        (_MaxNode, None),
    ]

    def presentation(self):
        return dict(constraintName = self.__class__.name,
                    min = self.min, max = self.max)

    @classmethod
    def fromData(cls, data):
        obj = cls(name = cls.name)
        obj.min = data.get('min')
        obj.max = data.get('max')
        return obj

class _ItemNode(xmllib.StringNode):
    name = 'item'

class _LegalValuesNode(_ExtendEnabledMixin, _NoCharDataNode):
    name = 'legalValues'

    _nodeDescription = [
        (_ItemNode, None),
    ]

    def presentation(self):
        return dict(constraintName = self.__class__.name,
                    values = list(self))

    @classmethod
    def fromData(cls, data):
        obj = cls(name = cls.name)

        obj.extend([ _ItemNode(name = _ItemNode.name).characters(str(x))
                    for x in data['values'] ])
        return obj


class _RegexpNode(xmllib.BaseNode):
    name = 'regexp'

    def presentation(self):
        return dict(constraintName = self.__class__.name,
                    value = self.getText())

    @classmethod
    def fromData(cls, data):
        return cls(name = cls.name).characters(data['value'])

class _LengthNode(xmllib.BaseNode):
    name = 'length'

    def presentation(self):
        return dict(constraintName = self.__class__.name,
                    value = int(self.getText()))

    @classmethod
    def fromData(cls, data):
        return cls(name = cls.name).characters(str(data['value']))

class _ConstraintsNode(_ExtendEnabledMixin, _NoCharDataNode):
    name = 'constraints'

    _nodeDescription = [
        (_Descriptions, None),
        (_RangeNode, None),
        (_LegalValuesNode, None),
        (_RegexpNode, None),
        (_LengthNode, None),
    ]

    def presentation(self):
        return [ x.presentation() for x in self if \
                not isinstance(x, _Descriptions) ]

    def getDescriptions(self):
        res = [x for x in self if isinstance(x, _Descriptions)]
        if res:
            return res[0].getDescriptions()
        return {}

    @classmethod
    def fromData(cls, constraints):
        if not constraints:
            return None
        cls._setMapping()
        # Reverse the mapping
        rev = dict((y, x) for (x, y) in cls._mapping.items())
        node = cls()
        for cdict in constraints:
            constraintName = cdict.get('constraintName')
            if constraintName not in rev:
                continue
            #setattr(node, constraintName, rev[constraintName].fromData(cdict))
            node._children.append(rev[constraintName].fromData(cdict))
        return node

class _DataFieldNode(_NoCharDataNode):
    name = 'field'

    _nodeDescription = [
        (_NameNode, None),
        (_Descriptions, None),
        (_TypeNode, None),
        (_MultipleNode, None),
        (_DefaultNode, None),
        (_ConstraintsNode, None),
        (_RequiredNode, None),
    ]

class _DataFieldsNode(_ExtendEnabledMixin, _NoCharDataNode):
    name = 'dataFields'

    _nodeDescription = [ (_DataFieldNode, None) ]

class _DescriptorNode(_NoCharDataNode):
    name = 'descriptor'

    _nodeDescription = [
        (_MetadataNode, 'metadata'),
        (_DataFieldsNode, 'dataFields'),
    ]

class DescriptorData(_BaseClass):
    "Class for representing the factory data"
    __slots__ = ['_fields', '_descriptor', '_fieldsMap']

    def __init__(self, fromStream = None, validate = False, descriptor = None):
        if descriptor is None:
            raise errors.FactoryDefinitionMissing()

        self._descriptor = descriptor
        _BaseClass.__init__(self, fromStream = fromStream)

    def _createBinder(self):
        binder = xmllib.DataBinder()
        binder.registerType(_DescriptorData)
        return binder

    def _postprocess(self, xmlObj):
        if not isinstance(xmlObj, _DescriptorData):
            raise Exception('No data found')
        for child in xmlObj.iterChildren():
            nodeName = child.getName()
            # Grab the descriptor for this field
            fieldDesc = self._descriptor.getDataField(nodeName)
            # Disable constraint checking, we will do it at the end
            field = _DescriptorDataField(child, fieldDesc,
                checkConstraints = False)
            self._fields.append(field)
            self._fieldsMap[nodeName] = field
        self.checkConstraints()

    def _initFields(self):
        self._fields = []
        self._fieldsMap = {}

    def getFields(self):
        return [ x for x in self._fields ]

    def addField(self, name, value = None):
        # Do not add the field if it was not defined
        fdesc = self._descriptor.getDataField(name)
        if fdesc is None:
            raise errors.UndefinedFactoryDataField(name)

        node = xmllib.BaseNode(name = name)
        if isinstance(value, list):
            for val in value:
                val = xmllib.StringNode(name = attrName).characters(str(val))
                node.addChild(val)
        else:
            node.characters(str(value))

        field = _DescriptorDataField(node, fdesc)
        self._fields.append(field)
        self._fieldsMap[field.getName()] = field

    def getField(self, name):
        if name not in self._fieldsMap:
            return None
        return self._fieldsMap[name].getValue()

    def checkConstraints(self):
        errorList = []

        for field in self._fields:
            try:
                field.checkConstraints()
            except errors.ConstraintsValidationError, e:
                errorList.extend(e.args[0])

        # next, look for missing fields
        missingRequiredFields = [ x.name
            for x in self._descriptor.getDataFields()
            if x.name not in self._fieldsMap
                and x.required ]

        for fieldName in missingRequiredFields:
            errorList.append("Missing field: '%s'" % fieldName)

        if errorList:
            raise errors.ConstraintsValidationError(errorList)

    @staticmethod
    def _getName():
        return 'factoryData'

    def _iterChildren(self):
        return iter(self._fields)

def _toStr(val):
    if isinstance(val, (str, unicode)):
        return val
    return str(val)

class _DescriptorData(xmllib.BaseNode):
    name = 'descriptorData'

class _FactoryDataFieldName(xmllib.StringNode):
    name = 'name'

class _FactoryDataFieldValue(xmllib.BaseNode):
    name = 'value'

class _FactoryDataFieldValues(_ExtendEnabledMixin, _NoCharDataNode):
    name = 'values'

    _nodeDescription = [
        (_FactoryDataFieldValue, None),
    ]

class _FactoryDataFieldModified(xmllib.BooleanNode):
    name = 'modified'

class _DescriptorDataField(object):
    __slots__ = [ '_node', '_nodeDescriptor' ]
    def __init__(self, node, nodeDescriptor, checkConstraints = True):
        self._node = node
        self._nodeDescriptor = nodeDescriptor
        if checkConstraints:
            self.checkConstraints()

    def checkConstraints(self):
        errorList = []
        if self._nodeDescriptor.multiple:
            # Get the node's children as values
            values = [ x.getText() for x in self._node.iterChildren() ]
            for value in values:
                errorList.extend(_validateSingleValue(value,
                                 self._nodeDescriptor.type,
                                 self._nodeDescriptor.descriptions[None],
                                 self._nodeDescriptor.constraints))
        else:
            value = self._node.getText()
            errorList.extend(_validateSingleValue(value,
                             self._nodeDescriptor.type,
                             self._nodeDescriptor.descriptions[None],
                             self._nodeDescriptor.constraints))
        if errorList:
            raise errors.ConstraintsValidationError(errorList)

    def getName(self):
        return self._node.getName()

    def getValue(self):
        vtype = self._nodeDescriptor.type
        if self._nodeDescriptor.multiple:
            return [ _cast(x.getText(), vtype)
                for x in self._node.iterChildren() ]
        return _cast(self._node.getText(), vtype)

    def getElementTree(self, parent = None):
        return self._node.getElementTree(parent = parent)

class _FactoryDataField(_NoCharDataNode):
    name = 'field'

    _nodeDescription = [
        (_FactoryDataFieldName, None),
        (_FactoryDataFieldValues, None),
        (_FactoryDataFieldValue, None),
        (_FactoryDataFieldModified, None)
    ]

class _FactoryData(_ExtendEnabledMixin, _NoCharDataNode):
    name = 'factoryData'

    _nodeDescription = [
        (_FactoryDataField, None),
    ]

class PresentationDataField(object):
    __slots__ = [ 'name', 'type', 'values', 'value']
    def __init__(self, node, fieldDefinition):
        self.name = node.name
        if fieldDefinition is None:
            # No field definition available; trust what the XML data says
            self.type = node.type
            multi = None
        else:
            self.type = fieldDefinition.type
            multi = fieldDefinition.multiple

        if multi or node.values is not None:
            self.value = None
            self.values = [ _cast(x.getText(), self.type) for x in node.values ]
        else:
            self.value = _cast(node.value.getText(), self.type)
            self.values = None

    def getValue(self):
        if self.values is None:
            return self.value
        return self.values

def _cast(val, typeStr):
    if typeStr == 'int':
        try:
            return int(val)
        except ValueError:
            raise errors.DataValidationError(val)
    elif typeStr == 'bool':
        val = _toStr(val)
        if val.upper() not in ('TRUE', '1', 'FALSE', '0'):
            raise errors.DataValidationError(val)
        return val.upper() in ('TRUE', '1')
    elif typeStr == 'str':
        if isinstance(val, unicode):
            return val

        try:
            return str(val).decode('utf-8')
        except UnicodeDecodeError, e_value:
            raise errors.DataValidationError('UnicodeDecodeError: %s'
                % str(e_value))
    return val

def _validateSingleValue(value, valueType, description, constraints):
    errorList = []
    try:
        cvalue = _cast(value, valueType)
    except errors.DataValidationError, e:
        errorList.append("'%s': invalid value '%s' for type '%s'" % (
            description, value, valueType))
        return errorList

    for constraint in constraints:
        if constraint['constraintName'] == 'legalValues':
            legalValues = [ _cast(v, valueType) for v in constraint['values'] ]
            if cvalue not in legalValues:
                errorList.append("'%s': '%s' is not a legal value" %
                                 (description, value))
            continue
        if constraint['constraintName'] == 'range':
            # Only applies to int
            if valueType != 'int':
                continue
            if 'min' in constraint:
                minVal = _cast(constraint['min'], valueType)
                if cvalue < minVal:
                    errorList.append(
                        "'%s': '%s' fails minimum range check '%s'" %
                            (description, value, minVal))
            if 'max' in constraint:
                maxVal = _cast(constraint['max'], valueType)
                if cvalue > maxVal:
                    errorList.append(
                        "'%s': '%s' fails maximum range check '%s'" %
                            (description, value, maxVal))
            continue
        if constraint['constraintName'] == 'length':
            # Only applies to str
            if valueType != 'str':
                continue
            if len(cvalue) > int(constraint['value']):
                errorList.append(
                    "'%s': '%s' fails length check '%s'" %
                            (description, value, constraint['value']))
            continue
        if constraint['constraintName'] == 'regexp':
            # Only applies to str
            if valueType != 'str':
                continue
            if not re.match(constraint['value'], cvalue):
                errorList.append(
                    "'%s': '%s' fails regexp check '%s'" %
                            (description, value, constraint['value']))
            continue

    return errorList

# The following code is here for completeness, it is not used in the package
# creator code, except for being in the base factory class.
from xml.dom import minidom

def xmlToDict(stream):
    dct = xmlToDictWithModified(stream)
    return dict((x[0], x[1][0]) for x in dct.iteritems())

def xmlToDictWithModified(stream):
    dom = minidom.parse(stream)
    ret = {}

    children = dom.getElementsByTagName('factoryData')
    if not children:
        return ret

    children = children[0].getElementsByTagName('field')
    for child in children:
        nodeName = getFirstNodeValue(child.getElementsByTagName('name'))
        nodeType = getFirstNodeValue(child.getElementsByTagName('type'), 'str')

        nodeValues = child.getElementsByTagName('values')
        nodeModified = getFirstNodeValue( \
                child.getElementsByTagName('modified'), 'false')
        if nodeValues:
            values = getChildValuesByName(nodeValues[0], 'value')
        else:
            values = getChildValuesByName(child, 'value')
            if not values:
                continue
        values = [ castValue(x, nodeType) for x in values ]
        if not nodeValues:
            values = values[0]
        modified = nodeModified.upper() in ('TRUE', '1')
        ret[nodeName] = (values, modified)
    return ret

def getChildValuesByName(node, childName):
    values = [ getFirstNodeValue([c])
               for c in node.getElementsByTagName(childName) ]
    return [ x for x in values if x is not None ]

def getFirstNodeValue(nodes, default = None):
    if not nodes:
        return default
    node = nodes[0]
    for child in [x for x in node.childNodes if x.nodeType == x.TEXT_NODE]:
        return child.data
    return None

def castValue(value, valueType):
    if valueType == "int":
        return int(value)
    if valueType == "bool":
        return value.upper() in ['TRUE', '1']
    if valueType == "str":
        return value.encode('utf-8')
    return value

