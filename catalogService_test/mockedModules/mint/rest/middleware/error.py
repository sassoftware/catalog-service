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


import logging
import traceback
from lxml import etree

from restlib import response

from mint import logerror
from mint import mint_error

log = logging.getLogger('mint_error')

class ErrorCallback(object):
    ERROR_TEMPLATE = """\
<?xml version='1.0' encoding='UTF-8'?>
<fault>
  <code>%s</code>
  <message>%s</message>
  <traceback>%s</traceback>
</fault>
"""

    def __init__(self, controller):
        self.controller = controller

    def processException(self, request, excClass, exception, tb):
        message = '%s: %s' % (excClass.__name__, exception)

        if hasattr(exception, 'status'):
            status = exception.status
        else:
            status = 500
            self.logError(request, excClass, exception, tb, doEmail=True)

        # Only send the traceback information if it's an unintentional
        # exception (i.e. a 500)
        if status == 500:
            tbString = 'Traceback:\n' + ''.join(traceback.format_tb(tb))
            text = [message + '\n', tbString]
        else:
            tbString = None
            text = [message + '\n']
        isFlash = 'HTTP_X_FLASH_VERSION' in request.headers
        if not getattr(request, 'contentType', None):
            request.contentType = 'text/xml'
            request.responseType = 'xml'
        if isFlash or request.contentType != 'text/plain':
        # for text/plain, just print out the traceback in the easiest to read
        # format.
            code = status
            if isFlash:
                # flash ignores all data sent with a non-200 error
                status = 200

            text = self._toXml(code, status, ''.join(text))
        return response.Response(text, content_type=request.contentType,
                                 status=status)

    def _toXml(self, code, status, text):
        faultNode = etree.Element("fault")
        node = etree.Element("code")
        node.text = str(code)
        faultNode.append(node)

        node = etree.Element("message")
        node.text = str(status)
        faultNode.append(node)

        node = etree.Element("traceback")
        node.text = text
        faultNode.append(node)

        content = etree.tostring(faultNode, pretty_print = True,
            xml_declaration = True, encoding = 'UTF-8')
        return content



    def logError(self, request, e_type, e_value, e_tb, doEmail=True):
        info = {
                'uri'               : request.thisUrl,
                'path'              : request.path,
                'method'            : request.method,
                'headers_in'        : request.headers,
                'request_params'    : request.GET,
                'post_params'       : request.POST,
                'remote'            : '[%s]:%d' % request.remote[:2],
                }
        try:
            logerror.logErrorAndEmail(self.controller.cfg, e_type, e_value,
                    e_tb, 'API call', info, doEmail=doEmail)
        except mint_error.MailError, err:
            log.error("Error sending mail: %s", str(err))
