#
# Copyright (c) 2008 rPath, Inc.
#

import os
import urllib

class BaseDriver(object):
    @staticmethod
    def addPrefix(prefix, data):
        data = urllib.quote(data, safe="")
        if prefix is None:
            return data
        return os.path.join(prefix, data)

