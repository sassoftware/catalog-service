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

import itertools
import tarfile
from StringIO import StringIO


class TarStreamExtractor(object):
    """
    Extract a tar stream, loading small files into memory for random access
    while not advancing past the large files so they can be streamed somewhere
    else.

    Accepts any format tar accepts, e.g. gzip or bzip2 compressed.
    """

    threshold = 1e6

    def __init__(self, fobj):
        self.tar = tarfile.open(fileobj=fobj, mode='r|*')
        self._iter = iter(self.tar)
        self._saved = None
        self._files = {}

    def _get_iter(self):
        if self._saved:
            saved = self._saved
            self._saved = None
            return itertools.chain([saved], self._iter)
        else:
            return self._iter

    def getSmallFiles(self):
        """
        Return a name:contents dictionary of all files up until the first one
        over the size threshold
        """
        ret = {}
        for info in self._get_iter():
            if info.size >= self.threshold:
                self._saved = info
                break
            if info.type != tarfile.REGTYPE:
                continue
            contents = self.tar.extractfile(info).read()
            self._files[info.name] = (info, contents)
            ret[info.name] = contents
        return ret

    def iterFileStreams(self):
        """
        Yield tuples of (name,tarinfo,fobj) where fobj is a file-like object
        that streams the file's contents.
        """
        for name, (info, contents) in self._files.iteritems():
            yield name, info, StringIO(contents)
        for info in self._get_iter():
            if info.type != tarfile.REGTYPE:
                continue
            stream = self.tar.extractfile(info)
            yield info.name, info, stream
