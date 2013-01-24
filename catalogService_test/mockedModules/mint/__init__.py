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


"""This module is a dummy module that implements exactly what cloud-catalog
needs from mint. This was done with a very specific API in order to
ensure the interaction between rBuilder and cloud catalog
is tightly controlled.

This module exists to break a dependency loop between cloud-catalog and mint.
cloud-catalog is integrated into rBuilder and tested there."""
