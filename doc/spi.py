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


class Instance(object):
    # think about using newinstance
    # maybe create a newInstance object at the time of rendering to xml.
    # is newInstance going to be generic enough?
    # we need to be able to accept stuff based on the package
    # creator format
    pass

class CloudTypeImplementation(object):
    cloudType = None  # name of this cloud type - should be unique.

    def listClouds(self):
        "return cloudIds for this cloud type"

    def cloudParameters(self):
        "object that knows how to turn intself in xml for cloud parameters"

    def newCloud(self, cloudId, parameters):
        "return cloudId for new cloud"

    def terminateCloud(self, cloudId):
        "return None or raise error if problem"

    def updateCloud(self, cloudId, parameters):
        "return None or raise error if problem"

    def listInstanceIds(self, cloudId):
        "return list of available instanceIds"

    def listImageIds(self, cloudId):
        "return list of available imageIds"

    def launchInstanceParameters(self):
        "return parameters that know how to turn themselves into xml"

    def launchInstances(self, cloudId, imageIds, parameters):
        "return instanceIds launched instances"

    def launchInstance(self, cloudId, imageId, parameters):
        "return instanceIds launched instance"

    def terminateInstances(self, cloudId, instanceIds):
        "return instanceIds of terminated instances"

    def terminateInstance(self, cloudId, instanceId):
        "return instanceIds of terminated instances"

    def getInstances(self, cloudId, instanceIds):
        "return instance objects which know how to turn themselves into xml"

    def getImages(self, cloudId, imageIds):
        "return image objects which know how to turn themselves into xml"
