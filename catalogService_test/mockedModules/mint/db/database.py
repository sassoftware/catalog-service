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


from conary import dbstore

class Database(object):
    def __init__(self, cfg, db = None):
        self.cfg = cfg
        self.db = dbstore.connect(cfg.dbPath, cfg.dbDriver)
        self.users = self.Users(self.db)

    class Users(object):
        def __init__(self, db):
            self.db = db

        def registerNewUser(self, username, password, fullName, email, *args,
                            **kwargs):
            cu = self.db.cursor()
            cu.execute("""
                INSERT INTO Users (username, fullName, email, passwd, active)
                VALUES (?, ?, ?, ?, ?)""", username, fullName, email, password, 1)
            return cu.lastid()

        def checkAuth(self, authToken):
            username, password = authToken
            auth = {'authorized': False, 'userId': -1}
            cu = self.db.cursor()
            cu.execute("""
                SELECT userId, passwd, fullName, admin, email
                  FROM Users
                 WHERE username=? AND active=1""", username)
            r = cu.fetchone()
            if r:
                auth['username'] = username
                auth['userId'] = r[0]
                auth['authorized'] = (r[1] == password)
                auth['fullName'] = r[2]
                auth['admin'] = bool(r[3])
                auth['email'] = r[4]
            return auth

    def transaction(self):
        return self.db.transaction()

    def reopen_fork(self, forked=False):
        self.db.close()
        self.db = dbstore.connect(self.cfg.dbPath, self.cfg.dbDriver)
        self.users.db = self.db

    def cursor(self):
        return self.db.cursor()
