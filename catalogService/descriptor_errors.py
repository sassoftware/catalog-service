#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

class Error(Exception):
    "Base error class"

class SchemaValidationError(Error):
    ""

class UnknownSchema(Error):
    ""

class DataValidationError(Error):
    ""

class ConstraintsValidationError(Error):
    ""

class InvalidDefaultValue(Error):
    ""

class UndefinedFactoryDataField(Error):
    ""
