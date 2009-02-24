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
    def __init__(self, globalStorePath, userStorePath, dismissalsPath):
        self.globalStore = self.storageFactory(
            storage.StorageConfig(globalStorePath))
        self.userStore = self.storageFactory(
            storage.StorageConfig(userStorePath))
        self.dismissalsStore = self.storageFactory(
            storage.StorageConfig(dismissalsPath))

    def storeGlobal(self, context, data, modified = None):
        keyPrefix = context
        return self._storeNotice(self.globalStore, keyPrefix, data, modified)

    def storeUser(self, context, data, modified = None):
        keyPrefix = context
        notice = self._storeNotice(self.userStore, keyPrefix, data, modified)
        return notice

    def retrieveGlobal(self, keyId, context = None):
        return self._getNoticeIfActive(keyId, context, isGlobal = True)

    def retrieveUser(self, keyId, context = None):
        return self._getNoticeIfActive(keyId, context, isGlobal = False)

    def enumerateAllStore(self):
        return mergeIterables([self.enumerateAllUserStore(),
            self.enumerateAllGlobalStore()], key = self._modifiedSortKey)

    def enumerateAllUserStore(self):
        return mergeIterables([ self.enumerateStoreUser(os.path.basename(ctx))
                                for ctx in self.userStore.enumerate() ],
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
        keyPrefix = context
        if isGlobal:
            store = self.globalStore
        else:
            store = self.userStore

        notices = self._enumerateNotices(store, keyPrefix = keyPrefix)
        dismissals = self._enumerateDismissals(isGlobal = isGlobal)
        dismissedNoticesMap = dict((x.noticeId, x) for x in dismissals)

        ret = []
        for notice in notices:
            if notice.id in dismissedNoticesMap:
                del dismissedNoticesMap[notice.id]
                continue
            ret.append(notice)
        # Remove any unused dismissals
        for dismissal in dismissedNoticesMap.values():
            self.dismissalsStore.delete(dismissal.id)
        ret.sort(key = self._modifiedSortKey)
        return ret

    def storeGlobalDismissal(self, key, context = None):
        return self._storeDismissal(key, context = context, isGlobal = True)

    def storeUserDismissal(self, key, context = None):
        return self._storeDismissal(key, context = context, isGlobal = False)

    @classmethod
    def _getNoticeKey(self, key, context = None):
        if isinstance(key, Notice):
            return key.id
        if context is None:
            return key
        return (context, key)

    def _storeDismissal(self, key, context = None, isGlobal = False):
        if isGlobal:
            keyPrefix = 'global'
            store = self.globalStore
        else:
            keyPrefix = 'user'
            store = self.userStore

        keyId = self._getNoticeKey(key, context)

        # Grab the notice
        notice = self._getNotice(store, keyId)
        if notice is None:
            # No key, nothing to dismiss
            return None

        self._addDismissal(isGlobal = isGlobal, keyId = keyId)
        return notice

    @classmethod
    def _modifiedSortKey(cls, x):
        return x.modified

    @classmethod
    def _timestampSortKey(cls, x):
        return x.timestamp

    @classmethod
    def _storeNotice(cls, store, keyPrefix, data, modified):
        if isinstance(data, Notice):
            noticeId = data.id
            if modified is None:
                modified = data.modified
            data = data.content
        else:
            if modified is None:
                modified = time.time()
            noticeId = store.newCollection(keyPrefix = keyPrefix)
        store.set((noticeId, "content"), data)
        store.set((noticeId, "modified"), "%.3f" % modified)
        return Notice(noticeId, data, modified)

    @classmethod
    def _getNotice(cls, store, keyId):
        if not store.exists(keyId):
            return None
        return Notice(keyId, store.get((keyId, "content")),
                             store.get((keyId, "modified")))

    def _getNoticeIfActive(self, keyId, context = None, isGlobal = False):
        if self._isDismissed(keyId, context, isGlobal = isGlobal):
            return None
        keyId = self._getNoticeKey(keyId, context)
        store = (isGlobal and self.globalStore) or self.userStore
        return self._getNotice(store, keyId)

    @classmethod
    def _enumerateNotices(cls, store, keyPrefix):
        for keyId in store.enumerate(keyPrefix = keyPrefix):
            notice = cls._getNotice(store, keyId)
            if notice is not None:
                yield notice

    def _addDismissal(self, isGlobal = False, keyId = None):
        dismissalType = (isGlobal and "global") or "user"
        dismissalId = (dismissalType, keyId)
        self.dismissalsStore.set(dismissalId, "")

    def _enumerateDismissals(self, isGlobal = False):
        dismissalType = (isGlobal and "global") or "user"
        for keyId in self.dismissalsStore.enumerateAll(keyPrefix = dismissalType):
            dismissal = self._createDismissal(keyId, '')
            if dismissal is None:
                # Invalid
                store.delete(keyId)
                continue
            yield dismissal

    def _isDismissed(self, keyId, context = None, isGlobal = False):
        dismissalType = (isGlobal and "global") or "user"
        keyPrefix = [dismissalType]
        if context is not None:
            keyPrefix.append(context)
        keyPrefix.append(keyId)
        return self.dismissalsStore.exists(tuple(keyPrefix))

    @classmethod
    def _createDismissal(cls, keyId, content):
        # Strip the first two parts of the key prefix (dismissals and
        # dismissalType)
        dismissalType, noticeId = keyId.split('/', 1)
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

def createStore(storagePath, userId):
    globalStorePath = os.path.join(storagePath, "global")
    userStorePath = os.path.join(storagePath, "users", str(userId), "notices")
    dismissalsPath = os.path.join(storagePath, "users", str(userId), "dismissals")
    return Storage(globalStorePath, userStorePath, dismissalsPath)
