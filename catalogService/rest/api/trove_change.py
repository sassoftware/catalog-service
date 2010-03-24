#
# Copyright (c) 2010 rPath, Inc.  All Rights Reserved.
#

import urllib

from conary.deps import deps
from conary import conaryclient
from conary import versions

from catalogService.rest.models import trove_change
from catalogService.rest.api.base import BaseCloudController
from catalogService.rest.middleware import response

class TroveChangesController(BaseCloudController):
    modelName = 'specTroveFrom'

    def create(self, request, cloudName, instanceId, troveSpec):
        tc = trove_change.TroveChange()
        data = request.read()
        tc.parseStream(data)
        troveSpec = urllib.unquote(troveSpec)
        conaryClient = self._getConaryClient()
        diff = TroveDiff(conaryClient, troveSpec, tc)
        troveChange = diff.computeDiff()
        return response.XmlSerializableObjectResponse(troveChange)

    def _getConaryClient(self):
        return self.db.productMgr.reposMgr.getUserClient()

# XXX This should probably be in some manager
class TroveDiff(object):
    def __init__(self, conaryClient, troveSpec, troveChangeRequest):
        self.conaryClient = conaryClient

        n, v, f = conaryclient.cmdline.parseTroveSpec(troveSpec)
        self.trvName = n
        self.trvNewVersion = versions.ThawVersion(v)
        self.trvNewFlavor = f

        fromVersion = self.trvNewVersion
        versionChange = troveChangeRequest.get_versionChange()
        if versionChange is not None:
            fromVersionStr = versionChange.get_from()
            if fromVersionStr:
                fromVersion = versions.ThawVersion(fromVersionStr)
        self.trvOldVersion = fromVersion

        fromFlavor = self.trvNewFlavor
        flavorChange = troveChangeRequest.get_flavorChange()
        if flavorChange is not None:
            fromFlavorStr = flavorChange.get_from()
            if fromFlavorStr:
                fromFlavor = deps.parseFlavor(fromFlavorStr)
        self.trvOldFlavor = fromFlavor

    def computeDiff(self):
        troveChange = trove_change.TroveChange()
        troveChange.set_name(self.trvName)
        if self.trvOldVersion != self.trvNewVersion:
            versionChange = trove_change.simpleChangeType.factory()
            versionChange.set_from(self.trvOldVersion.freeze())
            versionChange.set_to(self.trvNewVersion.freeze())
            troveChange.set_versionChange(versionChange)
        if self.trvOldFlavor != self.trvNewFlavor:
            flavorChange = trove_change.simpleChangeType.factory()
            flavorChange.set_from(str(self.trvOldFlavor))
            flavorChange.set_to(str(self.trvNewFlavor))
            troveChange.set_flavorChange(flavorChange)
        if troveChange.get_versionChange() is None and troveChange.get_flavorChange() is None:
            # No need to work harder, we're diffing against ourselves
            return troveChange

        oldTroveJob = (self.trvName, (None, None),
            (self.trvOldVersion, self.trvOldFlavor), True)
        newTroveJob = (self.trvName, (None, None),
            (self.trvNewVersion, self.trvNewFlavor), True)
        cs = self.conaryClient.createChangeSet([ oldTroveJob, newTroveJob],
            withFiles = True, withFileContents = False, recurse = False)
        oldTrvCs = cs.getNewTroveVersion(self.trvName, self.trvOldVersion,
            self.trvOldFlavor)
        newTrvCs = cs.getNewTroveVersion(self.trvName, self.trvNewVersion,
            self.trvNewFlavor)
        trvCs, fileDiff, troveDiff = newTrvCs.diff(oldTrvCs)
        for (trvName, oldVF, newVF, _) in troveDiff:
            if oldVF[0] is None:
                # Added trove
                tspec = self._newTroveSpec(trvName, newVF[0], newVF[1])
                troveChange.add_troveAddition(tspec)
                continue
            if newVF[0] is None:
                # Erased trove
                tspec =  self._newTroveSpec(trvName, oldVF[0], oldVF[1])
                troveChange.add_troveRemoval(tspec)
                continue
        return troveChange

    def _newTroveSpec(self, name, version, flavor):
        tspec = trove_change.troveSpecType.factory()
        tspec.set_name(name)
        tspec.set_version(version.freeze())
        tspec.set_flavor(str(flavor))
        return tspec
