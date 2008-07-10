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
