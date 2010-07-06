#!/usr/bin/python
#
# Copyright (c) 2009 rPath, Inc.  All Rights Reserved.
#

import decorator
from mint.rest.db import database

class RestDatabase(database.Database):
    pass

# This is slightly different that mint's, since it's decorating controller
# methods
@decorator.decorator
def commitafter(fn, self, *args, **kw):
    return self.db._commitAfter(fn, self, *args, **kw)
