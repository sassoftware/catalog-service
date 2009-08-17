#
# Copyright (c) 2008 rPath, Inc.
#

import rpath_xmllib as xmllib

import xmlNode

class BaseField(xmlNode.BaseNode):
    tag = 'field'
    __slots__ = [ 'credentialName', 'value' ]

class BaseFields(xmlNode.BaseNodeCollection):
    tag = "fields"

class BaseCredentials(xmlNode.BaseNode):
    tag = "credentials"
    __slots__ = [ 'fields', 'valid' ]

    def setValid(self, data):
        self.valid = None
        if data is None:
            return self
        data = xmllib.BooleanNode.toString(data)
        self.valid = xmllib.GenericNode().setName('valid').characters(data)
        return self

    def getValid(self):
        if self.valid is None:
            return None
        return xmllib.BooleanNode.fromString(self.valid.getText())

class Handler(xmllib.DataBinder):
    fieldClass = BaseField
    fieldsClass = BaseFields
    credentialsClass = BaseCredentials
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.fieldClass, self.fieldClass.tag)
        self.registerType(self.fieldsClass, self.fieldsClass.tag)
        self.registerType(self.credentialsClass, self.credentialsClass.tag)
