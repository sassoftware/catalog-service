#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

from mint.rest.middleware import auth

public = auth.public

class AuthenticationCallback(auth.AuthenticationCallback):
    def __init__(self, restdb, controller):
        auth.AuthenticationCallback.__init__(self, restdb.cfg, restdb, controller)
