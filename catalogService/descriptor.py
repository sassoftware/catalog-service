#!/usr/bin/python2.4
#
# Copyright (c) 2008 rPath, Inc.
#

import os
import StringIO

from rpath_common.xmllib import api1 as xmllib

from catalogService import descriptor_errors as errors
from catalogService import descriptor_nodes as dnodes

InvalidXML = xmllib.InvalidXML

class _BaseClass(xmllib.SerializableObject):
    xmlSchemaNamespace = 'http://www.w3.org/2001/XMLSchema-instance'
    schemaDir = '/usr/share/factory/schemas'

    xmlSchemaLocation = 'http://www.rpath.org/permanent/descriptor-1.0.xsd' \
                        ' descriptor-1.0.xsd'

    _rootNodeClass = None

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

    @classmethod
    def _createBinder(cls):
        binder = xmllib.DataBinder()
        stack = [ (cls._rootNodeClass, None) ]
        while stack:
            nodeClass, nodeClassName = stack.pop()
            binder.registerType(nodeClass, nodeClassName)
            scList = getattr(nodeClass, '_nodeDescription', [])
            for subClass, subClassName in scList:
                stack.append((subClass, subClassName))
        return binder

    @classmethod
    def _getName(cls):
        return cls._rootNodeClass.name

    def _postprocess(self, xmlObj):
        if not isinstance(xmlObj, self._rootNodeClass):
            raise Exception("No data found")

class BaseDescriptor(_BaseClass):
    _rootNodeClass = dnodes.DescriptorNode

    def _postprocess(self, xmlObj):
        _BaseClass._postprocess(self, xmlObj)
        self._metadata = xmlObj.metadata
        self._dataFields.extend(xmlObj.dataFields.iterChildren())
        self._dataFieldsHash.update(dict((x.name, x)
            for x in xmlObj.dataFields.iterChildren()))

    def getMetadata(self):
        """
        @return: the metadata associated with this object
        @rtype: C{descriptor_nodes.MetadataNode}
        """
        return self._metadata

    def getDisplayName(self):
        return self._metadata.displayName

    def setDisplayName(self, displayName):
        self._metadata.displayName = displayName

    def getDataFields(self):
        """
        @return: the data fields associated with this object
        @rtype: C{list} of C{descriptor_nodes.DataFieldNode}
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
        df = dnodes.DataFieldNode()
        df.name = name
        df.type = nodeType
        df.multiple = kwargs.get('multiple', None)
        df.descriptions = dnodes._Descriptions()
        df.descriptions.extend(
            [ dnodes.DescriptionNode.fromData(x.description, x.lang)
                for x in descriptions ])
        df.constraints = dnodes._ConstraintsNode.fromData(constraints)
        if df.constraints and constraintsDescriptions:
            df.constraints.descriptions = dnodes._Descriptions()
            # descriptions come first per XML schema. _ConstraintsNode.fromData
            # already defined the _children attribute, so we'll insert this
            # value in the front
            df.constraints._children.insert(0, df.constraints.descriptions)
            df.constraints.descriptions.extend([
                dnodes.DescriptionNode.fromData(x.description, x.lang) \
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
        @rtype: C{list} of C{description_nodes.DescriptionNode}
        """
        return self._metadata.descriptions.getDescriptions()

    def addDescription(self, description, lang=None):
        dn = dnodes.DescriptionNode.fromData(description, lang)
        if self._metadata.descriptions is None:
            self._metadata.descriptions = dnodes._Descriptions()
        self._metadata.descriptions.extend([dn])

    def _initFields(self):
        self._metadata = dnodes.MetadataNode()
        self._dataFields = dnodes._DataFieldsNode()
        self._dataFieldsHash = {}

    def _iterChildren(self):
        yield self._metadata
        yield self._dataFields

class DescriptorData(_BaseClass):
    "Class for representing the descriptor data"
    __slots__ = ['_fields', '_descriptor', '_fieldsMap']

    _rootNodeClass = dnodes.DescriptorDataNode

    def __init__(self, fromStream = None, validate = False, descriptor = None):
        if descriptor is None:
            raise errors.FactoryDefinitionMissing()

        self._descriptor = descriptor
        _BaseClass.__init__(self, fromStream = fromStream)

    def _postprocess(self, xmlObj):
        _BaseClass._postprocess(self, xmlObj)
        for child in xmlObj.iterChildren():
            nodeName = child.getName()
            # Grab the descriptor for this field
            fieldDesc = self._descriptor.getDataField(nodeName)
            # Disable constraint checking, we will do it at the end
            field = dnodes._DescriptorDataField(child, fieldDesc,
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

        field = dnodes._DescriptorDataField(node, fdesc)
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

    def _iterChildren(self):
        return iter(self._fields)

    def _getLocalNamespaces(self):
        # We have no schema for descriptor data
        return {}

    def _iterAttributes(self):
        return {}

class ConfigurationDescriptor(BaseDescriptor):
    "Class for representing the configuration descriptor definition"

class CredentialsDescriptor(BaseDescriptor):
    "Class for representing the credentials descriptor definition"

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
