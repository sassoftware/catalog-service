#
# Copyright (c) 2008 rPath, Inc.
#

class BaseConfig(object):
    """
    Base configration object
    """
    # Url to rBuilder server. If None, a shimclient will be used.
    # this config value expects to have two string substitution placeholders
    # for username and password eg, http://%s:%s@URL/
    rBuilderUrl = None
