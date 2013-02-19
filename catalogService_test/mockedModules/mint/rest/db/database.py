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


import base64
import json

from mint import mint_error

class Database(object):
    def __init__(self, cfg, db, auth=None, subscribers=None, dbOnly=False):
        self.cfg = cfg
        self.db = db
        self.auth = auth or AuthenticationManager()
        # These should be part of self.auth, but we won't mock that just yet
        self._mintAuth = None
        self._authToken = None
        self.imageMgr = ImageManager(self.db)
        self.targetMgr = TargetManager(self.db)
        self.productMgr = ProductManager(self.db)

    def cursor(self):
        return self.db.db.cursor()

    def _commitAfter(self, fn, *args, **kw):
        """
            Commits after running a function
        """
        self.db.transaction()
        try:
            rv = fn(*args, **kw)
            self.commit()
            return rv
        except:
            self.rollback()
            raise

    def commit(self):
        return self.db.db.commit()

    def rollback(self):
        return self.db.db.rollback()

    def setAuth(self, auth, authToken):
        self.auth.setAuth(auth, authToken)

    def getProduct(self, hostname):
        return self.productMgr.getProduct(hostname)

    def listProducts(self, start=0, limit=None, search=None, roles=None,
                     prodtype=None):
        return self.productMgr.listProducts(start=start, limit=limit,
                search=search, roles=roles, prodtype=prodtype)

class AuthenticationManager(object):
    def __init__(self):
        self.authToken = None
        self.auth = None
        self.userId = None

    def setAuth(self, auth, authToken):
        self.auth = auth
        self.authToken = authToken
        self.userId = auth.userId

class RepositoryManager(object):
    def __init__(self, mintdb):
        self.mintdb = mintdb

    def getUserClient(self):
        pass


class Product(object):
    shortname = 'foo'
    hostname = 'foo'

class ProductList(object):
    products = []

class ProductManager(object):
    def __init__(self, mintdb):
        self.mintdb = mintdb
        self.reposMgr = RepositoryManager(self.mintdb)

    def getProduct(self, fqdn):
        return Product()

    def listProducts(self, start=0, limit=None, search=None, roles=None,
                     prodtype=None):
        return ProductList()

class ImageManager(object):
    def __init__(self, mintdb):
        self.mintdb = mintdb

    def getAllImagesByType(self, buildType):
        return self.mintdb.db._buildData[buildType]

class TargetManager(object):
    def __init__(self, mintdb):
        self.mintdb = mintdb

    def _getCursor(self):
        return self.mintdb.cursor()

    def getUserId(self, username):
        cu = self._getCursor()
        cu.execute("SELECT userId FROM Users WHERE username=? AND active=1",
            username)
        for row in cu:
            return row[0]

    def getTargetTypeId(self, targetType):
        cu = self._getCursor()
        cu.execute("""
            SELECT target_type_id FROM target_types WHERE name = ?
        """, targetType)
        for row in cu:
            return row[0]

    def getTargetId(self, targetType, targetName):
        cu = self._getCursor()
        cu.execute("""
            SELECT t.targetId FROM Targets AS t
            JOIN target_types AS tt USING (target_type_id)
            WHERE tt.name = ? AND t.name = ?""", targetType, targetName)
        for row in cu:
            return row[0]

    def addTarget(self, targetType, targetName, targetData):
        targetId = self._addTarget(targetType, targetName)
        self._addTargetData(targetId, targetData)

    def deleteTarget(self, targetType, targetName):
        cu = self._getCursor()
        targetTypeId = self.getTargetTypeId(targetType)
        cu.execute("DELETE FROM Targets WHERE target_type_id=? AND name=?",
                targetTypeId, targetName)

    def _addTarget(self, targetType, targetName):
        cu = self._getCursor()
        targetId = self.getTargetId(targetType, targetName)
        if targetId:
            raise mint_error.TargetExists( \
                    "Target named '%s' of type '%s' already exists",
                    targetName, targetType)
        cu.execute("""INSERT INTO Targets (name, target_type_id)
            SELECT ?, tt.target_type_id
              FROM target_types AS tt
             WHERE tt.name = ?""", targetName, targetType)
        return cu.lastid()

    def _addTargetData(self, targetId, targetData):
        cu = self._getCursor()
        # perhaps check the id to be certain it's unique
        for name, value in targetData.iteritems():
            value = json.dumps(value)
            cu.execute("INSERT INTO TargetData VALUES(?, ?, ?)",
                    targetId, name, value)

    def getTargetData(self, targetType, targetName):
        cu = self._getCursor()
        cu.execute("""
            SELECT td.name, td.value
              FROM Targets
              JOIN TargetData AS td USING (targetId)
              JOIN target_types AS tt ON (Targets.target_type_id = tt.target_type_id)
             WHERE tt.name = ? AND Targets.name = ?
        """, targetType, targetName)
        res = {}
        return dict((k, self._stripUnicode(json.loads(v)))
            for (k, v) in cu)

    @classmethod
    def _stripUnicode(cls, value):
        if hasattr(value, 'encode'):
            return value.encode('ascii')
        return value

    def getConfiguredTargetsByType(self, targetType):
        cu = self._getCursor()
        cu.execute("""
            SELECT Targets.name, TargetData.name, TargetData.value
              FROM Targets
              JOIN TargetData USING (targetId)
              JOIN target_types AS tt ON (Targets.target_type_id = tt.target_type_id)
             WHERE tt.name = ?
        """, targetType)
        ret = {}
        for targetName, key, value in cu:
            ret.setdefault(targetName, {})[key] = self._stripUnicode(
                json.loads(value))
        return ret

    def getTargetsForUser(self, targetType, userName):
        cu = self._getCursor()
        cu.execute("""
            SELECT Targets.name,
                   TargetUserCredentials.credentials
              FROM Targets
         LEFT JOIN TargetUserCredentials USING (targetId)
              JOIN Users USING (userId)
              JOIN target_types AS tt ON (Targets.target_type_id = tt.target_type_id)
             WHERE tt.name = ?
               AND Users.username = ?
        """, targetType, userName)
        userCreds = {}
        for targetName, creds in cu:
            userCreds[targetName] = unmarshalTargetUserCredentials(creds)
        targetConfig = self.getConfiguredTargetsByType(targetType)
        ret = []
        for targetName, cfg in sorted(targetConfig.items()):
            ret.append((targetName, cfg, userCreds.get(targetName, {})))
        return ret

    def setTargetCredentialsForUser(self, targetType, targetName, userName,
                                    credentials):
        targetId = self.getTargetId(targetType, targetName)
        if targetId is None:
            raise Exception("XXX no target")
        userId = self.getUserId(userName)
        if userId is None:
            raise Exception("XXX no user")
        cu = self._getCursor()
        cu.execute(
            "DELETE FROM TargetUserCredentials WHERE targetId=? AND userId=?",
            targetId, userId)
        data = marshalTargetUserCredentials(credentials)
        cu.execute("""
            INSERT INTO TargetUserCredentials (targetId, userId, credentials)
            VALUES (?, ?, ?)""", targetId, userId, data)

    def getTargetCredentialsForUser(self, targetType, targetName, userName):
        cu = self._getCursor()
        cu.execute("""
            SELECT creds.credentials
              FROM Users
              JOIN TargetUserCredentials AS creds USING (userId)
              JOIN Targets USING (targetId)
              JOIN target_types AS tt ON (Targets.target_type_id = tt.target_type_id)
             WHERE tt.name = ?
               AND Targets.name = ?
               AND Users.username = ?
        """, targetType, targetName, userName)
        row = cu.fetchone()
        if not row:
            return {}
        return unmarshalTargetUserCredentials(row[0])

    def linkTargetImageToImage(self, targetType, targetName, fileId,
            targetImageId):
        for imgType, imgList in self.mintdb.db._buildData.items():
            for imageData in imgList:
                for fileData in imageData.get('files', []):
                    if fileData.get('fileId') != fileId:
                        continue
                    fileData.setdefault('targetImages', []).append(
                        (targetType, targetName, targetImageId))


def marshalTargetUserCredentials(creds):
    # creds: dictionary
    if not creds:
        return ""
    # Newline-separated credential fields
    data = '\n'.join("%s:%s" % (k, base64.b64encode(v))
        for (k, v) in sorted(creds.iteritems()))
    return data

def unmarshalTargetUserCredentials(creds):
    ret = {}
    for nameval in creds.split('\n'):
        arr = nameval.split(':', 1)
        if len(arr) != 2:
            continue
        ret[arr[0]] = base64.b64decode(arr[1])
    return ret
