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


import weakref

class Manager(object): 
    def __init__(self, cfg, db, auth, publisher=None):
        self.cfg = cfg
        self.auth = auth
        self._db = weakref.ref(db)
        self.publisher = publisher

    def _getDb(self):
        return self._db()

    db = property(_getDb)
