#!/usr/bin/python
#
# Copyright (c) 2009 rPath, Inc.
#

from lxml.builder import E
from lxml import etree as ET
import os

from catalogService.rest import auth
from catalogService.rest.base import BaseController
from catalogService.rest.response import XmlStringResponse, XmlResponse

from catalogService import notices_store
from StringIO import StringIO

class NoticesContextController(BaseController):
    modelName = "context"

    @auth.public
    def get(self, req, context = None):
        rss = RssHelper(self.cfg.storagePath, title = "Notices for context %s" % context)
        return rss.serialize(rss.store.enumerateStoreGlobal("default"))

class NoticesAggregationController(BaseController):
    modelName = None

    placeholder = "@PLACEHOLDER@"

    @auth.public
    def index(self, req):
        rss = RssHelper(self.cfg.storagePath, title = "Global Notices")
        return rss.serialize(rss.store.enumerateStoreGlobal("default"))

class NoticesController(BaseController):
    urls = dict(aggregation = NoticesAggregationController,
                contexts = NoticesContextController)

class RssHelper(object):
    placeholder = "@PLACEHOLDER@"

    def __init__(self, storagePath, **kwargs):
        self.store = self.createStore(storagePath)
        self.root, self.channel = self.makeXmlTree(**kwargs)

    def serialize(self, notices):
        ret = ET.tostring(self.root, xml_declaration = True, encoding = 'UTF-8')
        ret = ret.replace(self.placeholder, ''.join(x.content for x in notices))
        return XmlStringResponse(ret)

    @classmethod
    def createStore(cls, storagePath):
        return notices_store.createStore(os.path.join(storagePath, "notices"))

    @classmethod
    def makeXmlTree(cls, **kwargs):
        root = E.rss(version = "2.0")
        channel = E.channel(**kwargs)
        channel.text = cls.placeholder
        root.append(channel)
        return root, channel

