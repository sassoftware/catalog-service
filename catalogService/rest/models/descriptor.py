#!/usr/bin/python
#
# Copyright (c) 2008-2010 rPath, Inc.  All Rights Reserved.
#

from smartform import descriptor

errors = descriptor.errors
ConfigurationDescriptor = descriptor.ConfigurationDescriptor
DescriptorData = descriptor.DescriptorData
ProtectedUnicode = descriptor.ProtectedUnicode

class CredentialsDescriptor(descriptor.BaseDescriptor):
    "Class for representing the credentials descriptor definition"

class LaunchDescriptor(descriptor.BaseDescriptor):
    "Class for representing the launch descriptor definition"

class DeployDescriptor(descriptor.BaseDescriptor):
    "Class for representing the deploy descriptor definition"

