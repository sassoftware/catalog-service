#
# Copyright (c) 2008 rPath, Inc.  All Rights Reserved.
#

import sys
import os

# add the required modules to the path (this is sub-optimal, but ZSI has
# bugs we need to work around
vendor_dir = os.path.join(os.path.dirname(__file__), '..', 'viclient_vendor')
sys.path.append(vendor_dir)

import client, vmutils

VimService = client.VimService
