#
# Copyright (c) 2010 rPath, Inc.  All Rights Reserved.
#

import urllib
import generateds_trove_diff
from generateds_base import Base

simpleChangeType = generateds_trove_diff.simpleChangeType
troveSpecType = generateds_trove_diff.troveSpecType
troveType = generateds_trove_diff.troveType
versionType = generateds_trove_diff.versionType


class TroveChange(generateds_trove_diff.troveChangeType, Base):
    defaultNamespace = "http://www.rpath.com/permanent/conary/trove-diff-1.0.xsd"
    xmlSchemaLocation = defaultNamespace
    RootNode = 'troveChange'

    def setChanges(self, name, (oldVersion, oldFlavor),
            (newVersion, newFlavor)):
        self.set_name(name)
        self.set_versionChange(self.newSimpleChange(oldVersion, newVersion))
        self.set_flavorChange(self.newSimpleChange(oldFlavor, newFlavor))

    def newTroveAddition(self, name, version, flavor):
        tspec = self.newTroveSpec(name, version, flavor)
        self.add_troveAddition(tspec)

    def newTroveRemoval(self, name, version, flavor):
        tspec = self.newTroveSpec(name, version, flavor)
        self.add_troveRemoval(tspec)

    def newTroveChange(self, name, (oldVersion, oldFlavor),
            (newVersion, newFlavor)):
        troveChange = TroveChange()
        troveChange.setChanges(name, (oldVersion, oldFlavor),
            (newVersion, newFlavor))
        self.add_troveChange(troveChange)

    @classmethod
    def newTroveSpec(cls, name, version, flavor):
        tspec = troveSpecType.factory()
        rev = version.trailingRevision()

        trv = troveType.factory()
        trv.set_name(name)
        trv.set_flavor(str(flavor))
        ver = versionType.factory()
        trv.set_version(ver)

        ver.set_full(str(version))
        ver.set_label(str(version.trailingLabel()))
        ver.set_revision(str(rev))
        ver.set_ordering(rev.timeStamp)
        tspec.set_trove(trv)

        trv.set_id(urllib.quote("%s=%s[%s]" % (name, version, flavor),
            safe = ""))
        return tspec

    @classmethod
    def newSimpleChange(cls, fromItem, toItem):
        if fromItem == toItem:
            return None
        change = simpleChangeType.factory()
        change.set_from(fromItem)
        change.set_to(toItem)
        return change

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
