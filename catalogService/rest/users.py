from catalogService import userData
from base import BaseModelHandler
from catalogService.handler import StorageConfig
from catalogService import storage
from restlib.handler import RestModelHandler

class UserMixin(object):
    storageConfig = StorageConfig(storagePath = "storage")
    def _getUserDataStore(self):
        path = self.storageConfig.storagePath + '/userData'
        cfg = StorageConfig(storagePath = path)
        return storage.DiskStorage(cfg)

    @classmethod
    def _sanitizeKey(cls, key):
        return '/'.join(x for x in key.split('/') if x not in ('.', '..'))



class UsersController(RestModelHandler, UserMixin):
    paramName = 'userId'
    processSuburls = True

    def __init__(self, parent, path, cfg, mintClient):
        self.mintClient = mintClient
        self.cfg = cfg
        RestModelHandler.__init__(self, parent, path, [cfg, mintClient])


    def index(self, response, request, parameters, url):
        "enumerate the users"
        raise NotImplementedError

    def update(self, userId, response, request, parameters, keyId):
        "update a key"
        if userId != request.auth[0]:
            raise Exception("XXX 1", userId, request.auth[0])

        dataLen = request.getContentLength()
        data = request.read(dataLen)

        key = self._sanitizeKey(keyId)

        store = self._getUserDataStore()
        store.set(key, data)
        data = '<?xml version="1.0" encoding="UTF-8"?><id>%s</id>' % (self.url(request, '%s/%s' % (userId, key)))
        return response.write(data)

    def get(self, userId, response, request, parameters, keyPath):
        if userId != request.auth[0]:
            raise Exception("XXX 1", userId, request.auth[0])
        key = self._sanitizeKey(keyPath)

        prefix = self.url(request, '%s/' % (userId))
        store = self._getUserDataStore()

        xmlHeader = '<?xml version="1.0" encoding="UTF-8"?>'
        key = key.rstrip('/')
        if key != keyPath:
            # A trailing / means retrieving the contents from a collection
            if not store.isCollection(key):
                data = xmlHeader + '<list></list>'
                response.write(data)
                return
                #raise Exception("XXX 2", prefix, keyPath)

        if store.isCollection(key):
            node = userData.IdsNode()
            snodes = store.enumerate(keyPrefix = key)

            if key == keyPath:
                # No trailing /
                snodes = [ userData.IdNode().characters("%s%s" % (prefix, x))
                         for x in snodes ]
                node.extend(snodes)
                response.to_xml(node)
                return
            # Grab contents and wrap them in some XML
            data = [ store.get(x) for x in snodes ]
            data = xmlHeader + '<list>%s</list>' % ''.join(data)
            response.write(data)
            return

        data = store.get(key)
        if data is None:
            raise NotImplementedError
        response.write(data)


    def destroy(self, userId, response, request, parameters, key):
        if userId != request.auth[0]:
            raise Exception("XXX 1", userId, request.getUser())

        store = self._getUserDataStore()

        key = self._sanitizeKey(key)
        store.delete(key)
        url = self.url(request, '%s/%s' % (userId, key))
        data = '<?xml version="1.0" encoding="UTF-8"?><id>%s</id>' % (url)
        response.write(data)

    def process(self, userId, response, request, parameters, key):
        "create a new key entry in the store"
        if userId != request.auth[0]:
            raise Exception("XXX 1", userId, request.auth[0])

        dataLen = request.getContentLength()
        data = request.read(dataLen)
        store = self._getUserDataStore()

        # Sanitize key
        key = key.rstrip('/')
        keyPrefix = self._sanitizeKey(key)

        newId = store.store(data, keyPrefix = keyPrefix)
        url = self.url(request, '%s/%s' % (userId, newId) )
        txt = '<?xml version="1.0" encoding="UTF-8"?><id>%s</id>' % (url)
        return response.write(txt)


