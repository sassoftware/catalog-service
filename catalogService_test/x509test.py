#!/usr/bin/python
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


import testsuite
# Bootstrap the testsuite
testsuite.setup()

import os
import testbase

from catalogService.utils import x509

class X509Test(testbase.TestCase):

    def setUpJobs(self):
        pass

    def testComputeHash(self):
        # RBL-6322
        fname = os.path.join(self.workDir, "file.pem")
        file(fname, "w").write("""\
-----BEGIN CERTIFICATE-----
MIIDFjCCAf6gAwIBAgICbSMwDQYJKoZIhvcNAQEFBQAwRTFDMEEGA1UEAxM6Q2xp
ZW50IGNlcnRpZmljYXRlIGZvciBxYS1yYmE0LmVuZy5ycGF0aC5jb20sIGlkOiBk
ODRiYzQxYTAeFw0xMDA1MjUxODE4MzlaFw0xMzA1MjQxODE4MzlaMEUxQzBBBgNV
BAMTOkNsaWVudCBjZXJ0aWZpY2F0ZSBmb3IgcWEtcmJhNC5lbmcucnBhdGguY29t
LCBpZDogZDg0YmM0MWEwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDS
JAY6VTcRu9NTc51/RpC/clMLO1reyUxv2HkxRpll+TD5DmtYr8Owwws/WMu9c13x
pA+1TbVF8cDNlOXlxJKs7IVY5xRsswMTaEGL3vkEjWHTv/qmguinz6GIrnA2YbSy
A4vRhNZJD+pKIjA4e56atuwbhJWnuPLvhFlHdu6RhlJyOyANswXO4k9b+JpwbgJL
fi/DqHo7+GOeaFTh1XP0XWGsfyD7QfG7nRfT9uHljxbdCnUMGVSdve6tze+fv9vC
t6TD71AGNGZxR2+NCwjvllSi6L6FMmysZUjvttjmhIx2IkjV5soId9l7IMZVbD/V
2lv+0Sw0uR+VJRCw6o2xAgMBAAGjEDAOMAwGA1UdEwEB/wQCMAAwDQYJKoZIhvcN
AQEFBQADggEBAJRJW1+YkC2VzrKXAryKzrh1nt/1CBg6EceZNoifH49gATDQLIen
oyQGOSrBMlwuW47B0lbmf6lk6X8wMRnmgbUQ+jYBm1VNtDnej0j5Fm490mdeLrKI
C7lvY8yVjYJvGAlc85+x65bVVr8WJXkghB77xKUNMxSPrKQiSHUqwX1BJr/LuGIV
zbKXOfE2veakE7r5AXNgI17/EPxnNDZwsXDXKr+xa/j0IJomvZs8oqqOiEHn0R9R
yu+MQKUT8xlUa4HrGah9I0JI9XqmtOaZmHGIfh3DyyuRp4Cdwdd+paZRNbKI3Et2
OHmp+SUZVmL3DMFYJT4zyIJCTLq1hYVQZFU=
-----END CERTIFICATE-----
""")
        self.failUnlessEqual(x509.X509.computeHash(fname), '04ffb38d')

if __name__ == "__main__":
    testsuite.main()
