#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import os

from restlib.response import Response
from catalogService.rest.models import userData
from catalogService import storage
from catalogService.rest.api.base import BaseController
from catalogService.rest.middleware.response import XmlStringResponse, XmlResponse

class UsersController(BaseController):
    modelName = 'userId'
    processSuburls = True

    def _getUserDataStore(self, request):
        path = os.sep.join([self.storageCfg.storagePath, 'userData',
            self._sanitizeKey(request.auth[0])])
        cfg = storage.StorageConfig(storagePath = path)
        return storage.DiskStorage(cfg)

    @classmethod
    def _sanitizeKey(cls, key):
        return '/'.join(x for x in key.split('/') if x not in ('.', '..'))

    def index(self, request):
        "enumerate the users"
        raise NotImplementedError

    def update(self, request, userId):
        "update a key"
        if userId != request.auth[0]:
            raise Exception("XXX 1", userId, request.auth[0])

        dataLen = request.getContentLength()
        data = request.read(dataLen)

        keyId = request.unparsedPath
        key = self._sanitizeKey(keyId)

        store = self._getUserDataStore(request)
        store.set(key, data)
        data = '<?xml version="1.0" encoding="UTF-8"?><id>%s</id>' % (self.url(request, 'users', '%s/%s' % (userId, key)))
        return XmlStringResponse(data)

    def get(self, request, userId):
        if userId != request.auth[0]:
            raise Exception("XXX 1", userId, request.auth[0])
        keyPath = request.unparsedPath
        key = self._sanitizeKey(keyPath)
        prefix = self.url(request, 'users', '%s/' % (userId))
        store = self._getUserDataStore(request)

        xmlHeader = '<?xml version="1.0" encoding="UTF-8"?>'
        key = key.rstrip('/')
        if key != keyPath:
            # A trailing / means retrieving the contents from a collection
            if not store.isCollection(key):
                data = xmlHeader + '<list></list>'
                return XmlStringResponse(data)
                #raise Exception("XXX 2", prefix, keyPath)

        if store.isCollection(key):
            node = userData.IdsNode()
            snodes = store.enumerate(keyPrefix = key)

            if key == keyPath:
                # No trailing /
                snodes = [ userData.IdNode().characters("%s%s" % (prefix, x))
                         for x in snodes ]
                node.extend(snodes)
                return XmlResponse(node)
            # Grab contents and wrap them in some XML
            data = [ store.get(x) for x in snodes ]
            data = xmlHeader + '<list>%s</list>' % ''.join(data)
            return XmlStringResponse(data)
        else:
            data = store.get(key)
            if data is None:
                raise NotImplementedError
            return XmlStringResponse(data)


    def destroy(self, request, userId):
        if userId != request.auth[0]:
            raise Exception("XXX 1", userId, request.getUser())

        store = self._getUserDataStore(request)
        key = request.unparsedPath

        key = self._sanitizeKey(key)
        store.delete(key)
        url = self.url(request, 'users', '%s/%s' % (userId, key))
        data = '<?xml version="1.0" encoding="UTF-8"?><id>%s</id>' % (url)
        return XmlStringResponse(data)

    def process(self, request, userId):
        "create a new key entry in the store"
        if userId != request.auth[0]:
            raise Exception("XXX 1", userId, request.auth[0])
        key = request.unparsedPath

        dataLen = request.getContentLength()
        data = request.read(dataLen)
        store = self._getUserDataStore(request)

        # Sanitize key
        key = key.rstrip('/')
        keyPrefix = self._sanitizeKey(key)

        newId = store.store(data, keyPrefix = keyPrefix)
        url = self.url(request, 'users', '%s/%s' % (userId, newId) )
        txt = '<?xml version="1.0" encoding="UTF-8"?><id>%s</id>' % (url)
        return XmlStringResponse(txt)
