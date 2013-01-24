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


from mint.django_rest.rbuilder.inventory import models

class SystemManager(object):
    CREDS = {}
    VERSIONS = {}

    def getSoftwareVersionsForInstanceId(self, instanceId):
        if self.VERSIONS.has_key(instanceId):
            return self.VERSIONS[instanceId]
        else:
            installedGroups = [ 'group-blah=/foo@bar:baz/1234567890:1-2-3[]',
                                'group-second-appliance=/foo@bar:baz/1234567891:1-2-4[]' ]
            return '\n'.join(installedGroups)

    def setSoftwareVersionForInstanceId(self, instanceId, softwareVersion):
        self.VERSIONS[instanceId] = '\n'.join("%s=%s[%s]" %
            (x[1], x[1].freeze(), x[2])
                for x in softwareVersion)

    def setSystemSSLInfo(self, instanceId, sslCert, sslKey):
        return 'setSystemSSLInfo'

    def getSystemByInstanceId(self, instanceId):
        if self.CREDS.has_key(instanceId):
            cert, key = self.CREDS[instanceId]
            system = models.System(
                ssl_client_key = key,
                ssl_client_certificate = cert,
                is_manageable = True)
        else:
            system = models.System(
                is_manageable = False,
            )

        return system

    def getCachedUpdates(self, nvf):
        return None

    def cacheUpdate(self, nvf, updateNvf):
        return

    def clearCachedUpdates(self, nvfs):
        return

class Manager(object):
    def __init__(self, cfg, userName):
        self.cfg = cfg
        self.userName = userName
        self.sysMgr = SystemManager()

    def addLaunchedSystem(self, system, dnsName=None, targetName=None,
            targetType=None):
        # Dump certs
        file("/tmp/adfadf", "w").write(self.cfg.dataPath)
        certFile = "%s/x509.crt" % self.cfg.dataPath
        keyFile = "%s/x509.key" % self.cfg.dataPath
        file(certFile, "w").write(system.ssl_client_certificate)
        file(keyFile, "w").write(system.ssl_client_key)
        return system
