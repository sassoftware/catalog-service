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


from lxml import etree

class OVF(object):
    class _OVFFlavor(object):
        xsiNs = 'http://www.w3.org/2001/XMLSchema-instance'
        rasdNs = 'http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData'
        vssdNs = 'http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData'
        ovfNs = None
        def __init__(self, doc):
            self.doc = doc
            self.xmlns = doc.nsmap.get(None, None)

        @classmethod
        def addNode(cls, item, name, value, ns=None):
            if ns is None:
                ns = cls.rasdNs
            OVF._text(item, name, value, ns=ns)

        def tostring(self):
            return etree.tostring(self.doc, encoding = "UTF-8")

        def getNetworkNames(self):
            sections = self.getNetworkSections() or []
            ret = []
            for section in sections:
                for network in OVF._getNodeByName(section, 'Network',
                        [self.ovfNs, None]):
                    name = OVF._getNodeAttribute(network, 'name', self.ovfNs)
                    if name:
                        ret.append(name)
            return ret

        def getNodeText(self, node, name):
            return OVF._getNodeText(node, name, ns=self.rasdNs)

        def getInstanceId(self, node):
            return OVF._getNodeText(node, self.instanceIdTag, self.rasdNs)

        def addNewHardwareItem(self, hardwareSection):
            item = hardwareSection.makeelement("{%s}Item" % self.ovfNs)
            # We need to add the item at the end of the section
            allItems = list(hardwareSection.iterfind(item.tag))
            if not allItems:
                hardwareSection.insert(0, item)
            else:
                allItems[-1].addnext(item)
            return item

        def addHardwareItems(self, hardwareSection, nextInstanceId):
            networkNames = self.getNetworkNames()
            # Add back ethernet0 as E1000
            item = self.addNewHardwareItem(hardwareSection)
            if networkNames:
                networkName = networkNames[0]
            else:
                networkName = None
            self._addNetworkFields(item, nextInstanceId, networkName)

        def hasSystemNode(self, hardwareSection):
            tags = set([OVF._xmltag('System', self.ovfNs)])
            if self.xmlns is None:
                # Need to look for an item in the default namespace too
                tags.add(OVF._xmltag('System', None))
            for tag in tags:
                if hardwareSection.find(tag) is not None:
                    return True
            return False

        def addSystemNode(self, hardwareSection):
            name = self.getNameFromOvfId()
            system = hardwareSection.makeelement(
                OVF._xmltag("System", self.ovfNs))
            hardwareSection.insert(1, system)
            self.addNode(system, "InstanceId", "0", ns=self.vssdNs)
            self.addNode(system, "VirtualSystemIdentifier", name,
                ns=self.vssdNs)
            self.addNode(system, "VirtualSystemType", 'vmx-04', ns=self.vssdNs)

    class _OVF_09(_OVFFlavor):
        ovfNs = 'http://www.vmware.com/schema/ovf/1/envelope'
        instanceIdTag = "InstanceId"
        elementNameTag = "Caption"

        def getNameFromOvfId(self):
            contentNode = self.doc.find(OVF._xmltag('Content', self.xmlns))
            return OVF._getNodeAttribute(contentNode, 'id', self.ovfNs)

        def getNetworkSections(self):
            return OVF._getSectionsByType(self.doc, 'NetworkSection_Type',
                self.ovfNs, self.xsiNs)

        def getHardwareSections(self):
            contentNode = self.doc.find(OVF._xmltag('Content', self.xmlns))
            return OVF._getSectionsByType(contentNode,
                'VirtualHardwareSection_Type', self.ovfNs, self.xsiNs)

        def addNewHardwareItem(self, hardwareSection):
            item = hardwareSection.makeelement("{%s}Item" % self.ovfNs)
            hardwareSection.append(item)
            return item

        def _addNetworkFields(self, item, nextInstanceId, networkName):
            self.addNode(item, self.elementNameTag, "ethernet0")
            self.addNode(item, "Description", "E1000 ethernet adapter")
            self.addNode(item, self.instanceIdTag, str(nextInstanceId))
            self.addNode(item, "ResourceType", "10")
            self.addNode(item, "ResourceSubType", "E1000")
            self.addNode(item, "AutomaticAllocation", "true")
            if networkName:
                self.addNode(item, "Connection", networkName)

    class _OVF_10(_OVFFlavor):
        ovfNs = 'http://schemas.dmtf.org/ovf/envelope/1'
        instanceIdTag = "InstanceID"
        elementNameTag = "ElementName"

        def getNameFromOvfId(self):
            vsys = self.doc.find(OVF._xmltag('VirtualSystem', self.ovfNs))
            return OVF._getNodeAttribute(vsys, 'id', self.ovfNs)

        def getNetworkSections(self):
            return self.doc.findall(OVF._xmltag('NetworkSection', self.ovfNs))

        def getHardwareSections(self):
            vsys = self.doc.find(OVF._xmltag('VirtualSystem', self.ovfNs))
            return vsys.findall(OVF._xmltag('VirtualHardwareSection', self.ovfNs))

        def _addNetworkFields(self, item, nextInstanceId, networkName):
            self.addNode(item, "AddressOnParent", "7")
            self.addNode(item, "AutomaticAllocation", "true")
            if networkName:
                self.addNode(item, "Connection", networkName)
            self.addNode(item, "Description", "E1000 ethernet adapter")
            self.addNode(item, self.elementNameTag, "ethernet0")
            self.addNode(item, self.instanceIdTag, str(nextInstanceId))
            self.addNode(item, "ResourceSubType", "E1000")
            self.addNode(item, "ResourceType", "10")

    OvfVersions = [ _OVF_10, _OVF_09 ]

    def __init__(self, string):
        self._ovfContents = string
        doc = etree.fromstring(string)
        for cls in self.OvfVersions:
            if self._getNsPrefix(doc, cls.ovfNs):
                # In case the default ns is None, set it to the proper one
                if None not in doc.nsmap:
                    doc.nsmap[None] = cls.ovfNs
                self.ovf = cls(doc)
                break
        else: # for
            raise RuntimeError("Unsupported OVF")

        self.maxInstanceId = 0

    @property
    def networkNames(self):
        return self.ovf.getNetworkNames()

    def sanitize(self):
        hardwareSection = self.ovf.getHardwareSections()
        if hardwareSection is None:
            return self._ovfContents

        hardwareSection = hardwareSection[0]
        if not self.ovf.hasSystemNode(hardwareSection):
            self.ovf.addSystemNode(hardwareSection)

        # Iterate through all items
        todelete = []
        # instanceId is supposed to be unique, so compute the max; we'll add
        # our new devices starting with this max
        maxInstanceId = 0
        itemTags = set([ self._xmltag('Item', self.ovf.ovfNs)])
        if self.ovf.xmlns is None:
            # Need to look for an item in the default namespace too
            itemTags.add(self._xmltag('Item', None))
        for i, node in enumerate(hardwareSection.iterchildren()):
            if node.tag not in itemTags:
                continue

            resourceTypeText = self.ovf.getNodeText(node, "ResourceType")
            # We are creating cdroms and networks as part of the deployment,
            # so remove these sections
            if resourceTypeText in [ '10', '15' ]: # [ 'cdrom', 'ethernet' ]
                todelete.append(i)
                continue
            instanceId = self.ovf.getInstanceId(node)
            try:
                instanceId = int(instanceId or 0)
            except ValueError:
                # In case the instance id is not a number
                instanceId = 0
            maxInstanceId = max(maxInstanceId, instanceId)

        # Remove items to be deleted, in reverse order
        while todelete:
            i = todelete.pop()
            del hardwareSection[i]

        self.ovf.addHardwareItems(hardwareSection, maxInstanceId + 1)
        return self.ovf.tostring()


    @classmethod
    def _getNsPrefix(cls, node, namespace):
        ret = [ prefix for (prefix, ns) in node.nsmap.iteritems()
            if ns == namespace ]
        ret.sort()
        ret.reverse()
        return ret

    @classmethod
    def _getNodeByName(cls, node, name, xmlnsList):
        if not isinstance(xmlnsList, (list, tuple)):
            xmlnsList = [ xmlnsList ]
        for xmlns in xmlnsList:
            ret = node.findall(cls._xmltag(name, xmlns))
            if ret:
                return ret
        return []

    @classmethod
    def _getSectionsByType(cls, node, xstype, xmlns, xsins):
        # XXX Technically, if they chose to use a different namespace prefix
        # than ovf:, this would stop working.
        xstype = "ovf:" + xstype
        typeAttrib = cls._xmltag("type", xsins)
        if xmlns is not None:
            # Look for the node in the default namespace too
            xmlns = (xmlns, None)
        sections = cls._getNodeByName(node, 'Section', xmlns)
        return [ x for x in sections if x.get(typeAttrib) == xstype ]

    @classmethod
    def _getNodeAttribute(cls, element, attribute, ns=None):
        if ns is not None:
            attribute = "{%s}%s" % (ns, attribute)
        return element.attrib.get(attribute)

    @classmethod
    def _getNodeText(cls, element, tag, ns=None):
        if ns is not None:
            tag = "{%s}%s" % (ns, tag)
        node = element.find(tag)
        if node is None:
            return None
        return node.text

    @classmethod
    def _text(cls, element, tag, text, ns=None):
        if ns is not None:
            tag = "{%s}%s" % (ns, tag)
        item = element.makeelement(tag)
        item.text = text
        element.append(item)
        return item

    @classmethod
    def _xmltag(cls, name, namespace):
        if namespace is None:
            return name
        return "{%s}%s" % (namespace, name)
