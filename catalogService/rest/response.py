from restlib import response

from catalogService import xmlNode
class CatalogResponse(response.Response):
    def to_xml(self, data):
        hndlr = xmlNode.Handler()
        self.write(hndlr.toXml(data))
