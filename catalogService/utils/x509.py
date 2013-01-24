#
# Copyright (c) SAS Institute Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


"Simple module for generating x509 certificates"

import os
from rmake3.lib import gencert

class X509(object):

    class Options(object):
        __slots__ = ['C', 'ST', 'L', 'O', 'OU', 'CN', 'site_user',
                     'key_length', 'expiry', 'output', 'output_key']
        _defaults = dict(key_length = 2048, expiry = 10 * 365)
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

        o = cls.Options(CN = commonName)
        subject, extensions = gencert.name_from_options(o)
        rsa, x509 = gencert.new_cert(o.key_length,
            subject, o.expiry, isCA=False, extensions=extensions,
            timestamp_offset=-86400)

        certHash = cls.computeHashFromX509(x509)

        certFile = os.path.join(certDir, certHash + '.0')
        keyFile = os.path.join(certDir, certHash + '.0.key')

        o.output = certFile
        o.output_key = keyFile
        gencert.writeCert(o, rsa, x509)
        return certFile, keyFile

    @classmethod
    def load(cls, certFile):
        x509 = gencert.X509.load_cert(certFile)
        return x509

    @classmethod
    def computeHash(cls, certFile):
        x509 = cls.load(certFile)
        return cls.computeHashFromX509(x509)

    @classmethod
    def computeHashFromX509(cls, x509):
        certHash = "%08x" % x509.get_issuer().as_hash()
        return certHash
