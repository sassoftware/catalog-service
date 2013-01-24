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


import decorator
from mint.rest.db import database

class RestDatabase(database.Database):
    pass

# This is slightly different that mint's, since it's decorating controller
# methods
@decorator.decorator
def commitafter(fn, self, *args, **kw):
    return self.db._commitAfter(fn, self, *args, **kw)
