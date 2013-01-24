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


from rpath_xmllib import api1 as xmllib

from catalogService.rest.models import xmlNode

class UuidNode(xmlNode.BaseNode):
    tag = 'uuid'

    def __repr__(self):
        return "<%s:tag=%s at %#x>" % (self.__class__.__name__, self.tag,
                    id(self))

class UuidHandler(xmllib.DataBinder):
    uuidClass = UuidNode

    def __init__(self):
        xmllib.DataBinder.__init__(self)
        for cls in [ self.uuidClass ]:
            self.registerType(cls, cls.tag)

class ImageNode(xmlNode.BaseNode):
    tag = 'image'

class ImageHandler(xmllib.DataBinder):
    imageClass = ImageNode

    def __init__(self):
        xmllib.DataBinder.__init__(self)
        for cls in [ self.imageClass ]:
            self.registerType(cls, cls.tag)
