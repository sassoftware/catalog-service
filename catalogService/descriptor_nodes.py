#!/usr/bin/python2.4
#
# Copyright (c) 2008 rPath, Inc.
#

import re

from rpath_common.xmllib import api1 as xmllib

from catalogService import descriptor_errors as errors

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
        if getattr(child.__class__, 'multiple', None):
            vlist = getattr(self, attrName)
            if vlist is None:
                vlist = []
                setattr(self, attrName, vlist)
            vlist.append(child.finalize())
        elif hasattr(self, 'extend'):
            self.extend([child.finalize()])
        else:
            setattr(self, attrName, child.finalize())

    def _encodeChild(self, nodeClass, attrName, val):
        if issubclass(nodeClass, xmllib.IntegerNode):
            return xmllib.IntegerNode(name = attrName).characters(str(val))
        if issubclass(nodeClass, xmllib.StringNode):
            if not isinstance(val, basestring):
                val = str(val)
            return xmllib.StringNode(name = attrName).characters(val)
        if issubclass(nodeClass, xmllib.BooleanNode):
            return xmllib.BooleanNode(name = attrName).characters(
                xmllib.BooleanNode.toString(val))
        if issubclass(nodeClass, xmllib.NullNode):
            return xmllib.NullNode(name = attrName)
        if hasattr(val, 'getElementTree'):
            return val
        return None

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
                if getattr(nodeClass, 'multiple', None):
                    if not hasattr(val, 'extend'):
                        val = [ val ]
                else:
                    val = [ val ]

                for v in val:
                    node = self._encodeChild(nodeClass, attrName, v)
                    if node is not None:
                        yield node

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

class DescriptionNode(xmllib.BaseNode):
    name = 'desc'

    @classmethod
    def fromData(cls, description, lang = None):
        if isinstance(description, tuple):
            description, lang = description
        elif hasattr(description, 'description'):
            description, lang = description.description, description.lang
        attrs = {}
        if lang is not None:
            attrs['lang'] = lang
        dn = cls(attrs, name = cls.name)
        dn.characters(description)
        return dn

class _Descriptions(_ExtendEnabledMixin, _NoCharDataNode):
    name = 'descriptions'

    _nodeDescription = [(DescriptionNode, None)]

    def getDescriptions(self):
        return dict((x.getAttribute('lang'), x.getText()) for x in self)

class HelpNode(xmllib.BaseNode):
    name = 'help'
    multiple = True

    @classmethod
    def fromData(cls, href, lang = None):
        if isinstance(href, tuple):
            href, lang = href
        elif hasattr(href, 'href'):
            href, lang = href.href, href.lang
        attrs = {'href' : href}
        if lang is not None:
            attrs['lang'] = lang
        dn = cls(attrs, name = cls.name)
        return dn

    def _getLang(self):
        return self.getAttribute('lang')
    lang = property(_getLang)

    def _getHref(self):
        return self.getAttribute('href')
    def _setHref(self, val):
        # XXX that's not very polite
        self._otherAttributes[(None, 'href')] = val
    href = property(_getHref, _setHref)

class _RootElement(xmllib.StringNode):
    name = "rootElement"

class MetadataNode(_NoCharDataNode):
    name = 'metadata'

    _nodeDescription = [
        (_DisplayName, None),
        (_RootElement, None),
        (_Descriptions, None),
    ]

class _NameNode(xmllib.StringNode):
    name = 'name'

class _TypeNode(xmllib.StringNode):
    name = 'type'

class _KeyNode(xmllib.StringNode):
    name = 'key'

class _ValueWithDescriptionNode(_NoCharDataNode):
    name = 'describedValue'

    _nodeDescription = [
        (_Descriptions, None),
        (_KeyNode, None),
    ]

class _EnumeratedTypeNode(_ExtendEnabledMixin, _NoCharDataNode):
    name = 'enumeratedType'

    _nodeDescription = [
        (_ValueWithDescriptionNode, None),
    ]

class _MultipleNode(xmllib.BooleanNode):
    name = 'multiple'

class _DefaultNode(xmllib.StringNode):
    name = 'default'
    multiple = True

class _MinNode(xmllib.IntegerNode):
    name = 'min'

class _MaxNode(xmllib.IntegerNode):
    name = 'max'

class _RequiredNode(xmllib.BooleanNode):
    name = 'required'

class _PasswordNode(xmllib.BooleanNode):
    name = 'password'

class _HiddenNode(xmllib.BooleanNode):
    name = 'hidden'

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
        if isinstance(constraints, dict):
            # Only one constraint
            constraints = [ constraints ]
        for cdict in constraints:
            constraintName = cdict.get('constraintName')
            if constraintName not in rev:
                continue
            #setattr(node, constraintName, rev[constraintName].fromData(cdict))
            node._children.append(rev[constraintName].fromData(cdict))
        return node

class _FieldNameNode(xmllib.StringNode):
   name = 'fieldName'

class _OperatorNode(xmllib.StringNode):
    name = 'operator'

class _ValueNode(xmllib.StringNode):
    name = 'value'

class _ConditionalNode(_NoCharDataNode):
    name = 'conditional'

    _nodeDescription = [
        (_FieldNameNode, None),
        (_OperatorNode, None),
        (_ValueNode, None),
    ]

    @classmethod
    def fromConditional(cls, conditional):
        obj = cls(name = cls.name)
        obj.fieldName = conditional.fieldName
        obj.operator = conditional.operator
        obj.value = conditional.value
        return obj

class DataFieldNode(_NoCharDataNode):
    name = 'field'

    _nodeDescription = [
        (_NameNode, None),
        (_Descriptions, None),
        (HelpNode, None),
        (_TypeNode, None),
        (_EnumeratedTypeNode, None),
        (_MultipleNode, None),
        (_DefaultNode, None),
        (_ConstraintsNode, None),
        (_RequiredNode, None),
        (_HiddenNode, None),
        (_PasswordNode, None),
        (_ConditionalNode, None),
    ]

class _DataFieldsNode(_ExtendEnabledMixin, _NoCharDataNode):
    name = 'dataFields'

    _nodeDescription = [ (DataFieldNode, None) ]

class DescriptorNode(_NoCharDataNode):
    name = 'descriptor'

    _nodeDescription = [
        (MetadataNode, 'metadata'),
        (_DataFieldsNode, 'dataFields'),
    ]

class DescriptorDataNode(xmllib.BaseNode):
    name = 'descriptorData'

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
            values = [ x.getText() for x in self._node.iterChildren()
                if hasattr(x, 'getName') and x.getName() == 'item' ]
            if self._nodeDescriptor.required and not values:
                errorList.append("Missing field: '%s'" %
                    self._nodeDescriptor.name)
            elif isinstance(self._nodeDescriptor.type, list):
                errorList.extend(_validateEnumeratedValue(values,
                                 self._nodeDescriptor.type,
                                 self._nodeDescriptor.descriptions[None]))
            else:
                # It is conceivable that one has a multi-valued field with a
                # simple type
                errorList.extend(_validateMultiValue(values,
                                 self._nodeDescriptor.type,
                                 self._nodeDescriptor.descriptions.get(None),
                                 self._nodeDescriptor.constraints))
        else:
            value = self._node.getText()
            errorList.extend(_validateSingleValue(value,
                             self._nodeDescriptor.type,
                             self._nodeDescriptor.descriptions.get(None),
                             self._nodeDescriptor.constraints))
        if errorList:
            raise errors.ConstraintsValidationError(errorList)

    def getName(self):
        return self._node.getName()

    def getValue(self):
        vtype = self._nodeDescriptor.type
        if self._nodeDescriptor.multiple:
            return [ _cast(x.getText(), vtype)
                for x in self._node.iterChildren()
                if x.getName() == 'item' ]
        return _cast(self._node.getText(), vtype)

    def getElementTree(self, parent = None):
        return self._node.getElementTree(parent = parent)

def _toStr(val):
    if isinstance(val, (str, unicode)):
        return val
    return str(val)

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

def _validateEnumeratedValue(values, valueType, description):
    assert(isinstance(valueType, list))
    valuesHash = dict((x.key, None) for x in valueType)
    errorList = []
    for value in values:
        if value in valuesHash:
            continue
        errorList.append("'%s': invalid value '%s'" % (
            description, value))
    return errorList

def _validateMultiValue(values, valueType, description, constraints):
    errorList = []
    for value in values:
        errorList.extend(_validateSingleValue(value, valueType, description,
                         constraints))
    return errorList

def _validateSingleValue(value, valueType, description, constraints):
    if isinstance(valueType, list):
        return _validateEnumeratedValue([value], valueType, description)

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
            if not re.compile(constraint['value'], re.S).match(cvalue):
                errorList.append(
                    "'%s': '%s' fails regexp check '%s'" %
                            (description, value, constraint['value']))
            continue

    return errorList
