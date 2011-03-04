#
# Copyright (c) 2011 rPath, Inc.  All Rights Reserved.
#

# vim: set fileencoding=utf-8 :

import os
import subprocess
import tempfile
from boto.s3 import connection as s3connection
from boto.ec2.regioninfo import RegionInfo

from conary.lib import util
from mint import ec2

from catalogService import errors
from catalogService.rest.drivers.eucalyptus import eucaclient

# We're lazy
_configurationDescriptorXmlData = eucaclient._configurationDescriptorXmlData.replace(
    'Eucalyptus', 'OpenStack').replace('(Walrus) ', '')

_credentialsDescriptorXmlData = eucaclient._credentialsDescriptorXmlData.replace(
    'Eucalyptus', 'OpenStack')

class OpenStackClient(eucaclient.EucalyptusClient):
    cloudType = 'openstack'
    # XXX will need their own image type
    RBUILDER_BUILD_TYPE = 'RAW_FS_IMAGE'
    ImagePrefix = 'ami-'
    CallingFormat = s3connection.OrdinaryCallingFormat()

    configurationDescriptorXmlData = _configurationDescriptorXmlData
    credentialsDescriptorXmlData = _credentialsDescriptorXmlData

    def drvPopulateLaunchDescriptor(self, descr):
        eucaclient.EucalyptusClient.drvPopulateLaunchDescriptor(self, descr)
        descr.setDisplayName("OpenStack Launch Parameters")
        descr.addDescription("OpenStack Launch Parameters")
        return descr

    def _getEC2ConnectionInfo(self, credentials):
        targetConfiguration = self.getTargetConfiguration()
        port = targetConfiguration['port']
        return (RegionInfo(name=self.cloudName, endpoint=self.cloudName),
            port, '/services/Cloud', False)

    def _getS3ConnectionInfo(self, credentials):
        # XXX We should drive this through the configuration, but I didn't
        # feel like complicating the descriptor too much
        port = 3333
        return (self.cloudName, port, None, False,
            self.CallingFormat)

