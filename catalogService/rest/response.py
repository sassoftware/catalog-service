from restlib import response

from catalogService import xmlNode

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

class HtmlFileResponse(response.Response):
    def __init__(self, fileName, *args, **kw):
        content = file(fileName).read()
        response.Response.__init__(self, content, *args, **kw)
        self.headers['content-type'] = 'text/html'
        self.headers['Cache-Control'] = 'no-store'
