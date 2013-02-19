#!/usr/bin/python
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


"see __init__ for docstring"

import json
from catalogService_test import mockedData
from mint.mint_error import TargetExists, TargetMissing

class Authorization(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class Build(object):
    def __init__(self, buildId, buildData):
        self.buildId = buildId
        self.troveVersion = '/booya@rpl:linux/0.0:1.1-1-1'
    def getProjectId(self):
        return self.buildId
    def getArch(self):
        return 'x86_64'
    def getId(self):
        return self.buildId
    def getDataValue(self, key):
        return ''

class Project(object):
    def __init__(self, projectId):
        self.projectId = projectId
        self.hostname = 'booya'
    def getUrl(self):
        return 'http://localhost2/projects/booya'

class MintConfig(object):
    proxy = dict()

class MintConfigProxy(object):
    proxy = dict(
        http = "http://user:pass@host:3129",
        https = "https://user:pass@host:3129",
    )

class MintClient(object):
    def __init__(self, *args, **kwargs):
        self._cfg = MintConfig()
        # self.db is set by testbase's setUp

    def checkAuth(self):
        return Authorization(username = 'test', userId = 1, authorized = True,
            admin = False)

    def getEC2CredentialsForUser(x, userId):
        return {'awsPublicAccessKeyId' : mockedData.awsPublicAccessKeyId,
                'awsSecretAccessKey' : mockedData.awsSecretAccessKey,
                'awsAccountNumber' :  mockedData.awsAccountNumber}

    def setEC2CredentialsForUser(x, userId, awsAccountNumber, 
            awsAccessKeyId, awsSecretAccessKey, force):
        return True

    def getProject(self, projectId):
        return Project(projectId)

    @classmethod
    def _getTargetId(cls, targetType, targetName):
        cu = cls.db.cursor()
        cu.execute("""
            SELECT targetId FROM Targets
            WHERE targetType = ? AND targetName = ?""",
            targetType, targetName)
        for row in cu:
            return row[0]

    @classmethod
    def addTarget(cls, targetType, targetName, dataDict):
        targetId = cls._getTargetId(targetType, targetName)
        if targetId is not None:
            raise TargetExists("Target named '%s' of type '%s' already exists",
                targetName, targetType)
        cu = cls.db.cursor()
        cu.execute("INSERT INTO Targets (targetType, targetName) VALUES (?, ?)",
            targetType, targetName)
        targetId = cls._getTargetId(targetType, targetName)
        data = [ (targetId, k.encode('ascii'), json.dumps(v))
            for (k, v) in dataDict.items() ]
        cu.executemany("""
            INSERT INTO TargetData (targetId, name, value)
            VALUES (?, ?, ?)""", data)
        cls.db.commit()
        return True

    @classmethod
    def deleteTarget(cls, targetType, targetName):
        targetId = cls._getTargetId(targetType, targetName)
        if targetId is None:
            raise TargetMissing()
        cu = cls.db.cursor()
        cu.execute("DELETE FROM TargetData WHERE targetId = ?", targetId)
        cu.execute("DELETE FROM Targets WHERE targetId = ?", targetId)
        cls.db.commit()
        return True

    @classmethod
    def getTargetData(cls, targetType, targetName):
        targetId = cls._getTargetId(targetType, targetName)
        if targetId is None:
            raise TargetMissing()
        cu = cls.db.cursor()
        cu.execute("SELECT name, value FROM TargetData WHERE targetId = ?",
            targetId)
        return dict((k, json.loads(v)) for (k, v) in cu)

    @classmethod
    def getConfiguredTargetsData(cls, targetType):
        cu = cls.db.cursor()
        cu.execute("""
            SELECT Targets.targetName, TargetData.name, TargetData.value
              FROM Targets JOIN TargetData USING (targetId)
             WHERE Targets.targetType = ?""", targetType)
        ret = dict()
        for targetName, k, v in cu:
            l = ret.setdefault(targetName, {})
            l[k] = json.loads(v)
        return ret


ShimMintClient = MintClient
