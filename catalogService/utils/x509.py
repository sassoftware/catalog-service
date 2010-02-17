#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#
"Simple module for generating x509 certificates"

import os
import tempfile
from rmake.lib import gencert

class X509(object):

    class Options(object):
        __slots__ = ['C', 'ST', 'L', 'O', 'OU', 'CN', 'site_user',
                     'key_length', 'expiry', 'output', 'output_key']
        _defaults = dict(key_length = 2048, expiry = 3 * 365)
        def __init__(self, **kwargs):
            params = self._defaults.copy()
            params.update(kwargs)
            # Initialize from slots
            for slot in self.__slots__:
                val = params.get(slot, None)
                setattr(self, slot, val)

    @classmethod
    def new(cls, commonName, certDir):
        """
        Generate X509 certificate with the specified commonName
        Returns absolute paths to cert file and key file
        """

        fd, tempFile = tempfile.mkstemp(dir = certDir, prefix = 'new-cert-')
        os.close(fd)
        certFile = tempFile
        keyFile = certFile + '.key'

        o = cls.Options(CN = commonName, output = certFile,
            output_key = keyFile)
        gencert.new_ca(o, isCA = False)

        hash = cls.computeHash(certFile)
        newCertFile = os.path.join(certDir, hash + '.0')
        newKeyFile = os.path.join(certDir, hash + '.0.key')
        os.rename(certFile, newCertFile)
        os.rename(keyFile, newKeyFile)
        return newCertFile, newKeyFile

    @classmethod
    def load(cls, certFile):
        x509 = gencert.X509.load_cert(certFile)
        return x509

    @classmethod
    def computeHash(cls, certFile):
        x509 = cls.load(certFile)
        certHash = "%x" % x509.get_issuer().as_hash()
        return certHash
