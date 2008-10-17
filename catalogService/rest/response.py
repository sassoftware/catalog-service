from restlib import response

from catalogService import xmlNode

class XmlResponse(response.Response):
    def __init__(self, content, *args, **kw):
        hndlr = xmlNode.Handler()
        newContent = hndlr.toXml(content)
        response.Response.__init__(self, newContent, *args, **kw)
        self.headers['content-type'] = 'application/xml'
        self.headers['Cache-Control'] = 'No-store'

class XmlStringResponse(response.Response):
    def __init__(self, *args, **kw):
        response.Response.__init__(self, *args, **kw)
        self.headers['content-type'] = 'application/xml'
        self.headers['Cache-Control'] = 'No-store'
