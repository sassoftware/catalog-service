#
# Copyright (c) 2008 rPath, Inc.
#

import errno
import os
import re
import StringIO
import subprocess
import tempfile

class WorkspaceCloudProperties(object):
    __slots__ = [ 'properties' ]
    _properties = {
        'vws.factory' : 'localhost:8443',
        'vws.repository' : 'localhost:2811',
        'vws.factory.identity' : '/O=My Company Inc/CN=host/localhost',
        'vws.repository.identity' : '/O=My Company Inc/CN=host/localhost',
        'vws.memory.request' : '128',
        'ca.certs' : '/tmp',
    }
    ssh_pubkey = "~/.ssh/id_dsa.pub"

    def __init__(self, properties = None):
        self.properties = self._properties.copy()
        if properties is None:
            properties = {}
        for k, v in properties.items():
            if k in self._properties:
                self.set(k, v)

    def set(self, key, value):
        if key not in self._properties:
            raise AttributeError(key)
        self.properties[key] = value

    def get(self, key):
        return self.properties.get(key)

    def write(self, stream):
        for k, v in sorted(self.properties.items()):
            stream.write("%s=%s\n" % (k, v))

class WorkspaceCloudClient(object):
    GLOBUS_LOCATION = "/tmp/workspace-cloud-client-009"
    _image_re = re.compile(r"^.*'(.*)'.*$")

    def __init__(self, properties):
        self._properties = properties

        self._createConfigFile()

    def listImages(self):
        stdout, stderr, returncode = self._exec('--list')
        return self._parseListImages(stdout)

    def _createConfigFile(self):
        fd, self._configFile = tempfile.mkstemp(prefix = "vwsconf-")
        stream = os.fdopen(fd, "w")
        self._properties.write(stream)
        stream.close()

    def _exec(self, *args):
        cmdline = self._cmdline(args)
        p = subprocess.Popen(cmdline, stdout = subprocess.PIPE,
            stderr = subprocess.PIPE)
        stdout, stderr = p.communicate()
        return stdout, stderr, p.returncode

    def _cmdline(self, args):
        cmdline = [
            "java",
            "-DGLOBUS_LOCATION=%(top)s/lib/globus",
            "-Djava.endorsed.dirs=%(top)s/lib/globus/endorsed",
            "-DX509_CERT_DIR=%(certDir)s",
            "-Djava.security.egd=file:///dev/urandom",
            "-classpath",
            "%(top)s/lib/globus/lib/bootstrap.jar:"
                "%(top)s/lib/globus/lib/cog-url.jar:"
                "%(top)s/lib/globus/lib/axis-url.jar",
            "org.globus.bootstrap.Bootstrap",
            "org.globus.workspace.cloud.client.CloudClient",
            "--conf", "%(confFile)s",
            "--history-dir", "%(top)s/history"
        ] + list(args)
        replacements = dict(top = self.GLOBUS_LOCATION,
            certDir = self._properties.get('ca.certs'),
            confFile = self._configFile,
        )
        return [ x % replacements for x in cmdline ]

    def _parseListImages(self, data):
        ret = []
        sio = StringIO.StringIO(data)
        sio.seek(0)
        prefix = '[Image]'
        for line in sio:
            if not line.startswith(prefix):
                continue
            line = line[len(prefix):]
            # Look for the image name
            m = self._image_re.search(line)
            if not m:
                continue
            ret.append(m.group(1))
        return ret

    def __del__(self):
        if self._configFile:
            try:
                os.unlink(self._configFile)
            except OSError, e:
                if e.errno != errno.EBADF:
                    raise
            self._configFile = None

if __name__ == '__main__':
    conf = WorkspaceCloudProperties()
    conf.set('ca.certs', '/tmp/xx1')
    conf.set('vws.factory', 'speedy.eng.rpath.com:8443')
    conf.set('vws.repository', 'speedy.eng.rpath.com:2811')
    conf.set('vws.factory.identity', '/O=rPath Inc/CN=host/speedy')
    conf.set('vws.repository.identity', '/O=rPath Inc/CN=host/speedy')

    cli = WorkspaceCloudClient(conf)
    print " ".join(cli._cmdline(["--list"]))
    print cli.listImages()
