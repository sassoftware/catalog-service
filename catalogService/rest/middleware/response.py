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


import StringIO
from restlib import response

from catalogService.rest.models import xmlNode

class XmlStringResponse(response.Response):
    def __init__(self, *args, **kw):
        response.Response.__init__(self, *args, **kw)
        self.headers['content-type'] = 'application/xml'
        self.headers['Cache-Control'] = 'no-store'

class XmlResponse(XmlStringResponse):
    def __init__(self, content, *args, **kw):
        hndlr = xmlNode.Handler()
        newContent = hndlr.toXml(content)
        XmlStringResponse.__init__(self, newContent, *args, **kw)

class XmlSerializableObjectResponse(XmlStringResponse):
    def __init__(self, content, *args, **kw):
        sio = StringIO.StringIO()
        content.serialize(sio)
        XmlStringResponse.__init__(self, sio.getvalue(), *args, **kw)

class HtmlFileResponse(response.Response):
    def __init__(self, fileName, *args, **kw):
        content = file(fileName).read()
        response.Response.__init__(self, content, *args, **kw)
        self.headers['content-type'] = 'text/html'
        self.headers['Cache-Control'] = 'no-store'
