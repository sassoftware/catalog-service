#!/usr/bin/python2.4
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


table = log_error = config_tree = server_root = SERVER_RETURN = parse_qs = \
        parse_qsl = None


# This snippet searches mod_python's apache.py for trivial references to
# _apache, and attempts to automatically stub them into this module.
#
# It is a delicious hack. You must eat it.
#
import sys, os.path, re
isconst = re.compile('^(\S+)\s*=\s*_apache\.\\1')
for x in sys.path:
    y = os.path.join(x, 'mod_python', 'apache.py')
    if os.path.exists(y):
        f = open(y)
        for line in f:
            m = isconst.search(line)
            if m:
                setattr(sys.modules['_apache'], m.group(1), None)

mpm_query = lambda *P, **K: None
