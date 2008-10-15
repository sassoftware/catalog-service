#
# Copyright (c) 2008 rPath, Inc.
#
from catalogService.rest.response import XmlStringResponse

#class CatalogError(Exception):
#    """Base class for errors from Cloud Catalog Service"""
#    errcode = http_codes.HTTP_INTERNAL_SERVER_ERROR
#    def __str__(self):
#        if hasattr(self, 'msg'):
#            return self.msg
#        return str(self.__class__.__doc__)

#    def __repr__(self):
#        return self.__class__.__doc__ or ''

#class MissingCredentials(CatalogError):
#    """Cloud credentials are not set in rBuilder"""
#    errcode = http_codes.HTTP_BAD_REQUEST

#class PermissionDenied(CatalogError):
#    """Permission Denied"""
#    errcode = http_codes.HTTP_FORBIDDEN

#class ParameterError(CatalogError):
#    """Errors were detected in input"""
#    errcode = http_codes.HTTP_BAD_REQUEST
#    def __init__(self, msg = None):
#        if msg:
#            self.msg = msg


#class ResponseError(CatalogError):
#    """Response error from remote cloud service"""
#    errcode = http_codes.HTTP_OK
#    #errcode = http_codes.HTTP_BAD_REQUEST
#    # XXX flex's httpd stack requires we pass a 200 or it will junk the content
#    def __init__(self, status, reason, body):
#        # strip any xml tags
#        if body.strip().startswith('<?xml'):
#            body = ''.join(body.splitlines(True)[1:])
#        self.msg = "<wrapped_fault><status>%s</status><reason>%s</reason><body>%s</body></wrapped_fault>" % (status, reason, body)

#class HttpNotFound(CatalogError):
#    """File not found"""
#    errcode = 404

class ErrorMessageCallback(object):
    def processResponse(self, request, response):
        if response.status == 200 or response.content:
            return
        content = '''\
<?xml version="1.0" encoding="UTF-8"?>
<fault>
  <code>%(code)s</code>
  <message>%(message)s</message>
</fault>''' % dict(code=response.status, message=response.message)
        return XmlStringResponse(content,
                                 status=response.status,
                                 message=response.message,
                                 headers=response.headers)

