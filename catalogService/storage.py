#!/usr/bin/python2.4
#
# Copyright (c) 2008 rPath, Inc.
#
# This program is distributed under the terms of the Common Public License,
# version 1.0. A copy of this license should have been distributed with this
# source file in a file called LICENSE. If it is not present, the license
# is always available at http://www.rpath.com/permanent/licenses/CPL-1.0.
#
# This program is distributed in the hope that it will be useful, but
# without any warranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the Common Public License for
# full details.
#

import os
import sys

from conary.lib import util

from catalogService import config

#{ Exception classes
class StorageError(Exception):
    """Base class for all exceptions in the C{storage} module"""

class InvalidKeyError(StorageError):
    """An invalid key was specified"""

class KeyNotFoundError(StorageError):
    """The specified key was not found"""
#}

class BaseStorage(object):
    """
    Persistance class for the Package Creator
    cvar separator: separator between the class prefix and the key
    cvar keyLength: length of a key (not counting the optional prefix)
    """
    separator = ','
    keyLength = 16

    def __getitem__(self, key):
        """Get the value for the specified key.
        @param key: the key
        @type key: C{str}
        @rtype: C{str}
        @return: The value for the key, if set
        @raises InvalidKeyError: if the key was invalid
        @raises KeyNotFoundError: if the key is not set
        """
        key = self._sanitizeKey(key)
        if not self.exists(key):
            raise KeyNotFoundError(key)
        return self._real_get(key)

    def __setitem__(self, key, val):
        """Set the value for the specified key.
        @param key: the key
        @type key: C{str}
        @param val: value to store
        @type val: C{str}
        @raises InvalidKeyError: if the key was invalid
        """
        key = self._sanitizeKey(key)
        return self._real_set(key, val)

    def set(self, key, val):
        """Set the value for the specified key.
        @param key: the key
        @type key: C{str}
        @param val: value to store
        @type val: C{str}
        @raises InvalidKeyError: if the key was invalid
        """
        return self.__setitem__(key, val)

    def get(self, key, default = None):
        """Get the value for the specified key.
        @param key: the key
        @type key: C{str}
        @param default: a default value to be returned if the key is not set
        @type default: C{str}
        @rtype: C{str}
        @return: The value for the key, if set, or the value of C{default}
        @raises InvalidKeyError: if the key was invalid
        """
        if not self.exists(key):
            return default
        return self.__getitem__(key)

    def enumerate(self, keyPrefix):
        """Enumerate keys"""
        keyPrefix = self._sanitizeKey(keyPrefix)
        return self._real_enumerate(keyPrefix)

    def exists(self, key):
        """Check for a key's existance
        @param key: the key
        @type key: C{str}
        @rtype: C{bool}
        @return: True if the key exists, False otherwise
        """
        key = self._sanitizeKey(key)
        return self._real_exists(key)

    def isCollection(self, key):
        key = self._sanitizeKey(key)
        return self._real_is_collection(key)

    def newKey(self, keyPrefix = None, keyLength = None):
        if keyLength is None:
            keyLength = self.keyLength
        for i in range(5):
            newKey = self._generateString(keyLength)
            if keyPrefix:
                key = self.separator.join([keyPrefix, newKey])
            else:
                key = newKey
            if not self.exists(key):
                return key

        raise StorageError("Failed to generate a new key")

    def store(self, val, keyPrefix = None):
        """Generate a new key, and store the value.
        @param val: value to store
        @type val: C{str}
        @param keyPrefix: a prefix to be prepended to the key
        @type keyPrefix: C{str}
        @return: The newly generated key
        @rtype: C{str}
        @raises StorageError: if the module was unable to generate a new key
        """
        key = self.newKey(keyPrefix = keyPrefix)
        self.set(key, val)
        return key

    def delete(self, key):
        """Delete a key
        @param key: the key
        @type key: C{str}
        @rtype: C{bool}
        @return: True if the key exists, False otherwise
        """
        key = self._sanitizeKey(key)
        if self.isCollection(key):
            return self._real_delete_collection(key)
        return self._real_delete(key)

    #{ Methods that could be overwritten in subclasses
    def _generateString(self, length):
        """Generate a string
        @param length: length of the string to be generated
        @type length: C{int}
        @rtype: C{int}
        @return: The new string
        """
        randByteCount = int(round(length / 2.0))
        bytes = file("/dev/urandom").read(randByteCount)
        bytes = ''.join('%02x' % ord(x) for x in bytes)
        return bytes[:length]
    #}

    #{ Methods that should be overwritten in subclasses
    def _sanitizeKey(self, key):
        """Sanitize the key by removing potentially dangerous characters.
        @param key: key
        @type key: C{str}
        @rtype: C{str}
        @return: The sanitized key
        @raises InvalidKeyError: if the key was invalid
        """

    def _real_get(self, key):
        raise NotImplementedError()

    def _real_set(self, key, val):
        raise NotImplementedError()

    def _real_exists(self, key):
        raise NotImplementedError()

    def _real_delete(self, key):
        raise NotImplementedError()

    def _real_delete_collection(self, key):
        raise NotImplementedError()

    def _real_enumerate(self, keyPrefix):
        raise NotImplementedError()

    def _real_is_collection(self, key):
        raise NotImplementedError()

    #}

class DiskStorage(BaseStorage):
    separator = os.sep

    def __init__(self, cfg):
        """Constructor
        @param cfg: Configuration object
        @type cfg: C{StorageConfig}
        """
        self.cfg = cfg

    def _sanitizeKey(self, key):
        nkey = os.path.normpath(key)
        if key != nkey:
            raise InvalidKeyError(key)
        if key[0] == self.separator:
            raise InvalidKeyError(key)
        return key

    def _real_get(self, key):
        fpath = self._getFileForKey(key)
        return file(fpath).read()

    def _real_set(self, key, val):
        fpath = self._getFileForKey(key, createDirs = True)
        file(fpath, "w").write(str(val))

    def _real_exists(self, key):
        fpath = self._getFileForKey(key)
        return os.path.exists(fpath)

    def _real_delete(self, key):
        fpath = self._getFileForKey(key)
        if os.path.exists(fpath):
            os.unlink(fpath)

    def _real_delete_collection(self, key):
        fpath = self._getFileForKey(key)
        util.rmtree(fpath, ignore_errors = True)

    def _real_enumerate(self, keyPrefix):
        # Get rid of trailing /
        keyPrefix = keyPrefix.rstrip(self.separator)
        collection = self.separator.join([self.cfg.storagePath, keyPrefix])
        if not os.path.isdir(collection):
            return []
        dirContents = sorted(os.listdir(collection))
        return [ self.separator.join([keyPrefix, x]) for x in dirContents ]

    def _real_is_collection(self, key):
        collection = self.separator.join([self.cfg.storagePath, key])
        return os.path.isdir(collection)

    def _getFileForKey(self, key, createDirs = False):
        ret = self.separator.join([self.cfg.storagePath, key])
        if createDirs:
            util.mkdirChain(os.path.dirname(ret))
        return ret

class StorageConfig(config.BaseConfig):
    """
    Storage configuration object.
    @ivar storagePath: Path used for persisting the values.
    @type storagePath: C{str}
    """
    def __init__(self, storagePath):
        config.BaseConfig.__init__(self)
        self.storagePath = storagePath

