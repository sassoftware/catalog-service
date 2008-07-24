#
# Copyright (c) 2008 rPath, Inc.
#

import errno
import os
import re
import shutil
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
        'vws.cahash' : '6045a439',
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

    def __init__(self, properties, caCert, userCert, userKey):
        self._properties = properties
        self._caCert = caCert

        self._tmpDir = tempfile.mkdtemp(prefix="vws-session-")

        # Save the user's cert and key in files on the disk, the proxy
        # cert creation needs them
        self._userCertPath = os.path.join(self._tmpDir, "usercert.pem")
        self._openStream(self._userCertPath, 0644).write(userCert)

        self._userKeyPath = os.path.join(self._tmpDir, "userkey.pem")
        self._openStream(self._userKeyPath, 0600).write(userKey)

        self._caCertHash = None
        self._caCertSubject = None
        self._userCertSubject = None
        self._userCertIssuer = None
        self._proxyCertPath = os.path.join(self._tmpDir, "proxycert.pem")

        # Create the directory for CA certs
        self._caCertDir = os.path.join(self._tmpDir, "ca-certs")
        os.mkdir(self._caCertDir)

        self._initX509()
        self._createConfigFile()
        self._initProxyCert()

    def getCloudId(self):
        return self._properties.get('vws.factory')

    def listImages(self):
        cmdline = self._cmdline('--list')
        stdout, stderr, returncode = self._exec(cmdline)
        return self._parseListImages(stdout)

    def _createConfigFile(self):
        self._configFile = os.path.join(self._tmpDir, "cloud.properties")
        stream = self._openStream(self._configFile)
        self._properties.write(stream)
        stream.close()

    def _initX509(self):
        fd, tmpf = tempfile.mkstemp()
        stream = os.fdopen(fd, "w")
        stream.write(self._caCert)
        stream.close()

        cmdline = self._opensslCmdline('-in', tmpf,
            '-subject', '-issuer', '-hash')
        stdout, stderr, returncode = self._exec(cmdline)
        self._caCertSubject, _, self._caCertHash = self._parseCertData(stdout)
        if self._caCertSubject is None:
            # Some kind of syntax error
            raise Exception("XXX 1")

        cmdline = self._opensslCmdline('-in', self._userCertPath,
            '-subject', '-issuer', '-hash')
        stdout, stderr, returncode = self._exec(cmdline)
        stream.close()
        os.unlink(tmpf)
        self._userCertSubject, self._userCertIssuer, self._userCertHash = \
            self._parseCertData(stdout)
        if self._userCertSubject is None:
            raise Exception("XXX 1")

        fpath = os.path.join(self._caCertDir, self._caCertHash)
        # Write the cert as <hash>.0
        file(fpath + ".0", "w+").write(self._caCert)
        # Write the policy file
        data = dict(caHash = self._caCertHash,
            caSubject = self._caCertSubject,
            certSubject = self._userCertSubject)
        file(fpath + ".signing_policy", "w+").write(self._policyTemplate % data)

    def _initProxyCert(self):
        cmdline = self._cmdlineProxy()
        stdout, stderr, returncode = self._exec(cmdline)
        if returncode != 0:
            raise Exception("Passphrase-protected key", stdout)
        if not os.path.exists(self._proxyCertPath):
            raise Exception("Proxy certificate not created")

    def _openStream(self, fileName, mode = 0644):
        fd = os.open(fileName, os.O_RDWR | os.O_CREAT | os.O_EXCL, mode)
        stream = os.fdopen(fd, "w+")
        return stream

    def _parseCertData(self, data):
        sio = StringIO.StringIO(data)
        sio.seek(0)
        prefix = "subject= "
        line = sio.readline().strip()
        if not line.startswith(prefix):
            return None, None, None
        csubj = line[len(prefix):]

        prefix = "issuer= "
        line = sio.readline().strip()
        if not line.startswith(prefix):
            return None, None, None
        ciss = line[len(prefix):]

        chash = sio.readline().strip()
        return csubj, ciss, chash

    def _exec(self, cmdline, stdinData = None):
        if stdinData is not None:
            stdin = subprocess.PIPE
        else:
            stdin = file(os.devnull)

        p = subprocess.Popen(cmdline, stdout = subprocess.PIPE,
            stderr = subprocess.PIPE, stdin = stdin)
        stdout, stderr = p.communicate(stdinData)
        return stdout, stderr, p.returncode

    def _cmdline(self, *args):
        cmdline = [
            "java",
            "-DGLOBUS_LOCATION=%(top)s/lib/globus",
            "-Djava.endorsed.dirs=%(top)s/lib/globus/endorsed",
            "-DX509_USER_PROXY=%(proxyCert)s",
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
            certDir = self._caCertDir,
            confFile = self._configFile,
            proxyCert = self._proxyCertPath,
        )
        return [ x % replacements for x in cmdline ]

    def _opensslCmdline(self, *args):
        cmdline = ["openssl", "x509", "-noout"] + list(args)
        return cmdline

    def _cmdlineProxy(self):
        cmdline = [
            "%(top)s/bin/grid-proxy-init.sh",
            "-key", "%(userKey)s",
            "-cert", "%(userCert)s",
            "-out", "%(proxyCert)s",
        ]
        replacements = dict(top = self.GLOBUS_LOCATION,
            userKey = self._userKeyPath,
            userCert = self._userCertPath,
            proxyCert = self._proxyCertPath,
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

    def close(self):
        if self._tmpDir is None:
            return
        shutil.rmtree(self._tmpDir, ignore_errors = True)
        self._tmpDir = None

    def __del__(self):
        self.close()

    _policyTemplate = """
access_id_CA    X509    '%(caSubject)s'
pos_rights      globus  CA:sign
cond_subjects   globus  '"%(certSubject)s"'
"""
