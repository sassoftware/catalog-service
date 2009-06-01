
import os
import time

class InstanceStore(object):
    __slots__ = [ '_store', '_prefix' ]
    DEFAULT_EXPIRATION = 1800

    def __init__(self, store, prefix):
        self._store = store
        self._prefix = prefix

    def newKey(self, realId = None, imageId = None, expiration = None,
            state = None):
        if state is None:
            state = 'Creating'
        nkey = self._store.newKey(keyPrefix = self._prefix, keyLength = 6)
        instId = os.path.basename(nkey)
        if imageId is not None:
            self.setImageId(instId, imageId)
        if realId is not None:
            self.setId(instId, realId)
        self.setState(instId, state)
        self.setExpiration(instId, expiration)
        return instId

    def enumerate(self):
        return self._store.enumerate(self._prefix)

    def delete(self, key):
        instanceId = self._getInstanceId(key)
        self._store.delete(os.path.join(self._prefix, instanceId))

    def getImageId(self, instanceId):
        return self._get(instanceId, 'imageId')

    def setImageId(self, instanceId, imageId):
        return self._set(instanceId, 'imageId', imageId)

    def getInstanceName(self, instanceId):
        return self._set(instanceId, "instanceName", name)

    def setInstanceName(self, instanceId, name):
        return self._get(instanceId, "instanceName")

    def getId(self, instanceId):
        return self._get(instanceId, 'id')

    def setId(self, instanceId, realId):
        return self._set(instanceId, 'id', realId)

    def setUpdateStatusState(self, instanceId, state):
        return self._set(instanceId, 'updateStatusState', state)

    def setUpdateStatusTime(self, instanceId, time):
        return self._set(instanceId, 'updateStatusTime', time)

    def getUpdateStatusState(self, instanceId, default = None):
        return self._get(instanceId, 'updateStatusState', default = default)

    def getUpdateStatusTime(self, instanceId, default = None):
        return self._get(instanceId, 'updateStatusTime', default = default)

    def getState(self, instanceId, default = None):
        return self._get(instanceId, 'state', default = default)

    def setState(self, instanceId, state):
        ret = self._set(instanceId, 'state', state)
        if state is not None:
            # Also set the expiration
            self.setExpiration(instanceId)
        return ret

    def getPid(self, instanceId):
        ret = self._get(instanceId, 'pid')
        if ret is None:
            return ret
        return int(ret)

    def setPid(self, instanceId, pid = None):
        if pid is None:
            pid = os.getpid()
        return self._set(instanceId, 'pid', pid)

    def deletePid(self, instanceId):
        return self._set(instanceId, 'pid',  None)

    def getExpiration(self, instanceId):
        exp = self._get(instanceId, 'expiration')
        if exp is None:
            return None
        return int(float(exp))

    def setExpiration(self, instanceId, expiration = None):
        if expiration is None:
            expiration = self.DEFAULT_EXPIRATION
        return self._set(instanceId, 'expiration',
            int(time.time() + expiration))

    def _get(self, instanceId, key, default = None):
        instanceId = self._getInstanceId(instanceId)
        fkey = os.path.join(self._prefix, instanceId, key)
        return self._store.get(fkey, default = default)

    def _set(self, instanceId, key, value):
        instanceId = self._getInstanceId(instanceId)
        fkey = os.path.join(self._prefix, instanceId, key)
        if value is not None:
            return self._store.set(fkey, value)
        return self._store.delete(fkey)

    def _getInstanceId(self, key):
        return os.path.basename(key)
