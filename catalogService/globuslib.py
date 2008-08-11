#
# Copyright (c) 2008 rPath, Inc.
#

import errno
import os
import re
import shutil
import StringIO
import select
import subprocess
import tempfile
import time

from xml.dom import minidom

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
    GLOBUS_LOCATION = "/opt/workspace-cloud-client"
    _image_re = re.compile(r"^.*'(.*)'.*$")
    _instance_1_re = re.compile(r"^([\d]+)\. "
        r"([\d]+\.[\d]+\.[\d]+\.[\d]+) "
        r"\[ (.+) \]$")
    _timeFormat = "%a %b %d %H:%M:%S %Z %Y"

    def __init__(self, properties, caCert, userCert, userKey, sshPubKey,
                 cloudAlias):
        self._properties = properties
        self._caCert = caCert
        self._cloudAlias = cloudAlias

        self._tmpDir = tempfile.mkdtemp(prefix="vws-session-")

        # Save the user's cert and key in files on the disk, the proxy
        # cert creation needs them
        self._userCertPath = os.path.join(self._tmpDir, "usercert.pem")
        self._openStream(self._userCertPath, 0644).write(userCert)

        self._userKeyPath = os.path.join(self._tmpDir, "userkey.pem")
        self._openStream(self._userKeyPath, 0600).write(userKey)

        self._sshPubKeyPath = os.path.join(self._tmpDir, "ssh.pub")
        self._openStream(self._sshPubKeyPath).write(sshPubKey)

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

    @classmethod
    def isFunctional(cls):
        "Return True if the libraries for Globus Virtual Workspaces exist"
        return os.path.exists(cls.GLOBUS_LOCATION)

    def getCloudId(self):
        return self._properties.get('vws.factory')

    def getCloudAlias(self):
        return self._cloudAlias

    def listImages(self):
        cmdline = self._cmdline('--list')
        stdout, stderr, returncode = self._exec(cmdline)
        return self._parseListImages(stdout)

    def listInstances(self):
        cmdline = self._cmdline('--status')
        stdout, stderr, returncode = self._exec(cmdline)
        return self._parseListInstances(stdout)

    def transferInstance(self, filename):
        cmdline = self._cmdline('--transfer', '--sourcefile', filename)
        stdout, stderr, returncode = self._exec(cmdline)
        if returncode != 0:
            raise Exception("XXX 1")

    def launchInstances(self, imageIds, duration, callback):
        # duration is time in minutes
        # We only launch an instance for now
        imageId = imageIds[0]
        hours = duration / 60.0
        historyDir = "%s/history" % self._tmpDir
        try:
            os.mkdir(historyDir)
        except OSError, e:
            if e.errno != 17:
                raise
        cmdline = self._cmdline('--run', '--name', imageId,
                                '--hours', str(hours))
        instanceId, returnCode = self._execLaunchInstances(cmdline,
            historyDir, callback)
        return instanceId

    @classmethod
    def _execLaunchInstances(cls, cmdline, historyDir, callback):
        p = cls._execCmdBackend(cmdline)
        pobj = select.poll()
        flags = select.POLLIN | select.POLLERR | select.POLLHUP
        pobj.register(p.stdout.fileno(), flags)
        pobj.register(p.stderr.fileno(), flags)

        hndl = 'vm-001'
        xmlFile = os.path.join(historyDir, hndl, "vw-epr.xml")

        # poll for .2 s
        tmout = 200
        fdCount = 2
        instanceId = None
        while fdCount:
            ret = pobj.poll(tmout)
            # Get rid of the output
            for fd, evt in ret:
                if not evt & (select.POLLIN | select.POLLERR | select.POLLHUP):
                    continue
                data = cls._processData(pobj, fd)
                if data == "":
                    pobj.unregister(fd)
                    fdCount -= 1

            if tmout is None or not os.path.exists(xmlFile):
                # File doesn't exist, or we already read it
                continue
            # Don't consume CPU by looping tightly, just block until we have
            # the data available from now on
            tmout = None
            instanceId = cls._parseEprFile(xmlFile)
            callback(instanceId)
        p.wait()
        return instanceId, p.returncode

    @classmethod
    def _processData(cls, pollObj, fd):
        return os.read(fd, 1024)

    @classmethod
    def _parseEprFile(cls, xmlFile):
            # Parse the file and extract the instance ID
        epr = EPR()
        epr.parse(file(xmlFile))
        # The callback will tie the reservation ID to the instance ID
        return epr.id

    def _createConfigFile(self):
        self._configFile = os.path.join(self._tmpDir, "cloud.properties")
        stream = self._openStream(self._configFile)
        self._properties.write(stream)
        stream.write("\nssh.pubkey=%s\n" % self._sshPubKeyPath)
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
            raise Exception("Passphrase-protected key", stdout + stderr)
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

    @classmethod
    def _execCmdBackend(cls, cmdline, withStdin = False):
        if withStdin:
            stdin = subprocess.PIPE
        else:
            stdin = file(os.devnull)

        env = os.environ.copy()
        # XXX Hack
        javaHome = env.get('JAVA_HOME', '/usr/lib64/jvm/sun-java-5.0u15/jre')
        env['PATH'] = env['PATH'] + ':%s/bin' % javaHome
        p = subprocess.Popen(cmdline, stdout = subprocess.PIPE,
            stderr = subprocess.PIPE, stdin = stdin, env = env)
        return p

    @classmethod
    def _exec(cls, cmdline, stdinData = None):
        p = cls._execCmdBackend(cmdline, withStdin = (stdinData is not None))
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
            "--history-dir", "%(history)s"
        ] + list(args)
        replacements = dict(top = self.GLOBUS_LOCATION,
            certDir = self._caCertDir,
            confFile = self._configFile,
            proxyCert = self._proxyCertPath,
            history = os.path.join(self._tmpDir, 'history'),
        )
        return [ x % replacements for x in cmdline ]

    def _opensslCmdline(self, *args):
        cmdline = ["openssl", "x509", "-noout"] + list(args)
        return cmdline

    def _cmdlineProxy(self):
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
            "org.globus.tools.ProxyInit",
            "-key", "%(userKey)s",
            "-cert", "%(userCert)s",
            "-out", "%(proxyCert)s",
        ]
        replacements = dict(top = self.GLOBUS_LOCATION,
            certDir = self._caCertDir,
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

    def _parseListInstances(self, data):
        sio = StringIO.StringIO(data)
        sio.seek(0)
        instancesLines = self._splitListInstances(sio)
        ret = []
        for instanceLines in instancesLines:
            inst = self._parseInstanceLines(instanceLines)
            if inst is not None:
                ret.append(inst)
        return ret

    def _splitListInstances(self, sio):
        prefix = '[*]'
        ret = []
        for line in sio:
            line = line.strip()
            if not line:
                continue
            if line.startswith(prefix):
                ret.append([])
            if not ret:
                # We haven't found a start block line
                continue
            ret[-1].append(line)
        return ret

    @classmethod
    def _parseInstanceLines(cls, instanceLines):
        line = instanceLines[0]
        prefix = '[*] - Workspace #'
        if not line.startswith(prefix):
            return None
        line = line[len(prefix):]
        m = cls._instance_1_re.search(line)
        if not m:
            return None

        inst = Instance()
        instId, instIp, instName = m.groups()
        inst.setId(int(instId))
        inst.setIp(instIp)
        inst.setName(instName)

        timeFields = { 'Start time' : 'setStartTime',
                       'Shutdown time' : 'setShutdownTime',
                       'Termination time' : 'setTerminationTime', }
        for line in instanceLines[1:]:
            k, v = cls._splitLine(line)
            if k == 'State':
                inst.setState(v)
            elif k == 'Duration':
                suffix = ' minutes.'
                if not v.endswith(suffix):
                    continue
                try:
                    v = int(v[:-len(suffix)])
                    inst.setDuration(v)
                except ValueError:
                    pass
            elif k in timeFields:
                ttup = time.strptime(v, cls._timeFormat)
                tstamp = int(time.mktime(ttup))
                meth = getattr(inst, timeFields[k])
                meth(tstamp)
        return inst

    @classmethod
    def _parseLaunchInstances(cls, data, historyDir):
        # We should have a 'vm-001' in the output
        hndl = 'vm-001'
        if hndl not in data:
            raise Exception("XXX 1")
        # Grab the identifier from the XML file
        xmlFile = os.path.join(historyDir, hndl, "vw-epr.xml")
        epr = EPR()
        epr.parse(file(xmlFile))
        return epr.id

    @classmethod
    def _repackageImage(self, filename):
        """
        Take a .tar.gz image and convert it to a gzipped image with the same
        name, in the same directory
        """
        bname = os.path.basename(filename)
        for suffix in ['.tgz', '.tar.gz']:
            if bname.endswith(suffix):
                bname = bname[:-len(suffix)]
                break
        else: # for
            # Not a .tar.gz
            raise Exception("Not a tar-gzipped image")

        dname = os.path.dirname(filename)
        dfilename = os.path.join(dname, bname + '.gz')
        cmd = "tar zxvf %s --to-stdout | gzip -c > %s" % (filename, dfilename)
        p = subprocess.Popen(cmd, shell = True, stderr = file(os.devnull, "w"))
        p.wait()
        return dfilename

    @classmethod
    def _splitLine(cls, line):
        arr = line.split(': ', 1)
        if len(arr) != 2:
            return (None, None)
        return arr

    def close(self):
        if self._tmpDir is None:
            return
        shutil.rmtree(self._tmpDir, ignore_errors = True)
        self._tmpDir = None

    _policyTemplate = """
access_id_CA    X509    '%(caSubject)s'
pos_rights      globus  CA:sign
cond_subjects   globus  '"%(certSubject)s"'
"""

class Instance(object):
    __slots__ = [ '_id', '_name', '_state', '_ip', '_duration',
        '_startTime', '_shutdownTime', '_terminationTime', ]

    def __init__(self, **kwargs):
        for k in self.__slots__:
            val = kwargs.get(k, None)
            setattr(self, k, val)

    # Magic function mapper
    def __getattr__(self, name):
        if name[:3] not in ['get', 'set']:
            raise AttributeError(name)
        slot = "_%s%s" % (name[3].lower(), name[4:])
        if slot not in self.__slots__:
            raise AttributeError(name)
        if name[:3] == 'get':
            return lambda: self._get(slot)
        return lambda x: self._set(slot, x)

    def _set(self, key, value):
        setattr(self, key, value)

    def _get(self, key):
        val = getattr(self, key)
        return val

class EPR(object):
    def __init__(self):
        self.id = None

    def parse(self, stream):
        dom = minidom.parse(stream)

        try:
            nodes = dom.getElementsByTagName('ns2:WorkspaceKey')
            if nodes:
                node = nodes[0]
                self.id = int(node.childNodes[0].data)
        finally:
            dom.unlink()
