#!/usr/bin/python
# vim: set fileencoding=utf-8 :
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


import os
import subprocess

from conary.lib import util
import testsuite
# Bootstrap the testsuite
testsuite.setup()

from testrunner import testcase

from catalogService.rest.baseDriver import Archive

class ArchiveTest(testcase.TestCaseWithWorkDir):

    def setUp(self):
        testcase.TestCaseWithWorkDir.setUp(self)
        self._logEntries = []

    def makeDirectoryStructure(self):
        archiveDir = os.path.join(self.workDir, "archive")
        subdir = os.path.join(archiveDir, "subdir")
        subsubdir1 = os.path.join(subdir, "subsubdir1")
        subsubdir2 = os.path.join(subdir, "subsubdir2")
        deep = os.path.join(subsubdir1, "a", "b", "c")
        util.mkdirChain(subsubdir1)
        util.mkdirChain(subsubdir2)
        util.mkdirChain(deep)
        file(os.path.join(subdir, "foo.ovf"), "w").write("<foo/>")
        file(os.path.join(subsubdir1, "bar1.data"), "w").write("bar1")
        file(os.path.join(subsubdir2, "bar1.data"), "w").write("bar1")
        file(os.path.join(subsubdir2, "bar2.data"), "w").write("bar2")
        file(os.path.join(deep, "deep.data"), "w").write("deep")
        return archiveDir

    def _log(self, *args):
        self._logEntries.append(args)

    def testTarGz(self):
        workdir = self.makeDirectoryStructure()
        archivePath = os.path.join(workdir, 'archive.tar.gz')
        cmd = [ 'tar', 'zcf', archivePath,
            '-C', workdir, 'subdir' ]
        subprocess.call(cmd)
        util.rmtree(os.path.join(workdir, "subdir"))
        self._runTests(archivePath)

    def testOva(self):
        workdir = self.makeDirectoryStructure()
        archivePath = os.path.join(workdir, 'archive.tar.gz')
        cmd = [ 'tar', 'cf', archivePath,
            '-C', workdir, 'subdir' ]
        subprocess.call(cmd)
        util.rmtree(os.path.join(workdir, "subdir"))
        self._runTests(archivePath)

    def testGzip(self):
        workdir = os.path.join(self.workDir, "archive")
        util.mkdirChain(workdir)
        archivePath = os.path.join(workdir, "file")
        f = file(archivePath, "w+")
        content = "0123456789abcdef"
        for i in range(1024):
            f.write(content)
        f.close()
        cmd = [ 'gzip', archivePath ]
        subprocess.call(cmd)
        archivePath += '.gz'
        a = Archive(archivePath, self._log)
        a.extract()
        self.failUnlessEqual(sorted(x.name for x in a),
            [ 'file' ])
        self.failUnlessEqual(sorted(x.size for x in a),
            [ 16384 ])
        member = list(a)[0]
        fobj = a.extractfile(member)

        self.failUnlessEqual(fobj.size, 16384)
        self.failUnlessEqual(fobj.read(16), "0123456789abcdef")
        self.failUnlessEqual(fobj.tell(), 16)
        fobj.seek(1)
        self.failUnlessEqual(fobj.tell(), 1)
        fobj.close()

    def _runTests(self, archivePath):
        a = Archive(archivePath, self._log)
        a.extract()
        self.failUnlessEqual(sorted(x.name for x in a),
            [
                'subdir/foo.ovf', 'subdir/subsubdir1/a/b/c/deep.data',
                'subdir/subsubdir1/bar1.data',
                'subdir/subsubdir2/bar1.data', 'subdir/subsubdir2/bar2.data'])
        # Get one of the files
        member = [ x for x in a if x.name.endswith('deep.data') ][0]
        # Make sure we have a size member
        self.failUnlessEqual(member.size, 4)
        self.failUnlessEqual(member.name, 'subdir/subsubdir1/a/b/c/deep.data')
        # Make sure we can extract data
        fobj = a.extractfile(member)
        self.failUnlessEqual(fobj.name, 'subdir/subsubdir1/a/b/c/deep.data')
        self.failUnlessEqual(fobj.size, 4)
        self.failUnlessEqual(fobj.read(2), "de")
        self.failUnlessEqual(fobj.read(2), "ep")
        fobj = a.extractfile(member)
        self.failUnlessEqual(fobj.size, 4)
        self.failUnlessEqual(fobj.read(), "deep")
        self.failUnlessEqual(fobj.tell(), 4)
        fobj.seek(1)
        self.failUnlessEqual(fobj.tell(), 1)
        fobj.close()

if __name__ == "__main__":
    testsuite.main()
