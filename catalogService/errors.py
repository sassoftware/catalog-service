#
# Copyright (c) 2008 rPath, Inc.
#
from lxml import etree

from catalogService.rest.response import XmlStringResponse
from catalogService import http_codes

class CatalogErrorResponse(XmlStringResponse):
    def __init__(self, status, message, tracebackData='', *args, **kw):
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

        content = etree.tostring(faultNode, pretty_print = True,
            xml_declaration = True, encoding = 'UTF-8')
        XmlStringResponse.__init__(self, content=content,
                                   status=status,
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
        self.message = message

    def __str__(self):
        return self.message

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
    def __init__(self, status, reason, body):
        # strip any xml tags
        if body.strip().startswith('<?xml'):
            body = ''.join(body.splitlines(True)[1:])
        message = "<wrapped_fault><status>%s</status><reason>%s</reason><body>%s</body></wrapped_fault>" % (status, reason, body)
        CatalogError.__init__(self, message, status = status)

class HttpNotFound(CatalogError):
    """File not found"""
    status = 404

class ErrorMessageCallback(object):
    def processResponse(self, request, response):
        if response.status == 200 or response.content:
            return
        return CatalogErrorResponse(status=response.status,
                            message=response.message,
                            headers=response.headers)

    def processException(self, request, excClass, exception, tb):
        if isinstance(exception, CatalogError):
            return CatalogErrorResponse(status=exception.status,
                                        message=exception.message)
        from restlib.http import handler
        response = handler.ExceptionCallback().processException(request,
            excClass, exception, tb)
        return CatalogErrorResponse(status = response.status,
            message = response.message,
            tracebackData = response.content)
