#
# Copyright (c) 2008 rPath, Inc.
#

from catalogService import http_codes

class CatalogError(Exception):
    """Base class for errors from Cloud Catalog Service"""
    errcode = http_codes.HTTP_INTERNAL_SERVER_ERROR
    def __str__(self):
        if hasattr(self, 'msg'):
            return self.msg
        return str(self.__class__.__doc__)

class MissingCredentials(CatalogError):
    """Cloud credentials are not set in rBuilder"""
    errcode = http_codes.HTTP_BAD_REQUEST

class PermissionDenied(CatalogError):
    """Permission Denied"""
    errcode = http_codes.HTTP_FORBIDDEN

class ResponseError(CatalogError):
    """Response error from remote cloud service"""
    errcode = http_codes.HTTP_BAD_REQUEST
    def __init__(self, status, reason, body):
        # strip any xml tags
        if body.strip().startswith('<?xml'):
            body = ''.join(body.splitlines(True)[1:])
        self.msg = "<wrapped_fault><status>%s</status><reason>%s</reason><body>%s</body>" % (status, reason, body)

class HttpNotFound(CatalogError):
    """File not found"""
    errcode = 404
