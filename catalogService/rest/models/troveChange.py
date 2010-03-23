#
# Copyright (c) 2010 rPath, Inc.  All Rights Reserved.
#

import generateds_trove_diff
from generatedsBase import Base

class TroveChange(generateds_trove_diff.troveChangeType, Base):
    defaultNamespace = "http://www.rpath.com/permanent/conary/trove-diff-1.0.xsd"
    xmlSchemaLocation = defaultNamespace
    RootNode = 'troveChange'

if __name__ == '__main__':
    tc = TroveChange()
    tc.parseStream("<troveChange/>")
    tc.set_name("conary")
    vc = generateds_trove_diff.simpleChangeType.factory()
    vc.set_from("1-1-1")
    vc.set_to("1-2-3")
    tc.set_versionChange(vc)
    import sys
    tc.serialize(sys.stdout)
