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


import urllib

from conary.deps import deps
from conary import conaryclient
from conary import trove
from conary import versions

from catalogService.rest.models import trove_change
from catalogService.rest.api.base import BaseCloudController
from catalogService.rest.middleware import response

class TroveChangesController(BaseCloudController):
    modelName = 'troveSpecOther'

    def create(self, request, cloudName, instanceId, troveSpec):
        tc = trove_change.TroveChange()
        data = request.read()
        tc.parseStream(data)
        troveSpec = urllib.unquote(troveSpec)
        conaryClient = self._getConaryClient()
        diff = TroveDiff(conaryClient, troveSpec, tc)
        troveChange = diff.computeDiff()
        self._fixIds(request, troveChange)
        return response.XmlSerializableObjectResponse(troveChange)

    def get(self, request, cloudName, instanceId, troveSpec, troveSpecOther):
        troveSpec = urllib.unquote(troveSpec)
        troveSpecOther = urllib.unquote(troveSpecOther)
        conaryClient = self._getConaryClient()
        diff = TroveDiff(conaryClient, troveSpec,
            troveSpecOther = troveSpecOther)
        troveChange = diff.computeDiff()
        self._fixIds(request, troveChange)
        return response.XmlSerializableObjectResponse(troveChange)

    def _getConaryClient(self):
        return self.db.productMgr.reposMgr.getUserClient()

    def _fixIds(self, request, troveChange):
        troveUrl = "%s/catalog/troves/" % request.baseUrl
        trv = troveChange.get_from().get_trove()
        trv.set_id(troveUrl + trv.get_id())
        trv = troveChange.get_to().get_trove()
        trv.set_id(troveUrl + trv.get_id())
        for troveSpec in troveChange.get_troveAddition():
            trv = troveSpec.get_trove()
            trv.set_id(troveUrl + trv.get_id())
        for troveSpec in troveChange.get_troveRemoval():
            trv = troveSpec.get_trove()
            trv.set_id(troveUrl + trv.get_id())
        for subtrv in troveChange.get_troveChange():
            self._fixIds(request, subtrv)

# XXX This should probably be in some manager
class TroveDiff(object):
    def __init__(self, conaryClient, troveSpec, troveChangeRequest = None,
            troveSpecOther = None):
        self.conaryClient = conaryClient

        n, v, f = conaryclient.cmdline.parseTroveSpec(troveSpec)
        self.trvName = n
        self.trvNewVersion = versions.ThawVersion(v)
        self.trvNewFlavor = f

        self._fromTroveChangeRequest(troveChangeRequest)
        self._fromOtherTroveSpec(troveSpecOther)

    def _fromOtherTroveSpec(self, troveSpec):
        if not troveSpec:
            return
        n, v, f = conaryclient.cmdline.parseTroveSpec(troveSpec)
        self.trvOldVersion = versions.ThawVersion(v)
        self.trvOldFlavor = f

    def _fromTroveChangeRequest(self, troveChangeRequest):
        if troveChangeRequest is None:
            return
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
                fromFlavor = deps.parseFlavor(str(fromFlavorStr))
        self.trvOldFlavor = fromFlavor

    def computeDiff(self):
        troveChange = trove_change.TroveChange()
        troveChange.setChanges(self.trvName,
            (self.trvOldVersion, self.trvOldFlavor),
            (self.trvNewVersion, self.trvNewFlavor))
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
        oldTrv = trove.Trove(oldTrvCs)
        newTrv = trove.Trove(newTrvCs)
        trvCs, fileDiff, troveDiff = newTrv.diff(oldTrv)
        for (trvName, oldVF, newVF, _) in troveDiff:
            if oldVF[0] is None:
                # Added trove
                troveChange.newTroveAddition(trvName, newVF[0], newVF[1])
                continue
            if newVF[0] is None:
                # Erased trove
                troveChange.newTroveRemoval(trvName, oldVF[0], oldVF[1])
                continue
            troveChange.newTroveChange(trvName, oldVF, newVF)
        return troveChange
