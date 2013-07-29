#
# Copyright (c) SAS Institute Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import time
from conary.lib.util import copyfileobj


class PercentageCallback(object):
    """
    When called with a number of bytes transferred, invokes the inner callback
    with the same as a percentage of totalSize.
    """

    def __init__(self, totalSize, callback):
        self.totalSize = totalSize
        self.callback = callback

    def __call__(self, count):
        if self.totalSize:
            percent = int(count * 100 / self.totalSize)
            percent = min(100, max(0,  percent))
        else:
            percent = 100
        self.callback(percent)


class Sink(object):

    @staticmethod
    def write(data):
        pass


class StreamWithProgress(object):
    """
    Wrap a file stream and keep track of how many bytes have been read from it
    """

    interval = 1

    def __init__(self, fobj, callback):
        self.fobj = fobj
        self.callback = callback
        self.count = 0
        self.when = 0

    _DEFAULT = object()
    def read(self, size=_DEFAULT):
        if size is self._DEFAULT:
            data = self.fobj.read()
        else:
            data = self.fobj.read(size)
        self.count += len(data)

        now = time.time()
        if now - self.when >= self.interval:
            self.when = now
            self.callback(self.count)

        return data


def digestWithProgress(fobj, digest, callback):
    source = StreamWithProgress(fobj, callback)
    return copyfileobj(source, Sink, digest=digest)
