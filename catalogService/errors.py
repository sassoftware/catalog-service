#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import sys
import traceback
from lxml import etree

from mint.rest.middleware import error

from catalogService.rest.middleware.response import XmlStringResponse
from catalogService.rest.middleware import http_codes

class CatalogErrorResponse(XmlStringResponse):
    def __init__(self, status, message, tracebackData='', productCodeData=None, envelopeStatus=None,
                 *args, **kw):
        # See RBL-3818 - flex does not expose the content of a non-200
        # response, so we have to tunnel faults through 200.
        faultNode = etree.Element("fault")
        node = etree.Element("code")
        node.text = str(status)
        faultNode.append(node)

        node = etree.Element("message")
        node.text = message
        faultNode.append(node)

        if tracebackData:
            node = etree.Element("traceback")
            node.text = tracebackData
            faultNode.append(node)
        
        if productCodeData:
            node = etree.Element("productCode")
            for k, v in productCodeData.iteritems():
                node.set(k, v)
            faultNode.append(node)

        content = etree.tostring(faultNode, pretty_print = True,
            xml_declaration = True, encoding = 'UTF-8')
        # Prefer envelopeStatus if set, otherwise use status
        XmlStringResponse.__init__(self, content=content,
                                   status=envelopeStatus or status,
                                   message=message, *args, **kw)


class CatalogError(Exception):
    """Base class for errors from Cloud Catalog Service"""
    status = http_codes.HTTP_INTERNAL_SERVER_ERROR
    def __init__(self, message=None, status=None, *args, **kw):
        if not message:
            message = self.__class__.__doc__
        if not status:
            status = self.status
        self.status = status
        self.msg = message
        self.tracebackData = kw.get('tracebackData', None)
        self.productCodeData = kw.get('productCodeData', None)

    def __str__(self):
        return self.msg

class InvalidCloudName(CatalogError):
    """Cloud name is not valid"""
    status = http_codes.HTTP_NOT_FOUND

class MissingCredentials(CatalogError):
    """Cloud credentials are not set in rBuilder"""
    status = http_codes.HTTP_BAD_REQUEST

class PermissionDenied(CatalogError):
    """Permission Denied"""
    status = http_codes.HTTP_FORBIDDEN

class ParameterError(CatalogError):
    """Errors were detected in input"""
    status = http_codes.HTTP_BAD_REQUEST
    def __init__(self, message = None):
        CatalogError.__init__(self, message = message)

class ResponseError(CatalogError):
    """Response error from remote cloud service"""
    status = http_codes.HTTP_BAD_REQUEST
    # XXX flex's httpd stack requires we pass a 200 or it will junk the content
    def __init__(self, status, message, body, productCodeData=None):
        # strip any xml tags
        if body.strip().startswith('<?xml'):
            body = ''.join(body.splitlines(True)[1:])
        CatalogError.__init__(self, message, status = status, tracebackData = body, productCodeData = productCodeData)

class CloudExists(CatalogError):
    """Target already exists"""
    status = http_codes.HTTP_CONFLICT

class HttpNotFound(CatalogError):
    """File not found"""
    status = 404

class DownloadError(CatalogError):
    """Error downloading image"""
    status = 404

class ErrorMessageCallback(error.ErrorCallback):
    def processResponse(self, request, response):
        if response.status == 200 or response.content:
            return
        return CatalogErrorResponse(status=response.status,
                            message=response.message,
                            headers=response.headers,
                            envelopeStatus = self._getEnvelopeStatus(request))

    def processException(self, request, excClass, exception, tb):
        envelopeStatus = self._getEnvelopeStatus(request)
        if isinstance(exception, CatalogError):
            return CatalogErrorResponse(status=exception.status,
                                        message=exception.msg,
                                        envelopeStatus = envelopeStatus,
                                        tracebackData = exception.tracebackData,
                                        productCodeData = exception.productCodeData)
        return error.ErrorCallback.processException(self, request, excClass,
            exception, tb)

    @classmethod
    def _getEnvelopeStatus(cls, request):
        if 'HTTP_X_FLASH_VERSION' not in request.headers:
            return None
        return 200
