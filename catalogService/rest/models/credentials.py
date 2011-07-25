#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
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
    _slotTypeMap = dict(valid=bool)

class Handler(xmllib.DataBinder):
    fieldClass = BaseField
    fieldsClass = BaseFields
    credentialsClass = BaseCredentials
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.fieldClass, self.fieldClass.tag)
        self.registerType(self.fieldsClass, self.fieldsClass.tag)
        self.registerType(self.credentialsClass, self.credentialsClass.tag)
