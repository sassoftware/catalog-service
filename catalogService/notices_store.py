#!/usr/bin/python2.4
#
# Copyright (c) 2009 rPath, Inc.
#

import os
import time
from catalogService import storage

class DiskStorage(storage.DiskStorage):
    pass

class Storage(object):
    storageFactory = DiskStorage
    def __init__(self, globalStorePath, userStorePath):
        self.globalStore = self.storageFactory(
            storage.StorageConfig(globalStorePath))
        self.userStore = self.storageFactory(
            storage.StorageConfig(userStorePath))

    def storeGlobal(self, context, data, modified = None):
        keyPrefix = context
        return self._storeNotice(self.globalStore, keyPrefix, data, modified)

    def storeUser(self, context, data, modified = None):
        keyPrefix = ("notices", context)
        return self._storeNotice(self.userStore, keyPrefix, data, modified)

    def enumerateAllStore(self):
        return mergeIterables([self.enumerateAllUserStore(),
            self.enumerateAllGlobalStore()], key = self._modifiedSortKey)

    def enumerateAllUserStore(self):
        return mergeIterables([ self.enumerateStoreUser(os.path.basename(ctx))
                                for ctx in self.userStore.enumerate('notices') ],
            key = self._modifiedSortKey)

    def enumerateAllGlobalStore(self):
        return mergeIterables([ self.enumerateStoreGlobal(ctx)
                                for ctx in self.globalStore.enumerate() ],
            key = self._modifiedSortKey)

    def enumerateStoreGlobal(self, context):
        return self._enumerateStore(context, isGlobal = True)

    def enumerateStoreUser(self, context):
        return self._enumerateStore(context, isGlobal = False)

    def _enumerateStore(self, context, isGlobal = False):
        if isGlobal:
            keyPrefix = context
            store = self.globalStore
        else:
            keyPrefix = ("notices", context)
            store = self.userStore

        notices = self._enumerateNotices(store, keyPrefix = keyPrefix)
        dismissals = self._enumerateDismissals(self.userStore,
            isGlobal = isGlobal)
        dismissedNoticesMap = dict((x.noticeId, x) for x in dismissals)

        ret = []
        for notice in notices:
            if notice.id in dismissedNoticesMap:
                del dismissedNoticesMap[notice.id]
                continue
            ret.append(notice)
        # Remove any unused dismissals
        for dismissal in dismissedNoticesMap.values():
            self.userStore.delete(dismissal.id)
        ret.sort(key = self._modifiedSortKey)
        return ret

    def storeGlobalDismissal(self, key):
        return self._storeDismissal(key, isGlobal = True)

    def storeUserDismissal(self, key):
        return self._storeDismissal(key, isGlobal = False)

    def _storeDismissal(self, key, isGlobal = False):
        if isGlobal:
            keyPrefix = ('dismissals', 'global')
            store = self.globalStore
        else:
            keyPrefix = ('dismissals', 'user')
            store = self.userStore

        if isinstance(key, Notice):
            keyId = key.id
        else:
            keyId = key

        # Grab the notice
        notice = self._getNotice(store, keyId)
        if notice is None:
            # No key, nothing to dismiss
            return

        self._addDismissal(self.userStore, isGlobal = isGlobal, keyId = keyId)

    @classmethod
    def _modifiedSortKey(cls, x):
        return x.modified

    @classmethod
    def _timestampSortKey(cls, x):
        return x.timestamp

    @classmethod
    def _storeNotice(cls, store, keyPrefix, data, modified):
        if modified is None:
            modified = time.time()
        newColl = store.newCollection(keyPrefix = keyPrefix)
        store.set((newColl, "content"), data)
        store.set((newColl, "modified"), "%.3f" % modified)
        return Notice(newColl, data, modified)

    @classmethod
    def _getNotice(cls, store, keyId):
        if not store.exists(keyId):
            return None
        return Notice(keyId, store.get((keyId, "content")),
                             store.get((keyId, "modified")))

    @classmethod
    def _enumerateNotices(cls, store, keyPrefix):
        for keyId in store.enumerate(keyPrefix = keyPrefix):
            notice = cls._getNotice(store, keyId)
            if notice is not None:
                yield notice

    @classmethod
    def _addDismissal(cls, store, isGlobal = False, keyId = None):
        dismissalType = (isGlobal and "global") or "user"
        dismissalId = ("dismissals", dismissalType, keyId)
        store.set(dismissalId, "")

    @classmethod
    def _enumerateDismissals(cls, store, isGlobal = False):
        dismissalType = (isGlobal and "global") or "user"
        keyPrefix = ("dismissals", dismissalType)
        for keyId in store.enumerateAll(keyPrefix = keyPrefix):
            dismissal = cls._createDismissal(keyId, '')
            if dismissal is None:
                # Invalid
                store.delete(keyId)
                continue
            yield dismissal

    @classmethod
    def _createDismissal(cls, keyId, content):
        # Strip the first two parts of the key prefix (dismissals and
        # dismissalType)
        _, dismissalType, noticeId = keyId.split('/', 2)
        return Dismissal(keyId, noticeId = noticeId, dismissalType = dismissalType)

class Notice(object):
    __slots__ = [ 'modified', 'content', 'id' ]

    def __init__(self, keyId, content, modified):
        self.modified = modified
        if modified is not None:
            self.modified = float(modified)
        self.content = content
        self.id = keyId

class Dismissal(object):
    __slots__ = [ 'id', 'timestamp', 'noticeId', 'type' ]

    def __init__(self, keyId, timestamp = None, noticeId = None,
                 dismissalType = None):
        self.id = keyId
        self.timestamp = timestamp
        self.noticeId = noticeId
        self.type = dismissalType

def mergeIterables(iterables, key = None):
    if not iterables:
        return
    iter0 = iterables.pop()
    while iterables:
        iter1 = iterables.pop()
        iter0 = mergeTwo(iter0, iter1, key = key)
    for i in iter0:
        yield i

def mergeTwo(list1, list2, key = None):
    iter1 = iter(list1)
    iter2 = iter(list2)
    hasElem1 = hasElem2 = False
    eofl1 = eofl2 = False
    while 1:
        if not hasElem1 and not eofl1:
            try:
                elem1 = iter1.next()
            except StopIteration:
                eofl1 = True
            else:
                hasElem1 = True
        if not hasElem2 and not eofl2:
            try:
                elem2 = iter2.next()
            except StopIteration:
                eofl2 = True
            else:
                hasElem2 = True
        if eofl1 and eofl2:
            return
        if eofl1:
            yield elem2
            hasElem2 = False
            continue
        if eofl2:
            yield elem1
            hasElem1 = False
            continue
        if key is None:
            comparison = (elem1 <= elem2)
        else:
            comparison = (key(elem1) <= key(elem2))
        if comparison:
            yield elem1
            hasElem1 = False
        else:
            yield elem2
            hasElem2 = False

def createStore(storagePath):
    globalStorePath = os.path.join(storagePath, "global")
    userStorePath = os.path.join(storagePath, "user")
    return Storage(globalStorePath, userStorePath)
