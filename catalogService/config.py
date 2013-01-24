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


from conary import conarycfg

class BaseConfig(conarycfg.ConfigFile):
    """
    Base configration object
    """
    # Url to rBuilder server. If None, a shimclient will be used.
    # this config value expects to have two string substitution placeholders
    # for username and password eg, http://%s:%s@URL/
    rBuilderUrl = None
