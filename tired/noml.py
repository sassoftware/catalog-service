#
# Copyright (c) 2008 rPath, Inc.
#

import string

class RepresentationError(Exception):
    "Base error class"

class FreezeError(RepresentationError):
    "Raised when trying to freeze unsupported data"

class ThawError(RepresentationError):
    "Raised when invalid frozen data was presented"


class NOML(object):
    """
    Simple data representation
    """

    def freeze(self, obj, stream):
        """
        Freeze an object into a data stream

        @param obj: object to be serialized
        @type obj: C{list} or C{dict}
        @param stream: file-like object
        @param stream C{file}
        @raises FreezeError: when unsupported data is passed
        """
        if not isinstance(obj, (list, dict)):
            raise FreezeError("Unsupported data type for %s" % obj)
        if isinstance(obj, dict):
            self._freezeDict(obj, stream)
        else:
            for o in obj:
                self._freezeDict(obj, stream)
                stream.write("\n")

    def thaw(self, stream):
        """
        Read object representation(s) from stream

        @param stream: file-like object
        @param stream C{file}
        @return: a list of dictionary objects
        @rtype: C{list}
        """
        ret = []
        key = None
        values = []
        obj = {}
        while 1:
            line = stream.readline()
            if not line or not line.rstrip('\n'):
                # Empty line or EOF, it's marking that this object should be pushed
                if key is not None:
                    obj[key] = '\n'.join(values)
                    key = None
                    values = []
                if not line:
                    # EOF case. Try to handle the single object case
                    if not ret:
                        # Single value
                        return obj
                ret.append(obj)
                obj = {}
                if not line:
                    # EOF. We're done
                    return ret
                continue

            # Strip trailing newline
            line = line.rstrip('\n')
            if line[0] == ' ':
                if key is None:
                    raise ThawError("Line with no key")
                values.append(line[1:])
                continue
            if key is not None:
                # Push the key
                obj[key] = '\n'.join(values)
                values = []
            arr = line.split(': ', 1)
            if len(arr) == 1:
                raise ThawError("Malformed line")
            key = arr[0]
            values.append(arr[1])


    def _freezeDict(self, obj, stream):
        """
        Freeze a dictionary object into a data stream

        @param obj: object to be serialized
        @type obj: C{dict}
        @param stream: file-like object
        @param stream C{file}

        @raises FreezeError: when unsupported data is passed
        """
        if not isinstance(obj, dict):
            raise FreezeError("Unsupported data type for %s" % obj)
        for k, v in obj.items():
            self._validateKey(k)
            stream.write("%s: " % (k, ))
            self._writeValue(v, stream)

    _unsupportedKeyChars = ":\n"
    _keyMaps = string.maketrans("", "")

    def _validateKey(self, key):
        okey = string.translate(key, self._keyMaps, self._unsupportedKeyChars)
        if okey != key:
            raise FreezeError("Unsupported key characters in %s" % key)

    def _writeValue(self, value, stream):
        """
        Write value to stream. Handles multi-line cases too.
        """
        if not isinstance(value, (str, unicode)):
            value = str(value)
        lines = value.split('\n')
        stream.write(lines[0])
        stream.write('\n')
        for line in lines[1:]:
            stream.write(' ')
            stream.write(line)
            stream.write('\n')
