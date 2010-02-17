#
# Copyright (c) 2009 rPath, Inc.  All Rights Reserved.
#

import time

def utctime(timestr, timeFormat):
    if isinstance(timestr, basestring):
        timeTuple = time.strptime(timestr, timeFormat)
    else:
        timeTuple = timestr
    # Force no DST
    timeTuple = tuple(timeTuple[:-1]) + (0, )
    return int(time.mktime(timeTuple)) - time.timezone

