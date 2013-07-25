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


import StringIO
import itertools

class MultiResponse(object):
    __slots__ = [ '_idx', '_responses' ]
    def __init__(self, rlist):
        self._responses = rlist
        self.reset()

    def getData(self):
        data = self._responses[self._idx]
        self._idx += 1
        if isinstance(data, tuple):
            status, data = data
        else:
            status = 200
        return MockedResponse(data, status)

    def reset(self):
        self._idx = 0

class MockedResponse(object):
    "A response that returns canned data"
    def __init__(self, data, status=200, reason="No reason"):
        self.data = data
        self.status = status
        self.reason = reason
        self._io = StringIO.StringIO(data)
        self.headers = self.msg = {}
    def read(self, amt=None):
        return self._io.read(amt)
    def getheader(self, name, default=None):
        return self.headers.get(name, default)
    def close(self):
        pass

class HTTPResponse(object):
    def __init__(self, data, extraHeaders = None):
        self.headers = {
            'Date' : 'Fri, 12 Feb 2010 17:28:50 GMT',
            'Cache-Control' : 'no-cache',
            'Content-Type' : 'text/xml; charset=utf-8',
        }
        self.headers.update(dict(extraHeaders or []))
        self.data = data
        self.responseLine = "HTTP/1.1 200 OK"
        self.reset()

    def __str__(self):
        return self.data

    def getData(self):
        separator = '\r\n'
        if isinstance(self.data, list):
            data = str(self.data[self.idx])
            self.idx += 1
        else:
            data = self.data

        self.headers['Content-Length'] = str(len(data))
        return separator.join(itertools.chain([self.responseLine],
            (': '.join([k, v]) for k, v in self.headers.items()),
            ['', data]))

    def reset(self):
        self.idx = 0

def xmlEscape(data):
    from lxml import etree
    element = etree.Element("a")
    element.text = data
    # Strip leading <a> and trailing </a>
    ret = etree.tostring(element, xml_declaration=None, encoding="UTF-8")[3:-4]
    return ret

xml_getAllRegions1 = """\
<?xml version="1.0"?>
<DescribeRegionsResponse xmlns="http://ec2.amazonaws.com/doc/2008-12-01/">
    <requestId>c3868ddd-f00b-411d-9a84-62857929cf7f</requestId>
    <regionInfo>
        <item>
            <regionName>eu-west-1</regionName>
            <regionEndpoint>eu-west-1.ec2.amazonaws.com</regionEndpoint>
        </item>
        <item>
            <regionName>us-east-1</regionName>
            <regionEndpoint>us-east-1.ec2.amazonaws.com</regionEndpoint>
        </item>
    </regionInfo>
</DescribeRegionsResponse>"""

xml_getAllZones1 = """\
<?xml version="1.0"?>
<DescribeAvailabilityZonesResponse xmlns="http://ec2.amazonaws.com/doc/2009-04-04/">
    <requestId>2ea227d0-03fd-4116-9102-1f6cecf58bfb</requestId>
    <availabilityZoneInfo>
        <item>
            <zoneName>us-east-1a</zoneName>
            <zoneState>available</zoneState>
            <regionName>us-east-1</regionName>
        </item>
        <item>
            <zoneName>us-east-1b</zoneName>
            <zoneState>available</zoneState>
            <regionName>us-east-1</regionName>
        </item>
        <item>
            <zoneName>us-east-1c</zoneName>
            <zoneState>available</zoneState>
            <regionName>us-east-1</regionName>
        </item>
        <item>
            <zoneName>us-east-1d</zoneName>
            <zoneState>available</zoneState>
            <regionName>us-east-1</regionName>
        </item>
    </availabilityZoneInfo>
</DescribeAvailabilityZonesResponse>
"""

xml_getAllImages1 = """\
<?xml version="1.0"?>
<DescribeImagesResponse xmlns="http://ec2.amazonaws.com/doc/2008-02-01/">
    <imagesSet>
        <item>
            <imageId>aki-25de3b4c</imageId>
            <imageLocation>redhat-cloud/RHEL-5-Server/5.1/i386/kernels/kernel-2.6.18-53.1.4.el5xen.manifest.xml</imageLocation>
            <imageState>available</imageState>
            <imageOwnerId>432018295444</imageOwnerId>
            <isPublic>true</isPublic>
            <productCodes>
                <item>
                    <productCode>54DBF944</productCode>
                </item>
            </productCodes>
            <architecture>i386</architecture>
            <imageType>kernel</imageType>
        </item>
        <item>
            <imageId>ami-0435d06d</imageId>
            <imageLocation>rbuilder-online/reviewboard-1.0-x86_13964.img.manifest.xml</imageLocation>
            <imageState>available</imageState>
            <imageOwnerId>099034111737</imageOwnerId>
            <isPublic>true</isPublic>
            <productCodes>
                <item>
                    <productCode>8ED157F9</productCode>
                </item>
            </productCodes>
            <architecture>i386</architecture>
            <imageType>machine</imageType>
        </item>
    </imagesSet>
</DescribeImagesResponse>"""

xml_getAllImages2 = """\
<?xml version="1.0"?>
<DescribeImagesResponse xmlns="http://ec2.amazonaws.com/doc/2008-02-01/">
    <imagesSet>
        <item>
            <imageId>ami-afa642c6</imageId>
            <imageLocation>rbuilder-online/reviewboard-1.0-x86_13964.img.manifest.xml</imageLocation>
            <imageState>available</imageState>
            <imageOwnerId>099034111737</imageOwnerId>
            <isPublic>true</isPublic>
            <architecture>i386</architecture>
            <imageType>machine</imageType>
        </item>
    </imagesSet>
</DescribeImagesResponse>"""

xml_getAllImages3 = """\
<?xml version="1.0"?>
<DescribeImagesResponse xmlns="http://ec2.amazonaws.com/doc/2008-02-01/">
    <imagesSet>
        <item>
            <imageId>ami-3675905f</imageId>
            <imageLocation>rbuilder-online/reviewboard-1.0-x86_13964.img.manifest.xml</imageLocation>
            <imageState>available</imageState>
            <imageOwnerId>099034111737</imageOwnerId>
            <isPublic>true</isPublic>
            <architecture>i386</architecture>
            <imageType>machine</imageType>
        </item>
        <item>
            <imageId>ami-957590fc</imageId>
            <imageLocation>rbuilder-online/reviewboard-1.0-x86_13965.img.manifest.xml</imageLocation>
            <imageState>available</imageState>
            <imageOwnerId>099034111737</imageOwnerId>
            <isPublic>true</isPublic>
            <architecture>i386</architecture>
            <imageType>machine</imageType>
        </item>
    </imagesSet>
</DescribeImagesResponse>"""

xml_getAllImages4 = """\
<?xml version="1.0"?>
<DescribeImagesResponse xmlns="http://ec2.amazonaws.com/doc/2008-02-01/">
    <imagesSet>
        <item>
            <imageId>ami-decafbad</imageId>
            <imageLocation>rbuilder-online/reviewboard-1.0-x86_13964.img.manifest.xml</imageLocation>
            <imageState>available</imageState>
            <imageOwnerId>099034111737</imageOwnerId>
            <isPublic>true</isPublic>
            <architecture>i386</architecture>
            <imageType>machine</imageType>
        </item>
    </imagesSet>
</DescribeImagesResponse>"""


xml_getAllInstances1 = """\
<?xml version="1.0"?>
<DescribeInstancesResponse xmlns="http://ec2.amazonaws.com/doc/2008-02-01/">
    <reservationSet>
        <item>
            <reservationId>r-698a7500</reservationId>
            <ownerId>941766519978</ownerId>
            <groupSet>
                <item>
                    <groupId>BEA Demo</groupId>
                </item>
            </groupSet>
            <instancesSet>
                <item>
                    <instanceId>i-1639fe7f</instanceId>
                    <imageId>ami-3675905f</imageId>
                    <instanceState>
                        <code>16</code>
                        <name>running</name>
                    </instanceState>
                    <privateDnsName>domU-12-31-35-00-4D-84.z-2.compute-1.internal</privateDnsName>
                    <dnsName>ec2-75-101-210-216.compute-1.amazonaws.com</dnsName>
                    <reason/>
                    <keyName>tgerla</keyName>
                    <amiLaunchIndex>0</amiLaunchIndex>
                    <productCodes/>
                    <instanceType>m1.small</instanceType>
                    <launchTime>2008-04-07T18:22:49.000Z</launchTime>
                    <placement>
                        <availabilityZone>us-east-1c</availabilityZone>
                    </placement>
                    <productCodes>
                        <item>
                            <productCode>8ED157F9</productCode>
                            <productCode>8675309</productCode>
                        </item>
                    </productCodes>
                </item>
            </instancesSet>
        </item>
        <item>
            <reservationId>r-0af30c63</reservationId>
            <ownerId>941766519978</ownerId>
            <groupSet>
                <item>
                    <groupId>BEA Demo</groupId>
                </item>
            </groupSet>
            <instancesSet>
                <item>
                    <instanceId>i-805f98e9</instanceId>
                    <imageId>ami-957590fc</imageId>
                    <instanceState>
                        <code>16</code>
                        <name>running</name>
                    </instanceState>
                    <privateDnsName>domU-12-31-39-00-5C-E6.compute-1.internal</privateDnsName>
                    <dnsName>ec2-67-202-54-84.compute-1.amazonaws.com</dnsName>
                    <reason/>
                    <keyName>tgerla</keyName>
                    <amiLaunchIndex>1</amiLaunchIndex>
                    <productCodes/>
                    <instanceType>m1.small</instanceType>
                    <launchTime>2008-04-08T14:32:31.000Z</launchTime>
                    <placement>
                        <availabilityZone>imperial-russia</availabilityZone>
                    </placement>
                    <productCodes>
                        <item>
                            <productCode>8675309</productCode>
                            <productCode>8ED157F9</productCode>
                        </item>
                    </productCodes>
                </item>
            </instancesSet>
        </item>
    </reservationSet>
</DescribeInstancesResponse>"""

xml_ec2GetMyInstance = """\
<DescribeInstancesResponse xmlns="http://ec2.amazonaws.com/doc/2012-12-01/">
    <requestId>ff0cde17-1e21-4e9a-aff4-a515b8e06f4f</requestId>
    <reservationSet>
        <item>
            <reservationId>r-e44dbad6</reservationId>
            <ownerId>675450633870</ownerId>
            <groupSet>
                <item>
                    <groupId>sg-b4503f84</groupId>
                    <groupName>catalog-default</groupName>
                </item>
            </groupSet>
            <instancesSet>
                <item>
                    <instanceId>i-decafbad</instanceId>
                    <imageId>ami-7823a848</imageId>
                    <instanceState>
                        <code>16</code>
                        <name>running</name>
                    </instanceState>
                    <privateDnsName>ip-10-254-7-55.us-west-2.compute.internal</privateDnsName>
                    <dnsName>ec2-54-245-172-197.us-west-2.compute.amazonaws.com</dnsName>
                    <reason/>
                    <keyName>miiban</keyName>
                    <amiLaunchIndex>0</amiLaunchIndex>
                    <productCodes/>
                    <instanceType>m1.small</instanceType>
                    <launchTime>2013-01-21T17:16:38.000Z</launchTime>
                    <placement>
                        <availabilityZone>us-west-2a</availabilityZone>
                        <groupName/>
                        <tenancy>default</tenancy>
                    </placement>
                    <kernelId>aki-fa37baca</kernelId>
                    <monitoring>
                        <state>disabled</state>
                    </monitoring>
                    <privateIpAddress>10.254.7.55</privateIpAddress>
                    <ipAddress>54.245.172.197</ipAddress>
                    <groupSet>
                        <item>
                            <groupId>sg-b4503f84</groupId>
                            <groupName>catalog-default</groupName>
                        </item>
                    </groupSet>
                    <architecture>i386</architecture>
                    <rootDeviceType>instance-store</rootDeviceType>
                    <blockDeviceMapping/>
                    <virtualizationType>paravirtual</virtualizationType>
                    <clientToken/>
                    <tagSet>
                        <item>
                            <key>Name</key>
                            <value>ebs testing</value>
                        </item>
                    </tagSet>
                    <hypervisor>xen</hypervisor>
                    <networkInterfaceSet/>
                    <ebsOptimized>false</ebsOptimized>
                </item>
            </instancesSet>
        </item>
    </reservationSet>
</DescribeInstancesResponse>"""

xml_ec2CreateVolume = """\
<CreateVolumeResponse xmlns="http://ec2.amazonaws.com/doc/2012-12-01/">
    <requestId>a2c44b37-92ce-4023-bbd3-8392d3dbb093</requestId>
    <volumeId>vol-decafbad</volumeId>
    <size>1</size>
    <snapshotId/>
    <availabilityZone>us-west-2a</availabilityZone>
    <status>creating</status>
    <createTime>2013-01-21T21:46:43.000Z</createTime>
    <volumeType>standard</volumeType>
</CreateVolumeResponse>"""

xml_ec2AttachVolume = """\
<AttachVolumeResponse xmlns="http://ec2.amazonaws.com/doc/2012-12-01/">
    <requestId>b4a1943c-edcf-4ff6-9404-98e775511ccb</requestId>
    <volumeId>vol-decafbad</volumeId>
    <instanceId>i-decafbad</instanceId>
    <device>/dev/sdf</device>
    <status>attaching</status>
    <attachTime>2013-01-21T21:46:53.480Z</attachTime>
</AttachVolumeResponse>"""

xml_ec2CreateSnapshot = """\
<CreateSnapshotResponse xmlns="http://ec2.amazonaws.com/doc/2012-12-01/">
    <requestId>01f55287-4e75-4cd3-95c7-c06f00cfa1e6</requestId>
    <snapshotId>snap-decafbad</snapshotId>
    <volumeId>vol-decafbad</volumeId>
    <status>pending</status>
    <startTime>2013-01-21T21:47:44.000Z</startTime>
    <progress/>
    <ownerId>675450633870</ownerId>
    <volumeSize>1</volumeSize>
    <description/>
</CreateSnapshotResponse>"""

xml_ec2DescribeSnapshots1 = """\
<DescribeSnapshotsResponse xmlns="http://ec2.amazonaws.com/doc/2012-12-01/">
    <requestId>196303ad-7fb8-40f0-b743-5ff539377b9d</requestId>
    <snapshotSet>
        <item>
            <snapshotId>snap-decafbad</snapshotId>
            <volumeId>vol-decafbad</volumeId>
            <status>pending</status>
            <startTime>2013-01-21T21:47:44.000Z</startTime>
            <progress>9</progress>
            <ownerId>675450633870</ownerId>
            <volumeSize>1</volumeSize>
            <description/>
        </item>
    </snapshotSet>
</DescribeSnapshotsResponse>"""

xml_ec2DescribeSnapshots2 = """\
<DescribeSnapshotsResponse xmlns="http://ec2.amazonaws.com/doc/2012-12-01/">
    <requestId>74d3ba3e-a2fa-427d-a3f8-7e6282ef2d0e</requestId>
    <snapshotSet>
        <item>
            <snapshotId>snap-decafbad</snapshotId>
            <volumeId>vol-decafbad</volumeId>
            <status>completed</status>
            <startTime>2013-01-21T21:47:44.000Z</startTime>
            <progress>100%</progress>
            <ownerId>675450633870</ownerId>
            <volumeSize>1</volumeSize>
            <description/>
        </item>
    </snapshotSet>
</DescribeSnapshotsResponse>"""

xml_ec2RegisterImage = """\
<RegisterImageResponse xmlns="http://ec2.amazonaws.com/doc/2012-12-01/">
  <requestId>323a0177-beea-4b32-97af-22c784907177</requestId>
  <imageId>ami-decafbad</imageId>
</RegisterImageResponse>"""

xml_ec2DetachVolume = """\
<DetachVolumeResponse xmlns="http://ec2.amazonaws.com/doc/2012-12-01/">
  <requestId>3576b147-3357-4d34-9292-da5f34d5590e</requestId>
  <volumeId>vol-decafbad</volumeId>
  <instanceId>i-decafbad</instanceId>
  <device>/dev/sdf</device>
  <status>detaching</status>
  <attachTime>2013-01-21T21:46:53.000Z</attachTime>
</DetachVolumeResponse>"""

xml_ec2DescribeVolumes1 = """\
<DescribeVolumesResponse xmlns="http://ec2.amazonaws.com/doc/2012-12-01/">
    <requestId>8d018d08-ad91-4618-8bd6-1cf1d236f8b0</requestId>
    <volumeSet>
        <item>
            <volumeId>vol-decafbad</volumeId>
            <size>1</size>
            <snapshotId/>
            <availabilityZone>us-west-2a</availabilityZone>
            <status>in-use</status>
            <createTime>2013-01-21T21:46:43.000Z</createTime>
            <attachmentSet>
                <item>
                    <volumeId>vol-c35dc9fa</volumeId>
                    <instanceId>i-0cc5773e</instanceId>
                    <device>/dev/sdf</device>
                    <status>attached</status>
                    <attachTime>2013-01-21T21:46:53.000Z</attachTime>
                    <deleteOnTermination>false</deleteOnTermination>
                </item>
            </attachmentSet>
            <volumeType>standard</volumeType>
        </item>
    </volumeSet>
</DescribeVolumesResponse>"""

xml_ec2DescribeVolumes2 = """\
<DescribeVolumesResponse xmlns="http://ec2.amazonaws.com/doc/2012-12-01/">
    <requestId>75d3bcf2-b410-4e70-a3b1-73fe236525f4</requestId>
    <volumeSet>
        <item>
            <volumeId>vol-decafbad</volumeId>
            <size>1</size>
            <snapshotId/>
            <availabilityZone>us-west-2a</availabilityZone>
            <status>available</status>
            <createTime>2013-01-21T21:46:43.000Z</createTime>
            <attachmentSet/>
            <volumeType>standard</volumeType>
        </item>
    </volumeSet>
</DescribeVolumesResponse>"""

xml_ec2DeleteVolume = """\
<DeleteVolumeResponse xmlns="http://ec2.amazonaws.com/doc/2012-12-01/">
    <requestId>4988ebb9-d83e-432d-9f00-9b94565cbc13</requestId>
    <return>true</return>
</DeleteVolumeResponse>"""

xml_ec2CreateTags = """\
<CreateTagsResponse xmlns="http://ec2.amazonaws.com/doc/2012-08-15/">
    <requestId>79935348-522f-4e2c-8c7f-c3d2b5b977a8</requestId>
    <return>true</return>
</CreateTagsResponse>"""

xml_ec2RunInstances = """\
<RunInstancesResponse xmlns="http://ec2.amazonaws.com/doc/2012-08-15/">
    <requestId>ed6cca5a-7169-4e6d-99e0-9c48b474d253</requestId>
    <reservationId>r-09d55472</reservationId>
    <ownerId>675450633870</ownerId>
    <groupSet>
        <item>
            <groupId>sg-68f8c000</groupId>
            <groupName>misa-test</groupName>
        </item>
    </groupSet>
    <instancesSet>
        <item>
            <instanceId>i-decafbad0</instanceId>
            <imageId>ami-decafbad0</imageId>
            <instanceState>
                <code>0</code>
                <name>pending</name>
            </instanceState>
            <privateDnsName/>
            <dnsName/>
            <reason/>
            <keyName>miiban</keyName>
            <amiLaunchIndex>0</amiLaunchIndex>
            <productCodes/>
            <instanceType>m1.small</instanceType>
            <launchTime>2013-01-24T16:03:47.000Z</launchTime>
            <placement>
                <availabilityZone>us-east-1c</availabilityZone>
                <groupName/>
                <tenancy>default</tenancy>
            </placement>
            <kernelId>aki-decafbad</kernelId>
            <monitoring>
                <state>disabled</state>
            </monitoring>
            <groupSet>
                <item>
                    <groupId>sg-decafbad</groupId>
                    <groupName>launch-test</groupName>
                </item>
            </groupSet>
            <stateReason>
                <code>pending</code>
                <message>pending</message>
            </stateReason>
            <architecture>i386</architecture>
            <rootDeviceType>ebs</rootDeviceType>
            <rootDeviceName>/dev/sda</rootDeviceName>
            <blockDeviceMapping/>
            <virtualizationType>paravirtual</virtualizationType>
            <clientToken/>
            <hypervisor>xen</hypervisor>
            <networkInterfaceSet/>
            <ebsOptimized>false</ebsOptimized>
        </item>
        <item>
            <instanceId>i-decafbad1</instanceId>
            <imageId>ami-decafbad</imageId>
            <instanceState>
                <code>0</code>
                <name>pending</name>
            </instanceState>
            <privateDnsName/>
            <dnsName/>
            <reason/>
            <keyName>miiban</keyName>
            <amiLaunchIndex>0</amiLaunchIndex>
            <productCodes/>
            <instanceType>m1.small</instanceType>
            <launchTime>2013-01-24T16:03:47.000Z</launchTime>
            <placement>
                <availabilityZone>us-east-1c</availabilityZone>
                <groupName/>
                <tenancy>default</tenancy>
            </placement>
            <kernelId>aki-decafbad</kernelId>
            <monitoring>
                <state>disabled</state>
            </monitoring>
            <groupSet>
                <item>
                    <groupId>sg-decafbad</groupId>
                    <groupName>launch-test</groupName>
                </item>
            </groupSet>
            <stateReason>
                <code>pending</code>
                <message>pending</message>
            </stateReason>
            <architecture>i386</architecture>
            <rootDeviceType>ebs</rootDeviceType>
            <rootDeviceName>/dev/sda</rootDeviceName>
            <blockDeviceMapping/>
            <virtualizationType>paravirtual</virtualizationType>
            <clientToken/>
            <hypervisor>xen</hypervisor>
            <networkInterfaceSet/>
            <ebsOptimized>false</ebsOptimized>
        </item>
    </instancesSet>
</RunInstancesResponse>"""

xml_ec2DescribeImages = """\
<DescribeImagesResponse xmlns="http://ec2.amazonaws.com/doc/2012-08-15/">
    <requestId>bc5e8dda-43a7-45c1-86b3-fccce45a343c</requestId>
    <imagesSet>
        <item>
            <imageId>ami-decafbad</imageId>
            <imageLocation>675450633870/bofors-40mm-x86_20-f26a41bc</imageLocation>
            <imageState>available</imageState>
            <imageOwnerId>675450633870</imageOwnerId>
            <isPublic>false</isPublic>
            <architecture>i386</architecture>
            <imageType>machine</imageType>
            <kernelId>aki-decafbad</kernelId>
            <name>bofors-40mm-x86_20-f26a41bc</name>
            <description>bofors-40mm-x86_20-f26a41bc</description>
            <rootDeviceType>ebs</rootDeviceType>
            <rootDeviceName>/dev/sdc</rootDeviceName>
            <blockDeviceMapping>
                <item>
                    <deviceName>/dev/sdc</deviceName>
                    <ebs>
                        <snapshotId>snap-decafbad</snapshotId>
                        <volumeSize>1</volumeSize>
                        <deleteOnTermination>true</deleteOnTermination>
                        <volumeType>standard</volumeType>
                    </ebs>
                </item>
            </blockDeviceMapping>
            <virtualizationType>paravirtual</virtualizationType>
            <tagSet>
                <item>
                    <key>Name</key>
                    <value>misa-ebs-32-2</value>
                </item>
            </tagSet>
            <hypervisor>xen</hypervisor>
        </item>
    </imagesSet>
</DescribeImagesResponse>"""

xml_getAllInstances2 = (400, """\
<?xml version="1.0"?>
<Response><Errors><Error><Code>InvalidInstanceID.NotFound</Code><Message>The instance ID 'i-30a4c258' does not exist</Message></Error></Errors><RequestID>e53c7b2e-ae6e-4ac0-a47c-f0f4346a0dc2</RequestID></Response>
""")

xml_getAllInstances3 = xml_getAllInstances1.replace('i-1639fe7f',
    'i-e2df098b').replace('i-805f98e9', 'i-e5df098c')

xml_getAllKeyPairs1 = """\
<?xml version="1.0"?>
<DescribeKeyPairsResponse xmlns="http://ec2.amazonaws.com/doc/2008-02-01/">
    <keySet>
        <item>
            <keyName>tgerla</keyName>
            <keyFingerprint>ca:76:9a:97:69:18:e8:c7:e2:4c:27:f3:ba:c8:cb:7c:a4:65:9c:fd</keyFingerprint>
        </item>
        <item>
            <keyName>gxti</keyName>
            <keyFingerprint>d2:64:99:93:37:72:8c:05:8e:51:07:15:69:e6:d6:75:a4:fd:70:68</keyFingerprint>
        </item>
        <item>
            <keyName>bpja</keyName>
            <keyFingerprint>47:25:a3:6f:2c:76:d7:81:27:30:3e:1c:65:ae:5b:3d:18:6b:b8:cb</keyFingerprint>
        </item>
    </keySet>
</DescribeKeyPairsResponse>
"""

xml_getAllSecurityGroups1 = """\
<?xml version="1.0"?>
<DescribeSecurityGroupsResponse xmlns="http://ec2.amazonaws.com/doc/2008-02-01/">
    <securityGroupInfo>
        <item>
            <ownerId>941766519978</ownerId>
            <groupName>SAS Demo</groupName>
            <groupDescription>Permissions for SAS demo</groupDescription>
            <ipPermissions>
                <item>
                    <ipProtocol>tcp</ipProtocol>
                    <fromPort>0</fromPort>
                    <toPort>65535</toPort>
                    <groups/>
                    <ipRanges>
                        <item>
                            <cidrIp>149.173.12.1/24</cidrIp>
                        </item>
                        <item>
                            <cidrIp>149.173.13.1/24</cidrIp>
                        </item>
                        <item>
                            <cidrIp>149.173.8.1/24</cidrIp>
                        </item>
                        <item>
                            <cidrIp>24.163.70.1/24</cidrIp>
                        </item>
                        <item>
                            <cidrIp>66.192.95.1/24</cidrIp>
                        </item>
                    </ipRanges>
                </item>
                <item>
                    <ipProtocol>udp</ipProtocol>
                    <fromPort>0</fromPort>
                    <toPort>65535</toPort>
                    <groups/>
                    <ipRanges>
                        <item>
                            <cidrIp>149.173.12.1/24</cidrIp>
                        </item>
                        <item>
                            <cidrIp>149.173.13.1/24</cidrIp>
                        </item>
                        <item>
                            <cidrIp>149.173.8.1/24</cidrIp>
                        </item>
                        <item>
                            <cidrIp>24.163.70.1/24</cidrIp>
                        </item>
                        <item>
                            <cidrIp>66.192.95.1/24</cidrIp>
                        </item>
                    </ipRanges>
                </item>
            </ipPermissions>
        </item>
        <item>
            <ownerId>941766519978</ownerId>
            <groupName>build-cluster</groupName>
            <groupDescription>private group for rMake build cluster in ec2</groupDescription>
            <ipPermissions>
                <item>
                    <ipProtocol>tcp</ipProtocol>
                    <fromPort>1</fromPort>
                    <toPort>65535</toPort>
                    <groups>
                        <item>
                            <userId>941766519978</userId>
                            <groupName>build-cluster</groupName>
                        </item>
                    </groups>
                    <ipRanges/>
                </item>
                <item>
                    <ipProtocol>udp</ipProtocol>
                    <fromPort>1</fromPort>
                    <toPort>65535</toPort>
                    <groups>
                        <item>
                            <userId>941766519978</userId>
                            <groupName>build-cluster</groupName>
                        </item>
                    </groups>
                    <ipRanges/>
                </item>
                <item>
                    <ipProtocol>icmp</ipProtocol>
                    <fromPort>-1</fromPort>
                    <toPort>-1</toPort>
                    <groups>
                        <item>
                            <userId>941766519978</userId>
                            <groupName>build-cluster</groupName>
                        </item>
                    </groups>
                    <ipRanges/>
                </item>
                <item>
                    <ipProtocol>tcp</ipProtocol>
                    <fromPort>0</fromPort>
                    <toPort>65535</toPort>
                    <groups/>
                    <ipRanges>
                        <item>
                            <cidrIp>66.192.95.194/32</cidrIp>
                        </item>
                    </ipRanges>
                </item>
                <item>
                    <ipProtocol>udp</ipProtocol>
                    <fromPort>0</fromPort>
                    <toPort>65535</toPort>
                    <groups/>
                    <ipRanges>
                        <item>
                            <cidrIp>66.192.95.194/32</cidrIp>
                        </item>
                    </ipRanges>
                </item>
            </ipPermissions>
        </item>
    </securityGroupInfo>
</DescribeSecurityGroupsResponse>
"""

xml_getAllSecurityGroups2 = xml_getAllSecurityGroups1.replace(
    "    </securityGroupInfo>",
    """
        <item>
            <ownerId>941766519978</ownerId>
            <groupName>catalog-default</groupName>
            <groupDescription>Not the real description</groupDescription>
            <ipPermissions>
                <item>
                    <ipProtocol>tcp</ipProtocol>
                    <fromPort>80</fromPort>
                    <toPort>80</toPort>
                    <groups/>
                    <ipRanges>
                        <item>
                            <cidrIp>1.2.3.4/32</cidrIp>
                        </item>
                    </ipRanges>
                </item>
                <item>
                    <ipProtocol>tcp</ipProtocol>
                    <fromPort>443</fromPort>
                    <toPort>443</toPort>
                    <groups/>
                    <ipRanges>
                        <item>
                            <cidrIp>1.2.3.4/32</cidrIp>
                        </item>
                    </ipRanges>
                </item>
                <item>
                    <ipProtocol>tcp</ipProtocol>
                    <fromPort>8003</fromPort>
                    <toPort>8003</toPort>
                    <groups/>
                    <ipRanges>
                        <item>
                            <cidrIp>1.2.3.4/32</cidrIp>
                        </item>
                    </ipRanges>
                </item>
            </ipPermissions>
        </item>
    </securityGroupInfo>
""")

xml_registerImage1 = """\
<?xml version='1.0' encoding='UTF-8'?>
<RegisterImageResponse>
  <imageId>ami-00112233</imageId>
</RegisterImageResponse>
"""

xml_authorizeSecurityGroupSuccess = """\
<AuthorizeSecurityGroupIngressResponse xmlns="http://ec2.amazonaws.com/doc/2013-02-01/">
  <requestId>59dbff89-35bd-4eac-99ed-be587EXAMPLE</requestId>
  <return>true</return>
</AuthorizeSecurityGroupIngressResponse>
"""

xml_environment1 = """\
<?xml version='1.0' encoding='UTF-8'?>
<environment>
  <cloud>
    <id>http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws</id>
    <cloudName>aws</cloudName>
    <cloudType>ec2</cloudType>
    <cloudAlias>ec2</cloudAlias>
    <instanceTypes>
      <instanceType>
        <id>http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/instanceTypes/m1.small</id>
        <instanceTypeId>m1.small</instanceTypeId>
        <description>Small</description>
      </instanceType>
      <instanceType>
        <id>http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/instanceTypes/m1.large</id>
        <instanceTypeId>m1.large</instanceTypeId>
        <description>Large</description>
      </instanceType>
      <instanceType>
        <id>http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/instanceTypes/m1.xlarge</id>
        <instanceTypeId>m1.xlarge</instanceTypeId>
        <description>Extra Large</description>
      </instanceType>
      <instanceType>
        <id>http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/instanceTypes/c1.medium</id>
        <instanceTypeId>c1.medium</instanceTypeId>
        <description>High-CPU Medium</description>
      </instanceType>
      <instanceType>
        <id>http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/instanceTypes/c1.xlarge</id>
        <instanceTypeId>c1.xlarge</instanceTypeId>
        <description>High-CPU Extra Large</description>
      </instanceType>
    </instanceTypes>
    <keyPairs>
      <keyPair>
        <id>http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/keyPairs/tgerla</id>
        <keyName>tgerla</keyName>
        <keyFingerprint>ca:76:9a:97:69:18:e8:c7:e2:4c:27:f3:ba:c8:cb:7c:a4:65:9c:fd</keyFingerprint>
      </keyPair>
      <keyPair>
        <id>http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/keyPairs/gxti</id>
        <keyName>gxti</keyName>
        <keyFingerprint>d2:64:99:93:37:72:8c:05:8e:51:07:15:69:e6:d6:75:a4:fd:70:68</keyFingerprint>
      </keyPair>
      <keyPair>
        <id>http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/keyPairs/bpja</id>
        <keyName>bpja</keyName>
        <keyFingerprint>47:25:a3:6f:2c:76:d7:81:27:30:3e:1c:65:ae:5b:3d:18:6b:b8:cb</keyFingerprint>
      </keyPair>
    </keyPairs>
    <securityGroups>
      <securityGroup>
        <id>http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/securityGroups/catalog-default</id>
        <groupName>catalog-default</groupName>
        <description>Default EC2 Catalog Security Group</description>
      </securityGroup>
      <securityGroup>
        <id>http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/securityGroups/SAS%20Demo</id>
        <ownerId>941766519978</ownerId>
        <groupName>SAS Demo</groupName>
        <description>Permissions for SAS demo</description>
      </securityGroup>
      <securityGroup>
        <id>http://mumbo.jumbo.com/bottom/clouds/ec2/instances/aws/securityGroups/build-cluster</id>
        <ownerId>941766519978</ownerId>
        <groupName>build-cluster</groupName>
        <description>private group for rMake build cluster in ec2</description>
      </securityGroup>
    </securityGroups>
  </cloud>
</environment>
"""

xml_newInstance1 = """\
<?xml version="1.0" encoding="UTF-8"?>
<newInstance>
  <imageId>ami-0435d06d</imageId>
  <instanceName>testing</instanceName>
  <minCount>1</minCount>
  <maxCount>2</maxCount>
  <availabilityZone>us-east-1c</availabilityZone>
  <instanceType>m1.small</instanceType>
  <keyName>tgerla</keyName>
  <securityGroups>
    <item>SAS Demo</item>
    <item>build-cluster</item>
    <extraGunk>0</extraGunk>
  </securityGroups>
  <userData>my user data</userData>
</newInstance>
"""

xml_newInstance2 = """\
<?xml version="1.0" encoding="UTF-8"?>
<newInstance>
  <imageId>0903de41206786d4407ff24ab6e972c0d6b801f3.gz</imageId>
  <instanceName>testing</instanceName>
  <minCount>1</minCount>
  <maxCount>2</maxCount>
  <instanceType>vws.small</instanceType>
  <duration>123</duration>
</newInstance>
"""

xml_newInstance3 = """\
<?xml version="1.0" encoding="UTF-8"?>
<newInstance>
  <imageId>b3fb7387bb04b1403bc0eb06bd55c0ef5f02d9bb.gz</imageId>
  <instanceName>testing</instanceName>
  <minCount>1</minCount>
  <maxCount>2</maxCount>
  <instanceType>vws.small</instanceType>
  <duration>123</duration>
</newInstance>
"""

xml_newInstance4 = """\
<?xml version="1.0" encoding="UTF-8"?>
<newInstance>
  <imageId>ami-decafbad</imageId>
  <instanceName>testing</instanceName>
  <minCount>1</minCount>
  <maxCount>1</maxCount>
  <instanceType>m1.small</instanceType>
  <keyName>gxti</keyName>
  <securityGroups>
    <item>catalog-default</item>
    <item>build-cluster</item>
    <item>SAS Demo</item>
    <extraGunk>0</extraGunk>
  </securityGroups>
  <remoteIp>192.168.1.1</remoteIp>
</newInstance>
"""

xml_newInstance5 = """\
<?xml version="1.0" encoding="UTF-8"?>
<newInstance>
  <imageId>ami-afa642c6</imageId>
  <instanceName>testing</instanceName>
  <minCount>1</minCount>
  <maxCount>1</maxCount>
  <instanceType>m1.small</instanceType>
  <keyName>gxti</keyName>
  <securityGroups>
    <item>catalog-default</item>
    <extraGunk>0</extraGunk>
  </securityGroups>
</newInstance>
"""

xml_newInstance6 = """\
<?xml version="1.0" encoding="UTF-8"?>
<newInstance>
  <imageId>ami-afa642c6</imageId>
  <instanceName>testing</instanceName>
  <minCount>1</minCount>
  <maxCount>2</maxCount>
  <availabilityZone>us-east-1c</availabilityZone>
  <instanceType>m1.small</instanceType>
  <keyName>tgerla</keyName>
  <securityGroups>
    <item>SAS Demo</item>
    <item>build-cluster</item>
    <extraGunk>0</extraGunk>
  </securityGroups>
  <userData>my user data</userData>
</newInstance>
"""

xml_newInstance7 = xml_newInstance1.replace('ami-0435d06d', 'ami-afa642c6')

xml_newImage_EC2_1 = """\
<?xml version="1.0" encoding="UTF-8"?>
<newImage>
  <imageId>%s</imageId>
  <imageName>aaa-bbb</imageName>
  <imageDescription>AAA-BBB</imageDescription>
</newImage>
"""


xml_newInstanceEuca1 = xml_newInstance6.replace(
    '</instanceType>',
    (
        '</instanceType>'
        '<instanceName>New instance 1</instanceName>'
        '<instanceDescription>New instance 1 description</instanceDescription>'
    ))

xml_newInstanceOpenStackTempl = """\
<newInstance>
  <imageId>%(imageId)s</imageId>
  <instanceName>%(instanceName)s</instanceName>
  <instanceDescription>%(instanceDescription)s</instanceDescription>
  <flavor>%(flavor)s</flavor>
</newInstance>
"""

xml_newInstanceXen1 = """\
<?xml version="1.0" encoding="UTF-8"?>
<newInstance>
  <imageId>%s</imageId>
  <instanceName>new instance</instanceName>
  <minCount>1</minCount>
  <maxCount>1</maxCount>
  <instanceType>xenent.small</instanceType>
  <storageRepository>494115e9-0901-9719-1a13-c0857fd4d3d8</storageRepository>
</newInstance>
"""

xml_newInstanceVMware1 = """\
<?xml version="1.0" encoding="UTF-8"?>
<newInstance>
  <imageId>%s</imageId>
  <instanceName>instance-foo</instanceName>
  <dataCenter>datacenter-2</dataCenter>
  <vmfolder-datacenter-2>group-v3</vmfolder-datacenter-2>
  <cr-datacenter-2>domain-c5</cr-datacenter-2>
  <network-datacenter-2>dvportgroup-9987</network-datacenter-2>
  <dataStoreSelection-domain-c5>dataStoreManual-domain-c5</dataStoreSelection-domain-c5>
  <dataStore-domain-c5>datastore-18</dataStore-domain-c5>
  <resourcePool-domain-c5>resgroup-50</resourcePool-domain-c5>
  <rootSshKeys>bleepy</rootSshKeys>
</newInstance>
"""

xml_newImageVMware1 = """\
<?xml version="1.0" encoding="UTF-8"?>
<newImage>
  <imageId>%s</imageId>
  <imageName>instance-foo</imageName>
  <dataCenter>datacenter-2</dataCenter>
  <vmfolder-datacenter-2>group-v3</vmfolder-datacenter-2>
  <cr-datacenter-2>domain-c5</cr-datacenter-2>
  <network-datacenter-2>dvportgroup-9987</network-datacenter-2>
  <dataStoreSelection-domain-c5>dataStoreManual-domain-c5</dataStoreSelection-domain-c5>
  <dataStore-domain-c5>datastore-18</dataStore-domain-c5>
  <resourcePool-domain-c5>resgroup-50</resourcePool-domain-c5>
  <diskProvisioning>thin</diskProvisioning>
</newImage>
"""

xml_newImageVCloud1 = """\
<?xml version="1.0" encoding="UTF-8"?>
<newImage>
  <imageId>%s</imageId>
  <imageName>image-foo</imageName>
  <imageDescription>description for image-foo</imageDescription>
  <dataCenter>vdc-52889018</dataCenter>
  <catalog>catalog-1422628290</catalog>
  <network-vdc-52889018>network-2072223164</network-vdc-52889018>
</newImage>
"""

xml_newInstanceVCloud1 = """\
<?xml version="1.0" encoding="UTF-8"?>
<newInstance>
  <imageId>%s</imageId>
  <instanceName>instance-foo</instanceName>
  <dataCenter>vdc-52889018</dataCenter>
  <catalog>catalog-1422628290</catalog>
  <network-vdc-52889018>network-2072223164</network-vdc-52889018>
</newInstance>
"""


xml_createSecurityGroupSuccess = """\
<?xml version="1.0"?>
<CreateSecurityGroupResponse xmlns="http://ec2.amazonaws.com/doc/2008-02-01/">
    <return>true</return>
</CreateSecurityGroupResponse>
"""

xml_authorizeSecurityGroupIngressSuccess = """\
<?xml version="1.0"?>
<AuthorizeSecurityGroupIngressResponse xmlns="http://ec2.amazonaws.com/doc/2008-02-01/">
    <return>true</return>
</AuthorizeSecurityGroupIngressResponse>
"""

xml_revokeSecurityGroupIngressSuccess = """\
<?xml version="1.0"?>
<RevokeSecurityGroupIngressResponse xmlns="http://ec2.amazonaws.com/doc/2008-02-01/">
    <return>true</return>
</RevokeSecurityGroupIngressResponse>
"""

xml_runInstances1 = """\
<?xml version="1.0"?>
<RunInstancesResponse xmlns="http://ec2.amazonaws.com/doc/2008-02-01/">
    <reservationId>r-7968aa10</reservationId>
    <ownerId>941766519978</ownerId>
    <groupSet>
        <item>
            <groupId>Brett</groupId>
        </item>
        <item>
            <groupId>elliot</groupId>
        </item>
    </groupSet>
    <instancesSet>
        <item>
            <instanceId>i-e2df098b</instanceId>
            <imageId>ami-afa642c6</imageId>
            <instanceState>
                <code>0</code>
                <name>pending</name>
            </instanceState>
            <privateDnsName/>
            <dnsName/>
            <reason/>
            <keyName>misa</keyName>
            <amiLaunchIndex>0</amiLaunchIndex>
            <instanceType>m1.small</instanceType>
            <launchTime>2008-06-26T13:15:20.000Z</launchTime>
            <placement>
                <availabilityZone>us-east-1c</availabilityZone>
            </placement>
        </item>
        <item>
            <instanceId>i-e5df098c</instanceId>
            <imageId>ami-afa642c6</imageId>
            <instanceState>
                <code>0</code>
                <name>pending</name>
            </instanceState>
            <privateDnsName/>
            <dnsName/>
            <reason/>
            <keyName>misa</keyName>
            <amiLaunchIndex>1</amiLaunchIndex>
            <instanceType>m1.small</instanceType>
            <launchTime>2008-06-26T13:15:20.000Z</launchTime>
            <placement>
                <availabilityZone>us-east-1c</availabilityZone>
            </placement>
        </item>
    </instancesSet>
</RunInstancesResponse>
"""

xml_getAllRegions2 = (403, """\
<?xml version="1.0"?>
<Response><Errors><Error><Code>InvalidClientTokenId</Code><Message>The AWS Access Key Id you provided does not exist in our records.</Message></Error></Errors><RequestID>10f59dc7-1053-4cc5-9e8b-20cdef2428d3</RequestID></Response>""")

xml_runInstances2 = """\
<?xml version="1.0"?>
<Response><Errors><Error><Code>AuthFailure</Code><Message>Subscription to Produc
tCode 8ED157F9 required.</Message></Error></Errors><RequestID>8e7ae965-f09c-4fc2-b517-346180e670ec</RequestID></Response>"""

xml_runInstances3 = xml_runInstances1.replace('ami-afa642c6', 'ami-decafbad')

xml_authorizeSecurityGroupIngressFailure = (400, """\
<?xml version="1.0"?>
<Response><Errors><Error><Code>InvalidPermission.Malformed</Code><Message>Invalid IP range: 'rbatest01.eng.rpath.com/32'</Message></Error></Errors><RequestID>68bc1a0e-a253-4be2-a07a-fd98b59da002</RequestID></Response>""")

xml_terminateInstance1 = """\
<?xml version='1.0' encoding='UTF-8'?>
<instance>
  <id>i-60f12709</id>
</instance>
"""

xml_awsTerminateInstances1 = """\
<?xml version="1.0"?>
<TerminateInstancesResponse xmlns="http://ec2.amazonaws.com/doc/2008-02-01/">
    <instancesSet>
        <item>
            <instanceId>i-60f12709</instanceId>
            <shutdownState>
<!--                <code>32</code>
                <name>shutting-down</name> -->
            </shutdownState>
            <previousState>
<!--                <code>16</code>
                <name>running</name> -->
            </previousState>
        </item>
    </instancesSet>
</TerminateInstancesResponse>
"""

launchInstanceOutput = """
SSH public keyfile contained tilde:
  - '~/.ssh/id_dsa.pub' --> '/home/misa/.ssh/id_dsa.pub'

Launching workspace.

Workspace Factory Service:
    https://speedy.eng.rpath.com:8443/wsrf/services/WorkspaceFactoryService

Creating workspace "vm-001"... done.


       IP address: 192.168.0.2
         Hostname: pub02
       Start time: Mon Jul 28 19:12:19 EDT 2008
    Shutdown time: Mon Jul 28 20:12:19 EDT 2008
 Termination time: Mon Jul 28 20:22:19 EDT 2008

Waiting for updates.
"""

_epr1 = """
<WORKSPACE_EPR xsi:type="ns1:EndpointReferenceType" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:ns1="http://schemas.xmlsoap.org/ws/2004/03/addressing">
 <ns1:Address xsi:type="ns1:AttributedURI">https://127.0.0.1:8443/wsrf/services/WorkspaceService</ns1:Address>
 <ns1:ReferenceProperties xsi:type="ns1:ReferencePropertiesType">
  <ns2:WorkspaceKey xmlns:ns2="http://www.globus.org/2008/06/workspace">%(id)s</ns2:WorkspaceKey>
 </ns1:ReferenceProperties>
 <ns1:ReferenceParameters xsi:type="ns1:ReferenceParametersType"/>
</WORKSPACE_EPR>
"""

sshPubKey = """\
ssh-dss AAAAB3NzaC1kc3MAAAEBALWyU/YlO5G5JWlooR5hTtylgOa9sQ+4HoMMP+Inj/XZPnbqgxvE+BSgi6w5Z50rPmDXYP/wAFzy6hhYjM+uhxz0N0OHHOyK8NCPuQvnDY38g6uE8V++B81KmRguXODM2lSOZRMBYL/KqPs25QO4orIGFNiPMWYPWBx8Kch7itcWX2dynwOYpM/IgIGBoRlc7mbk9vFaQqj7cBMCuQfrwbMIiMvvzzalcDKX+CevMVxJLUDA+V63JLXAyjWGMbpkrDgfjaTwAnC5FSrcWPpVIPC42H9UcS/UR9R8igO8JQKnKqhhrpDNZkTxbnRa5Jhm1BckcwJkAX+4ZmjsboK1OcsAAAAVAJWTCngn/uQfT3NptCgUQAItpD1xAAABAQCNmrzcqsbaUcAHi3dcZbArsmZU2tAupOqwp8Jq2Cyw8gigkAQg0kOhDCnUy/+SkQdx6IuWhWAzfCiQo2Iu8bwa1VvWyxQSM/4p2hZiqCAWpOLim6h/0XuCmiinX/QPIfFFoFFP2P+IE+87gV/rNoJoi8ImYwBpILH4/nTx7dFx3Qj6xY/39o0/+VFqt8RPAM9apzqCQDE6fkR5++csshpREHji1kAOmc2fSGp2YuV5qwfxfReG7rZgpWIJndnh/KaXQH34sYCfoIw3WfLrzJd/lRPX/5UwAG/XEJOWU36xQXVXC5B3ILl1VcQRdlw8jf0HzC0Sm+bhT22HnLGzg66EAAABAQCfM3YtYXh93nmtTf3+Ign65DhhjxcLgCD44X3fx1nwmoR5jW1EDCpswgffzm/GEy0i673+o9pz6H7HoSP/sYCruR1nFLr6SzlwxZw27hz4ePRX/YryrUQcgQPmgBNsyVGYgAUGC6RQssmt/9KCi7yXLKW7Pj+6gjmNn4plyM6+iVN8MpslV9e+Iq738BXWzEOSeHq9vHqG6NiHlDpLDxKvWjwGjKgNxy9+ilFYAz7jtw5nea52JlJhwNA9mvhI3rXL2btgnslCUOormeN3ypo4SM/xUbTWci2KS4R/DEInhXfkNQeaUl589XIYg3FJwLU8UWFhDhVpATv79mn9QIQZ misa@rpath.com
"""

awsPublicAccessKeyId = 'nosuchpubkey'
awsSecretAccessKey = 'nosuchseckey'
awsAccountNumber = '1122334455'

ec2ProductCode = '8675309'
ec2ProductOfferingUrl = 'https://aws-portal.amazon.com/gp/aws/user/subscription/index.html?productCode=%s'  % ec2ProductCode
ec2ProductCodeErrorReason = 'Subscription to ProductCode %s required.' % ec2ProductCode
ec2ProductCodeErrorXML = """\
<?xml version="1.0"?>\n<Response><Errors><Error><Code>AuthFailure</Code><Message>%s</Message></Error></Errors><RequestID>76467959-d192-4314-820a-87f31d739137</RequestID></Response>
""" % ec2ProductCodeErrorReason

# uncomment for real data
#awsPublicAccessKeyId = '16CVNRTTWQG9MZ517782'
#awsSecretAccessKey = 'B/kKJ5K+jcr3/Sr2DSMRx6dMXzqdaEv+4yFwOUj/'
#awsAccountNumber = 'test_id'


tmp_alias1 = "speedy"
tmp_cloud1 = "speedy.eng.rpath.com:8443"
tmp_cloud1Desc = "Super Speedy Super Cloud"
tmp_repo1 = "speedy.eng.rpath.com:2811"
tmp_alias2 = "snaily"
tmp_cloud2 = "snaily.eng.rpath.com:8443"
tmp_cloud2Desc = "Super Slow Micro Cloud"
tmp_repo2 = "snaily.eng.rpath.com:2811"

tmp_factoryIdentity = "/O=rPath Inc/CN=host/speedy"
tmp_repoIdentity = "/O=rPath Inc/CN=host/speedy"

tmp_caCert = """\
-----BEGIN CERTIFICATE-----
MIIDgjCCAmqgAwIBAgIJAPLXTVV50nVgMA0GCSqGSIb3DQEBBQUAMDQxEjAQBgNV
BAoTCXJQYXRoIEluYzEeMBwGA1UEAxMVQ2VydGlmaWNhdGUgQXV0aG9yaXR5MB4X
DTA4MDcxODIwMzk0MloXDTE4MDQxNzIwMzk0MlowNDESMBAGA1UEChMJclBhdGgg
SW5jMR4wHAYDVQQDExVDZXJ0aWZpY2F0ZSBBdXRob3JpdHkwggEiMA0GCSqGSIb3
DQEBAQUAA4IBDwAwggEKAoIBAQCXj+qt11WXGM+uwVdmThiA2bBlvdEVRHenalve
TujMZtiV0PxTP47zT+mLZ2hNFpk87/OHf0+GtGjB8XhEr60OVwN9KSdX3YDG2ekH
hyDFsS9wKYN2AS75Z3vudNHhdnvITHeMEhEv3Gl++SDvwyjE1hD1tWfCIxTiCOtg
/vRHQHnL125178ZpNLLlqdqQktsysesUtIt2+fNIL13UUMipc9Ikul+K4IYPDfhl
f1odBunKUMke9IxEmQNunaG+pfkC+hFgb7nS3vHzrE91OTI1QCH9aaeneClaNblx
k/Cep+WwyjgpBuOz8Q4vGyUADX2vDa4sfIHdBMThaO/D8Ey3AgMBAAGjgZYwgZMw
HQYDVR0OBBYEFOHPAHyY4EhAzMaXqqInHo5NDeUsMGQGA1UdIwRdMFuAFOHPAHyY
4EhAzMaXqqInHo5NDeUsoTikNjA0MRIwEAYDVQQKEwlyUGF0aCBJbmMxHjAcBgNV
BAMTFUNlcnRpZmljYXRlIEF1dGhvcml0eYIJAPLXTVV50nVgMAwGA1UdEwQFMAMB
Af8wDQYJKoZIhvcNAQEFBQADggEBAC83PCKo4mD9HfmMLgJ9LuLa4Af7dxnT+Yw0
Oopz5O7ylBbExUjUY0dM1XhCbMmQBxbUeq3PbZFLZAhFPcT+0G2ivkEyvt9Sx22+
2wHWK6QiFLV+T8o7RT7Uk6BS4rDfNOO1qXFRO0pxL1VTZJHaD8N38dG0CgB+P0YQ
E70zs864AGoMV8jSe78tn0kx1xDTnou5F2UrGoFHWLVcvIHQw7iyRSVFLbnNoI3i
F4CTK4Fqr0GYRxpQh2Nj4FpMbfmqLlrMNnAMnVlgBsgytlzqwbqAa03p11L7U++Q
veW8k5K9wvIkSCeNXcXBH0TaXTQnGYRbTQr25MPK/+Al2AW2kII=
-----END CERTIFICATE-----
-----BEGIN RSA PRIVATE KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: DES-EDE3-CBC,0986ABFCDBC144AB

wz3kysVWNjJtkHs7YDVy1wVwgNZ5G1LnNxnaB3I9ENw+Itk83jBU/P+0msvkFzt1
RvBy+GTE/bS0h5CupKjiqcBigckKnTZp0HPW15GWbug9mzFq9/uEcxYMf7IvKwO4
iKgLK1D0Ozm7lcXAB1zGhLAzJht65lruuSG3NqaCSTfL+jWmz8WBXOcZAMB672Hn
MKwttIwAxWmIQK2Ph8FzW9bu7PgycVfeAS2QeRcnsmPaOj7HOTYwtVGq1GDdLu3b
NfdX6zgPsg6g+Fci/NHaEPfbf9EwZsLi5V+YYoWM44GiSdmEn3Fqk2xbpwilHv1l
JaZzQ1dTbkkvW2uBEHrW4niLgJUIYsQnVUNwldZ/lnIn7kl68SRmmXWNgrHTdj2k
vn6IKaFeyOvooEJmMwVrvPxiS3FITwaD9K48gi3qNfWaHl3se+BVy/AAFSxxHs5b
irNZt/AUTEo13/iQtK478bmpiN229NktLOWaGkLbjPU/nsFbjvqdtGOu5EVMUTdI
ODF4zI+yWYab0P0tGynvp0obAyoGs5e5NYC5k4SIWf5YwJljFJcgWnID1e9OJQQ9
zh2xuRtU4AQaYvofcw0nS3qUg0q1s6Z2mi9PoAARTWB7kbtQfZg21A9MI1xCPcGG
u8tGXZftss7iatoZtdB0npHePid80xFaBl7siCTinPbYpWaq6gOW7gq7mqWws+dS
YoUgPWxjJDW39YzGPVew2dIkrsdvsgxE6tYIWW75aiAkekzhrg7FrJxy2+zKaga9
VnCJV3lnUJRPucDVuWLFvBbl6AcTuf6v+szTSa8i8GyJs3hqeLcOdX/TNxkw2uIq
Dxf9eNTSSTAyQs8RR8PwvYvPtwffP5xEhD13xLoMatcA5MzxLYEkRNb4RM19rR7Y
bIOH6gRaRpHlc9sHsbl9e/sFzbyJrrrjYLS88EXn1Jq+bo72q932EgelNrXW1jU+
TI7bm3/5zQUZvSkSIvvoh+itSRrahBBCA1fSpdpVUsXbf8z/4bILWySzdMgSJxft
Wd/X+N9r9aMyO/jXMk7N4O83gFepcbZ7qhtd6+Lze0JzzXtkgf5bWW1ZX5rYZVD2
NeK7ZR6R4qii8LzbTqt8nbYxaajq/F7ySfEvu/311RWGbwdO3e2nHUZxOeI5+KsK
eZqkVw67kcFDt2RJYTwO6u577hEvz6HUArW8PgIbxj+MrCP/JeNiGVA2pJdjVqmL
mPNOs8NzcE2K2aB9/noWQxec5W0OwgbY3RdXcwvK/EnPZS384yHHPsJ9SN2GrVrN
OmZ3autp5XvEMAgEioz1KMMWwHxUwuiR07vM7TU7ZJCpA1ciNwnFUMGBxf3Kbvfb
uwDJ7QO63PNWaONmwZ+3HGQ+LJyXJqVQsAScauAlrw7VPhOI/5u2KhpUQSMFQEQq
ruRr4g036UBtaDoaJ2meQSxWtTyCJNd1Ri0RZMXBsc6/uDJR0pAdDgf8AWrSFXKN
URNDOfrup8+TssU+PhcOr9snlq/DZA2aCIRaZ0/lvOKYd0fWvQfd4Z73N40MjYM2
Xp667Y4iNuSD8aZ+hkGA6WQdqo1S72+lhOd0nG5sdZ1nS3i7CyYcpg==
-----END RSA PRIVATE KEY-----
"""

tmp_userCert = """\
-----BEGIN CERTIFICATE-----
MIICbTCCAVWgAwIBAgIBATANBgkqhkiG9w0BAQQFADA0MRIwEAYDVQQKEwlyUGF0
aCBJbmMxHjAcBgNVBAMTFUNlcnRpZmljYXRlIEF1dGhvcml0eTAeFw0wOTA3MjAy
MDA3MTRaFw0xMDA3MjAyMDA3MTRaMC0xEjAQBgNVBAoTCXJQYXRoIEluYzEXMBUG
A1UEAwwObWlzYUBycGF0aC5jb20wgZ8wDQYJKoZIhvcNAQEBBQADgY0AMIGJAoGB
AKh4OcbqD7l4ohln/ZbYj45P90oRiMf3H2cYRf6MUE343/cmUNw5IJ5KIPTi3/OM
V94PRFW8MqhlFlO6nd1CfAe7ZqN5AcZKtvC/FWkMv9UPkNkpf7E/7e30SSo4MBYB
UyJIL9TTllqOo7Tg5RFxHXCUdSnY0x5k2PbG/wmhWnT9AgMBAAGjFTATMBEGCWCG
SAGG+EIBAQQEAwIE8DANBgkqhkiG9w0BAQQFAAOCAQEAkoLoxvLHYDQXR7BaTyzt
sRW3WU3N+wR8Y6MuuhibdhmalyPB3lN41XY0DbmwbirhQcQSHdQqSCAV0voTXSL0
6tq2mQgaZxnXUYeKzKhn2Mw8TJpK2xwembSiuBSHleY/OHAwTEu4yr2FM4z4NJ6Q
BYTnx1jkqhKntGOdtOa1Y8DdTRVH8xsqRH3meA+EU97Pr3EjXXkfyZyZ8XC/7Msj
A8/wwR9e5Qkp/XCipQLTaGPp7LuU6TH83gYJLL8fWfTw3SV7wEcJ25Hq7zo8txZ7
tuLT2f2r8W2V27lqDx9N+79ViIFofR3jK1WuOMzA4MdKEri6oTOxnv/DHlSYVAlz
ow==
-----END CERTIFICATE-----
"""

tmp_userKey = """\
-----BEGIN RSA PRIVATE KEY-----
MIICXAIBAAKBgQCoeDnG6g+5eKIZZ/2W2I+OT/dKEYjH9x9nGEX+jFBN+N/3JlDc
OSCeSiD04t/zjFfeD0RVvDKoZRZTup3dQnwHu2ajeQHGSrbwvxVpDL/VD5DZKX+x
P+3t9EkqODAWAVMiSC/U05ZajqO04OURcR1wlHUp2NMeZNj2xv8JoVp0/QIDAQAB
AoGBAINx+rKG4Wn3A5MLHkNaCPgi0HFMKQrMeAX6XHJ1jBqqOiUeEi0hrZ+Tew9X
DSF7uPsbsleqlWPqK3d8vbtrKlWbqL84bkLsSKdNT+4MD8ljWZHs2WEx2QGMUqLy
b7h8tDU9FkZI3rzqa+CX54fqf+7UnW7qopLjX93tM7jHTjOJAkEA/QyylDcfqMp8
RV0F8bdofg82fKXZ2kImoEUJa67UQ5ecZCOH1J+oIVQn92UmBzgNrGHAW0f70eoL
2x9dP2skMwJBAKpvEubTqm9Hzgf1G83BDgp1H3lWiCs8E+FWXicO7L/cna9c0VSw
Zb4KdM/n9GADmUD9Nz7Lj3wPXOxJODKZUg8CQA5SMqUavYry8reGPTjh1WMU/1Ns
m3izt7XoUlEq0s6EfRBZxm0tH/nK5nwk2FMeQ//WhGlmGIVXxpX/H2rgaGsCQC7h
bLaXpHsFqlOgBWzcXKtdujGbLsuNs/44zp85yL+hxLIW+vGrr+DNaYJC0IKUmtQ4
kriwL6C1bR8FqPKqH9sCQCs5bERV7tOnQYR01AdqjfV2AJmovlafnXPhPjq/w2vj
HcJBycydcS1JPEcZcChN3YEHL1EOOupOvWvrWYuVdgM=
-----END RSA PRIVATE KEY-----
"""

tmp_alias3 = "nimbus"
tmp_cloud3 = "tp-grid3.ci.uchicago.edu:8445"
tmp_cloud3Desc = "Nimbus Cloud at University of Chicago"
tmp_repo3 = "tp-vm1.ci.uchicago.edu:2811"

tmp_cloud3FactoryIdentity = "/O=Grid/OU=GlobusTest/OU=simple-workspace-ca/CN=host/tp-grid3.ci.uchicago.edu"
tmp_cloud3RepoIdentity = "/O=Grid/OU=GlobusTest/OU=simple-workspace-ca/CN=host/tp-vm1.ci.uchicago.edu"

tmp_cloud3CaCert = """
-----BEGIN CERTIFICATE-----
MIICZTCCAc6gAwIBAgIBADANBgkqhkiG9w0BAQQFADBVMQ0wCwYDVQQKEwRHcmlk
MRMwEQYDVQQLEwpHbG9idXNUZXN0MRwwGgYDVQQLExNzaW1wbGUtd29ya3NwYWNl
LWNhMREwDwYDVQQDEwhTaW1wbGVDQTAeFw0wNzAyMjYwMjE4MDBaFw0xMjAyMjUw
MjE4MDBaMFUxDTALBgNVBAoTBEdyaWQxEzARBgNVBAsTCkdsb2J1c1Rlc3QxHDAa
BgNVBAsTE3NpbXBsZS13b3Jrc3BhY2UtY2ExETAPBgNVBAMTCFNpbXBsZUNBMIGf
MA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCpFzJ+klOA7XvDs6e9T4EKFzVc5+gP
nsQPk6ARxJMBJvvEmHDVHOiGBKl4ua3KscP/LOPyhTbshtukcE4FrzG3HRrfSzJL
lbRrtmrLFp+9hIv8g2klC9/a444DnBTdrBjcAywRjiDDZwYKZucYjbmivbuzVYDs
xy7eDixbTCmWewIDAQABo0UwQzAPBgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBQ8
HTYkMIb4nykLBEPFRApQAnik/DARBglghkgBhvhCAQEEBAMCAAcwDQYJKoZIhvcN
AQEEBQADgYEAgtdSTpYug9NgtiMK+1ivN+Hug+BAYnfWoqMqbFeRN0R/l7bHI5Q5
E7/27cGZV/rkWw/XiZcY8tvq6IpSj8EO4DNHoPf1fcB456LJC1JynAakR0Um/s/O
mGHoqfb9hJbpLdxyvhdR2RjZYsOjSrF1zrqwCwuYEhVKuCav+oYyC+Q=
-----END CERTIFICATE-----
"""

tmp_cloud3UserCert = """
-----BEGIN CERTIFICATE-----
MIICUjCCAbugAwIBAgIBHDANBgkqhkiG9w0BAQQFADBVMQ0wCwYDVQQKEwRHcmlk
MRMwEQYDVQQLEwpHbG9idXNUZXN0MRwwGgYDVQQLExNzaW1wbGUtd29ya3NwYWNl
LWNhMREwDwYDVQQDEwhTaW1wbGVDQTAeFw0wODA3MjUyMTIyMzZaFw0wOTA3MjUy
MTIyMzZaMHIxDTALBgNVBAoTBEdyaWQxEzARBgNVBAsTCkdsb2J1c1Rlc3QxHDAa
BgNVBAsTE3NpbXBsZS13b3Jrc3BhY2UtY2ExFTATBgNVBAsTDHVjaGljYWdvLmVk
dTEXMBUGA1UEAxMOTWloYWkgSWJhbmVzY3UwgZ8wDQYJKoZIhvcNAQEBBQADgY0A
MIGJAoGBAOSv+hLY0YxieIxzFUgWyRcrjRMHCu+4NJotLUgIZYa9VPlgrjyUeKmJ
y2teYS5TzdHVW3Pl00rKSFcCtVglxMLT6RSxDsa+J6UZo3/EzKMk3ITwTbWNr8d4
TLigLXBhIu9e6+m8JCYPU7S3XCueB5hl0rCGewOka0NK6f1TZrmJAgMBAAGjFTAT
MBEGCWCGSAGG+EIBAQQEAwIE8DANBgkqhkiG9w0BAQQFAAOBgQBoKibUofxRt9/j
KAUotmB1OpBWXaBL7wdgz9CM3T4sbJaKyv3OTSmtDFRe2M2s4tu6nDlylq+RnWWj
xXdD/093TL3tt+LtkSS3hn5nDSoMjRpqmcS9ThaiMB+GFAdj0eDqtJor7lJuIfTE
GEiTuTWWWXTxNc+of+OQWB85UF+fqw==
-----END CERTIFICATE-----
"""

tmp_cloud3UserKey = """
-----BEGIN RSA PRIVATE KEY-----
MIICXQIBAAKBgQDkr/oS2NGMYniMcxVIFskXK40TBwrvuDSaLS1ICGWGvVT5YK48
lHipictrXmEuU83R1Vtz5dNKykhXArVYJcTC0+kUsQ7GvielGaN/xMyjJNyE8E21
ja/HeEy4oC1wYSLvXuvpvCQmD1O0t1wrngeYZdKwhnsDpGtDSun9U2a5iQIDAQAB
AoGAI2y/KDw9+aknU1pgaZJeBCDS8aedohS+0UM+SHJEh+K8TwUS+H9nUZvuzusH
0s1YjLCoQgPP/z3mhtP8k3MGT3zavSwRb6nZslwDBwfKuX6cCi7aL9tqc4Ctc4x2
ZRbKH+/IdIoX4oQQsiRwAQjHOfHsqJQ6k9lExZTTrlW8TqECQQD2Rza90wEFYSqz
dAKO0+c7sy0nOIoGRGaGeXaHRiUcraWUrKQ7BIt9x2NA0V46HEJXG7UvPvYEq0k9
qbXf9n3zAkEA7bb/d869+RgS97OMRQ6wyCOspHVt9bWk2ZfXiJ1rnaTt8/8C3jZ8
NXoBcnQR9cQhk+Tp+CNwlAihP6cVYqC9kwJAEitQ05JUmfQANXsSkTz660GdzC30
qN+0/KjLYNGA/WumMqDGAQCl1eK25NpNbFYXYtvNcy3e8ps8bQsvOtWxlwJBAKey
FkzVq00Df7YAku7Qq0O1bwBh2x2gc9gQ9zroGtgOVtNvTf2nID61gDnWyii/oRRt
Q+UKU0wLPn3iCAMY9EMCQQCS5MOelpclV0kQWWxFobS9IDW2XbE/AvtqafxrGQ9a
7KhykMTHcLm2150q1KwSHnoiWpsCDFam1X/Jo70F8dWi
-----END RSA PRIVATE KEY-----
"""

tmp_ssh_pubkey = """\
ssh-dss AAAAB3NzaC1kc3MAAAEBALWyU/YlO5G5JWlooR5hTtylgOa9sQ+4HoMMP+Inj/XZPnbqgxvE+BSgi6w5Z50rPmDXYP/wAFzy6hhYjM+uhxz0N0OHHOyK8NCPuQvnDY38g6uE8V++B81KmRguXODM2lSOZRMBYL/KqPs25QO4orIGFNiPMWYPWBx8Kch7itcWX2dynwOYpM/IgIGBoRlc7mbk9vFaQqj7cBMCuQfrwbMIiMvvzzalcDKX+CevMVxJLUDA+V63JLXAyjWGMbpkrDgfjaTwAnC5FSrcWPpVIPC42H9UcS/UR9R8igO8JQKnKqhhrpDNZkTxbnRa5Jhm1BckcwJkAX+4ZmjsboK1OcsAAAAVAJWTCngn/uQfT3NptCgUQAItpD1xAAABAQCNmrzcqsbaUcAHi3dcZbArsmZU2tAupOqwp8Jq2Cyw8gigkAQg0kOhDCnUy/+SkQdx6IuWhWAzfCiQo2Iu8bwa1VvWyxQSM/4p2hZiqCAWpOLim6h/0XuCmiinX/QPIfFFoFFP2P+IE+87gV/rNoJoi8ImYwBpILH4/nTx7dFx3Qj6xY/39o0/+VFqt8RPAM9apzqCQDE6fkR5++csshpREHji1kAOmc2fSGp2YuV5qwfxfReG7rZgpWIJndnh/KaXQH34sYCfoIw3WfLrzJd/lRPX/5UwAG/XEJOWU36xQXVXC5B3ILl1VcQRdlw8jf0HzC0Sm+bhT22HnLGzg66EAAABAQCfM3YtYXh93nmtTf3+Ign65DhhjxcLgCD44X3fx1nwmoR5jW1EDCpswgffzm/GEy0i673+o9pz6H7HoSP/sYCruR1nFLr6SzlwxZw27hz4ePRX/YryrUQcgQPmgBNsyVGYgAUGC6RQssmt/9KCi7yXLKW7Pj+6gjmNn4plyM6+iVN8MpslV9e+Iq738BXWzEOSeHq9vHqG6NiHlDpLDxKvWjwGjKgNxy9+ilFYAz7jtw5nea52JlJhwNA9mvhI3rXL2btgnslCUOormeN3ypo4SM/xUbTWci2KS4R/DEInhXfkNQeaUl589XIYg3FJwLU8UWFhDhVpATv79mn9QIQZ misa@rpath.com
"""

tmp_xenentName1 = 'abc.eng.rpath.com'
tmp_xenentAlias1 = 'abc'
tmp_xenentDescription1 = 'abc cloud'

tmp_xenentName2 = 'xs01.eng.rpath.com'
tmp_xenentAlias2 = 'xs01'
tmp_xenentDescription2 = 'xs01 cloud'

vws_repositoryBaseDir = "/foo"

xenent_listInstances1 = ({'Status' : 'Success',
 'Value' : {
'OpaqueRef:215551e4-70e0-489a-7b46-5775fa10acc6': {'HVM_boot_params': {},
                                                    'HVM_boot_policy': '',
                                                    'HVM_shadow_multiplier': 1.0,
                                                    'PCI_bus': '',
                                                    'PV_args': '',
                                                    'PV_bootloader': 'pygrub',
                                                    'PV_bootloader_args': '',
                                                    'PV_kernel': '',
                                                    'PV_legacy_args': 'root=/dev/xvda1 ro',
                                                    'PV_ramdisk': '',
                                                    'VBDs': ['OpaqueRef:49b4843c-483b-7466-f7a8-e879e501b7c8',
                                                             'OpaqueRef:7547e7aa-2a19-61ae-3f9f-a51b563fba5b'],
                                                    'VCPUs_at_startup': '1',
                                                    'VCPUs_max': '1',
                                                    'VCPUs_params': {},
                                                    'VIFs': [],
                                                    'VTPMs': [],
                                                    'actions_after_crash': 'destroy',
                                                    'actions_after_reboot': 'restart',
                                                    'actions_after_shutdown': 'destroy',
                                                    'affinity': 'OpaqueRef:c401bb77-1e36-bc4d-0b4a-ffbd020555d3',
                                                    'allowed_operations': ['clone',
                                                                           'start',
                                                                           'start_on',
                                                                           'export',
                                                                           'destroy',
                                                                           'make_into_template'],
                                                    'consoles': [],
                                                    'crash_dumps': [],
                                                    'current_operations': {},
                                                    'domarch': 'x32',
                                                    'domid': '-1',
                                                    'guest_metrics':
                                                    'OpaqueRef:GuestMetricsNetworks1',
                                                    'is_a_template': False,
                                                    'is_control_domain': False,
                                                    'last_boot_CPU_flags': {},
                                                    'last_booted_record': '<value><struct><member><name>uuid</name><value>ea67e6e2-8cc9-633a-edfa-e615cc9717e5</value></member><member><name>allowed_operations</name><value><array><data/></array></value></member><member><name>current_operations</name><value><struct><member><name>OpaqueRef:153c5214-b00a-8acc-ef6f-d25b6d6fac1b</name><value>start</value></member></struct></value></member><member><name>power_state</name><value>Halted</value></member><member><name>name_label</name><value>rPath Appliance Platform - Linux Service import (1)</value></member><member><name>name_description</name><value>Created by rPath rBuilder</value></member><member><name>user_version</name><value>0</value></member><member><name>is_a_template</name><value><boolean>0</boolean></value></member><member><name>suspend_VDI</name><value>OpaqueRef:NULL</value></member><member><name>resident_on</name><value>OpaqueRef:NULL</value></member><member><name>affinity</name><value>OpaqueRef:c401bb77-1e36-bc4d-0b4a-ffbd020555d3</value></member><member><name>memory_static_max</name><value>268435456</value></member><member><name>memory_dynamic_max</name><value>268435456</value></member><member><name>memory_dynamic_min</name><value>268435456</value></member><member><name>memory_static_min</name><value>0</value></member><member><name>VCPUs_params</name><value><struct/></value></member><member><name>VCPUs_max</name><value>1</value></member><member><name>VCPUs_at_startup</name><value>1</value></member><member><name>actions_after_shutdown</name><value>destroy</value></member><member><name>actions_after_reboot</name><value>restart</value></member><member><name>actions_after_crash</name><value>destroy</value></member><member><name>consoles</name><value><array><data/></array></value></member><member><name>VIFs</name><value><array><data/></array></value></member><member><name>VBDs</name><value><array><data><value>OpaqueRef:49b4843c-483b-7466-f7a8-e879e501b7c8</value><value>OpaqueRef:7547e7aa-2a19-61ae-3f9f-a51b563fba5b</value></data></array></value></member><member><name>crash_dumps</name><value><array><data/></array></value></member><member><name>VTPMs</name><value><array><data/></array></value></member><member><name>PV_bootloader</name><value>pygrub</value></member><member><name>PV_kernel</name><value/></member><member><name>PV_ramdisk</name><value/></member><member><name>PV_args</name><value/></member><member><name>PV_bootloader_args</name><value/></member><member><name>PV_legacy_args</name><value>root=/dev/xvda1 ro</value></member><member><name>HVM_boot_policy</name><value/></member><member><name>HVM_boot_params</name><value><struct/></value></member><member><name>HVM_shadow_multiplier</name><value><double>1</double></value></member><member><name>platform</name><value><struct><member><name>acpi</name><value>true</value></member><member><name>apic</name><value>true</value></member><member><name>nx</name><value>false</value></member><member><name>pae</name><value>true</value></member></struct></value></member><member><name>PCI_bus</name><value/></member><member><name>other_config</name><value><struct><member><name>import_task</name><value>OpaqueRef:bd96c0a7-ed2b-f3a6-494b-5f9f686adfa7</value></member><member><name>mac_seed</name><value>60cf70bd-e85b-820f-05fc-f5987b98ab42</value></member></struct></value></member><member><name>domid</name><value>-1</value></member><member><name>domarch</name><value/></member><member><name>last_boot_CPU_flags</name><value><struct/></value></member><member><name>is_control_domain</name><value><boolean>0</boolean></value></member><member><name>metrics</name><value>OpaqueRef:b6585965-07ec-39a2-374d-d3edceae5915</value></member><member><name>guest_metrics</name><value>OpaqueRef:NULL</value></member><member><name>last_booted_record</name><value/></member><member><name>recommendations</name><value/></member><member><name>xenstore_data</name><value><struct/></value></member></struct></value>',
                                                    'memory_dynamic_max': '268435456',
                                                    'memory_dynamic_min': '268435456',
                                                    'memory_static_max': '268435456',
                                                    'memory_static_min': '0',
                                                    'metrics': 'OpaqueRef:b6585965-07ec-39a2-374d-d3edceae5915',
                                                    'name_description': 'Created by rPath rBuilder',
                                                    'name_label': 'rPath Appliance Platform - Linux Service import (1)',
                                                    'other_config': {'import_task': 'OpaqueRef:bd96c0a7-ed2b-f3a6-494b-5f9f686adfa7',
                                                                     'last_shutdown_action': 'Destroy',
                                                                     'last_shutdown_initiator': 'internal',
                                                                     'last_shutdown_reason': 'halted',
                                                                     'last_shutdown_time': '20081021T13:50:24Z',
                                                                     'mac_seed': '60cf70bd-e85b-820f-05fc-f5987b98ab42'},
                                                    'platform': {'acpi': 'true',
                                                                 'apic': 'true',
                                                                 'nx': 'false',
                                                                 'pae': 'true'},
                                                    'power_state': 'Halted',
                                                    'recommendations': '',
                                                    'resident_on': 'OpaqueRef:NULL',
                                                    'suspend_VDI': 'OpaqueRef:NULL',
                                                    'user_version': '0',
                                                    'uuid': 'VmUuid1',
                                                    'xenstore_data': {}},
 'OpaqueRef:48cba081-283e-86f9-870c-29359ce16c26': {'HVM_boot_params': {},
                                                    'HVM_boot_policy': '',
                                                    'HVM_shadow_multiplier': 1.0,
                                                    'PCI_bus': '',
                                                    'PV_args': '',
                                                    'PV_bootloader': '',
                                                    'PV_bootloader_args': '',
                                                    'PV_kernel': '',
                                                    'PV_legacy_args': '',
                                                    'PV_ramdisk': '',
                                                    'VBDs': [],
                                                    'VCPUs_at_startup': '4',
                                                    'VCPUs_max': '4',
                                                    'VCPUs_params': {},
                                                    'VIFs': [],
                                                    'VTPMs': [],
                                                    'actions_after_crash': 'destroy',
                                                    'actions_after_reboot': 'destroy',
                                                    'actions_after_shutdown': 'destroy',
                                                    'affinity': 'OpaqueRef:c401bb77-1e36-bc4d-0b4a-ffbd020555d3',
                                                    'allowed_operations': [],
                                                    'consoles': ['OpaqueRef:c88dcbed-c92d-3f8e-0429-2b5de838da74'],
                                                    'crash_dumps': [],
                                                    'current_operations': {},
                                                    'domarch': 'x32',
                                                    'domid': '0',
                                                    'guest_metrics': 'OpaqueRef:GuestMetricsNetworks1',
                                                    'is_a_template': False,
                                                    'is_control_domain': True,
                                                    'last_boot_CPU_flags': {},
                                                    'last_booted_record': '',
                                                    'memory_dynamic_max': '219152384',
                                                    'memory_dynamic_min': '219152384',
                                                    'memory_static_max': '790102016',
                                                    'memory_static_min': '790102016',
                                                    'metrics': 'OpaqueRef:abed4e8d-25f9-7422-21fa-4c77bad76d68',
                                                    'name_description': 'The domain which manages physical devices and manages other domains',
                                                    'name_label': 'Control domain on host: localhost.localdomain',
                                                    'other_config': {},
                                                    'platform': {},
                                                    'power_state': 'Running',
                                                    'recommendations': '',
                                                    'resident_on': 'OpaqueRef:c401bb77-1e36-bc4d-0b4a-ffbd020555d3',
                                                    'suspend_vdi': 'OpaqueRef:NULL',
                                                    'user_version': '1',
                                                    'uuid': '9b01f3fb-3e66-4c0b-9a8f-3c8ea1a6769e',
                                                    'xenstore_data': {}},
 'OpaqueRef:4c199434-d479-a55c-279f-887dfc1fec2d': {'HVM_boot_params': {},
                                                    'HVM_boot_policy': '',
                                                    'HVM_shadow_multiplier': 1.0,
                                                    'PCI_bus': '',
                                                    'PV_args': '',
                                                    'PV_bootloader': 'pygrub',
                                                    'PV_bootloader_args': '',
                                                    'PV_kernel': '',
                                                    'PV_legacy_args': 'root=/dev/xvda1 ro',
                                                    'PV_ramdisk': '',
                                                    'VBDs': ['OpaqueRef:f4bbd3bb-c11a-2a03-8aa6-8786b961dd6a',
                                                             'OpaqueRef:2f547765-284f-bb75-cbbc-bf1308199ced'],
                                                    'VCPUs_at_startup': '1',
                                                    'VCPUs_max': '1',
                                                    'VCPUs_params': {},
                                                    'VIFs': [],
                                                    'VTPMs': [],
                                                    'actions_after_crash': 'destroy',
                                                    'actions_after_reboot': 'restart',
                                                    'actions_after_shutdown': 'destroy',
                                                    'affinity': 'OpaqueRef:c401bb77-1e36-bc4d-0b4a-ffbd020555d3',
                                                    'allowed_operations': ['clone',
                                                                           'start',
                                                                           'start_on',
                                                                           'export',
                                                                           'destroy',
                                                                           'make_into_template'],
                                                    'consoles': [],
                                                    'crash_dumps': [],
                                                    'current_operations': {},
                                                    'domarch': 'x32',
                                                    'domid': '-1',
                                                    'guest_metrics': 'OpaqueRef:NULL',
                                                    'is_a_template': False,
                                                    'is_control_domain': False,
                                                    'last_boot_CPU_flags': {},
                                                    'last_booted_record': '<value><struct><member><name>uuid</name><value>c1af2f03-2e0c-0807-9447-9883c578aa32</value></member><member><name>allowed_operations</name><value><array><data/></array></value></member><member><name>current_operations</name><value><struct><member><name>OpaqueRef:96abbc54-9577-3efa-ff41-c7b7c6d96839</name><value>start</value></member></struct></value></member><member><name>power_state</name><value>Halted</value></member><member><name>name_label</name><value>Support Issue replication import (1)</value></member><member><name>name_description</name><value>Created by rPath rBuilder</value></member><member><name>user_version</name><value>0</value></member><member><name>is_a_template</name><value><boolean>0</boolean></value></member><member><name>suspend_VDI</name><value>OpaqueRef:NULL</value></member><member><name>resident_on</name><value>OpaqueRef:NULL</value></member><member><name>affinity</name><value>OpaqueRef:c401bb77-1e36-bc4d-0b4a-ffbd020555d3</value></member><member><name>memory_static_max</name><value>268435456</value></member><member><name>memory_dynamic_max</name><value>268435456</value></member><member><name>memory_dynamic_min</name><value>268435456</value></member><member><name>memory_static_min</name><value>0</value></member><member><name>VCPUs_params</name><value><struct/></value></member><member><name>VCPUs_max</name><value>1</value></member><member><name>VCPUs_at_startup</name><value>1</value></member><member><name>actions_after_shutdown</name><value>destroy</value></member><member><name>actions_after_reboot</name><value>restart</value></member><member><name>actions_after_crash</name><value>destroy</value></member><member><name>consoles</name><value><array><data/></array></value></member><member><name>VIFs</name><value><array><data/></array></value></member><member><name>VBDs</name><value><array><data><value>OpaqueRef:f4bbd3bb-c11a-2a03-8aa6-8786b961dd6a</value><value>OpaqueRef:2f547765-284f-bb75-cbbc-bf1308199ced</value></data></array></value></member><member><name>crash_dumps</name><value><array><data/></array></value></member><member><name>VTPMs</name><value><array><data/></array></value></member><member><name>PV_bootloader</name><value>pygrub</value></member><member><name>PV_kernel</name><value/></member><member><name>PV_ramdisk</name><value/></member><member><name>PV_args</name><value/></member><member><name>PV_bootloader_args</name><value/></member><member><name>PV_legacy_args</name><value>root=/dev/xvda1 ro</value></member><member><name>HVM_boot_policy</name><value/></member><member><name>HVM_boot_params</name><value><struct/></value></member><member><name>HVM_shadow_multiplier</name><value><double>1</double></value></member><member><name>platform</name><value><struct><member><name>acpi</name><value>true</value></member><member><name>apic</name><value>true</value></member><member><name>nx</name><value>false</value></member><member><name>pae</name><value>true</value></member></struct></value></member><member><name>PCI_bus</name><value/></member><member><name>other_config</name><value><struct><member><name>import_task</name><value>OpaqueRef:1aac7ac3-5733-98ee-75a8-7c8d8aea373b</value></member><member><name>mac_seed</name><value>0b583262-4ad6-9f3c-3f9e-087733474ba9</value></member></struct></value></member><member><name>domid</name><value>-1</value></member><member><name>domarch</name><value/></member><member><name>last_boot_CPU_flags</name><value><struct/></value></member><member><name>is_control_domain</name><value><boolean>0</boolean></value></member><member><name>metrics</name><value>OpaqueRef:effdd3d1-3d38-5ae1-46f4-6b059e0816d6</value></member><member><name>guest_metrics</name><value>OpaqueRef:NULL</value></member><member><name>last_booted_record</name><value/></member><member><name>recommendations</name><value/></member><member><name>xenstore_data</name><value><struct/></value></member></struct></value>',
                                                    'memory_dynamic_max': '268435456',
                                                    'memory_dynamic_min': '268435456',
                                                    'memory_static_max': '268435456',
                                                    'memory_static_min': '0',
                                                    'metrics': 'OpaqueRef:effdd3d1-3d38-5ae1-46f4-6b059e0816d6',
                                                    'name_description': 'Created by rPath rBuilder',
                                                    'name_label': 'Support Issue replication import (1)',
                                                    'other_config': {'import_task': 'OpaqueRef:1aac7ac3-5733-98ee-75a8-7c8d8aea373b',
                                                                     'last_shutdown_action': 'Destroy',
                                                                     'last_shutdown_initiator': 'external',
                                                                     'last_shutdown_reason': 'halted',
                                                                     'last_shutdown_time': '20081021T13:44:33Z',
                                                                     'mac_seed': '0b583262-4ad6-9f3c-3f9e-087733474ba9'},
                                                    'platform': {'acpi': 'true',
                                                                 'apic': 'true',
                                                                 'nx': 'false',
                                                                 'pae': 'true'},
                                                    'power_state': 'Halted',
                                                    'recommendations': '',
                                                    'resident_on': 'OpaqueRef:NULL',
                                                    'suspend_VDI': 'OpaqueRef:NULL',
                                                    'user_version': '0',
                                                    'uuid': 'c1af2f03-2e0c-0807-9447-9883c578aa32',
                                                    'xenstore_data': {}},
 'OpaqueRef:4f366fc0-cd2b-4081-d79a-d879294243f5': {'HVM_boot_params': {},
                                                    'HVM_boot_policy': '',
                                                    'HVM_shadow_multiplier': 1.0,
                                                    'PCI_bus': '',
                                                    'PV_args': '',
                                                    'PV_bootloader': 'pygrub',
                                                    'PV_bootloader_args': '',
                                                    'PV_kernel': '',
                                                    'PV_legacy_args': 'root=/dev/xvda1 ro',
                                                    'PV_ramdisk': '',
                                                    'VBDs': ['OpaqueRef:1f636eba-9920-3283-5a04-9a01d07732a9',
                                                             'OpaqueRef:de7ea258-cf55-f07b-22ff-aa5762b55d0d'],
                                                    'VCPUs_at_startup': '1',
                                                    'VCPUs_max': '1',
                                                    'VCPUs_params': {},
                                                    'VIFs': [],
                                                    'VTPMs': [],
                                                    'actions_after_crash': 'destroy',
                                                    'actions_after_reboot': 'restart',
                                                    'actions_after_shutdown': 'destroy',
                                                    'affinity': 'OpaqueRef:c401bb77-1e36-bc4d-0b4a-ffbd020555d3',
                                                    'allowed_operations': ['clone',
                                                                           'start',
                                                                           'start_on',
                                                                           'export',
                                                                           'destroy',
                                                                           'make_into_template'],
                                                    'consoles': [],
                                                    'crash_dumps': [],
                                                    'current_operations': {},
                                                    'domarch': 'x32',
                                                    'domid': '-1',
                                                    'guest_metrics': 'OpaqueRef:NULL',
                                                    'is_a_template': False,
                                                    'is_control_domain': False,
                                                    'last_boot_CPU_flags': {},
                                                    'last_booted_record': '<value><struct><member><name>uuid</name><value>0a5bb7f9-8b2b-436e-8e5f-e157101ce7f1</value></member><member><name>allowed_operations</name><value><array><data><value>pause</value><value>clean_shutdown</value><value>clean_reboot</value><value>hard_shutdown</value><value>hard_reboot</value><value>suspend</value></data></array></value></member><member><name>current_operations</name><value><struct/></value></member><member><name>power_state</name><value>Running</value></member><member><name>name_label</name><value>rPath Appliance Platform - Linux Service import</value></member><member><name>name_description</name><value>Created by rPath rBuilder</value></member><member><name>user_version</name><value>0</value></member><member><name>is_a_template</name><value><boolean>0</boolean></value></member><member><name>suspend_VDI</name><value>OpaqueRef:NULL</value></member><member><name>resident_on</name><value>OpaqueRef:c401bb77-1e36-bc4d-0b4a-ffbd020555d3</value></member><member><name>affinity</name><value>OpaqueRef:c401bb77-1e36-bc4d-0b4a-ffbd020555d3</value></member><member><name>memory_static_max</name><value>268435456</value></member><member><name>memory_dynamic_max</name><value>268435456</value></member><member><name>memory_dynamic_min</name><value>268435456</value></member><member><name>memory_static_min</name><value>0</value></member><member><name>VCPUs_params</name><value><struct/></value></member><member><name>VCPUs_max</name><value>1</value></member><member><name>VCPUs_at_startup</name><value>1</value></member><member><name>actions_after_shutdown</name><value>destroy</value></member><member><name>actions_after_reboot</name><value>restart</value></member><member><name>actions_after_crash</name><value>destroy</value></member><member><name>consoles</name><value><array><data><value>OpaqueRef:3e2caef4-34b9-f39b-215c-3c98eedd68bc</value></data></array></value></member><member><name>VIFs</name><value><array><data/></array></value></member><member><name>VBDs</name><value><array><data><value>OpaqueRef:1f636eba-9920-3283-5a04-9a01d07732a9</value><value>OpaqueRef:de7ea258-cf55-f07b-22ff-aa5762b55d0d</value></data></array></value></member><member><name>crash_dumps</name><value><array><data/></array></value></member><member><name>VTPMs</name><value><array><data/></array></value></member><member><name>PV_bootloader</name><value>pygrub</value></member><member><name>PV_kernel</name><value/></member><member><name>PV_ramdisk</name><value/></member><member><name>PV_args</name><value/></member><member><name>PV_bootloader_args</name><value/></member><member><name>PV_legacy_args</name><value>root=/dev/xvda1 ro</value></member><member><name>HVM_boot_policy</name><value/></member><member><name>HVM_boot_params</name><value><struct/></value></member><member><name>HVM_shadow_multiplier</name><value><double>1</double></value></member><member><name>platform</name><value><struct><member><name>acpi</name><value>true</value></member><member><name>apic</name><value>true</value></member><member><name>nx</name><value>false</value></member><member><name>pae</name><value>true</value></member></struct></value></member><member><name>PCI_bus</name><value/></member><member><name>other_config</name><value><struct><member><name>last_shutdown_time</name><value>20081021T13:50:20Z</value></member><member><name>last_shutdown_action</name><value>Restart</value></member><member><name>last_shutdown_initiator</name><value>internal</value></member><member><name>last_shutdown_reason</name><value>rebooted</value></member><member><name>import_task</name><value>OpaqueRef:49842b60-2954-2005-fa16-76959587d1dd</value></member><member><name>mac_seed</name><value>a767e71a-a690-5f56-2e68-d6aa81e84588</value></member></struct></value></member><member><name>domid</name><value>8</value></member><member><name>domarch</name><value>x32</value></member><member><name>last_boot_CPU_flags</name><value><struct/></value></member><member><name>is_control_domain</name><value><boolean>0</boolean></value></member><member><name>metrics</name><value>OpaqueRef:a6743d44-bba1-1980-4362-439a72864f86</value></member><member><name>guest_metrics</name><value>OpaqueRef:NULL</value></member><member><name>last_booted_record</name><value/></member><member><name>recommendations</name><value/></member><member><name>xenstore_data</name><value><struct/></value></member></struct></value>',
                                                    'memory_dynamic_max': '268435456',
                                                    'memory_dynamic_min': '268435456',
                                                    'memory_static_max': '268435456',
                                                    'memory_static_min': '0',
                                                    'metrics': 'OpaqueRef:a6743d44-bba1-1980-4362-439a72864f86',
                                                    'name_description': 'Created by rPath rBuilder',
                                                    'name_label': 'rPath Appliance Platform - Linux Service import',
                                                    'other_config': {'import_task': 'OpaqueRef:49842b60-2954-2005-fa16-76959587d1dd',
                                                                     'last_shutdown_action': 'Destroy',
                                                                     'last_shutdown_initiator': 'external',
                                                                     'last_shutdown_reason': 'halted',
                                                                     'last_shutdown_time': '20081021T13:50:26Z',
                                                                     'mac_seed': 'a767e71a-a690-5f56-2e68-d6aa81e84588'},
                                                    'platform': {'acpi': 'true',
                                                                 'apic': 'true',
                                                                 'nx': 'false',
                                                                 'pae': 'true'},
                                                    'power_state': 'Halted',
                                                    'recommendations': '',
                                                    'resident_on': 'OpaqueRef:NULL',
                                                    'suspend_VDI': 'OpaqueRef:NULL',
                                                    'user_version': '0',
                                                    'uuid': '0a5bb7f9-8b2b-436e-8e5f-e157101ce7f1',
                                                    'xenstore_data': {}},
 'OpaqueRef:58ac4cbc-0e8b-50a1-781f-ad9c92107d0c': {'HVM_boot_params': {'order': 'cd'},
                                                    'HVM_boot_policy': 'BIOS order',
                                                    'HVM_shadow_multiplier': 1.0,
                                                    'PCI_bus': '',
                                                    'PV_args': '',
                                                    'PV_bootloader': 'pygrub',
                                                    'PV_bootloader_args': '',
                                                    'PV_kernel': '',
                                                    'PV_legacy_args': 'root=/dev/xvda1 ro',
                                                    'PV_ramdisk': '',
                                                    'VBDs': ['OpaqueRef:0510382e-c078-4cf0-e9fa-2730aec38efe',
                                                             'OpaqueRef:ac3e1861-d9cc-016b-7b7b-d3faf9f6fa49'],
                                                    'VCPUs_at_startup': '1',
                                                    'VCPUs_max': '1',
                                                    'VCPUs_params': {},
                                                    'VIFs': ['OpaqueRef:a97d77f1-6eb1-393d-6ce5-4e8b71c3eb65'],
                                                    'VTPMs': [],
                                                    'actions_after_crash': 'destroy',
                                                    'actions_after_reboot': 'restart',
                                                    'actions_after_shutdown': 'destroy',
                                                    'affinity': 'OpaqueRef:NULL',
                                                    'allowed_operations': ['hard_shutdown',
                                                                           'resume',
                                                                           'resume_on',
                                                                           'export'],
                                                    'consoles': [],
                                                    'crash_dumps': [],
                                                    'current_operations': {},
                                                    'domarch': 'hvm',
                                                    'domid': '-1',
                                                    'guest_metrics': 'OpaqueRef:NULL',
                                                    'is_a_template': False,
                                                    'is_control_domain': False,
                                                    'last_boot_CPU_flags': {},
                                                    'last_booted_record': '<value><struct><member><name>uuid</name><value>1fce577a-f49c-f956-cbdf-45ffae28fd02</value></member><member><name>allowed_operations</name><value><array><data><value>pause</value><value>hard_shutdown</value><value>hard_reboot</value><value>suspend</value></data></array></value></member><member><name>current_operations</name><value><struct/></value></member><member><name>power_state</name><value>Running</value></member><member><name>name_label</name><value>Support Issue replication import</value></member><member><name>name_description</name><value>Created by rPath rBuilder</value></member><member><name>user_version</name><value>0</value></member><member><name>is_a_template</name><value><boolean>0</boolean></value></member><member><name>suspend_VDI</name><value>OpaqueRef:NULL</value></member><member><name>resident_on</name><value>OpaqueRef:c401bb77-1e36-bc4d-0b4a-ffbd020555d3</value></member><member><name>affinity</name><value>OpaqueRef:NULL</value></member><member><name>memory_static_max</name><value>268435456</value></member><member><name>memory_dynamic_max</name><value>268435456</value></member><member><name>memory_dynamic_min</name><value>268435456</value></member><member><name>memory_static_min</name><value>0</value></member><member><name>VCPUs_params</name><value><struct/></value></member><member><name>VCPUs_max</name><value>1</value></member><member><name>VCPUs_at_startup</name><value>1</value></member><member><name>actions_after_shutdown</name><value>destroy</value></member><member><name>actions_after_reboot</name><value>restart</value></member><member><name>actions_after_crash</name><value>destroy</value></member><member><name>consoles</name><value><array><data><value>OpaqueRef:a98c9104-104b-9bf7-a04d-aac335ea5a96</value></data></array></value></member><member><name>VIFs</name><value><array><data><value>OpaqueRef:a97d77f1-6eb1-393d-6ce5-4e8b71c3eb65</value></data></array></value></member><member><name>VBDs</name><value><array><data><value>OpaqueRef:0510382e-c078-4cf0-e9fa-2730aec38efe</value><value>OpaqueRef:ac3e1861-d9cc-016b-7b7b-d3faf9f6fa49</value></data></array></value></member><member><name>crash_dumps</name><value><array><data/></array></value></member><member><name>VTPMs</name><value><array><data/></array></value></member><member><name>PV_bootloader</name><value>pygrub</value></member><member><name>PV_kernel</name><value/></member><member><name>PV_ramdisk</name><value/></member><member><name>PV_args</name><value/></member><member><name>PV_bootloader_args</name><value/></member><member><name>PV_legacy_args</name><value>root=/dev/xvda1 ro</value></member><member><name>HVM_boot_policy</name><value>BIOS order</value></member><member><name>HVM_boot_params</name><value><struct><member><name>order</name><value>cd</value></member></struct></value></member><member><name>HVM_shadow_multiplier</name><value><double>1</double></value></member><member><name>platform</name><value><struct><member><name>timeoffset</name><value>0</value></member><member><name>acpi</name><value>true</value></member><member><name>apic</name><value>true</value></member><member><name>nx</name><value>false</value></member><member><name>pae</name><value>true</value></member></struct></value></member><member><name>PCI_bus</name><value/></member><member><name>other_config</name><value><struct><member><name>last_shutdown_time</name><value>20080923T17:48:01Z</value></member><member><name>last_shutdown_action</name><value>Restart</value></member><member><name>last_shutdown_initiator</name><value>internal</value></member><member><name>last_shutdown_reason</name><value>rebooted</value></member><member><name>import_task</name><value>OpaqueRef:6eb02946-82e6-b390-b18e-80eed76416fe</value></member><member><name>mac_seed</name><value>05b6b192-6435-7c58-7840-fedf8a76b738</value></member></struct></value></member><member><name>domid</name><value>4</value></member><member><name>domarch</name><value>hvm</value></member><member><name>last_boot_CPU_flags</name><value><struct/></value></member><member><name>is_control_domain</name><value><boolean>0</boolean></value></member><member><name>metrics</name><value>OpaqueRef:464a4be0-4e79-237d-5604-3a08278c9371</value></member><member><name>guest_metrics</name><value>OpaqueRef:NULL</value></member><member><name>last_booted_record</name><value/></member><member><name>recommendations</name><value/></member><member><name>xenstore_data</name><value><struct/></value></member></struct></value>',
                                                    'memory_dynamic_max': '268435456',
                                                    'memory_dynamic_min': '268435456',
                                                    'memory_static_max': '268435456',
                                                    'memory_static_min': '0',
                                                    'metrics': 'OpaqueRef:464a4be0-4e79-237d-5604-3a08278c9371',
                                                    'name_description': 'Created by rPath rBuilder',
                                                    'name_label': 'Support Issue replication import',
                                                    'other_config': {'import_task': 'OpaqueRef:6eb02946-82e6-b390-b18e-80eed76416fe',
                                                                     'last_shutdown_action': 'Restart',
                                                                     'last_shutdown_initiator': 'internal',
                                                                     'last_shutdown_reason': 'rebooted',
                                                                     'last_shutdown_time': '20080923T17:48:01Z',
                                                                     'mac_seed': '05b6b192-6435-7c58-7840-fedf8a76b738'},
                                                    'platform': {'acpi': 'true',
                                                                 'apic': 'true',
                                                                 'nx': 'false',
                                                                 'pae': 'true',
                                                                 'timeoffset': '-2'},
                                                    'power_state': 'Suspended',
                                                    'recommendations': '',
                                                    'resident_on': 'OpaqueRef:NULL',
                                                    'suspend_VDI': 'OpaqueRef:2e565380-d625-2c64-51fd-ee813de980d1',
                                                    'user_version': '0',
                                                    'uuid': '1fce577a-f49c-f956-cbdf-45ffae28fd02',
                                                    'xenstore_data': {}},
 'OpaqueRef:e7e9a1c2-4e01-8535-606b-27b31cf56a76': {'HVM_boot_params': {},
                                                    'HVM_boot_policy': '',
                                                    'HVM_shadow_multiplier': 1.0,
                                                    'PCI_bus': '',
                                                    'PV_args': '',
                                                    'PV_bootloader': 'pygrub',
                                                    'PV_bootloader_args': '',
                                                    'PV_kernel': '',
                                                    'PV_legacy_args': 'root=/dev/xvda1 ro',
                                                    'PV_ramdisk': '',
                                                    'VBDs': ['OpaqueRef:49bd11f7-ac82-e9d7-c115-98f4c572e91c',
                                                             'OpaqueRef:f33d54db-5d88-c0d7-a87a-eb100b05317f',
                                                             'OpaqueRef:e1b3b582-21fe-8d22-caa0-be8964bedfb7'],
                                                    'VCPUs_at_startup': '1',
                                                    'VCPUs_max': '1',
                                                    'VCPUs_params': {},
                                                    'VIFs': ['OpaqueRef:acf08183-8028-b9e9-4279-21417e5ec644'],
                                                    'VTPMs': [],
                                                    'actions_after_crash': 'destroy',
                                                    'actions_after_reboot': 'restart',
                                                    'actions_after_shutdown': 'destroy',
                                                    'affinity': 'OpaqueRef:c401bb77-1e36-bc4d-0b4a-ffbd020555d3',
                                                    'allowed_operations': ['pause',
                                                                           'clean_shutdown',
                                                                           'clean_reboot',
                                                                           'hard_shutdown',
                                                                           'hard_reboot',
                                                                           'suspend'],
                                                    'consoles': ['OpaqueRef:63c90947-8a92-04a5-1b96-1a0831124d6a'],
                                                    'crash_dumps': [],
                                                    'current_operations': {},
                                                    'domarch': 'x32',
                                                    'domid': '1',
                                                    'guest_metrics': 'OpaqueRef:GuestMetricsNetworks2',
                                                    'is_a_template': False,
                                                    'is_control_domain': False,
                                                    'last_boot_CPU_flags': {},
                                                    'last_booted_record': '<value><struct><member><name>uuid</name><value>98aef2dc-e6f3-803c-f490-791b847d3a3e</value></member><member><name>allowed_operations</name><value><array><data/></array></value></member><member><name>current_operations</name><value><struct><member><name>OpaqueRef:a50fea9c-e668-a523-090e-549dcebfb8c4</name><value>start</value></member></struct></value></member><member><name>power_state</name><value>Halted</value></member><member><name>name_label</name><value>rpath update service import</value></member><member><name>name_description</name><value>Created by rPath rBuilder</value></member><member><name>user_version</name><value>0</value></member><member><name>is_a_template</name><value><boolean>0</boolean></value></member><member><name>suspend_VDI</name><value>OpaqueRef:NULL</value></member><member><name>resident_on</name><value>OpaqueRef:NULL</value></member><member><name>affinity</name><value>OpaqueRef:c401bb77-1e36-bc4d-0b4a-ffbd020555d3</value></member><member><name>memory_static_max</name><value>268435456</value></member><member><name>memory_dynamic_max</name><value>268435456</value></member><member><name>memory_dynamic_min</name><value>268435456</value></member><member><name>memory_static_min</name><value>0</value></member><member><name>VCPUs_params</name><value><struct/></value></member><member><name>VCPUs_max</name><value>1</value></member><member><name>VCPUs_at_startup</name><value>1</value></member><member><name>actions_after_shutdown</name><value>destroy</value></member><member><name>actions_after_reboot</name><value>restart</value></member><member><name>actions_after_crash</name><value>destroy</value></member><member><name>consoles</name><value><array><data/></array></value></member><member><name>VIFs</name><value><array><data><value>OpaqueRef:acf08183-8028-b9e9-4279-21417e5ec644</value></data></array></value></member><member><name>VBDs</name><value><array><data><value>OpaqueRef:49bd11f7-ac82-e9d7-c115-98f4c572e91c</value><value>OpaqueRef:f33d54db-5d88-c0d7-a87a-eb100b05317f</value><value>OpaqueRef:e1b3b582-21fe-8d22-caa0-be8964bedfb7</value></data></array></value></member><member><name>crash_dumps</name><value><array><data/></array></value></member><member><name>VTPMs</name><value><array><data/></array></value></member><member><name>PV_bootloader</name><value>pygrub</value></member><member><name>PV_kernel</name><value/></member><member><name>PV_ramdisk</name><value/></member><member><name>PV_args</name><value/></member><member><name>PV_bootloader_args</name><value/></member><member><name>PV_legacy_args</name><value>root=/dev/xvda1 ro</value></member><member><name>HVM_boot_policy</name><value/></member><member><name>HVM_boot_params</name><value><struct/></value></member><member><name>HVM_shadow_multiplier</name><value><double>1</double></value></member><member><name>platform</name><value><struct><member><name>acpi</name><value>true</value></member><member><name>apic</name><value>true</value></member><member><name>nx</name><value>false</value></member><member><name>pae</name><value>true</value></member></struct></value></member><member><name>PCI_bus</name><value/></member><member><name>other_config</name><value><struct><member><name>last_shutdown_time</name><value>20081023T15:57:26Z</value></member><member><name>last_shutdown_action</name><value>Destroy</value></member><member><name>last_shutdown_initiator</name><value>external</value></member><member><name>last_shutdown_reason</name><value>halted</value></member><member><name>import_task</name><value>OpaqueRef:f8c00164-848a-7816-3f7b-856731d4074b</value></member><member><name>mac_seed</name><value>8e9836b0-5637-0961-2b79-6b8a0ebdd440</value></member></struct></value></member><member><name>domid</name><value>-1</value></member><member><name>domarch</name><value>x32</value></member><member><name>last_boot_CPU_flags</name><value><struct/></value></member><member><name>is_control_domain</name><value><boolean>0</boolean></value></member><member><name>metrics</name><value>OpaqueRef:dc508953-8d2e-2cf6-1581-694296190d99</value></member><member><name>guest_metrics</name><value>OpaqueRef:NULL</value></member><member><name>last_booted_record</name><value/></member><member><name>recommendations</name><value/></member><member><name>xenstore_data</name><value><struct/></value></member></struct></value>',
                                                    'memory_dynamic_max': '268435456',
                                                    'memory_dynamic_min': '268435456',
                                                    'memory_static_max': '268435456',
                                                    'memory_static_min': '0',
                                                    'metrics': 'OpaqueRef:0226e077-10f1-7efc-a6a7-aa2f6b83a9b6',
                                                    'name_description': 'Created by rPath rBuilder',
                                                    'name_label': 'rpath update service import',
                                                    'other_config': {'import_task': 'OpaqueRef:f8c00164-848a-7816-3f7b-856731d4074b',
                                                                     'last_shutdown_action': 'Destroy',
                                                                     'last_shutdown_initiator': 'external',
                                                                     'last_shutdown_reason': 'halted',
                                                                     'last_shutdown_time': '20081023T15:57:26Z',
                                                                     'mac_seed': '8e9836b0-5637-0961-2b79-6b8a0ebdd440'},
                                                    'platform': {'acpi': 'true',
                                                                 'apic': 'true',
                                                                 'nx': 'false',
                                                                 'pae': 'true'},
                                                    'power_state': 'Running',
                                                    'recommendations': '',
                                                    'resident_on': 'OpaqueRef:c401bb77-1e36-bc4d-0b4a-ffbd020555d3',
                                                    'suspend_VDI': 'OpaqueRef:NULL',
                                                    'user_version': '0',
                                                    'uuid': '98aef2dc-e6f3-803c-f490-791b847d3a3e',
                                                    'xenstore_data': {}}}
}, )

xenent_listImages1 = ({'Status' : 'Success',
 'Value' : {
 'OpaqueRef:6bc2d696-20e6-2d91-b205-29539f669793': {'HVM_boot_params': {},
                                                    'HVM_boot_policy': '',
                                                    'HVM_shadow_multiplier': 1.0,
                                                    'PCI_bus': '',
                                                    'PV_args': 'graphical utf8',
                                                    'PV_bootloader': 'eliloader',
                                                    'PV_bootloader_args': '',
                                                    'PV_kernel': '',
                                                    'PV_legacy_args': '',
                                                    'PV_ramdisk': '',
                                                    'VBDs': [],
                                                    'VCPUs_at_startup': '1',
                                                    'VCPUs_max': '1',
                                                    'VCPUs_params': {},
                                                    'VIFs': [],
                                                    'VTPMs': [],
                                                    'actions_after_crash': 'restart',
                                                    'actions_after_reboot': 'restart',
                                                    'actions_after_shutdown': 'destroy',
                                                    'affinity': 'OpaqueRef:NULL',
                                                    'allowed_operations': ['clone',
                                                                           'export',
                                                                           'provision'],
                                                    'consoles': [],
                                                    'crash_dumps': [],
                                                    'current_operations': {},
                                                    'domarch': '',
                                                    'domid': '-1',
                                                    'guest_metrics': 'OpaqueRef:NULL',
                                                    'is_a_template': True,
                                                    'is_control_domain': False,
                                                    'last_boot_CPU_flags': {},
                                                    'last_booted_record': '',
                                                    'memory_dynamic_max': '268435456',
                                                    'memory_dynamic_min': '268435456',
                                                    'memory_static_max': '268435456',
                                                    'memory_static_min': '16777216',
                                                    'metrics': 'OpaqueRef:85f98c55-b476-9b99-f261-39bded757a65',
                                                    'name_description': 'Template that allows VM installation from Xen-aware EL-based distros.  To use this template from the CLI, install your VM using vm-install, then set other-config-install-repository to the path to your network repository, e.g. http://<server>/<path> or nfs:server:/<path>',
                                                    'name_label': 'Oracle Enterprise Linux 5.0',
                                                    'other_config': {'default_template': 'true',
                                                                     'disks': '<provision>\n  <disk device="0"  size="8589934592"  sr=""  bootable="true"  type="system"/>\n</provision>',
                                                                     'install-distro': 'rhlike',
                                                                     'linux_template': 'true',
                                                                     'mac_seed': '7522d631-57e7-3979-6698-230c4212e683',
                                                                     'rhel5': 'true',
                                                                     'cloud-catalog-checksum' : '0903de41206786d4407ff24ab6e972c0d6b801f3'},
                                                    'platform': {'acpi': 'true',
                                                                 'apic': 'true',
                                                                 'nx': 'false',
                                                                 'pae': 'true'},
                                                    'power_state': 'Halted',
                                                    'recommendations': '<restrictions><restriction field="memory-static-max" max="34359738368" /><restriction field="vcpus-max" max="8" /><restriction property="number-of-vbds" max="7" /><restriction property="number-of-vifs" max="3" /></restrictions>',
                                                    'resident_on': 'OpaqueRef:NULL',
                                                    'suspend_VDI': 'OpaqueRef:NULL',
                                                    'user_version': '1',
                                                    'uuid': '52f75c4d-9782-15a2-6f76-a96a71d3d9b1',
                                                    'xenstore_data': {}},
 'OpaqueRef:73f00dc0-71d4-260c-6d6d-b04727afa7a7': {'HVM_boot_params': {},
                                                    'HVM_boot_policy': '',
                                                    'HVM_shadow_multiplier': 1.0,
                                                    'PCI_bus': '',
                                                    'PV_args': 'graphical utf8',
                                                    'PV_bootloader': 'eliloader',
                                                    'PV_bootloader_args': '',
                                                    'PV_kernel': '',
                                                    'PV_legacy_args': '',
                                                    'PV_ramdisk': '',
                                                    'VBDs': [],
                                                    'VCPUs_at_startup': '1',
                                                    'VCPUs_max': '1',
                                                    'VCPUs_params': {},
                                                    'VIFs': [],
                                                    'VTPMs': [],
                                                    'actions_after_crash': 'restart',
                                                    'actions_after_reboot': 'restart',
                                                    'actions_after_shutdown': 'destroy',
                                                    'affinity': 'OpaqueRef:NULL',
                                                    'allowed_operations': ['clone',
                                                                           'export',
                                                                           'provision'],
                                                    'consoles': [],
                                                    'crash_dumps': [],
                                                    'current_operations': {},
                                                    'domarch': '',
                                                    'domid': '-1',
                                                    'guest_metrics': 'OpaqueRef:NULL',
                                                    'is_a_template': True,
                                                    'is_control_domain': False,
                                                    'last_boot_CPU_flags': {},
                                                    'last_booted_record': '',
                                                    'memory_dynamic_max': '268435456',
                                                    'memory_dynamic_min': '268435456',
                                                    'memory_static_max': '268435456',
                                                    'memory_static_min': '16777216',
                                                    'metrics': 'OpaqueRef:242ec0ae-e27a-9b0f-62ea-d84b354790d9',
                                                    'name_description': 'Template that allows VM installation from Xen-aware EL-based distros.  To use this template from the CLI, install your VM using vm-install, then set other-config-install-repository to the path to your network repository, e.g. http://<server>/<path> or nfs:server:/<path>',
                                                    'name_label': 'Oracle Enterprise Linux 5.0 x64',
                                                    'other_config': {'default_template': 'true',
                                                                     'disks': '<provision>\n  <disk device="0"  size="8589934592"  sr=""  bootable="true"  type="system"/>\n</provision>',
                                                                     'install-distro': 'rhlike',
                                                                     'linux_template': 'true',
                                                                     'mac_seed': '3b6a4e05-9622-189b-c1ce-d5cfb8383e03',
                                                                     'rhel5': 'true'},
                                                    'platform': {'acpi': 'true',
                                                                 'apic': 'true',
                                                                 'nx': 'false',
                                                                 'pae': 'true'},
                                                    'power_state': 'Halted',
                                                    'recommendations': '<restrictions><restriction field="memory-static-max" max="34359738368" /><restriction field="vcpus-max" max="8" /><restriction property="number-of-vbds" max="7" /><restriction property="number-of-vifs" max="3" /></restrictions>',
                                                    'resident_on': 'OpaqueRef:NULL',
                                                    'suspend_VDI': 'OpaqueRef:NULL',
                                                    'user_version': '1',
                                                    'uuid': 'd0bf8f0e-afce-d9fb-8121-e9e174a7c99b',
                                                    'xenstore_data': {}},
 'OpaqueRef:fe960786-d6bf-8852-33fc-c6b7561d158e': {'HVM_boot_params': {},
                                                    'HVM_boot_policy': '',
                                                    'HVM_shadow_multiplier': 1.0,
                                                    'PCI_bus': '',
                                                    'PV_args': 'graphical utf8',
                                                    'PV_bootloader': 'eliloader',
                                                    'PV_bootloader_args': '',
                                                    'PV_kernel': '',
                                                    'PV_legacy_args': '',
                                                    'PV_ramdisk': '',
                                                    'VBDs': [],
                                                    'VCPUs_at_startup': '1',
                                                    'VCPUs_max': '1',
                                                    'VCPUs_params': {},
                                                    'VIFs': [],
                                                    'VTPMs': [],
                                                    'actions_after_crash': 'restart',
                                                    'actions_after_reboot': 'restart',
                                                    'actions_after_shutdown': 'destroy',
                                                    'affinity': 'OpaqueRef:NULL',
                                                    'allowed_operations': ['clone',
                                                                           'export',
                                                                           'provision'],
                                                    'consoles': [],
                                                    'crash_dumps': [],
                                                    'current_operations': {},
                                                    'domarch': '',
                                                    'domid': '-1',
                                                    'guest_metrics': 'OpaqueRef:NULL',
                                                    'is_a_template': True,
                                                    'is_control_domain': False,
                                                    'last_boot_CPU_flags': {},
                                                    'last_booted_record': '',
                                                    'memory_dynamic_max': '268435456',
                                                    'memory_dynamic_min': '268435456',
                                                    'memory_static_max': '268435456',
                                                    'memory_static_min': '16777216',
                                                    'metrics': 'OpaqueRef:0361c897-b7a3-6c4c-c56a-46f6eb304a62',
                                                    'name_description': 'Template that allows VM installation from Xen-aware EL-based distros.  To use this template from the CLI, install your VM using vm-install, then set other-config-install-repository to the path to your network repository, e.g. http://<server>/<path> or nfs:server:/<path>',
                                                    'name_label': 'CentOS 5.1',
                                                    'other_config': {'default_template': 'true',
                                                                     'disks': '<provision>\n  <disk device="0"  size="8589934592"  sr=""  bootable="true"  type="system"/>\n</provision>',
                                                                     'install-distro': 'rhlike',
                                                                     'linux_template': 'true',
                                                                     'mac_seed': 'cc97f486-1f65-1d8b-a822-fa92fd4eb436',
                                                                     'rhel5': 'true'},
                                                    'platform': {'acpi': 'true',
                                                                 'apic': 'true',
                                                                 'nx': 'false',
                                                                 'pae': 'true'},
                                                    'power_state': 'Halted',
                                                    'recommendations': '<restrictions><restriction field="memory-static-max" max="34359738368" /><restriction field="vcpus-max" max="8" /><restriction property="number-of-vbds" max="7" /><restriction property="number-of-vifs" max="3" /></restrictions>',
                                                    'resident_on': 'OpaqueRef:NULL',
                                                    'suspend_VDI': 'OpaqueRef:NULL',
                                                    'user_version': '1',
                                                    'uuid': 'c4664768-622b-8ab7-a76f-5a1c62c2688f',
                                                    'xenstore_data': {}}}

}, )

xenent_SR_get_uuid1 = ({'Status' : 'Error',
    'ErrorDescription' : ['HANDLE_INVALID', 'blah', 'blah'],
}, )

xenent_SR_get_uuid2 = ({'Status' : 'Success',
  'Value' : 'b9e4d88e-88e9-3a2e-92ff-4b180f3fee5d',
}, )

xenent_SR_get_by_uuid1 = ({'Status' : 'Success',
  'Value' : 'OpaqueRef:SRref1',
}, )

xenent_listSRs1 = ({'Status' : 'Success',
  'Value' : {
  'OpaqueRef:2d7dcc1f-cc36-5dc1-453f-a96334eaa2d9' : {   'PBDs': ['OpaqueRef:cc5527aa-6105-3205-0ffd-47f2734b432d'],
    'VDIs': ['OpaqueRef:1e6f2442-f6c3-2f69-3a1b-babcf8efc2f2'],
    'allowed_operations': [   'forget',
                              'vdi_introduce',
                              'plug',
                              'destroy',
                              'scan',
                              'vdi_clone',
                              'unplug'],
    'content_type': 'iso',
    'current_operations': {},
    'name_description': 'Physical DVD drives',
    'name_label': 'DVD drives',
    'other_config': {   'i18n-key': 'local-hotplug-cd',
                        'i18n-original-value-name_description': 'Physical DVD drives',
                        'i18n-original-value-name_label': 'DVD drives'},
    'physical_size': '0',
    'physical_utilisation': '0',
    'shared': False,
    'sm_config': {'type': 'cd'},
    'type': 'udev',
    'uuid': 'e60e7e6f-e652-4b13-d03b-4591e3208347',
    'virtual_allocation': '0'},
  'OpaqueRef:3f9b7d5d-30d8-a8c9-8e11-106125f8e072' : {   'PBDs': ['OpaqueRef:0f7d8062-dddc-0812-7c5c-ec92dde30d71'],
    'VDIs': [],
    'allowed_operations': [   'forget',
                              'vdi_introduce',
                              'plug',
                              'destroy',
                              'scan',
                              'vdi_clone',
                              'unplug'],
    'content_type': 'disk',
    'current_operations': {},
    'name_description': '',
    'name_label': 'Removable storage',
    'other_config': {   'i18n-key': 'local-hotplug-disk',
                        'i18n-original-value-name_label': 'Removable storage'},
    'physical_size': '0',
    'physical_utilisation': '0',
    'shared': False,
    'sm_config': {'type': 'block'},
    'type': 'udev',
    'uuid': 'ca9738cc-2bf4-532c-3ad4-ddbb1e528fd0',
    'virtual_allocation': '0'},
  'OpaqueRef:46f2bd9d-8159-6a7e-cbbd-e34836484213' : {   'PBDs': [],
    'VDIs': [],
    'allowed_operations': [   'forget',
                              'vdi_create',
                              'plug',
                              'destroy',
                              'vdi_destroy',
                              'scan',
                              'vdi_clone',
                              'vdi_resize',
                              'unplug'],
    'content_type': 'user',
    'current_operations': {},
    'name_description': '',
    'name_label': 'Local storage',
    'other_config': {   'i18n-key': 'local-storage',
                        'i18n-original-value-name_label': 'Local storage'},
    'physical_size': '71777124352',
    'physical_utilisation': '0',
    'shared': False,
    'sm_config': {'devserial': 'scsi-SATA_WDC_WD800JD-75M_WD-WMAM9EP32932,'},
    'type': 'lvm',
    'uuid': '0df2c7c2-1758-1f26-1dfc-601a6cf8a42b',
    'virtual_allocation': '0'},
  'OpaqueRef:7ef07046-77d8-0675-ede5-29787aaaf142' : {   'PBDs': [],
    'VDIs': [],
    'allowed_operations': [   'forget',
                              'vdi_create',
                              'plug',
                              'destroy',
                              'vdi_destroy',
                              'scan',
                              'vdi_clone',
                              'vdi_resize',
                              'unplug'],
    'content_type': 'user',
    'current_operations': {},
    'name_description': '',
    'name_label': 'Local storage',
    'other_config': {   'i18n-key': 'local-storage',
                        'i18n-original-value-name_label': 'Local storage'},
    'physical_size': '32887537664',
    'physical_utilisation': '0',
    'shared': False,
    'sm_config': {'devserial': 'scsi-SATA_Maxtor_6E040L0_E154HKCN_,'},
    'type': 'lvm',
    'uuid': '22aaa128-7b83-cc8a-c01d-18ff9009142b',
    'virtual_allocation': '0'},
  'OpaqueRef:92cc15d2-ec5a-d79d-3cff-b38f5fe435ae' : {   'PBDs': [],
    'VDIs': ['OpaqueRef:fb15bf1e-d2ba-a8e1-1fa4-6c30101822ed'],
    'allowed_operations': [   'forget',
                              'vdi_introduce',
                              'plug',
                              'destroy',
                              'scan',
                              'vdi_clone',
                              'unplug'],
    'content_type': 'iso',
    'current_operations': {},
    'name_description': 'Physical DVD drives',
    'name_label': 'DVD drives',
    'other_config': {   'i18n-key': 'local-hotplug-cd',
                        'i18n-original-value-name_description': 'Physical DVD drives',
                        'i18n-original-value-name_label': 'DVD drives'},
    'physical_size': '0',
    'physical_utilisation': '0',
    'shared': False,
    'sm_config': {'type': 'cd'},
    'type': 'udev',
    'uuid': 'dbb4639f-87f1-e772-8578-a1d955f52976',
    'virtual_allocation': '0'},
  'OpaqueRef:932fc07a-a7be-8b1b-1789-14b8a00c69fe' : {   'PBDs': [],
    'VDIs': [],
    'allowed_operations': [   'forget',
                              'vdi_introduce',
                              'plug',
                              'destroy',
                              'scan',
                              'vdi_clone',
                              'unplug'],
    'content_type': 'disk',
    'current_operations': {},
    'name_description': '',
    'name_label': 'Removable storage',
    'other_config': {   'i18n-key': 'local-hotplug-disk',
                        'i18n-original-value-name_label': 'Removable storage'},
    'physical_size': '0',
    'physical_utilisation': '0',
    'shared': False,
    'sm_config': {'type': 'block'},
    'type': 'udev',
    'uuid': '42eb8b31-a4fc-0fad-514f-57f3cb24b932',
    'virtual_allocation': '0'},
  'OpaqueRef:98afcf45-dcd2-abdf-06ca-4fb538e2a8ff' : {   'PBDs': [   'OpaqueRef:39b5e70a-ef4e-815c-33e4-f5832f6a0cdc',
                'OpaqueRef:3c63aa29-44c5-66f7-9cce-90d929fda786'],
    'VDIs': ['OpaqueRef:9971d594-e3a5-9178-1bae-8600e7ce51f1'],
    'allowed_operations': [   'forget',
                              'plug',
                              'destroy',
                              'scan',
                              'vdi_clone',
                              'unplug'],
    'content_type': 'iso',
    'current_operations': {},
    'name_description': 'XenServer Tools ISOs',
    'name_label': 'XenServer Tools',
    'other_config': {   'i18n-key': 'xenserver-tools',
                        'i18n-original-value-name_description': 'XenServer Tools ISOs',
                        'i18n-original-value-name_label': 'XenServer Tools',
                        'xenserver_tools_sr': 'true',
                        'xensource_internal': 'true'},
    'physical_size': '-1',
    'physical_utilisation': '-1',
    'shared': True,
    'sm_config': {},
    'type': 'iso',
    'uuid': 'cfbd5bde-aa76-08df-7bd0-ab17921a8a21',
    'virtual_allocation': '0'},
  'OpaqueRef:ad59a0ed-34e9-8cef-aad7-c2473d15cb2f' : {   'PBDs': ['OpaqueRef:0a39bcef-fd0d-4a38-efc6-1a06c731ee06'],
    'VDIs': ['OpaqueRef:bbffedcb-9b89-dd45-7491-8ba957b1b518'],
    'allowed_operations': [   'forget',
                              'vdi_introduce',
                              'plug',
                              'destroy',
                              'scan',
                              'vdi_clone',
                              'unplug'],
    'content_type': 'iso',
    'current_operations': {},
    'name_description': 'Physical DVD drives',
    'name_label': 'DVD drives',
    'other_config': {   'i18n-key': 'local-hotplug-cd',
                        'i18n-original-value-name_description': 'Physical DVD drives',
                        'i18n-original-value-name_label': 'DVD drives'},
    'physical_size': '0',
    'physical_utilisation': '0',
    'shared': False,
    'sm_config': {'type': 'cd'},
    'type': 'udev',
    'uuid': 'a6264012-4943-1c05-cb7b-4255d7a59b1d',
    'virtual_allocation': '0'},
  'OpaqueRef:af31d19a-de35-2810-8d38-1b581923c544' : {   'PBDs': ['OpaqueRef:2bd110df-4847-0baa-72a7-2bb6b8821b88'],
    'VDIs': [],
    'allowed_operations': [   'forget',
                              'vdi_introduce',
                              'plug',
                              'destroy',
                              'scan',
                              'vdi_clone',
                              'unplug'],
    'content_type': 'disk',
    'current_operations': {},
    'name_description': '',
    'name_label': 'Removable storage',
    'other_config': {   'i18n-key': 'local-hotplug-disk',
                        'i18n-original-value-name_label': 'Removable storage'},
    'physical_size': '0',
    'physical_utilisation': '0',
    'shared': False,
    'sm_config': {'type': 'block'},
    'type': 'udev',
    'uuid': 'c3ac762b-d8c3-2786-cba4-624067159d8b',
    'virtual_allocation': '0'},
  'OpaqueRef:b02a184c-cd4f-3447-55ee-ee47e3761b63' : {   'PBDs': ['OpaqueRef:pbd2'],
    'VDIs': [],
    'allowed_operations': [   'forget',
                              'vdi_create',
                              'plug',
                              'destroy',
                              'vdi_destroy',
                              'scan',
                              'vdi_clone',
                              'vdi_resize',
                              'unplug'],
    'content_type': 'user',
    'current_operations': {},
    'name_description': '',
    'name_label': 'Local storage',
    'other_config': {   'i18n-key': 'local-storage',
                        'i18n-original-value-name_label': 'Local storage'},
    'physical_size': '71777124352',
    'physical_utilisation': '0',
    'shared': False,
    'sm_config': {'devserial': 'scsi-SATA_WDC_WD800JD-75M_WD-WMAM9EP32932,'},
    'type': 'lvm',
    'uuid': 'b9e4d88e-88e9-3a2e-92ff-4b180f3fee5d',
    'virtual_allocation': '0'},
  'OpaqueRef:bac48d71-604e-0602-1f56-a5e3b92faac6' : {   'PBDs': [],
    'VDIs': ['OpaqueRef:8377adbe-cc7e-322e-6524-43af3e9037a2'],
    'allowed_operations': [   'forget',
                              'vdi_introduce',
                              'plug',
                              'destroy',
                              'scan',
                              'vdi_clone',
                              'unplug'],
    'content_type': 'iso',
    'current_operations': {},
    'name_description': 'Physical DVD drives',
    'name_label': 'DVD drives',
    'other_config': {   'i18n-key': 'local-hotplug-cd',
                        'i18n-original-value-name_description': 'Physical DVD drives',
                        'i18n-original-value-name_label': 'DVD drives'},
    'physical_size': '0',
    'physical_utilisation': '0',
    'shared': False,
    'sm_config': {'type': 'cd'},
    'type': 'udev',
    'uuid': '25bc59e5-5bf6-259b-224f-60a1494db77a',
    'virtual_allocation': '0'},
  'OpaqueRef:bdd83fc7-e0ef-d1fd-5ca8-538a5fabdfde' : {   'PBDs': [   'OpaqueRef:e583c52e-9101-f069-4442-b3659a3fdb06',
                'OpaqueRef:24200ce4-d5be-9d32-8783-0d554e58b7d4'],
    'VDIs': [],
    'allowed_operations': [   'forget',
                              'vdi_create',
                              'vdi_snapshot',
                              'plug',
                              'destroy',
                              'vdi_destroy',
                              'scan',
                              'vdi_clone',
                              'unplug'],
    'content_type': '',
    'current_operations': {},
    'name_description': 'NFS SR [nas2.eng.rpath.com:/mnt/vg00/nfs-storage/vmware-images/proserv-xenstorage]',
    'name_label': 'NFS virtual disk storage',
    'other_config': {},
    'physical_size': '724237287424',
    'physical_utilisation': '326945996800',
    'shared': True,
    'sm_config': {},
    'type': 'nfs',
    'uuid': 'eab9d53e-ae74-9fa9-c5ff-edd32a944657',
    'virtual_allocation': '10308763648'},
  'OpaqueRef:c0dad8b9-29c0-f720-e323-10d179239fbc' : {   'PBDs': [],
    'VDIs': [],
    'allowed_operations': [   'forget',
                              'vdi_introduce',
                              'plug',
                              'destroy',
                              'scan',
                              'vdi_clone',
                              'unplug'],
    'content_type': 'disk',
    'current_operations': {},
    'name_description': '',
    'name_label': 'Removable storage',
    'other_config': {   'i18n-key': 'local-hotplug-disk',
                        'i18n-original-value-name_label': 'Removable storage'},
    'physical_size': '0',
    'physical_utilisation': '0',
    'shared': False,
    'sm_config': {'type': 'block'},
    'type': 'udev',
    'uuid': '610c6704-1924-d02b-93ef-30c69a8d6305',
    'virtual_allocation': '0'},
  'OpaqueRef:c6716ca5-2c3e-6058-f1db-ebb6c07111ce' : {   'PBDs': [   'OpaqueRef:a48839a7-dfe5-8467-0191-64364ee83d4d',
                'OpaqueRef:a1203f85-db07-a5c1-4638-d8eb523f0e33'],
    'VDIs': [   'OpaqueRef:86310568-4058-7370-772e-e9f7b3b31b95',
                'OpaqueRef:54c5bad9-34fe-41e5-6f14-59e7e3c04d65',
                'OpaqueRef:91bd2c1b-3616-8e97-6b94-e670474a177e'],
    'allowed_operations': [   'forget',
                              'vdi_create',
                              'vdi_snapshot',
                              'plug',
                              'destroy',
                              'vdi_destroy',
                              'scan',
                              'vdi_clone',
                              'unplug'],
    'content_type': '',
    'current_operations': {},
    'name_description': 'NFS SR [nas2.eng.rpath.com:/mnt/vg00/nfs-storage/vmware-images/proserv-xenstorage]',
    'name_label': 'nas2.eng',
    'other_config': {'auto-scan': 'false'},
    'physical_size': '724237287424',
    'physical_utilisation': '328078983168',
    'shared': True,
    'sm_config': {},
    'type': 'nfs',
    'uuid': '65168a01-302f-9886-a1b3-eb467e8a113b',
    'virtual_allocation': '9144664064'},
  'OpaqueRef:d3092446-160d-c2f8-ee55-8e90dc600b7c' : {   'PBDs': [],
    'VDIs': [],
    'allowed_operations': [   'forget',
                              'vdi_create',
                              'plug',
                              'destroy',
                              'vdi_destroy',
                              'scan',
                              'vdi_clone',
                              'vdi_resize',
                              'unplug'],
    'content_type': 'user',
    'current_operations': {},
    'name_description': '',
    'name_label': 'Local storage',
    'other_config': {   'i18n-key': 'local-storage',
                        'i18n-original-value-name_label': 'Local storage'},
    'physical_size': '31784435712',
    'physical_utilisation': '0',
    'shared': False,
    'sm_config': {'devserial': ''},
    'type': 'lvm',
    'uuid': '4145355e-be01-21c3-16b6-906d6b7b5e7b',
    'virtual_allocation': '0'},
  'OpaqueRef:dfa8ab18-d760-088b-8cef-5631ba90100e' : {   'PBDs': [],
    'VDIs': [],
    'allowed_operations': [   'forget',
                              'vdi_introduce',
                              'plug',
                              'destroy',
                              'scan',
                              'vdi_clone',
                              'unplug'],
    'content_type': 'disk',
    'current_operations': {},
    'name_description': '',
    'name_label': 'Removable storage',
    'other_config': {   'i18n-key': 'local-hotplug-disk',
                        'i18n-original-value-name_label': 'Removable storage'},
    'physical_size': '0',
    'physical_utilisation': '0',
    'shared': False,
    'sm_config': {'type': 'block'},
    'type': 'udev',
    'uuid': '9c1e4259-dbfb-e925-9066-a65741d4f696',
    'virtual_allocation': '0'},
  'OpaqueRef:e39b751d-723d-6a54-851c-f194f9381394' : {   'PBDs': ['OpaqueRef:pbd1'],
    'VDIs': [   'OpaqueRef:188363bf-2e4d-4d2e-a5e8-b034ef5f0475',
                'OpaqueRef:1e83f472-117b-e115-d537-a604b41e4eaa',
                'OpaqueRef:996b12c6-64c7-fd37-9e6f-0b1b8774fb05',
                'OpaqueRef:3f7dd941-f26b-ca60-07c7-b239068eabae',
                'OpaqueRef:0c27736b-5356-a259-cdbd-c025cd9012b7',
                'OpaqueRef:dfaf8758-4512-a9f5-f29e-a4661da9d4ad'],
    'allowed_operations': [   'forget',
                              'vdi_create',
                              'plug',
                              'destroy',
                              'vdi_destroy',
                              'scan',
                              'vdi_clone',
                              'vdi_resize',
                              'unplug'],
    'content_type': 'user',
    'current_operations': {},
    'name_description': '',
    'name_label': 'Local storage',
    'other_config': {   'i18n-key': 'local-storage',
                        'i18n-original-value-name_label': 'Local storage'},
    'physical_size': '111765618688',
    'physical_utilisation': '8120172544',
    'shared': False,
    'sm_config': {   'devserial': 'scsi-SATA_ST340014AS_5MQ2XDC0,scsi-SATA_ST380013AS_5MR4ZVK0,'},
    'type': 'lvm',
    'uuid': '494115e9-0901-9719-1a13-c0857fd4d3d8',
    'virtual_allocation': '8120172544'},
  'OpaqueRef:ecba0068-b84e-6e88-b9db-a92c6bc35ce4' : {   'PBDs': [],
    'VDIs': [],
    'allowed_operations': [   'forget',
                              'vdi_introduce',
                              'plug',
                              'destroy',
                              'scan',
                              'vdi_clone',
                              'unplug'],
    'content_type': 'iso',
    'current_operations': {},
    'name_description': 'Physical DVD drives',
    'name_label': 'DVD drives',
    'other_config': {   'i18n-key': 'local-hotplug-cd',
                        'i18n-original-value-name_description': 'Physical DVD drives',
                        'i18n-original-value-name_label': 'DVD drives'},
    'physical_size': '0',
    'physical_utilisation': '0',
    'shared': False,
    'sm_config': {'type': 'cd'},
    'type': 'udev',
    'uuid': '3ea386d4-fa35-bc20-f583-5137429973e7',
    'virtual_allocation': '0'},
    }
}, )

xenent_listSRs2 = ({'Status' : 'Success',
  'Value' : {
    }
}, )

xenent_listPools1 = ({'Status' : 'Success',
  'Value' : {
    'OpaqueRef:poolRef1': {
        'uuid': 'a534859a-903a-77b2-f9da-5e59eb79e906',
        'other_config': {},
        'name_label': 'Pool1',
        'suspend_image_SR': 'OpaqueRef:42a31524-adf9-ea49-a711-52e094ebba18',
        'crash_dump_SR': 'OpaqueRef:42a31524-adf9-ea49-a711-52e094ebba18',
        'master': 'OpaqueRef:d3565cb8-5de8-5562-a92a-6ce52fbde613',
        'default_SR': 'OpaqueRef:42a31524-adf9-ea49-a711-52e094ebba18',
        'name_description': ''
    }
  }
}, )

xenent_pool_get_all1 = ({'Status' : 'Success',
  'Value' : 'OpaqueRef:poolRef1',
}, )

xenent_pool_get_master1 = ({'Status' : 'Success',
  'Value' : 'OpaqueRef:poolMaster1',
}, )

xenent_VM_get_by_uuid1 = ({'Status' : 'Success',
    'Value' : 'OpaqueRef:aabbccdd1',
}, )

xenent_VM_get_name_label = ({'Status' : 'Success',
    'Value' : 'bob the builder',
}, )


xenent_VM_set_generic = ({'Status' : 'Success',
    'Value' : '',
}, )

xenent_VM_get_uuid1 = ({'Status' : 'Success',
  'Value' : 'VmUuid1',
}, )


xenent_VM_get_record1 = ({'Status' : 'Success',
  'Value' : {
  'HVM_boot_params' : {},
  'HVM_boot_policy' : '',
  'HVM_shadow_multiplier' : 1.0,
  'PCI_bus' : '',
  'PV_args' : '',
  'PV_bootloader' : 'pygrub',
  'PV_bootloader_args' : '',
  'PV_kernel' : '',
  'PV_legacy_args' : 'root=/dev/xvda1 ro',
  'PV_ramdisk' : '',
  'VBDs' : [   'OpaqueRef:vbd1', 'OpaqueRef:vbd2'],
  'VCPUs_at_startup' : '1',
  'VCPUs_max' : '1',
  'VCPUs_params' : {},
  'VIFs' : [],
  'VTPMs' : [],
  'actions_after_crash' : 'destroy',
  'actions_after_reboot' : 'restart',
  'actions_after_shutdown' : 'destroy',
  'affinity' : 'OpaqueRef:NULL',
  'allowed_operations' : [   'pause',
    'clean_shutdown',
    'clean_reboot',
    'hard_shutdown',
    'hard_reboot',
    'suspend'],
  'consoles' : ['OpaqueRef:cb7b6793-f7d9-7920-78dc-afeff0fe4e46'],
  'crash_dumps' : [],
  'current_operations' : {},
  'domarch' : 'x32',
  'domid' : '13',
  'guest_metrics' : 'OpaqueRef:NULL',
  'is_a_template' : False,
  'is_control_domain' : False,
  'last_boot_CPU_flags' : {},
  'last_booted_record' : '',
  'memory_dynamic_max' : '268435456',
  'memory_dynamic_min' : '134217728',
  'memory_static_max' : '268435456',
  'memory_static_min' : '134217728',
  'metrics' : 'OpaqueRef:3d2fccec-88d5-a74d-1d42-8df6d8b20748',
  'name_description' : 'blahblah',
  'name_label' : 'New name',
  'other_config' : {   'catalog-client-state': 'Importing',
    'mac_seed': 'cc0fe1ab-d466-d9fd-6bfc-f9da4bd7e7e8'},
  'platform' : {},
  'power_state' : 'Running',
  'recommendations' : '',
  'resident_on' : 'OpaqueRef:d3565cb8-5de8-5562-a92a-6ce52fbde613',
  'suspend_VDI' : 'OpaqueRef:NULL',
  'user_version' : '0',
  'uuid' : 'vm-uuid-1',
  'xenstore_data' : {},
}
}, )

xenent_VM_clone1 = ({'Status' : 'Success',
    'Value' : 'OpaqueRef:vmclone1',
}, )

xenent_VM_guest_metrics_get_networks1 =  ({'Status' : 'Success',
  'Value' : {
    '0/ip' : '10.0.0.1',
  }
}, )

xenent_VM_guest_metrics_get_networks2 =  ({'Status' : 'Success',
  'Value' : {
    '0/ip' : '10.0.0.2',
  }
}, )

import xmlrpclib
d = xmlrpclib.DateTime()
d.value = '20090306T14:15:16Z'
xenent_VM_metrics_get_record1 = ({'Status' : 'Success',
  'Value' : {
     'start_time' : d,
  }
}, )

xenent_VBD_get_record1 = ({'Status' : 'Success',
  'Value' : {
    'bootable' : True,
    'device' : 0,
    'empty' : False,
    'mode' : '',
    'qos_algorithm_params' : '',
    'qos_algorithm_type' : '',
    'type' : 'Disk',
    'userdevice' : 'xvda1',
    'other_config' : {},
    'VDI' : 'OpaqueRef:vdi1',
  }
}, )

xenent_VBD_get_record2 = ({'Status' : 'Success',
  'Value' : {
    'bootable' : False,
    'device' : 1,
    'empty' : True,
    'mode' : '',
    'qos_algorithm_params' : '',
    'qos_algorithm_type' : '',
    'type' : 'CDROM',
    'userdevice' : '',
    'other_config' : {},
    'VDI' : 'OpaqueRef:NULL',
  }
}, )

xenent_VBD_create1 = ({'Status' : 'Success',
    'Value' : '',
}, )

xenent_VDI_set_other_config1 = xenent_VBD_create1
xenent_VDI_set_name_label1 = xenent_VDI_set_other_config1
xenent_VDI_set_name_description1 = xenent_VDI_set_other_config1
xenent_VDI_create1 = ({'Status' : 'Success',
    'Value' : '',
}, )

xenent_VM_destroy1 = xenent_VBD_create1

xenent_task_create1 = ({'Status' : 'Success',
    'Value' : 'OpaqueRef:NoBananas',
}, )

xenent_task_get_record1 = ({'Status' : 'Success',
  'Value' : {
    'status' : 'success',
    'result' : '<value><array><data><value>OpaqueRef:VMref1</value></data></array></value>',
  },
}, )

xenent_task_get_record2 = ({'Status' : 'Success',
  'Value' : {
    'status' : 'failed',
  },
}, )

xenent_task_get_status1 = ({'Status' : 'Success',
  'Value' : 'success',
  },
)


xenent_PIF_get_all_records1 = ({'Status' : 'Success',
    'Value' :
{
  'OpaqueRef:7afb1580-5af9-b175-d85f-3b2abf5402d1' : {   'DNS': '',
    'IP': '',
    'MAC': '00:12:3f:75:29:53',
    'MTU': '1500',
    'VLAN': '-1',
    'VLAN_master_of': 'OpaqueRef:NULL',
    'VLAN_slave_of': [],
    'bond_master_of': [],
    'bond_slave_of': 'OpaqueRef:NULL',
    'currently_attached': True,
    'device': 'eth0',
    'gateway': '',
    'host': 'OpaqueRef:d3565cb8-5de8-5562-a92a-6ce52fbde613',
    'ip_configuration_mode': 'DHCP',
    'management': True,
    'metrics': 'OpaqueRef:6b050f2c-5bd2-794f-1d90-9f1ca85728d9',
    'netmask': '',
    'network': 'OpaqueRef:7cf81819-98fc-6c81-5fd0-2c7483534752',
    'other_config': {},
    'physical': True,
    'uuid': '19760dd1-185b-5d9c-a8dd-b1f72238e253'},
  'OpaqueRef:9ba985d7-fe45-e3fa-af2d-33a1fb1a2439' : {   'DNS': '',
    'IP': '',
    'MAC': '00:12:3f:75:29:85',
    'MTU': '1500',
    'VLAN': '-1',
    'VLAN_master_of': 'OpaqueRef:NULL',
    'VLAN_slave_of': [],
    'bond_master_of': [],
    'bond_slave_of': 'OpaqueRef:NULL',
    'currently_attached': True,
    'device': 'eth0',
    'gateway': '',
    'host': 'OpaqueRef:d6dadee2-be35-441d-9514-b6ae219543b5',
    'ip_configuration_mode': 'DHCP',
    'management': True,
    'metrics': 'OpaqueRef:7e6abfe8-46aa-0890-fb32-49ad147422bf',
    'netmask': '',
    'network': 'OpaqueRef:7cf81819-98fc-6c81-5fd0-2c7483534752',
    'other_config': {},
    'physical': True,
    'uuid': 'b5cfe708-225c-8931-224e-50d16af1a3f1'},
}
}, )

xenent_PIF_get_network1 = ({'Status' : 'Success',
    'Value' : 'OpaqueRef:PIFnetwork1',
}, )

xenent_PBD_get_host1 = ({'Status' : 'Success',
    'Value' : 'OpaqueRef:host1',
}, )

xenent_PBD_get_host2 = ({'Status' : 'Success',
    'Value' : 'OpaqueRef:host2',
}, )

xenent_host_get_API_version_major1 = ({'Status' : 'Success',
    'Value' : 1,
}, )

xenent_host_get_record1 = ({'Status' : 'Success',
  'Value' : {
    'address' : '1.1.1.1',
  },
}, )

xenent_host_get_record2 = ({'Status' : 'Success',
  'Value' : {
    'address' : '2.2.2.2',
  },
}, )

vws_listImages_1 = """
[Image] 'image1'                      Read/write
        Modified: Jul 21 @ 22:06   Size: 0 bytes (~0 MB)

[Image] 'image/2'                Read/write
        Modified: Jul 22 @ 02:04   Size: 586 bytes (~0 MB)

[Image] 'image/3/4'  Read/write
        Modified: Jul 22 @ 18:45   Size: 101836800 bytes (~97 MB)

[Image] '0903de41206786d4407ff24ab6e972c0d6b801f3.gz' Read/write
        Modified: Jul 22 @ 18:45   Size: 101836800 bytes (~97 MB)
"""

vws_listImages_2 = """
[Image] 'something_bogus' Read/write
        Modified: Jul 22 @ 18:45   Size: 101836800 bytes (~97 MB)

[Image] 'b3fb7387bb04b1403bc0eb06bd55c0ef5f02d9bb.gz' Read/write
        Modified: Jul 22 @ 18:45   Size: 101836800 bytes (~97 MB)
"""

vws_listInstances_1 = """
[*] - Workspace #23. 192.168.0.2 [ pub02 ]
      State: Running
      Duration: 60 minutes.
      Start time: Fri Jul 25 13:26:29 EDT 2008
      Shutdown time: Fri Jul 25 14:26:29 EDT 2008
      Termination time: Fri Jul 25 14:36:29 EDT 2008
[*] - Workspace #24. 192.168.0.3 [ pub03 ]
      State: Running
      Duration: 60 minutes.
      Start time: Fri Jul 25 13:26:52 EDT 2008
      Shutdown time: Fri Jul 25 14:26:52 EDT 2008
      Termination time: Fri Jul 25 14:36:52 EDT 2008
[*] - Workspace #25. 192.168.0.4 [ pub04 ]
      State: Running
      Duration: 19945 minutes.
      Start time: Fri Jul 25 13:36:00 EDT 2008
      Shutdown time: Fri Aug 08 10:01:00 EDT 2008
      Termination time: Fri Aug 08 10:11:00 EDT 2008
"""

tmp_vmwareName1 = 'virtcenter.eng.rpath.com'
tmp_vmwareAlias1 = 'virtcenter'
tmp_vmwareDescription1 = 'virtual center'

_vmwareReqRetrievePropertiesTemplate = (
 '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" '
 'xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" '
 'xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" '
 'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
 '<SOAP-ENV:Header></SOAP-ENV:Header>'
 '<SOAP-ENV:Body xmlns:ns1="urn:vim25">'
 '<ns1:RetrieveProperties>'
 '<_this type="PropertyCollector">propertyCollector</_this>'
 '<specSet>'
 '%s'
 '</specSet>'
 '</ns1:RetrieveProperties>'
 '</SOAP-ENV:Body>'
 '</SOAP-ENV:Envelope>'
)

_vmwareReqRetrievePropertiesSimpleTemplate = _vmwareReqRetrievePropertiesTemplate % (
    '<propSet>'
      '<ns1:type>%(klass)s</ns1:type>'
      '<ns1:all>false</ns1:all>'
      '<ns1:pathSet>%(path)s</ns1:pathSet>'
    '</propSet>'
    '<objectSet>'
      '<obj type="%(klass)s">%(value)s</obj>'
      '<ns1:skip>false</ns1:skip>'
    '</objectSet>'
)

_vmwareReqRetrievePropertiesSimpleTypedTemplate = _vmwareReqRetrievePropertiesTemplate % (
    '<propSet>'
      '<ns1:type>%(klass)s</ns1:type>'
      '<ns1:all>false</ns1:all>'
      '<ns1:pathSet>%(path)s</ns1:pathSet>'
    '</propSet>'
    '<objectSet>'
      '<obj type="%(klass)s" xsi:type="%(rklass)s">%(value)s</obj>'
      '<ns1:skip>false</ns1:skip>'
    '</objectSet>'
)

_vmwareRespRetrievePropertiesTemplate = (
 '<?xml version="1.0" encoding="UTF-8"?>'
 '<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
   '<soapenv:Body>'
     '<RetrievePropertiesResponse xmlns="urn:vim25">'
       '%s'
     '</RetrievePropertiesResponse>'
   '</soapenv:Body>'
 '</soapenv:Envelope>'
)

_vmwareReturnValSimpleTemplate = (
  '<returnval>'
    '<obj type="%(klass)s">%(value)s</obj>'
    '<propSet>'
      '<name>%(path)s</name>'
      '<val type="%(rklass)s" xsi:type="%(rtype)s">%(propval)s</val>'
    '</propSet>'
  '</returnval>'
)

vmwareReqGetVirtualMachineProps1 = _vmwareReqRetrievePropertiesTemplate % (
   '<propSet xsi:type="ns1:PropertySpec">'
     '<ns1:type>VirtualMachine</ns1:type>'
     '<ns1:all>false</ns1:all>'
     '<ns1:pathSet>name</ns1:pathSet>'
     '<ns1:pathSet>config.annotation</ns1:pathSet>'
     '<ns1:pathSet>config.template</ns1:pathSet>'
     '<ns1:pathSet>runtime.powerState</ns1:pathSet>'
     '<ns1:pathSet>runtime.bootTime</ns1:pathSet>'
     '<ns1:pathSet>config.uuid</ns1:pathSet>'
     '<ns1:pathSet>guest.ipAddress</ns1:pathSet>'
  '</propSet>'
  '<objectSet>'
    '<obj type="Folder">group-d1</obj>'
    '<ns1:skip>false</ns1:skip>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
      '<ns1:name>visitFolders</ns1:name>'
      '<ns1:type>Folder</ns1:type>'
      '<ns1:path>childEntity</ns1:path>'
      '<ns1:skip>false</ns1:skip>'
      '<selectSet>'
        '<ns1:name>visitFolders</ns1:name>'
      '</selectSet>'
      '<selectSet>'
        '<ns1:name>dcToHf</ns1:name>'
      '</selectSet>'
      '<selectSet>'
        '<ns1:name>dcToVmf</ns1:name>'
      '</selectSet>'
      '<selectSet>'
        '<ns1:name>crToH</ns1:name>'
      '</selectSet>'
      '<selectSet>'
        '<ns1:name>crToRp</ns1:name>'
      '</selectSet>'
      '<selectSet>'
        '<ns1:name>HToVm</ns1:name>'
      '</selectSet>'
      '<selectSet>'
        '<ns1:name>rpToVm</ns1:name>'
      '</selectSet>'
      '<selectSet>'
        '<ns1:name>dcToNetwork</ns1:name>'
      '</selectSet>'
    '</selectSet>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
    '<ns1:name>dcToVmf</ns1:name>'
    '<ns1:type>Datacenter</ns1:type>'
    '<ns1:path>vmFolder</ns1:path>'
    '<ns1:skip>false</ns1:skip>'
    '<selectSet><ns1:name>visitFolders</ns1:name>'
    '</selectSet></selectSet>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
    '<ns1:name>dcToHf</ns1:name>'
    '<ns1:type>Datacenter</ns1:type>'
    '<ns1:path>hostFolder</ns1:path>'
    '<ns1:skip>false</ns1:skip>'
    '<selectSet>'
    '<ns1:name>visitFolders</ns1:name>'
    '</selectSet>'
    '</selectSet>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
    '<ns1:name>crToH</ns1:name><ns1:type>ComputeResource</ns1:type>'
    '<ns1:path>host</ns1:path>'
    '<ns1:skip>false</ns1:skip>'
    '</selectSet>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
    '<ns1:name>crToRp</ns1:name>'
    '<ns1:type>ComputeResource</ns1:type>'
    '<ns1:path>resourcePool</ns1:path>'
    '<ns1:skip>false</ns1:skip>'
    '<selectSet>'
    '<ns1:name>rpToRp</ns1:name>'
    '</selectSet>'
    '<selectSet>'
    '<ns1:name>rpToVm</ns1:name>'
    '</selectSet>'
    '</selectSet>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
    '<ns1:name>rpToRp</ns1:name>'
    '<ns1:type>ResourcePool</ns1:type>'
    '<ns1:path>resourcePool</ns1:path>'
    '<ns1:skip>false</ns1:skip>'
    '<selectSet>'
    '<ns1:name>rpToRp</ns1:name>'
    '</selectSet>'
    '<selectSet>'
    '<ns1:name>rpToVm</ns1:name>'
    '</selectSet></selectSet>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
    '<ns1:name>HToVm</ns1:name>'
    '<ns1:type>HostSystem</ns1:type>'
    '<ns1:path>vm</ns1:path>'
    '<ns1:skip>false</ns1:skip>'
    '<selectSet><ns1:name>visitFolders</ns1:name>'
    '</selectSet></selectSet>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
    '<ns1:name>rpToVm</ns1:name>'
    '<ns1:type>ResourcePool</ns1:type>'
    '<ns1:path>vm</ns1:path>'
    '<ns1:skip>false</ns1:skip>'
    '</selectSet>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
      '<ns1:name>dcToNetwork</ns1:name>'
      '<ns1:type>Datacenter</ns1:type>'
      '<ns1:path>networkFolder</ns1:path>'
      '<ns1:skip>false</ns1:skip>'
      '<selectSet>'
        '<ns1:name>visitFolders</ns1:name>'
      '</selectSet>'
    '</selectSet>'
  '</objectSet>'
)

vmwareReqGetVirtualMachineProps35 = _vmwareReqRetrievePropertiesTemplate % (
   '<propSet xsi:type="ns1:PropertySpec">'
     '<ns1:type>VirtualMachine</ns1:type>'
     '<ns1:all>false</ns1:all>'
     '<ns1:pathSet>name</ns1:pathSet>'
     '<ns1:pathSet>config.annotation</ns1:pathSet>'
     '<ns1:pathSet>config.template</ns1:pathSet>'
     '<ns1:pathSet>runtime.powerState</ns1:pathSet>'
     '<ns1:pathSet>runtime.bootTime</ns1:pathSet>'
     '<ns1:pathSet>config.uuid</ns1:pathSet>'
     '<ns1:pathSet>guest.ipAddress</ns1:pathSet>'
  '</propSet>'
  '<objectSet>'
    '<obj type="Folder">group-d1</obj>'
    '<ns1:skip>false</ns1:skip>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
      '<ns1:name>visitFolders</ns1:name>'
      '<ns1:type>Folder</ns1:type>'
      '<ns1:path>childEntity</ns1:path>'
      '<ns1:skip>false</ns1:skip>'
      '<selectSet>'
        '<ns1:name>visitFolders</ns1:name>'
      '</selectSet>'
      '<selectSet>'
        '<ns1:name>dcToHf</ns1:name>'
      '</selectSet>'
      '<selectSet>'
        '<ns1:name>dcToVmf</ns1:name>'
      '</selectSet>'
      '<selectSet>'
        '<ns1:name>crToH</ns1:name>'
      '</selectSet>'
      '<selectSet>'
        '<ns1:name>crToRp</ns1:name>'
      '</selectSet>'
      '<selectSet>'
        '<ns1:name>HToVm</ns1:name>'
      '</selectSet>'
      '<selectSet>'
        '<ns1:name>rpToVm</ns1:name>'
      '</selectSet>'
    '</selectSet>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
    '<ns1:name>dcToVmf</ns1:name>'
    '<ns1:type>Datacenter</ns1:type>'
    '<ns1:path>vmFolder</ns1:path>'
    '<ns1:skip>false</ns1:skip>'
    '<selectSet><ns1:name>visitFolders</ns1:name>'
    '</selectSet></selectSet>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
    '<ns1:name>dcToHf</ns1:name>'
    '<ns1:type>Datacenter</ns1:type>'
    '<ns1:path>hostFolder</ns1:path>'
    '<ns1:skip>false</ns1:skip>'
    '<selectSet>'
    '<ns1:name>visitFolders</ns1:name>'
    '</selectSet>'
    '</selectSet>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
    '<ns1:name>crToH</ns1:name><ns1:type>ComputeResource</ns1:type>'
    '<ns1:path>host</ns1:path>'
    '<ns1:skip>false</ns1:skip>'
    '</selectSet>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
    '<ns1:name>crToRp</ns1:name>'
    '<ns1:type>ComputeResource</ns1:type>'
    '<ns1:path>resourcePool</ns1:path>'
    '<ns1:skip>false</ns1:skip>'
    '<selectSet>'
    '<ns1:name>rpToRp</ns1:name>'
    '</selectSet>'
    '<selectSet>'
    '<ns1:name>rpToVm</ns1:name>'
    '</selectSet>'
    '</selectSet>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
    '<ns1:name>rpToRp</ns1:name>'
    '<ns1:type>ResourcePool</ns1:type>'
    '<ns1:path>resourcePool</ns1:path>'
    '<ns1:skip>false</ns1:skip>'
    '<selectSet>'
    '<ns1:name>rpToRp</ns1:name>'
    '</selectSet>'
    '<selectSet>'
    '<ns1:name>rpToVm</ns1:name>'
    '</selectSet></selectSet>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
    '<ns1:name>HToVm</ns1:name>'
    '<ns1:type>HostSystem</ns1:type>'
    '<ns1:path>vm</ns1:path>'
    '<ns1:skip>false</ns1:skip>'
    '<selectSet><ns1:name>visitFolders</ns1:name>'
    '</selectSet></selectSet>'
    '<selectSet xsi:type="ns1:TraversalSpec">'
    '<ns1:name>rpToVm</ns1:name>'
    '<ns1:type>ResourcePool</ns1:type>'
    '<ns1:path>vm</ns1:path>'
    '<ns1:skip>false</ns1:skip>'
    '</selectSet>'
  '</objectSet>'
)

vmwareReqGetVirtualMachineProps35_2 = vmwareReqGetVirtualMachineProps35.replace(
    '<obj type="Folder">group-d1</obj>',
    '<obj type="VirtualMachine">vm-1201</obj>')

vmwareReqGetVirtualMachineProps2 = vmwareReqGetVirtualMachineProps1.replace(
    '<obj type="Folder">group-d1</obj>',
    '<obj type="VirtualMachine">vm-1201</obj>')

vmwareResponseGetVirtualMachineProps = HTTPResponse(
 '<?xml version="1.0" encoding="UTF-8"?>\n'
 '<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"\n xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"\n xmlns:xsd="http://www.w3.org/2001/XMLSchema"\n xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
 '<soapenv:Body>\n'
 '<RetrievePropertiesResponse xmlns="urn:vim25">'
 '<returnval>'
 '<obj type="VirtualMachine">vm-1201</obj>'
 '<propSet><name>config.annotation</name><val xsi:type="xsd:string">\xc3\xbc</val></propSet>'
 '<propSet><name>config.template</name><val xsi:type="xsd:boolean">false</val></propSet>'
 '<propSet><name>runtime.bootTime</name><val xsi:type="xsd:dateTime">2008-11-17T14:24:28.295394Z</val></propSet>'
 '<propSet><name>config.uuid</name><val xsi:type="xsd:string">50344408-f9b7-3927-417b-14258d839e26</val></propSet>'
 '<propSet><name>guest.ipAddress</name><val xsi:type="xsd:string">10.11.12.13</val></propSet>'
 '<propSet><name>name</name><val xsi:type="xsd:string">Solaris10a</val></propSet>'
 '<propSet><name>config.extraConfig</name><val xsi:type="ArrayOfOptionValue"><OptionValue xsi:type="OptionValue"><key>checkpoint.vmState</key><value xsi:type="xsd:string"></value></OptionValue><OptionValue xsi:type="OptionValue"><key>config.readOnly</key><value xsi:type="xsd:string">false</value></OptionValue><OptionValue xsi:type="OptionValue"><key>deploymentPlatform</key><value xsi:type="xsd:string">windows</value></OptionValue><OptionValue xsi:type="OptionValue"><key>evcCompatibilityMode</key><value xsi:type="xsd:string">FALSE</value></OptionValue><OptionValue xsi:type="OptionValue"><key>guestCPUID.0</key><value xsi:type="xsd:string">0000000a756e65476c65746e49656e69</value></OptionValue><OptionValue xsi:type="OptionValue"><key>guestCPUID.1</key><value xsi:type="xsd:string">000006f800010800000022110febfbff</value></OptionValue><OptionValue xsi:type="OptionValue"><key>guestCPUID.80000001</key><value xsi:type="xsd:string">00000000000000000000000120100000</value></OptionValue><OptionValue xsi:type="OptionValue"><key>hostCPUID.0</key><value xsi:type="xsd:string">0000000a756e65476c65746e49656e69</value></OptionValue><OptionValue xsi:type="OptionValue"><key>hostCPUID.1</key><value xsi:type="xsd:string">000006f6000208000004e33dbfebfbff</value></OptionValue><OptionValue xsi:type="OptionValue"><key>hostCPUID.80000001</key><value xsi:type="xsd:string">00000000000000000000000120100000</value></OptionValue><OptionValue xsi:type="OptionValue"><key>nvram</key><value xsi:type="xsd:string">smerp-tabula-rasa.nvram</value></OptionValue><OptionValue xsi:type="OptionValue"><key>sched.swap.derivedName</key><value xsi:type="xsd:string">/vmfs/volumes/48b47134-c01805f0-6371-00188b401fd1/smerp-tabula-rasa-a08337b3.vswp</value></OptionValue><OptionValue xsi:type="OptionValue"><key>scsi0:0.redo</key><value xsi:type="xsd:string"></value></OptionValue><OptionValue xsi:type="OptionValue"><key>snapshot.action</key><value xsi:type="xsd:string">keep</value></OptionValue><OptionValue xsi:type="OptionValue"><key>tools.remindInstall</key><value xsi:type="xsd:string">false</value></OptionValue><OptionValue xsi:type="OptionValue"><key>userCPUID.0</key><value xsi:type="xsd:string">0000000a756e65476c65746e49656e69</value></OptionValue><OptionValue xsi:type="OptionValue"><key>userCPUID.1</key><value xsi:type="xsd:string">000006f6000208000004e33dbfebfbff</value></OptionValue><OptionValue xsi:type="OptionValue"><key>userCPUID.80000001</key><value xsi:type="xsd:string">00000000000000000000000120100000</value></OptionValue><OptionValue xsi:type="OptionValue"><key>virtualHW.productCompatibility</key><value xsi:type="xsd:string">hosted</value></OptionValue><OptionValue xsi:type="OptionValue"><key>vmware.tools.requiredversion</key><value xsi:type="xsd:string">7299</value></OptionValue><OptionValue xsi:type="OptionValue"><key>vmware.tools.internalversion</key><value xsi:type="xsd:string">0</value></OptionValue><OptionValue xsi:type="OptionValue"><key>vmware.tools.requiredversion</key><value xsi:type="xsd:string">7299</value></OptionValue><OptionValue xsi:type="OptionValue"><key>vmware.tools.installstate</key><value xsi:type="xsd:string">none</value></OptionValue><OptionValue xsi:type="OptionValue"><key>vmware.tools.lastInstallStatus.result</key><value xsi:type="xsd:string">unknown</value></OptionValue></val></propSet>'
 '<propSet><name>runtime.powerState</name><val xsi:type="VirtualMachinePowerState">poweredOff</val></propSet>'
 '</returnval>'
 '<returnval>'
 '<obj type="VirtualMachine">vm-1023</obj>'
 '<propSet><name>config.annotation</name><val xsi:type="xsd:string">Ma\xc3\xafs</val></propSet>'
 '<propSet><name>config.template</name><val xsi:type="xsd:boolean">true</val></propSet>'
 '<propSet><name>config.uuid</name><val xsi:type="xsd:string">50348202-8fcd-a662-2585-c4db19d28079</val></propSet>'
 '<propSet><name>name</name><val xsi:type="xsd:string">msw-proxy</val></propSet>'
 '<propSet><name>config.extraConfig</name><val xsi:type="ArrayOfOptionValue"><OptionValue xsi:type="OptionValue"><key>checkpoint.vmState</key><value xsi:type="xsd:string"></value></OptionValue><OptionValue xsi:type="OptionValue"><key>config.readOnly</key><value xsi:type="xsd:string">false</value></OptionValue><OptionValue xsi:type="OptionValue"><key>deploymentPlatform</key><value xsi:type="xsd:string">windows</value></OptionValue><OptionValue xsi:type="OptionValue"><key>evcCompatibilityMode</key><value xsi:type="xsd:string">FALSE</value></OptionValue><OptionValue xsi:type="OptionValue"><key>guestCPUID.0</key><value xsi:type="xsd:string">0000000a756e65476c65746e49656e69</value></OptionValue><OptionValue xsi:type="OptionValue"><key>guestCPUID.1</key><value xsi:type="xsd:string">000006f800010800000022110febfbff</value></OptionValue><OptionValue xsi:type="OptionValue"><key>guestCPUID.80000001</key><value xsi:type="xsd:string">00000000000000000000000120100000</value></OptionValue><OptionValue xsi:type="OptionValue"><key>hostCPUID.0</key><value xsi:type="xsd:string">0000000a756e65476c65746e49656e69</value></OptionValue><OptionValue xsi:type="OptionValue"><key>hostCPUID.1</key><value xsi:type="xsd:string">000006f6000208000004e33dbfebfbff</value></OptionValue><OptionValue xsi:type="OptionValue"><key>hostCPUID.80000001</key><value xsi:type="xsd:string">00000000000000000000000120100000</value></OptionValue><OptionValue xsi:type="OptionValue"><key>nvram</key><value xsi:type="xsd:string">smerp-tabula-rasa.nvram</value></OptionValue><OptionValue xsi:type="OptionValue"><key>sched.swap.derivedName</key><value xsi:type="xsd:string">/vmfs/volumes/48b47134-c01805f0-6371-00188b401fd1/smerp-tabula-rasa-a08337b3.vswp</value></OptionValue><OptionValue xsi:type="OptionValue"><key>scsi0:0.redo</key><value xsi:type="xsd:string"></value></OptionValue><OptionValue xsi:type="OptionValue"><key>snapshot.action</key><value xsi:type="xsd:string">keep</value></OptionValue><OptionValue xsi:type="OptionValue"><key>tools.remindInstall</key><value xsi:type="xsd:string">false</value></OptionValue><OptionValue xsi:type="OptionValue"><key>userCPUID.0</key><value xsi:type="xsd:string">0000000a756e65476c65746e49656e69</value></OptionValue><OptionValue xsi:type="OptionValue"><key>userCPUID.1</key><value xsi:type="xsd:string">000006f6000208000004e33dbfebfbff</value></OptionValue><OptionValue xsi:type="OptionValue"><key>userCPUID.80000001</key><value xsi:type="xsd:string">00000000000000000000000120100000</value></OptionValue><OptionValue xsi:type="OptionValue"><key>virtualHW.productCompatibility</key><value xsi:type="xsd:string">hosted</value></OptionValue><OptionValue xsi:type="OptionValue"><key>vmware.tools.requiredversion</key><value xsi:type="xsd:string">7299</value></OptionValue><OptionValue xsi:type="OptionValue"><key>vmware.tools.internalversion</key><value xsi:type="xsd:string">0</value></OptionValue><OptionValue xsi:type="OptionValue"><key>vmware.tools.requiredversion</key><value xsi:type="xsd:string">7299</value></OptionValue><OptionValue xsi:type="OptionValue"><key>vmware.tools.installstate</key><value xsi:type="xsd:string">none</value></OptionValue><OptionValue xsi:type="OptionValue"><key>vmware.tools.lastInstallStatus.result</key><value xsi:type="xsd:string">unknown</value></OptionValue></val></propSet>'
'<propSet><name>runtime.powerState</name><val xsi:type="VirtualMachinePowerState">poweredOff</val></propSet>'
 '</returnval>'
 '<returnval>'
 '<obj type="VirtualMachine">vm-1024</obj>'
 '<propSet><name>config.template</name><val xsi:type="xsd:boolean">false</val></propSet>'
 '<propSet><name>config.uuid</name><val xsi:type="xsd:string">50348202-8fcd-a662-2585-aabbccddeeff</val></propSet>'
 '<propSet><name>name</name><val xsi:type="xsd:string">without-annotation</val></propSet>'
 '<propSet><name>config.extraConfig</name><val xsi:type="ArrayOfOptionValue"><OptionValue xsi:type="OptionValue"><key>checkpoint.vmState</key><value xsi:type="xsd:string"></value></OptionValue><OptionValue xsi:type="OptionValue"><key>config.readOnly</key><value xsi:type="xsd:string">false</value></OptionValue><OptionValue xsi:type="OptionValue"><key>deploymentPlatform</key><value xsi:type="xsd:string">windows</value></OptionValue><OptionValue xsi:type="OptionValue"><key>evcCompatibilityMode</key><value xsi:type="xsd:string">FALSE</value></OptionValue><OptionValue xsi:type="OptionValue"><key>guestCPUID.0</key><value xsi:type="xsd:string">0000000a756e65476c65746e49656e69</value></OptionValue><OptionValue xsi:type="OptionValue"><key>guestCPUID.1</key><value xsi:type="xsd:string">000006f800010800000022110febfbff</value></OptionValue><OptionValue xsi:type="OptionValue"><key>guestCPUID.80000001</key><value xsi:type="xsd:string">00000000000000000000000120100000</value></OptionValue><OptionValue xsi:type="OptionValue"><key>hostCPUID.0</key><value xsi:type="xsd:string">0000000a756e65476c65746e49656e69</value></OptionValue><OptionValue xsi:type="OptionValue"><key>hostCPUID.1</key><value xsi:type="xsd:string">000006f6000208000004e33dbfebfbff</value></OptionValue><OptionValue xsi:type="OptionValue"><key>hostCPUID.80000001</key><value xsi:type="xsd:string">00000000000000000000000120100000</value></OptionValue><OptionValue xsi:type="OptionValue"><key>nvram</key><value xsi:type="xsd:string">smerp-tabula-rasa.nvram</value></OptionValue><OptionValue xsi:type="OptionValue"><key>sched.swap.derivedName</key><value xsi:type="xsd:string">/vmfs/volumes/48b47134-c01805f0-6371-00188b401fd1/smerp-tabula-rasa-a08337b3.vswp</value></OptionValue><OptionValue xsi:type="OptionValue"><key>scsi0:0.redo</key><value xsi:type="xsd:string"></value></OptionValue><OptionValue xsi:type="OptionValue"><key>snapshot.action</key><value xsi:type="xsd:string">keep</value></OptionValue><OptionValue xsi:type="OptionValue"><key>tools.remindInstall</key><value xsi:type="xsd:string">false</value></OptionValue><OptionValue xsi:type="OptionValue"><key>userCPUID.0</key><value xsi:type="xsd:string">0000000a756e65476c65746e49656e69</value></OptionValue><OptionValue xsi:type="OptionValue"><key>userCPUID.1</key><value xsi:type="xsd:string">000006f6000208000004e33dbfebfbff</value></OptionValue><OptionValue xsi:type="OptionValue"><key>userCPUID.80000001</key><value xsi:type="xsd:string">00000000000000000000000120100000</value></OptionValue><OptionValue xsi:type="OptionValue"><key>virtualHW.productCompatibility</key><value xsi:type="xsd:string">hosted</value></OptionValue><OptionValue xsi:type="OptionValue"><key>vmware.tools.requiredversion</key><value xsi:type="xsd:string">7299</value></OptionValue><OptionValue xsi:type="OptionValue"><key>vmware.tools.internalversion</key><value xsi:type="xsd:string">0</value></OptionValue><OptionValue xsi:type="OptionValue"><key>vmware.tools.requiredversion</key><value xsi:type="xsd:string">7299</value></OptionValue><OptionValue xsi:type="OptionValue"><key>vmware.tools.installstate</key><value xsi:type="xsd:string">none</value></OptionValue><OptionValue xsi:type="OptionValue"><key>vmware.tools.lastInstallStatus.result</key><value xsi:type="xsd:string">unknown</value></OptionValue></val></propSet>'
'<propSet><name>runtime.powerState</name><val xsi:type="VirtualMachinePowerState">poweredOff</val></propSet>'
 '</returnval>'
 '</RetrievePropertiesResponse>'
 '</soapenv:Body>\n'
 '</soapenv:Envelope>'
 # END RESPONSE - get virtual machine props
)

vmwareResponseGetVirtualMachinePropsWithAnnot = HTTPResponse(
    vmwareResponseGetVirtualMachineProps.data.replace(
    '<propSet><name>config.annotation</name><val xsi:type="xsd:string">Ma\xc3\xafs</val></propSet>',
    '<propSet><name>config.annotation</name><val xsi:type="xsd:string">junk:a\nRbA-uuId: 361d7fa1-d994-31e1-6a3a-438c8d4ebaa7\nmoreJunk</val></propSet>'))

vmwareResponseGetVirtualMachinePropsWithIp = HTTPResponse(
    vmwareResponseGetVirtualMachineProps.data.replace(
    '<propSet><name>name</name>',
    '<propSet>'
        '<name>guest.ipAddress</name>'
        '<val xsi:type="xsd:string">10.11.12.13</val>'
    '</propSet>'
    '<propSet><name>name</name>'))

vmwareRetrievePropertiesHostReq = vmwareReqGetVirtualMachineProps1.replace(
 '<ns1:type>VirtualMachine</ns1:type>', '<ns1:type>HostSystem</ns1:type>').replace(
 '<ns1:pathSet>config.annotation</ns1:pathSet>'
 '<ns1:pathSet>config.template</ns1:pathSet>'
 '<ns1:pathSet>runtime.powerState</ns1:pathSet>'
 '<ns1:pathSet>runtime.bootTime</ns1:pathSet>'
 '<ns1:pathSet>config.uuid</ns1:pathSet>'
 '<ns1:pathSet>guest.ipAddress</ns1:pathSet>',
 '').replace(
    '<obj type="Folder">group-d1</obj>',
    '<obj type="Folder" xsi:type="ns1:ManagedObjectReference">group-v3</obj>')

vmwareRetrievePropertiesHostReq35 = vmwareReqGetVirtualMachineProps35.replace(
 '<ns1:type>VirtualMachine</ns1:type>', '<ns1:type>HostSystem</ns1:type>').replace(
 '<ns1:pathSet>config.annotation</ns1:pathSet>'
 '<ns1:pathSet>config.template</ns1:pathSet>'
 '<ns1:pathSet>runtime.powerState</ns1:pathSet>'
 '<ns1:pathSet>runtime.bootTime</ns1:pathSet>'
 '<ns1:pathSet>config.uuid</ns1:pathSet>'
 '<ns1:pathSet>guest.ipAddress</ns1:pathSet>',
 '').replace(
    '<obj type="Folder">group-d1</obj>',
    '<obj type="Folder" xsi:type="ns1:ManagedObjectReference">group-v3</obj>')

vmwareRetrievePropertiesHostResp = HTTPResponse(data="""\
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Body>
    <RetrievePropertiesResponse xmlns="urn:vim25">
      <returnval>
        <obj type="HostSystem">host-879</obj>
        <propSet>
          <name>datastore</name>
          <val xsi:type="ArrayOfManagedObjectReference">
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-16</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-18</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-20</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-884</ManagedObjectReference>
          </val>
        </propSet>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">esx02.eng.rpath.com</val>
        </propSet>
        <propSet>
          <name>network</name>
          <val xsi:type="ArrayOfManagedObjectReference">
            <ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-22</ManagedObjectReference>
          </val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Folder">group-v1622</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">rBO</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="ResourcePool">resgroup-7</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">Resources</val>
        </propSet>
        <propSet>
          <name>parent</name>
          <val type="ClusterComputeResource" xsi:type="ManagedObjectReference">domain-c5</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Folder">group-v1191</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">OS tests</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="ClusterComputeResource">domain-c5</obj>
        <propSet>
          <name>datastore</name>
          <val xsi:type="ArrayOfManagedObjectReference">
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-16</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-18</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-20</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-563</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-565</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-884</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-887</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-559</ManagedObjectReference>
          </val>
        </propSet>
        <propSet>
          <name>host</name>
          <val xsi:type="ArrayOfManagedObjectReference">
            <ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-183</ManagedObjectReference>
            <ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-206</ManagedObjectReference>
            <ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-879</ManagedObjectReference>
            <ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-881</ManagedObjectReference>
            <ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-9</ManagedObjectReference>
          </val>
        </propSet>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">lab</val>
        </propSet>
        <propSet>
          <name>network</name>
          <val xsi:type="ArrayOfManagedObjectReference">
            <ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-22</ManagedObjectReference>
            <ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-2282</ManagedObjectReference>
          </val>
        </propSet>
        <propSet>
          <name>parent</name>
          <val type="Folder" xsi:type="ManagedObjectReference">group-h4</val>
        </propSet>
        <propSet>
          <name>resourcePool</name>
          <val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-7</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Folder">group-v2317</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">rUS</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="ResourcePool">resgroup-181</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">QA</val>
        </propSet>
        <propSet>
          <name>parent</name>
          <val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-7</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Folder">group-v2329</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">Discovered Virtual Machine</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Folder">group-v1935</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">rPA testing</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Folder">group-v3</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">vm</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="HostSystem">host-206</obj>
        <propSet>
          <name>datastore</name>
          <val xsi:type="ArrayOfManagedObjectReference">
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-16</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-18</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-20</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-565</ManagedObjectReference>
          </val>
        </propSet>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">esx04.eng.rpath.com</val>
        </propSet>
        <propSet>
          <name>network</name>
          <val xsi:type="ArrayOfManagedObjectReference">
            <ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-22</ManagedObjectReference>
          </val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="ResourcePool">resgroup-537</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">Proserv</val>
        </propSet>
        <propSet>
          <name>parent</name>
          <val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-7</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Folder">group-v2279</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">rBA</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="HostSystem">host-9</obj>
        <propSet>
          <name>datastore</name>
          <val xsi:type="ArrayOfManagedObjectReference">
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-16</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-18</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-20</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-559</ManagedObjectReference>
          </val>
        </propSet>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">esx01.eng.rpath.com</val>
        </propSet>
        <propSet>
          <name>network</name>
          <val xsi:type="ArrayOfManagedObjectReference">
            <ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-2282</ManagedObjectReference>
            <ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-22</ManagedObjectReference>
          </val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="HostSystem">host-183</obj>
        <propSet>
          <name>datastore</name>
          <val xsi:type="ArrayOfManagedObjectReference">
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-16</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-18</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-20</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-563</ManagedObjectReference>
          </val>
        </propSet>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">esx03.eng.rpath.com</val>
        </propSet>
        <propSet>
          <name>network</name>
          <val xsi:type="ArrayOfManagedObjectReference">
            <ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-22</ManagedObjectReference>
          </val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="ResourcePool">resgroup-50</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">Franks</val>
        </propSet>
        <propSet>
          <name>parent</name>
          <val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-7</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="ResourcePool">resgroup-51</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">General</val>
        </propSet>
        <propSet>
          <name>parent</name>
          <val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-7</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Folder">group-v506</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">Cognos</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Folder">group-v354</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">QA</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="HostSystem">host-881</obj>
        <propSet>
          <name>datastore</name>
          <val xsi:type="ArrayOfManagedObjectReference">
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-16</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-18</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-20</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-887</ManagedObjectReference>
          </val>
        </propSet>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">esx05.eng.rpath.com</val>
        </propSet>
        <propSet>
          <name>network</name>
          <val xsi:type="ArrayOfManagedObjectReference">
            <ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-22</ManagedObjectReference>
          </val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Folder">group-v355</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">Templates</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Folder">group-v356</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">Field</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Folder">group-d1</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">Datacenters</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Folder">group-v357</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">Engineering</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Folder">group-v358</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">Support</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Folder">group-h4</obj>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">host</val>
        </propSet>
      </returnval>
      <returnval>
        <obj type="Datacenter">datacenter-2</obj>
        <propSet>
          <name>datastore</name>
          <val xsi:type="ArrayOfManagedObjectReference">
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-16</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-18</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-20</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-559</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-563</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-565</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-887</ManagedObjectReference>
            <ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-884</ManagedObjectReference>
          </val>
        </propSet>
        <propSet>
          <name>hostFolder</name>
          <val type="Folder" xsi:type="ManagedObjectReference">group-h4</val>
        </propSet>
        <propSet>
          <name>name</name>
          <val xsi:type="xsd:string">rPath</val>
        </propSet>
        <propSet>
          <name>network</name>
          <val xsi:type="ArrayOfManagedObjectReference">
            <ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-2282</ManagedObjectReference>
            <ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-22</ManagedObjectReference>
          </val>
        </propSet>
        <propSet>
          <name>vmFolder</name>
          <val type="Folder" xsi:type="ManagedObjectReference">group-v3</val>
        </propSet>
      </returnval>
    </RetrievePropertiesResponse>
  </soapenv:Body>
</soapenv:Envelope>
""")

vmwareQueryConfigOptionReq = '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><SOAP-ENV:Header></SOAP-ENV:Header><SOAP-ENV:Body xmlns:ns1="urn:vim25"><ns1:QueryConfigOption><_this type="EnvironmentBrowser" xsi:type="ns1:ManagedObjectReference">envbrowser-5</_this><host type="HostSystem">host-879</host></ns1:QueryConfigOption></SOAP-ENV:Body></SOAP-ENV:Envelope>'

vmwareQueryConfigOptionResp = """\
HTTP/1.1 200 OK
Date: Fri, 22 May 2009 20:33:31 GMT
Cache-Control: no-cache
Content-Type: text/xml; charset=utf-8
Content-Length: 31987

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
<QueryConfigOptionResponse xmlns="urn:vim25"><returnval><version>vmx-04</version><description>ESX 3.x virtual machine</description><guestOSDescriptor><id>otherLinuxGuest</id><family>linuxGuest</family><fullName>Other Linux (32-bit)</fullName><supportedMaxCPUs>4</supportedMaxCPUs><supportedMinMemMB>32</supportedMinMemMB><supportedMaxMemMB>65532</supportedMaxMemMB><recommendedMemMB>256</recommendedMemMB><recommendedColorDepth>16</recommendedColorDepth><supportedDiskControllerList>VirtualBusLogicController</supportedDiskControllerList><supportedDiskControllerList>VirtualLsiLogicController</supportedDiskControllerList><supportedDiskControllerList>VirtualIDEController</supportedDiskControllerList><recommendedSCSIController>VirtualLsiLogicController</recommendedSCSIController><recommendedDiskController>VirtualLsiLogicController</recommendedDiskController><supportedNumDisks>16</supportedNumDisks><recommendedDiskSizeMB>8192</recommendedDiskSizeMB><supportedEthernetCard>VirtualPCNet32</supportedEthernetCard><supportedEthernetCard>VirtualVmxnet</supportedEthernetCard><recommendedEthernetCard>VirtualPCNet32</recommendedEthernetCard><supportsSlaveDisk>true</supportsSlaveDisk><cpuFeatureMask><level>0</level><eax>xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx</eax><ebx>HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH</ebx><ecx>HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH</ecx><edx>HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH</edx></cpuFeatureMask><cpuFeatureMask><level>1</level><eax>RRRR:HHHH:HHHH:xxxx:RRxx:HHHH:xxxx:xxxx</eax><ebx>xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx</ebx><ecx>xRRR:R0RR:HR0H:H0RR:00xR:R0H0:0000:00RH</ecx><edx>0000:HHHH:HHHR:HHHH:HHHH:HR1H:HHHH:HHHH</edx></cpuFeatureMask><cpuFeatureMask><level>-2147483648</level><eax>xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx</eax><ebx>xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx</ebx><ecx>xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx</ecx><edx>xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx</edx></cpuFeatureMask><cpuFeatureMask><level>-2147483647</level><eax>xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx</eax><ebx>xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx</ebx><ecx>RRRR:RRRR:RRRR:RRRR:RRRR:RRRR:RRRR:RRRx</ecx><edx>RRxR:HRRR:RRRH:RRRR:RRRR:xRRR:RRRR:RRRR</edx></cpuFeatureMask><cpuFeatureMask><level>0</level><vendor>amd</vendor><eax>xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx</eax><ebx>HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH</ebx><ecx>HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH</ecx><edx>HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH</edx></cpuFeatureMask><cpuFeatureMask><level>1</level><vendor>amd</vendor><eax>RRRR:HHHH:HHHH:xxxx:RRxx:HHHH:xxxx:xxxx</eax><ebx>xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx</ebx><ecx>xRRR:RRRR:HRRR:RRRR:RRxR:RRHR:RRRR:0RRH</ecx><edx>RRR0:RHHH:HRRR:HRHH:HHHH:HR1H:HHHH:HHHH</edx></cpuFeatureMask><cpuFeatureMask><level>-2147483647</level><vendor>amd</vendor><eax>RRRR:xxxx:xxxx:xxxx:RRxx:xxxx:xxxx:xxxx</eax><ebx>xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx</ebx><ecx>RRRR:RRRR:RRRR:RRRR:RR00:R00H:HHH0:x00x</ecx><edx>HHxR:H0HH:HHRH:RRHH:HHHH:xR1H:HHHH:HHHH</edx></cpuFeatureMask><supportsWakeOnLan>false</supportsWakeOnLan></guestOSDescriptor><guestOSDefaultIndex>4</guestOSDefaultIndex><hardwareOptions><hwVersion>4</hwVersion><virtualDeviceOption xsi:type="VirtualSerialPortOption"><type>VirtualSerialPort</type><connectOption><startConnected><supported>true</supported><defaultValue>true</defaultValue></startConnected><allowGuestControl><supported>true</supported><defaultValue>true</defaultValue></allowGuestControl></connectOption><controllerType>VirtualSIOController</controllerType><autoAssignController><supported>false</supported><defaultValue>false</defaultValue></autoAssignController><backingOption xsi:type="VirtualSerialPortDeviceBackingOption"><type>VirtualSerialPortDeviceBackingInfo</type><autoDetectAvailable><supported>true</supported><defaultValue>true</defaultValue></autoDetectAvailable></backingOption><backingOption xsi:type="VirtualSerialPortFileBackingOption"><type>VirtualSerialPortFileBackingInfo</type><fileNameExtensions><choiceInfo><label>Any</label><summary>Serial port output files</summary><key>any</key></choiceInfo><defaultIndex>0</defaultIndex></fileNameExtensions></backingOption><backingOption xsi:type="VirtualSerialPortPipeBackingOption"><type>VirtualSerialPortPipeBackingInfo</type><endpoint><choiceInfo><label>Client</label><summary>Connected to a client</summary><key>client</key></choiceInfo><choiceInfo><label>Server</label><summary>Connected to a server</summary><key>server</key></choiceInfo><defaultIndex>0</defaultIndex></endpoint><noRxLoss><supported>true</supported><defaultValue>true</defaultValue></noRxLoss></backingOption><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay><yieldOnPoll><supported>true</supported><defaultValue>true</defaultValue></yieldOnPoll></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualParallelPortOption"><type>VirtualParallelPort</type><connectOption><startConnected><supported>true</supported><defaultValue>true</defaultValue></startConnected><allowGuestControl><supported>true</supported><defaultValue>true</defaultValue></allowGuestControl></connectOption><controllerType>VirtualSIOController</controllerType><autoAssignController><supported>false</supported><defaultValue>false</defaultValue></autoAssignController><backingOption xsi:type="VirtualParallelPortDeviceBackingOption"><type>VirtualParallelPortDeviceBackingInfo</type><autoDetectAvailable><supported>true</supported><defaultValue>true</defaultValue></autoDetectAvailable></backingOption><backingOption xsi:type="VirtualParallelPortFileBackingOption"><type>VirtualParallelPortFileBackingInfo</type><fileNameExtensions><choiceInfo><label>Any</label><summary>Parallel port output files</summary><key>any</key></choiceInfo><defaultIndex>0</defaultIndex></fileNameExtensions></backingOption><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualFloppyOption"><type>VirtualFloppy</type><connectOption><startConnected><supported>true</supported><defaultValue>true</defaultValue></startConnected><allowGuestControl><supported>true</supported><defaultValue>true</defaultValue></allowGuestControl></connectOption><controllerType>VirtualSIOController</controllerType><autoAssignController><supported>true</supported><defaultValue>true</defaultValue></autoAssignController><backingOption xsi:type="VirtualFloppyDeviceBackingOption"><type>VirtualFloppyDeviceBackingInfo</type><autoDetectAvailable><supported>true</supported><defaultValue>true</defaultValue></autoDetectAvailable></backingOption><backingOption xsi:type="VirtualFloppyImageBackingOption"><type>VirtualFloppyImageBackingInfo</type><fileNameExtensions><choiceInfo><label>.flp</label><summary>Floppy image files</summary><key>flp</key></choiceInfo><defaultIndex>0</defaultIndex></fileNameExtensions></backingOption><backingOption xsi:type="VirtualFloppyRemoteDeviceBackingOption"><type>VirtualFloppyRemoteDeviceBackingInfo</type><autoDetectAvailable><supported>true</supported><defaultValue>true</defaultValue></autoDetectAvailable></backingOption><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualCdromOption"><type>VirtualCdrom</type><connectOption><startConnected><supported>true</supported><defaultValue>true</defaultValue></startConnected><allowGuestControl><supported>true</supported><defaultValue>true</defaultValue></allowGuestControl></connectOption><controllerType>VirtualIDEController</controllerType><autoAssignController><supported>false</supported><defaultValue>false</defaultValue></autoAssignController><backingOption xsi:type="VirtualCdromAtapiBackingOption"><type>VirtualCdromAtapiBackingInfo</type><autoDetectAvailable><supported>true</supported><defaultValue>true</defaultValue></autoDetectAvailable></backingOption><backingOption xsi:type="VirtualCdromIsoBackingOption"><type>VirtualCdromIsoBackingInfo</type><fileNameExtensions><choiceInfo><label>.iso</label><summary>ISO image files</summary><key>iso</key></choiceInfo><defaultIndex>0</defaultIndex></fileNameExtensions></backingOption><backingOption xsi:type="VirtualCdromRemotePassthroughBackingOption"><type>VirtualCdromRemotePassthroughBackingInfo</type><autoDetectAvailable><supported>true</supported><defaultValue>true</defaultValue></autoDetectAvailable><exclusive><supported>true</supported><defaultValue>false</defaultValue></exclusive></backingOption><backingOption xsi:type="VirtualCdromRemoteAtapiBackingOption"><type>VirtualCdromRemoteAtapiBackingInfo</type><autoDetectAvailable><supported>true</supported><defaultValue>true</defaultValue></autoDetectAvailable></backingOption><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualSIOControllerOption"><type>VirtualSIOController</type><autoAssignController><supported>true</supported><defaultValue>true</defaultValue></autoAssignController><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay><devices><min>0</min><max>4</max><defaultValue>0</defaultValue></devices><supportedDevice>VirtualFloppyOption</supportedDevice><supportedDevice>VirtualSerialPortOption</supportedDevice><supportedDevice>VirtualParallelPortOption</supportedDevice><numFloppyDrives><min>0</min><max>2</max><defaultValue>1</defaultValue></numFloppyDrives><numSerialPorts><min>0</min><max>4</max><defaultValue>1</defaultValue></numSerialPorts><numParallelPorts><min>0</min><max>3</max><defaultValue>1</defaultValue></numParallelPorts></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualBusLogicControllerOption"><type>VirtualBusLogicController</type><controllerType>VirtualPCIController</controllerType><autoAssignController><supported>true</supported><defaultValue>true</defaultValue></autoAssignController><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay><devices><min>0</min><max>15</max><defaultValue>0</defaultValue></devices><supportedDevice>VirtualDiskOption</supportedDevice><supportedDevice>VirtualCdromOption</supportedDevice><supportedDevice>VirtualSCSIPassthroughOption</supportedDevice><numSCSIDisks><min>1</min><max>15</max><defaultValue>1</defaultValue></numSCSIDisks><numSCSICdroms><min>0</min><max>15</max><defaultValue>0</defaultValue></numSCSICdroms><numSCSIPassthrough><min>0</min><max>15</max><defaultValue>0</defaultValue></numSCSIPassthrough><sharing>physicalSharing</sharing><sharing>virtualSharing</sharing><sharing>noSharing</sharing><defaultSharedIndex>0</defaultSharedIndex><hotAddRemove><supported>true</supported><defaultValue>true</defaultValue></hotAddRemove><scsiCtlrUnitNumber>7</scsiCtlrUnitNumber></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualLsiLogicControllerOption"><type>VirtualLsiLogicController</type><controllerType>VirtualPCIController</controllerType><autoAssignController><supported>true</supported><defaultValue>true</defaultValue></autoAssignController><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay><devices><min>0</min><max>15</max><defaultValue>0</defaultValue></devices><supportedDevice>VirtualDiskOption</supportedDevice><supportedDevice>VirtualCdromOption</supportedDevice><supportedDevice>VirtualSCSIPassthroughOption</supportedDevice><numSCSIDisks><min>1</min><max>15</max><defaultValue>1</defaultValue></numSCSIDisks><numSCSICdroms><min>0</min><max>15</max><defaultValue>0</defaultValue></numSCSICdroms><numSCSIPassthrough><min>0</min><max>15</max><defaultValue>0</defaultValue></numSCSIPassthrough><sharing>physicalSharing</sharing><sharing>virtualSharing</sharing><sharing>noSharing</sharing><defaultSharedIndex>0</defaultSharedIndex><hotAddRemove><supported>true</supported><defaultValue>true</defaultValue></hotAddRemove><scsiCtlrUnitNumber>7</scsiCtlrUnitNumber></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualVideoCardOption"><type>VirtualMachineVideoCard</type><controllerType>VirtualPCIController</controllerType><autoAssignController><supported>true</supported><defaultValue>true</defaultValue></autoAssignController><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualPointingDeviceOption"><type>VirtualPointingDevice</type><controllerType>VirtualPS2Controller</controllerType><autoAssignController><supported>true</supported><defaultValue>true</defaultValue></autoAssignController><backingOption xsi:type="VirtualPointingDeviceBackingOption"><type>VirtualPointingDeviceDeviceBackingInfo</type><autoDetectAvailable><supported>true</supported><defaultValue>true</defaultValue></autoDetectAvailable><hostPointingDevice><choiceInfo><label>Autodetect</label><summary>Autodetect</summary><key>autodetect</key></choiceInfo><choiceInfo><label>Intellimouse Explorer</label><summary>Intellimouse Explorer</summary><key>intellimouse_explorer</key></choiceInfo><choiceInfo><label>Intellimouse PS2</label><summary>Intellimouse PS2</summary><key>intellimouse_ps2</key></choiceInfo><choiceInfo><label>Logitech Mouseman</label><summary>Logitech Mouseman</summary><key>logitech_mouseman</key></choiceInfo><choiceInfo><label>Microsoft Serial Mouse</label><summary>Microsoft Serial Mouse</summary><key>microsoft_serial</key></choiceInfo><choiceInfo><label>Mouse Systems</label><summary>Mouse Systems</summary><key>mouse_systems</key></choiceInfo><choiceInfo><label>Mouseman Serial</label><summary>Mouseman Serial</summary><key>mouseman_serial</key></choiceInfo><choiceInfo><label>PS2</label><summary>PS2</summary><key>ps_2</key></choiceInfo><defaultIndex>0</defaultIndex></hostPointingDevice></backingOption><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualPS2ControllerOption"><type>VirtualPS2Controller</type><autoAssignController><supported>true</supported><defaultValue>true</defaultValue></autoAssignController><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay><devices><min>0</min><max>2</max><defaultValue>2</defaultValue></devices><supportedDevice>VirtualPointingDeviceOption</supportedDevice><supportedDevice>VirtualKeyboardOption</supportedDevice><numKeyboards><min>1</min><max>1</max><defaultValue>1</defaultValue></numKeyboards><numPointingDevices><min>1</min><max>1</max><defaultValue>1</defaultValue></numPointingDevices></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualPCIControllerOption"><type>VirtualPCIController</type><autoAssignController><supported>true</supported><defaultValue>true</defaultValue></autoAssignController><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay><devices><min>0</min><max>6</max><defaultValue>2</defaultValue></devices><supportedDevice>VirtualSCSIControllerOption</supportedDevice><supportedDevice>VirtualEthernetCardOption</supportedDevice><supportedDevice>VirtualSoundCardOption</supportedDevice><supportedDevice>VirtualVideoCardOption</supportedDevice><supportedDevice>VirtualVMIROMOption</supportedDevice><numSCSIControllers><min>0</min><max>4</max><defaultValue>1</defaultValue></numSCSIControllers><numEthernetCards><min>0</min><max>4</max><defaultValue>1</defaultValue></numEthernetCards><numVideoCards><min>1</min><max>1</max><defaultValue>1</defaultValue></numVideoCards><numSoundCards><min>1</min><max>1</max><defaultValue>1</defaultValue></numSoundCards><numVmiRoms><min>0</min><max>1</max><defaultValue>0</defaultValue></numVmiRoms></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualKeyboardOption"><type>VirtualKeyboard</type><controllerType>VirtualPS2Controller</controllerType><autoAssignController><supported>true</supported><defaultValue>true</defaultValue></autoAssignController><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualIDEControllerOption"><type>VirtualIDEController</type><autoAssignController><supported>true</supported><defaultValue>true</defaultValue></autoAssignController><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay><devices><min>0</min><max>2</max><defaultValue>0</defaultValue></devices><supportedDevice>VirtualDiskOption</supportedDevice><supportedDevice>VirtualCdromOption</supportedDevice><numIDEDisks><min>0</min><max>0</max><defaultValue>0</defaultValue></numIDEDisks><numIDECdroms><min>0</min><max>2</max><defaultValue>1</defaultValue></numIDECdroms></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualVMIROMOption"><type>VirtualMachineVMIROM</type><controllerType>VirtualPCIController</controllerType><autoAssignController><supported>true</supported><defaultValue>true</defaultValue></autoAssignController><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualE1000Option"><type>VirtualE1000</type><connectOption><startConnected><supported>true</supported><defaultValue>true</defaultValue></startConnected><allowGuestControl><supported>true</supported><defaultValue>true</defaultValue></allowGuestControl></connectOption><controllerType>VirtualPCIController</controllerType><autoAssignController><supported>true</supported><defaultValue>true</defaultValue></autoAssignController><backingOption xsi:type="VirtualEthernetCardNetworkBackingOption"><type>VirtualEthernetCardNetworkBackingInfo</type><autoDetectAvailable><supported>false</supported><defaultValue>false</defaultValue></autoDetectAvailable></backingOption><backingOption xsi:type="VirtualEthernetCardLegacyNetworkBackingOption"><type>VirtualEthernetCardLegacyNetworkBackingInfo</type><autoDetectAvailable><supported>false</supported><defaultValue>false</defaultValue></autoDetectAvailable></backingOption><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay><supportedOUI><choiceInfo><label>00:50:56</label><summary>OUI</summary><key>00:50:56</key></choiceInfo><defaultIndex>0</defaultIndex></supportedOUI><macType><choiceInfo><label>Assigned</label><summary>Assigned</summary><key>assigned</key></choiceInfo><choiceInfo><label>Manual</label><summary>Manual</summary><key>manual</key></choiceInfo><choiceInfo><label>Generated</label><summary>Generated</summary><key>generated</key></choiceInfo><defaultIndex>0</defaultIndex></macType><wakeOnLanEnabled><supported>true</supported><defaultValue>true</defaultValue></wakeOnLanEnabled></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualVmxnet2Option"><type>VirtualVmxnet2</type><connectOption><startConnected><supported>true</supported><defaultValue>true</defaultValue></startConnected><allowGuestControl><supported>true</supported><defaultValue>true</defaultValue></allowGuestControl></connectOption><controllerType>VirtualPCIController</controllerType><autoAssignController><supported>true</supported><defaultValue>true</defaultValue></autoAssignController><backingOption xsi:type="VirtualEthernetCardNetworkBackingOption"><type>VirtualEthernetCardNetworkBackingInfo</type><autoDetectAvailable><supported>false</supported><defaultValue>false</defaultValue></autoDetectAvailable></backingOption><backingOption xsi:type="VirtualEthernetCardLegacyNetworkBackingOption"><type>VirtualEthernetCardLegacyNetworkBackingInfo</type><autoDetectAvailable><supported>false</supported><defaultValue>false</defaultValue></autoDetectAvailable></backingOption><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay><supportedOUI><choiceInfo><label>00:50:56</label><summary>OUI</summary><key>00:50:56</key></choiceInfo><defaultIndex>0</defaultIndex></supportedOUI><macType><choiceInfo><label>Assigned</label><summary>Assigned</summary><key>assigned</key></choiceInfo><choiceInfo><label>Manual</label><summary>Manual</summary><key>manual</key></choiceInfo><choiceInfo><label>Generated</label><summary>Generated</summary><key>generated</key></choiceInfo><defaultIndex>0</defaultIndex></macType><wakeOnLanEnabled><supported>true</supported><defaultValue>true</defaultValue></wakeOnLanEnabled></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualPCNet32Option"><type>VirtualPCNet32</type><connectOption><startConnected><supported>true</supported><defaultValue>true</defaultValue></startConnected><allowGuestControl><supported>true</supported><defaultValue>true</defaultValue></allowGuestControl></connectOption><controllerType>VirtualPCIController</controllerType><autoAssignController><supported>true</supported><defaultValue>true</defaultValue></autoAssignController><backingOption xsi:type="VirtualEthernetCardNetworkBackingOption"><type>VirtualEthernetCardNetworkBackingInfo</type><autoDetectAvailable><supported>false</supported><defaultValue>false</defaultValue></autoDetectAvailable></backingOption><backingOption xsi:type="VirtualEthernetCardLegacyNetworkBackingOption"><type>VirtualEthernetCardLegacyNetworkBackingInfo</type><autoDetectAvailable><supported>false</supported><defaultValue>false</defaultValue></autoDetectAvailable></backingOption><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>false</plugAndPlay><supportedOUI><choiceInfo><label>00:50:56</label><summary>OUI</summary><key>00:50:56</key></choiceInfo><defaultIndex>0</defaultIndex></supportedOUI><macType><choiceInfo><label>Assigned</label><summary>Assigned</summary><key>assigned</key></choiceInfo><choiceInfo><label>Manual</label><summary>Manual</summary><key>manual</key></choiceInfo><choiceInfo><label>Generated</label><summary>Generated</summary><key>generated</key></choiceInfo><defaultIndex>0</defaultIndex></macType><wakeOnLanEnabled><supported>true</supported><defaultValue>true</defaultValue></wakeOnLanEnabled><supportsMorphing>true</supportsMorphing></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualVmxnetOption"><type>VirtualVmxnet</type><connectOption><startConnected><supported>true</supported><defaultValue>true</defaultValue></startConnected><allowGuestControl><supported>true</supported><defaultValue>true</defaultValue></allowGuestControl></connectOption><controllerType>VirtualPCIController</controllerType><autoAssignController><supported>true</supported><defaultValue>true</defaultValue></autoAssignController><backingOption xsi:type="VirtualEthernetCardNetworkBackingOption"><type>VirtualEthernetCardNetworkBackingInfo</type><autoDetectAvailable><supported>false</supported><defaultValue>false</defaultValue></autoDetectAvailable></backingOption><backingOption xsi:type="VirtualEthernetCardLegacyNetworkBackingOption"><type>VirtualEthernetCardLegacyNetworkBackingInfo</type><autoDetectAvailable><supported>false</supported><defaultValue>false</defaultValue></autoDetectAvailable></backingOption><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>true</deprecated><plugAndPlay>false</plugAndPlay><supportedOUI><choiceInfo><label>00:50:56</label><summary>OUI</summary><key>00:50:56</key></choiceInfo><defaultIndex>0</defaultIndex></supportedOUI><macType><choiceInfo><label>Assigned</label><summary>Assigned</summary><key>assigned</key></choiceInfo><choiceInfo><label>Manual</label><summary>Manual</summary><key>manual</key></choiceInfo><choiceInfo><label>Generated</label><summary>Generated</summary><key>generated</key></choiceInfo><defaultIndex>0</defaultIndex></macType><wakeOnLanEnabled><supported>true</supported><defaultValue>true</defaultValue></wakeOnLanEnabled></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualDiskOption"><type>VirtualDisk</type><controllerType>VirtualSCSIController</controllerType><autoAssignController><supported>false</supported><defaultValue>false</defaultValue></autoAssignController><backingOption xsi:type="VirtualDiskRawDiskMappingVer1BackingOption"><type>VirtualDiskRawDiskMappingVer1BackingInfo</type><autoDetectAvailable><supported>false</supported><defaultValue>false</defaultValue></autoDetectAvailable><descriptorFileNameExtensions><choiceInfo><label>.dsk</label><summary>Disk description file</summary><key>dsk</key></choiceInfo><choiceInfo><label>.rdm</label><summary>RDM description file</summary><key>rdm</key></choiceInfo><choiceInfo><label>.vmdk</label><summary>VMDK Disk description file</summary><key>vmdk</key></choiceInfo><defaultIndex>0</defaultIndex></descriptorFileNameExtensions><compatibilityMode><choiceInfo><label>Virtual Mode</label><summary>Virtual mode - Disk modes are respected</summary><key>virtualMode</key></choiceInfo><choiceInfo><label>physical</label><summary>Physical mode - Commands are passed through to the LUN</summary><key>physicalMode</key></choiceInfo><defaultIndex>0</defaultIndex></compatibilityMode><diskMode><choiceInfo><label>persistent</label><summary>Persistent</summary><key>persistent</key></choiceInfo><choiceInfo><label>persistent</label><summary>Persistent</summary><key>independent_persistent</key></choiceInfo><choiceInfo><label>independent-nonpersistent</label><summary>Independent nonpersistent disks</summary><key>independent_nonpersistent</key></choiceInfo><defaultIndex>0</defaultIndex></diskMode><uuid>true</uuid></backingOption><backingOption xsi:type="VirtualDiskFlatVer2BackingOption"><type>VirtualDiskFlatVer2BackingInfo</type><fileNameExtensions><choiceInfo><label>.vmdk</label><summary>Disk file</summary><key>vmdk</key></choiceInfo><defaultIndex>0</defaultIndex></fileNameExtensions><diskMode><choiceInfo><label>persistent</label><summary>Persistent disks</summary><key>persistent</key></choiceInfo><choiceInfo><label>persistent</label><summary>Persistent disks</summary><key>independent_persistent</key></choiceInfo><choiceInfo><label>independent-nonpersistent</label><summary>Independent non-persistent disks</summary><key>independent_nonpersistent</key></choiceInfo><defaultIndex>0</defaultIndex></diskMode><split><supported>false</supported><defaultValue>false</defaultValue></split><writeThrough><supported>false</supported><defaultValue>false</defaultValue></writeThrough><growable>true</growable><hotGrowable>true</hotGrowable><uuid>true</uuid></backingOption><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>true</plugAndPlay><capacityInKB><min>1024</min><max>17179869184</max><defaultValue>1048576</defaultValue></capacityInKB></virtualDeviceOption><virtualDeviceOption xsi:type="VirtualSCSIPassthroughOption"><type>VirtualSCSIPassthrough</type><controllerType>VirtualSCSIController</controllerType><autoAssignController><supported>false</supported><defaultValue>false</defaultValue></autoAssignController><backingOption xsi:type="VirtualSCSIPassthroughDeviceBackingOption"><type>VirtualSCSIPassthroughDeviceBackingInfo</type><autoDetectAvailable><supported>false</supported><defaultValue>false</defaultValue></autoDetectAvailable></backingOption><defaultBackingOptionIndex>0</defaultBackingOptionIndex><deprecated>false</deprecated><plugAndPlay>true</plugAndPlay></virtualDeviceOption><deviceListReadonly>false</deviceListReadonly><numCPU>1</numCPU><numCPU>2</numCPU><numCPU>4</numCPU><numCpuReadonly>false</numCpuReadonly><memoryMB><min>4</min><max>65532</max><defaultValue>256</defaultValue></memoryMB><numPCIControllers><min>1</min><max>1</max><defaultValue>1</defaultValue></numPCIControllers><numIDEControllers><min>2</min><max>2</max><defaultValue>2</defaultValue></numIDEControllers><numUSBControllers><min>0</min><max>1</max><defaultValue>0</defaultValue></numUSBControllers><numSIOControllers><min>1</min><max>1</max><defaultValue>1</defaultValue></numSIOControllers><numPS2Controllers><min>1</min><max>1</max><defaultValue>1</defaultValue></numPS2Controllers></hardwareOptions><capabilities><snapshotOperationsSupported>true</snapshotOperationsSupported><multipleSnapshotsSupported>true</multipleSnapshotsSupported><snapshotConfigSupported>true</snapshotConfigSupported><poweredOffSnapshotsSupported>true</poweredOffSnapshotsSupported><memorySnapshotsSupported>true</memorySnapshotsSupported><revertToSnapshotSupported>true</revertToSnapshotSupported><quiescedSnapshotsSupported>true</quiescedSnapshotsSupported><disableSnapshotsSupported>false</disableSnapshotsSupported><lockSnapshotsSupported>false</lockSnapshotsSupported><consolePreferencesSupported>true</consolePreferencesSupported><cpuFeatureMaskSupported>true</cpuFeatureMaskSupported><s1AcpiManagementSupported>true</s1AcpiManagementSupported><settingScreenResolutionSupported>true</settingScreenResolutionSupported><toolsAutoUpdateSupported>false</toolsAutoUpdateSupported><vmNpivWwnSupported>true</vmNpivWwnSupported><npivWwnOnNonRdmVmSupported>false</npivWwnOnNonRdmVmSupported><swapPlacementSupported>true</swapPlacementSupported><toolsSyncTimeSupported>true</toolsSyncTimeSupported><virtualMmuUsageSupported>true</virtualMmuUsageSupported><diskSharesSupported>true</diskSharesSupported><bootOptionsSupported>true</bootOptionsSupported><settingVideoRamSizeSupported>true</settingVideoRamSizeSupported></capabilities><datastore><unsupportedVolumes><fileSystemType>HostVmfsVolume</fileSystemType><majorVersion>2</majorVersion></unsupportedVolumes></datastore><defaultDevice xsi:type="VirtualIDEController"><key>200</key><deviceInfo><label>IDE 0</label><summary>IDE 0</summary></deviceInfo><busNumber>0</busNumber></defaultDevice><defaultDevice xsi:type="VirtualIDEController"><key>201</key><deviceInfo><label>IDE 1</label><summary>IDE 1</summary></deviceInfo><busNumber>1</busNumber></defaultDevice><defaultDevice xsi:type="VirtualPS2Controller"><key>300</key><deviceInfo><label>PS2 Controller </label><summary>PS2 Controller</summary></deviceInfo><busNumber>0</busNumber></defaultDevice><defaultDevice xsi:type="VirtualPCIController"><key>100</key><deviceInfo><label>PCI Controller </label><summary>PCI Controller</summary></deviceInfo><busNumber>0</busNumber></defaultDevice><defaultDevice xsi:type="VirtualSIOController"><key>400</key><deviceInfo><label>SIO Controller </label><summary>SIO Controller</summary></deviceInfo><busNumber>0</busNumber></defaultDevice><defaultDevice xsi:type="VirtualKeyboard"><key>600</key><deviceInfo><label>Keyboard </label><summary>Keyboard</summary></deviceInfo><controllerKey>300</controllerKey><unitNumber>0</unitNumber></defaultDevice><defaultDevice xsi:type="VirtualPointingDevice"><key>700</key><deviceInfo><label>Pointing Device</label><summary>Pointing device; Device</summary></deviceInfo><backing xsi:type="VirtualPointingDeviceDeviceBackingInfo"><deviceName></deviceName><useAutoDetect>false</useAutoDetect><hostPointingDevice>autodetect</hostPointingDevice></backing><controllerKey>300</controllerKey><unitNumber>1</unitNumber></defaultDevice><defaultDevice xsi:type="VirtualMachineVideoCard"><key>500</key><deviceInfo><label>Video Card </label><summary>Video Card</summary></deviceInfo><controllerKey>100</controllerKey><unitNumber>0</unitNumber><videoRamSizeInKB>4096</videoRamSizeInKB></defaultDevice><supportedMonitorType>release</supportedMonitorType><supportedMonitorType>debug</supportedMonitorType></returnval></QueryConfigOptionResponse>
</soapenv:Body>
</soapenv:Envelope>
"""

vmwareFindByInventoryPathReq = '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><SOAP-ENV:Header></SOAP-ENV:Header><SOAP-ENV:Body xmlns:ns1="urn:vim25"><ns1:FindByInventoryPath><_this type="SearchIndex">SearchIndex</_this><ns1:inventoryPath>/rPath/vm/%s</ns1:inventoryPath></ns1:FindByInventoryPath></SOAP-ENV:Body></SOAP-ENV:Envelope>'

vmwareFindByInventoryPathResp = """\
HTTP/1.1 200 OK
Date: Thu, 21 May 2009 22:05:37 GMT
Cache-Control: no-cache
Content-Type: text/xml; charset=utf-8
Content-Length: 456

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
<FindByInventoryPathResponse xmlns="urn:vim25"><returnval type="VirtualMachine">%s</returnval></FindByInventoryPathResponse>
</soapenv:Body>
</soapenv:Envelope>
"""

vmwareFindByInventoryPathRespFail = """\
HTTP/1.1 200 OK
Date: Thu, 21 May 2009 22:21:40 GMT
Cache-Control: no-cache
Content-Type: text/xml; charset=utf-8
Content-Length: 404

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
<FindByInventoryPathResponse xmlns="urn:vim25"></FindByInventoryPathResponse>
</soapenv:Body>
</soapenv:Envelope>
"""

vmwareRegisterVMreq = '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><SOAP-ENV:Header></SOAP-ENV:Header><SOAP-ENV:Body xmlns:ns1="urn:vim25"><ns1:RegisterVM_Task><_this type="Folder" xsi:type="ns1:ManagedObjectReference">group-v3</_this><ns1:path>[nas2-nfs]/template-some-file-6-1-x86-1/foo.vmx</ns1:path><ns1:name>template-some-file-6-1-x86-1</ns1:name><ns1:asTemplate>false</ns1:asTemplate><pool type="ResourcePool">resgroup-50</pool><host type="HostSystem">host-206</host></ns1:RegisterVM_Task></SOAP-ENV:Body></SOAP-ENV:Envelope>'

vmwareRegisterVMresp = """\
HTTP/1.1 200 OK
Date: Thu, 21 May 2009 22:21:40 GMT
Cache-Control: no-cache
Content-Type: text/xml; charset=utf-8
Content-Length: 443

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
 <RegisterVM_TaskResponse xmlns="urn:vim25">
 <returnval type="Task">task-42</returnval>
 </RegisterVM_TaskResponse>
</soapenv:Body>
</soapenv:Envelope>
"""

vmwareRegisterVMreq2 = vmwareRegisterVMreq.replace(
    'template-some-file-6-1-x86-1', 'instance-foo')

vmwareCreateFilterForTaskReq = (
 '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"'
 ' xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"'
 ' xmlns:ZSI="http://www.zolera.com/schemas/ZSI/"'
 ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
 ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
 '<SOAP-ENV:Header>'
 '</SOAP-ENV:Header>'
 '<SOAP-ENV:Body xmlns:ns1="urn:vim25">'
 '<ns1:CreateFilter>'
 '<_this type="PropertyCollector">propertyCollector</_this>'
 '<spec xsi:type="ns1:PropertyFilterSpec">'
 '<propSet xsi:type="ns1:PropertySpec">'
 '<ns1:type>Task</ns1:type>'
 '<ns1:pathSet>info.state</ns1:pathSet>'
 '<ns1:pathSet>info.progress</ns1:pathSet>'
 '<ns1:pathSet>info.error</ns1:pathSet>'
 '</propSet>'
 '<objectSet xsi:type="ns1:ObjectSpec">'
 '<obj type="Task">%s</obj><ns1:skip>false</ns1:skip>'
 '</objectSet>'
 '</spec>'
 '<ns1:partialUpdates>true</ns1:partialUpdates>'
 '</ns1:CreateFilter></SOAP-ENV:Body></SOAP-ENV:Envelope>')

vmwareCreateFilterForTaskRespTmpl = (
 '<?xml version="1.0" encoding="UTF-8"?>\n'
 '<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"\n'
 ' xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"\n'
 ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"\n'
 ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
 '<soapenv:Body>\n<CreateFilterResponse xmlns="urn:vim25">'
 '<returnval type="PropertyFilter">session[%s]%s</returnval>'
 '</CreateFilterResponse>\n'
 '</soapenv:Body>\n'
 '</soapenv:Envelope>')

# no progress report for this one
vmwareCreateFilterForHttpNfcLeaseReqTemplate = vmwareCreateFilterForTaskReq.replace(
 '<ns1:pathSet>info.progress</ns1:pathSet>', '').replace(
 '<ns1:type>Task</ns1:type>'
 '<ns1:pathSet>info.state</ns1:pathSet>'
 '<ns1:pathSet>info.error</ns1:pathSet>',
   '<ns1:type>HttpNfcLease</ns1:type>'
   '<ns1:pathSet>state</ns1:pathSet>').replace(
 '<obj type="Task">%s',
   '<obj type="HttpNfcLease">session[%s]%s')

vmwareHttpNfcLeaseSession1 = ('B5C33EEA-25CE-461E-A752-A086E76E88B6',
    'CDC328E3-F102-49B7-A698-D9A6A12D6AE3')

vmwareCreateFilterForHttpNfcLeaseReq1 = vmwareCreateFilterForHttpNfcLeaseReqTemplate % vmwareHttpNfcLeaseSession1

vmwareFilter1 = ('uuidA1', 'uuidA1')

vmwareCreateFilterForHttpNfcLeaseRespTemplate = vmwareCreateFilterForTaskRespTmpl

vmwareCreateFilterForHttpNfcLeaseResp1 = HTTPResponse(
    vmwareCreateFilterForHttpNfcLeaseRespTemplate % vmwareFilter1)

vmwareDestroyFilterReq = (
 '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"'
 ' xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"'
 ' xmlns:ZSI="http://www.zolera.com/schemas/ZSI/"'
 ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
 ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
 '<SOAP-ENV:Header></SOAP-ENV:Header>'
 '<SOAP-ENV:Body xmlns:ns1="urn:vim25"><ns1:DestroyPropertyFilter>'
 '<_this type="PropertyFilter">session[%s]%s</_this>'
 '</ns1:DestroyPropertyFilter>'
 '</SOAP-ENV:Body>'
 '</SOAP-ENV:Envelope>')

vmwareDestroyFilterResp = HTTPResponse(
 '<?xml version="1.0" encoding="UTF-8"?>\n'
 '<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"\n'
 ' xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"\n'
 ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"\n'
 ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
 '<soapenv:Body>\n'
 '<DestroyPropertyFilterResponse xmlns="urn:vim25"></DestroyPropertyFilterResponse>\n'
 '</soapenv:Body>\n'
 '</soapenv:Envelope>')

vmwareRetrievePropertiesTaskReq = _vmwareReqRetrievePropertiesSimpleTemplate % \
    dict(klass = 'Task', path = 'info', value = '%s')

vmwareRetrievePropertiesTaskResp = HTTPResponse("""\
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Body>
    <RetrievePropertiesResponse xmlns="urn:vim25">
      <returnval>
        <obj type="Task">task-10269</obj>
        <propSet>
          <name>info</name>
          <val xsi:type="TaskInfo">
            <key>task-10269</key>
            <task type="Task">task-10269</task>
            <name>CloneVM_Task</name>
            <descriptionId>VirtualMachine.clone</descriptionId>
            <entity type="VirtualMachine">vm-987</entity>
            <entityName>template-remote-update-1-x86_64</entityName>
            <state>success</state>
            <cancelled>false</cancelled>
            <cancelable>false</cancelable>
            <result type="VirtualMachine" xsi:type="ManagedObjectReference">vm-4739</result>
            <reason xsi:type="TaskReasonUser">
              <userName>eng</userName>
            </reason>
            <queueTime>2009-05-22T20:20:27.28175Z</queueTime>
            <startTime>2009-05-22T20:20:27.297375Z</startTime>
            <completeTime>2009-05-22T20:33:28.641125Z</completeTime>
            <eventChainId>300977</eventChainId>
          </val>
        </propSet>
      </returnval>
    </RetrievePropertiesResponse>
  </soapenv:Body>
</soapenv:Envelope>
""")

vmwareCloneVMTaskReq = (
'<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
'<SOAP-ENV:Header></SOAP-ENV:Header>'
'<SOAP-ENV:Body xmlns:ns1="urn:vim25">'
 '<ns1:CloneVM_Task>'
  '<_this type="VirtualMachine">vm-987</_this>'
  '<folder type="Folder">group-v3</folder>'
  '<ns1:name>instance-foo</ns1:name>'
  '<spec>'
   '<location>'
    '<datastore type="Datastore">datastore-18</datastore>'
    '<pool type="ResourcePool">resgroup-50</pool>'
   '</location>'
   '<ns1:template>false</ns1:template>'
   '<config>'
    '<ns1:annotation>just words and stuff</ns1:annotation>'
    '<deviceChange xsi:type="ns1:VirtualDeviceConfigSpec">'
      '<operation>edit</operation>'
      '<device xsi:type="ns1:VirtualPCNet32">'
        '<ns1:key>4000</ns1:key>'
        '<deviceInfo>'
          '<ns1:label>Network Adapter 1</ns1:label>'
          '<ns1:summary>VM Network</ns1:summary>'
        '</deviceInfo>'
        '<backing xsi:type="ns1:VirtualEthernetCardDistributedVirtualPortBackingInfo">'
          '<port>'
            '<ns1:switchUuid>19 e9 34 50 73 a6 9e 1d-12 1b 2c 4b b9 5a 62 17</ns1:switchUuid>'
            '<ns1:portgroupKey>dvportgroup-9987</ns1:portgroupKey>'
          '</port>'
        '</backing>'
        '<connectable>'
          '<ns1:startConnected>true</ns1:startConnected>'
          '<ns1:allowGuestControl>true</ns1:allowGuestControl>'
          '<ns1:connected>true</ns1:connected>'
        '</connectable>'
        '<ns1:controllerKey>100</ns1:controllerKey>'
        '<ns1:unitNumber>7</ns1:unitNumber>'
        '<ns1:addressType>assigned</ns1:addressType>'
        '<ns1:macAddress>00:50:56:b4:31:33</ns1:macAddress>'
        '<ns1:wakeOnLanEnabled>true</ns1:wakeOnLanEnabled>'
      '</device>'
    '</deviceChange>'
   '</config>'
   '<ns1:powerOn>false</ns1:powerOn>'
  '</spec>'
 '</ns1:CloneVM_Task>'
'</SOAP-ENV:Body>'
'</SOAP-ENV:Envelope>'
)

vmwareCloneVMTaskReq2 = vmwareCloneVMTaskReq.replace(
    'vm-987', 'vm-1023')

vmwareCloneVMTaskReq3 = vmwareCloneVMTaskReq.replace(
    '<_this type="VirtualMachine">vm-987</_this>',
    '<_this type="VirtualMachine" xsi:type="ns1:ManagedObjectReference">vm-4739</_this>')

vmwareCloneVMTaskResp = """\
HTTP/1.1 200 OK
Date: Fri, 22 May 2009 20:20:27 GMT
Cache-Control: no-cache
Content-Type: text/xml; charset=utf-8
Content-Length: 432

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
<CloneVM_TaskResponse xmlns="urn:vim25"><returnval type="Task">%s</returnval></CloneVM_TaskResponse>
</soapenv:Body>
</soapenv:Envelope>
"""

vmwareReconfigVMTaskReq2 = '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><SOAP-ENV:Header></SOAP-ENV:Header><SOAP-ENV:Body xmlns:ns1="urn:vim25"><ns1:ReconfigVM_Task><_this type="VirtualMachine" xsi:type="ns1:ManagedObjectReference">vm-4739</_this><spec><ns1:numCPUs>1</ns1:numCPUs><ns1:memoryMB>1024</ns1:memoryMB><deviceChange xsi:type="ns1:VirtualDeviceConfigSpec"><operation>add</operation><device xsi:type="ns1:VirtualCdrom"><ns1:key>-1</ns1:key><backing xsi:type="ns1:VirtualCdromIsoBackingInfo"><ns1:fileName>[nas2-nfs]misa-remote-update-4/credentials.iso</ns1:fileName><datastore type="Datastore" xsi:type="ns1:ManagedObjectReference">datastore-18</datastore></backing><ns1:controllerKey>200</ns1:controllerKey><ns1:unitNumber>0</ns1:unitNumber></device></deviceChange></spec></ns1:ReconfigVM_Task></SOAP-ENV:Body></SOAP-ENV:Envelope>'

vmwareReconfigVMTaskReqTemplate = (
'<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
 '<SOAP-ENV:Header></SOAP-ENV:Header>'
 '<SOAP-ENV:Body xmlns:ns1="urn:vim25">'
   '<ns1:ReconfigVM_Task>'
    '<_this type="VirtualMachine" xsi:type="ns1:ManagedObjectReference">%(vm)s</_this>'
    '<spec>'
     '<ns1:annotation>rba-uuid: %(uuid)s</ns1:annotation>'
     '%(extraSpec)s'
    '</spec>'
   '</ns1:ReconfigVM_Task>'
   '</SOAP-ENV:Body>'
'</SOAP-ENV:Envelope>')

vmwareReconfigVMTaskReq = vmwareReconfigVMTaskReqTemplate % dict(
    vm = 'vm-4739',
    uuid = '361d7fa1-d994-31e1-6a3a-438c8d4ebaa7',
    extraSpec = '',
)

vmwareReconfigVMTaskReq3 = vmwareReconfigVMTaskReq.replace(
    '361d7fa1-d994-31e1-6a3a-438c8d4ebaa7',
    '00000000-0000-0000-0000-000000000000')

vmwareReconfigVMTaskReq4 = vmwareReconfigVMTaskReq2.replace(
    ' xsi:type="ns1:ManagedObjectReference">vm-4739<',
    '>vm-987<')

_vmwareReconfigVMTaskReq5 = (vmwareReconfigVMTaskReqTemplate % dict(
    vm = 'vm-987',
    uuid = 'aaaaaabb-bbbb-bbbc-cccc-ccccccdddddd',
    extraSpec = (
        '<deviceChange xsi:type="ns1:VirtualDeviceConfigSpec">'
          '<operation>add</operation>'
          '<device xsi:type="ns1:VirtualPCNet32">'
            '<ns1:key>-1</ns1:key>'
            '<backing xsi:type="ns1:VirtualEthernetCardDistributedVirtualPortBackingInfo">'
              '<port>'
                '<ns1:switchUuid>19 e9 34 50 73 a6 9e 1d-12 1b 2c 4b b9 5a 62 17</ns1:switchUuid>'
                '<ns1:portgroupKey>dvportgroup-9987</ns1:portgroupKey>'
              '</port>'
            '</backing>'
            '<ns1:addressType>generated</ns1:addressType>'
          '</device>'
        '</deviceChange>'
    )
))

vmwareReconfigVMTaskReq5 = _vmwareReconfigVMTaskReq5.replace(
    '<_this type="VirtualMachine" xsi:type="ns1:ManagedObjectReference">',
    '<_this type="VirtualMachine">')

vmwareReconfigVMTaskReq6 = _vmwareReconfigVMTaskReq5.replace(
    'aaaaaabb-bbbb-bbbc-cccc-ccccccdddddd',
    '361d7fa1-d994-31e1-6a3a-438c8d4ebaa7').replace('vm-987', 'vm-4739')

vmwareReconfigVMTaskReq7 = vmwareReconfigVMTaskReq6.replace(
    '<ns1:annotation>rba-uuid: 361d7fa1-d994-31e1-6a3a-438c8d4ebaa7</ns1:annotation>',
    '')

vmwareReconfigVMTaskReq8 = vmwareReconfigVMTaskReq5.replace(
    '<ns1:annotation>rba-uuid: aaaaaabb-bbbb-bbbc-cccc-ccccccdddddd</ns1:annotation>',

    '')
vmwareReconfigVMTaskResp = """\
HTTP/1.1 200 OK
Date: Fri, 22 May 2009 20:33:32 GMT
Cache-Control: no-cache
Content-Type: text/xml; charset=utf-8
Content-Length: 438

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
<ReconfigVM_TaskResponse xmlns="urn:vim25"><returnval type="Task">%s</returnval></ReconfigVM_TaskResponse>
</soapenv:Body>
</soapenv:Envelope>
"""

vmwarePowerOnVMTaskReqTempl = '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><SOAP-ENV:Header></SOAP-ENV:Header><SOAP-ENV:Body xmlns:ns1="urn:vim25"><ns1:PowerOnVM_Task><_this type="VirtualMachine" xsi:type="ns1:ManagedObjectReference">%s</_this></ns1:PowerOnVM_Task></SOAP-ENV:Body></SOAP-ENV:Envelope>'

vmwarePowerOnVMTaskReqTempl2 = vmwarePowerOnVMTaskReqTempl.replace(
     ' xsi:type="ns1:ManagedObjectReference"', '')

vmwarePowerOnVMTaskResp = """\
HTTP/1.1 200 OK
Date: Fri, 22 May 2009 20:33:34 GMT
Cache-Control: no-cache
Content-Type: text/xml; charset=utf-8
Content-Length: %s

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
<PowerOnVM_TaskResponse xmlns="urn:vim25"><returnval type="Task">%s</returnval></PowerOnVM_TaskResponse>
</soapenv:Body>
</soapenv:Envelope>"""

vmwareMarkAsTemplateReq1 = '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><SOAP-ENV:Header></SOAP-ENV:Header><SOAP-ENV:Body xmlns:ns1="urn:vim25"><ns1:MarkAsTemplate><_this type="VirtualMachine">vm-987</_this></ns1:MarkAsTemplate></SOAP-ENV:Body></SOAP-ENV:Envelope>'

vmwareMarkAsTemplateReq2 = vmwareMarkAsTemplateReq1.replace(
    'vm-987', 'vm-4739').replace(
        '<_this type="VirtualMachine"',
        '<_this type="VirtualMachine" xsi:type="ns1:ManagedObjectReference"')

vmwareMarkAsTemplateResp = """\
HTTP/1.1 200 OK
Date: Fri, 22 May 2009 20:33:34 GMT
Cache-Control: no-cache
Content-Type: text/xml; charset=utf-8
Content-Length: 437

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
<MarkAsTemplateResponse xmlns="urn:vim25"><returnval type="Task">task-foo</returnval></MarkAsTemplateResponse>
</soapenv:Body>
</soapenv:Envelope>"""

vmwareRetrievePropertiesDatacenterReq = \
    _vmwareReqRetrievePropertiesSimpleTemplate % dict(
        klass = 'Datacenter', path = 'hostFolder', value = 'datacenter-2')

vmwareRetrievePropertiesDatacenterResp = HTTPResponse("""\
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
<RetrievePropertiesResponse xmlns="urn:vim25"><returnval><obj type="Datacenter">datacenter-2</obj><propSet><name>vmFolder</name><val type="Folder" xsi:type="ManagedObjectReference">group-v3</val></propSet></returnval></RetrievePropertiesResponse>
</soapenv:Body>
</soapenv:Envelope>
""")

vmwareRetrievePropertiesVMNetworkReq1 = \
    _vmwareReqRetrievePropertiesSimpleTemplate % dict(
        klass = 'VirtualMachine', path = 'network', value = 'vm-987')

vmwareRetrievePropertiesVMNetworkReq2 = \
    _vmwareReqRetrievePropertiesSimpleTypedTemplate % dict(
        klass = 'VirtualMachine', path = 'network', value = 'vm-4739',
        rklass = "ns1:ManagedObjectReference")

vmwareRetrievePropertiesVMNetworkResp1 = HTTPResponse("""\
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
  <RetrievePropertiesResponse xmlns="urn:vim25">
    <returnval>
      <obj type="VirtualMachine">vm-987</obj>
        <propSet>
          <name>network</name>
          <val xsi:type="ArrayOfManagedObjectReference">
          </val>
        </propSet>
    </returnval>
  </RetrievePropertiesResponse>
</soapenv:Body>
</soapenv:Envelope>
""")

vmwareRetrievePropertiesDVSConfigReq = _vmwareReqRetrievePropertiesSimpleTemplate % \
    dict(klass = 'DistributedVirtualPortgroup',
        path = 'config.distributedVirtualSwitch',
        value = 'dvportgroup-9987')

vmwareRetrievePropertiesDVSConfigResp = HTTPResponse(
    _vmwareRespRetrievePropertiesTemplate % (
      _vmwareReturnValSimpleTemplate % dict(
        klass = 'DistributedVirtualPortgroup',
        path = 'config.distributedVirtualSwitch',
        value = 'dvportgroup-9987',
        rklass = 'VmwareDistributedVirtualSwitch',
        rtype = 'ManagedObjectReference',
        propval = 'dvs-9985')
    )
)

vmwareRetrievePropertiesDVSUuidReq = _vmwareReqRetrievePropertiesSimpleTypedTemplate % \
    dict(klass = 'VmwareDistributedVirtualSwitch',
        rklass = 'ns1:ManagedObjectReference',
        path = 'uuid',
        value = 'dvs-9985')

vmwareRetrievePropertiesDVSUuidResp = HTTPResponse(
    _vmwareRespRetrievePropertiesTemplate % (
      _vmwareReturnValSimpleTemplate % dict(
        klass = 'VmwareDistributedVirtualSwitch',
        path = 'uuid',
        value = 'dvs-9985',
        rklass = 'xsd:string',
        rtype = 'xsd:string',
        propval = '19 e9 34 50 73 a6 9e 1d-12 1b 2c 4b b9 5a 62 17')
    )
)

vmwareRetrievePropertiesReq1 = vmwareReqGetVirtualMachineProps1.replace(
 '<ns1:type>VirtualMachine</ns1:type>', '<ns1:type>Datacenter</ns1:type>').replace(
 '<ns1:pathSet>config.annotation</ns1:pathSet>'
 '<ns1:pathSet>config.template</ns1:pathSet>'
 '<ns1:pathSet>runtime.powerState</ns1:pathSet>'
 '<ns1:pathSet>runtime.bootTime</ns1:pathSet>'
 '<ns1:pathSet>config.uuid</ns1:pathSet>'
 '<ns1:pathSet>guest.ipAddress</ns1:pathSet>',
    '<ns1:pathSet>hostFolder</ns1:pathSet>'
    '<ns1:pathSet>vmFolder</ns1:pathSet>'
    '<ns1:pathSet>datastore</ns1:pathSet>'
    '<ns1:pathSet>network</ns1:pathSet>'
   '</propSet>'
   '<propSet xsi:type="ns1:PropertySpec">'
    '<ns1:type>ResourcePool</ns1:type>'
    '<ns1:all>false</ns1:all>'
    '<ns1:pathSet>name</ns1:pathSet>'
    '<ns1:pathSet>parent</ns1:pathSet>'
   '</propSet>'
   '<propSet xsi:type="ns1:PropertySpec">'
    '<ns1:type>Network</ns1:type>'
    '<ns1:all>false</ns1:all>'
    '<ns1:pathSet>name</ns1:pathSet>'
    '<ns1:pathSet>host</ns1:pathSet>'
    '<ns1:pathSet>tag</ns1:pathSet>'
   '</propSet>'
   '<propSet xsi:type="ns1:PropertySpec">'
    '<ns1:type>ComputeResource</ns1:type>'
    '<ns1:all>false</ns1:all>'
    '<ns1:pathSet>name</ns1:pathSet>'
    '<ns1:pathSet>datastore</ns1:pathSet>'
    '<ns1:pathSet>parent</ns1:pathSet>'
    '<ns1:pathSet>host</ns1:pathSet>'
    '<ns1:pathSet>resourcePool</ns1:pathSet>'
    '<ns1:pathSet>network</ns1:pathSet>'
   '</propSet>'
   '<propSet xsi:type="ns1:PropertySpec">'
    '<ns1:type>HostSystem</ns1:type>'
    '<ns1:all>false</ns1:all>'
    '<ns1:pathSet>name</ns1:pathSet>'
    '<ns1:pathSet>datastore</ns1:pathSet>'
    '<ns1:pathSet>network</ns1:pathSet>'
   '</propSet>'
   '<propSet xsi:type="ns1:PropertySpec">'
    '<ns1:type>Folder</ns1:type>'
    '<ns1:all>false</ns1:all>'
    '<ns1:pathSet>name</ns1:pathSet>'
    '<ns1:pathSet>parent</ns1:pathSet>'
    '<ns1:pathSet>childType</ns1:pathSet>'
)

vmwareRetrievePropertiesReq35 = vmwareReqGetVirtualMachineProps1.replace(
 '<ns1:type>VirtualMachine</ns1:type>', '<ns1:type>Datacenter</ns1:type>').replace(
   '<selectSet><ns1:name>dcToNetwork</ns1:name></selectSet>', '').replace(
 '<ns1:pathSet>config.annotation</ns1:pathSet>'
 '<ns1:pathSet>config.template</ns1:pathSet>'
 '<ns1:pathSet>runtime.powerState</ns1:pathSet>'
 '<ns1:pathSet>runtime.bootTime</ns1:pathSet>'
 '<ns1:pathSet>config.uuid</ns1:pathSet>'
 '<ns1:pathSet>guest.ipAddress</ns1:pathSet>',
    '<ns1:pathSet>hostFolder</ns1:pathSet>'
    '<ns1:pathSet>vmFolder</ns1:pathSet>'
    '<ns1:pathSet>datastore</ns1:pathSet>'
    '<ns1:pathSet>network</ns1:pathSet>'
   '</propSet>'
   '<propSet xsi:type="ns1:PropertySpec">'
    '<ns1:type>Folder</ns1:type>'
    '<ns1:all>false</ns1:all>'
    '<ns1:pathSet>name</ns1:pathSet>'
    '<ns1:pathSet>parent</ns1:pathSet>'
    '<ns1:pathSet>childType</ns1:pathSet>'
   '</propSet>'
   '<propSet xsi:type="ns1:PropertySpec">'
    '<ns1:type>HostSystem</ns1:type>'
    '<ns1:all>false</ns1:all>'
    '<ns1:pathSet>name</ns1:pathSet>'
    '<ns1:pathSet>datastore</ns1:pathSet>'
    '<ns1:pathSet>network</ns1:pathSet>'
   '</propSet>'
   '<propSet xsi:type="ns1:PropertySpec">'
    '<ns1:type>ComputeResource</ns1:type>'
    '<ns1:all>false</ns1:all>'
    '<ns1:pathSet>name</ns1:pathSet>'
    '<ns1:pathSet>datastore</ns1:pathSet>'
    '<ns1:pathSet>parent</ns1:pathSet>'
    '<ns1:pathSet>host</ns1:pathSet>'
    '<ns1:pathSet>resourcePool</ns1:pathSet>'
    '<ns1:pathSet>network</ns1:pathSet>'
   '</propSet>'
   '<propSet xsi:type="ns1:PropertySpec">'
    '<ns1:type>ResourcePool</ns1:type>'
    '<ns1:all>false</ns1:all>'
    '<ns1:pathSet>name</ns1:pathSet>'
    '<ns1:pathSet>parent</ns1:pathSet>').replace(
  '<selectSet xsi:type="ns1:TraversalSpec">'
    '<ns1:name>dcToNetwork</ns1:name>'
    '<ns1:type>Datacenter</ns1:type>'
    '<ns1:path>networkFolder</ns1:path>'
    '<ns1:skip>false</ns1:skip>'
    '<selectSet>'
      '<ns1:name>visitFolders</ns1:name>'
    '</selectSet>'
  '</selectSet>',
  '')

vmwareRetrievePropertiesResp2 = HTTPResponse('<?xml version="1.0" encoding="UTF-8"?>'
'<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
  '<soapenv:Body>'
    '<RetrievePropertiesResponse xmlns="urn:vim25">'
      '<returnval>'
        '<obj type="HostSystem">host-100</obj>'
        '<propSet>'
          '<name>datastore</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-100</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-101</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-102</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">esx-100.eng.rpath.com</val>'
        '</propSet>'
        '<propSet>'
          '<name>network</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-10</ManagedObjectReference>'
          '</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="HostSystem">host-101</obj>'
        '<propSet>'
          '<name>datastore</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-100</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-101</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-102</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">esx-101.eng.rpath.com</val>'
        '</propSet>'
        '<propSet>'
          '<name>network</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-10</ManagedObjectReference>'
          '</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="HostSystem">host-200</obj>'
        '<propSet>'
          '<name>datastore</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-200</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-201</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-202</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">esx-200.eng.rpath.com</val>'
        '</propSet>'
        '<propSet>'
          '<name>network</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-20</ManagedObjectReference>'
          '</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="HostSystem">host-201</obj>'
        '<propSet>'
          '<name>datastore</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-200</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-201</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-202</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">esx-201.eng.rpath.com</val>'
        '</propSet>'
        '<propSet>'
          '<name>network</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-20</ManagedObjectReference>'
          '</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="ResourcePool">resgroup-10</obj>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">Resources</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="ClusterComputeResource" xsi:type="ManagedObjectReference">domain-c10</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="ResourcePool">resgroup-20</obj>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">Resources</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="ClusterComputeResource" xsi:type="ManagedObjectReference">domain-c20</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="ClusterComputeResource">domain-c10</obj>'
        '<propSet>'
          '<name>datastore</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-100</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-101</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-102</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>host</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-100</ManagedObjectReference>'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-101</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">lab 1</val>'
        '</propSet>'
        '<propSet>'
          '<name>network</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-10</ManagedObjectReference>'
            '<ManagedObjectReference type="DistributedVirtualPortgroup" xsi:type="ManagedObjectReference">dvportgroup-100</ManagedObjectReference>'
            '<ManagedObjectReference type="DistributedVirtualPortgroup" xsi:type="ManagedObjectReference">dvportgroup-101</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="Folder" xsi:type="ManagedObjectReference">group-h10</val>'
        '</propSet>'
        '<propSet>'
          '<name>resourcePool</name>'
          '<val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-10</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="ClusterComputeResource">domain-c20</obj>'
        '<propSet>'
          '<name>datastore</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-200</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-201</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-202</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>host</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-200</ManagedObjectReference>'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-201</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">lab 2</val>'
        '</propSet>'
        '<propSet>'
          '<name>network</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-20</ManagedObjectReference>'
            '<ManagedObjectReference type="DistributedVirtualPortgroup" xsi:type="ManagedObjectReference">dvportgroup-200</ManagedObjectReference>'
            '<ManagedObjectReference type="DistributedVirtualPortgroup" xsi:type="ManagedObjectReference">dvportgroup-201</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="Folder" xsi:type="ManagedObjectReference">group-h20</val>'
        '</propSet>'
        '<propSet>'
          '<name>resourcePool</name>'
          '<val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-20</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="ResourcePool">resgroup-100</obj>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">Resource Pool 100</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-10</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="ResourcePool">resgroup-101</obj>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">Resource Pool 101</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-10</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="ResourcePool">resgroup-200</obj>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">Resource Pool 200</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-20</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="ResourcePool">resgroup-201</obj>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">Resource Pool 201</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-20</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="Datacenter">datacenter-10</obj>'
        '<propSet>'
          '<name>datastore</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-100</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-101</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-102</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>hostFolder</name>'
          '<val type="Folder" xsi:type="ManagedObjectReference">group-h10</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">rPath 1</val>'
        '</propSet>'
        '<propSet>'
          '<name>network</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-10</ManagedObjectReference>'
            '<ManagedObjectReference type="DistributedVirtualPortgroup" xsi:type="ManagedObjectReference">dvportgroup-100</ManagedObjectReference>'
            '<ManagedObjectReference type="DistributedVirtualPortgroup" xsi:type="ManagedObjectReference">dvportgroup-101</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>vmFolder</name>'
          '<val type="Folder" xsi:type="ManagedObjectReference">group-v10</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="Datacenter">datacenter-20</obj>'
        '<propSet>'
          '<name>datastore</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-200</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-201</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-202</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>hostFolder</name>'
          '<val type="Folder" xsi:type="ManagedObjectReference">group-h20</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">rPath 2</val>'
        '</propSet>'
        '<propSet>'
          '<name>network</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-20</ManagedObjectReference>'
            '<ManagedObjectReference type="DistributedVirtualPortgroup" xsi:type="ManagedObjectReference">dvportgroup-200</ManagedObjectReference>'
            '<ManagedObjectReference type="DistributedVirtualPortgroup" xsi:type="ManagedObjectReference">dvportgroup-201</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>vmFolder</name>'
          '<val type="Folder" xsi:type="ManagedObjectReference">group-v20</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="Network">network-10</obj>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">VM Network 10</val>'
        '</propSet>'
        '<propSet>'
          '<name>host</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-100</ManagedObjectReference>'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-101</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>tag</name>'
          '<val xsi:type="ArrayOfTag"/>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="Network">network-20</obj>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">VM Network 20</val>'
        '</propSet>'
        '<propSet>'
          '<name>host</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-200</ManagedObjectReference>'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-201</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>tag</name>'
          '<val xsi:type="ArrayOfTag"/>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="DistributedVirtualPortgroup">dvportgroup-100</obj>'
        '<propSet>'
          '<name>host</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-100</ManagedObjectReference>'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-101</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">esx trunk uplink 10</val>'
        '</propSet>'
        '<propSet>'
          '<name>tag</name>'
          '<val xsi:type="ArrayOfTag">'
            '<Tag xsi:type="Tag">'
              '<key>SYSTEM/DVS.UPLINKPG</key>'
            '</Tag>'
          '</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="DistributedVirtualPortgroup">dvportgroup-101</obj>'
        '<propSet>'
          '<name>host</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-100</ManagedObjectReference>'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-101</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">Engineering Lab 10</val>'
        '</propSet>'
        '<propSet>'
          '<name>tag</name>'
          '<val xsi:type="ArrayOfTag"/>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="DistributedVirtualPortgroup">dvportgroup-200</obj>'
        '<propSet>'
          '<name>host</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-200</ManagedObjectReference>'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-201</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">esx trunk uplink 20</val>'
        '</propSet>'
        '<propSet>'
          '<name>tag</name>'
          '<val xsi:type="ArrayOfTag">'
            '<Tag xsi:type="Tag">'
              '<key>SYSTEM/DVS.UPLINKPG</key>'
            '</Tag>'
          '</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="DistributedVirtualPortgroup">dvportgroup-201</obj>'
        '<propSet>'
          '<name>host</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-200</ManagedObjectReference>'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-201</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">Engineering Lab 20</val>'
        '</propSet>'
        '<propSet>'
          '<name>tag</name>'
          '<val xsi:type="ArrayOfTag"/>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="Folder">group-v10</obj>'
        '<propSet>'
          '<name>childType</name>'
          '<val xsi:type="ArrayOfString">'
            '<string xsi:type="xsd:string">Folder</string>'
            '<string xsi:type="xsd:string">VirtualMachine</string>'
            '<string xsi:type="xsd:string">VirtualApp</string>'
         '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">vm 10</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="Datacenter" xsi:type="ManagedObjectReference">datacenter-10</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="Folder">group-v20</obj>'
        '<propSet>'
          '<name>childType</name>'
          '<val xsi:type="ArrayOfString">'
            '<string xsi:type="xsd:string">Folder</string>'
            '<string xsi:type="xsd:string">VirtualMachine</string>'
            '<string xsi:type="xsd:string">VirtualApp</string>'
         '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">vm 20</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="Datacenter" xsi:type="ManagedObjectReference">datacenter-20</val>'
        '</propSet>'
      '</returnval>'
    '</RetrievePropertiesResponse>'
  '</soapenv:Body>'
'</soapenv:Envelope>'
)

vmwareRetrievePropertiesResp1 = HTTPResponse('<?xml version="1.0" encoding="UTF-8"?>'
'<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
  '<soapenv:Body>'
    '<RetrievePropertiesResponse xmlns="urn:vim25">'
      '<returnval>'
        '<obj type="HostSystem">host-9</obj>'
        '<propSet>'
          '<name>datastore</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-16</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-18</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-20</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-559</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">esx01.eng.rpath.com</val>'
        '</propSet>'
        '<propSet>'
          '<name>network</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-2282</ManagedObjectReference>'
            '<ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-22</ManagedObjectReference>'
          '</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="HostSystem">host-879</obj>'
        '<propSet>'
          '<name>datastore</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-16</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-18</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-20</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">esx02.eng.rpath.com</val>'
        '</propSet>'
        '<propSet>'
          '<name>network</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-22</ManagedObjectReference>'
          '</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="HostSystem">host-206</obj>'
        '<propSet>'
          '<name>datastore</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-16</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-18</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-20</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-565</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">esx03.eng.rpath.com</val>'
        '</propSet>'
        '<propSet>'
          '<name>network</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-22</ManagedObjectReference>'
          '</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="ResourcePool">resgroup-7</obj>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">Resources</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="ClusterComputeResource" xsi:type="ManagedObjectReference">domain-c5</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="ClusterComputeResource">domain-c5</obj>'
        '<propSet>'
          '<name>datastore</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-16</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-18</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-20</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-563</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-565</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-884</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-887</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-559</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>host</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-206</ManagedObjectReference>'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-879</ManagedObjectReference>'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-9</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">lab</val>'
        '</propSet>'
        '<propSet>'
          '<name>network</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-22</ManagedObjectReference>'
            '<ManagedObjectReference type="DistributedVirtualPortgroup" xsi:type="ManagedObjectReference">dvportgroup-9986</ManagedObjectReference>'
            '<ManagedObjectReference type="DistributedVirtualPortgroup" xsi:type="ManagedObjectReference">dvportgroup-9987</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="Folder" xsi:type="ManagedObjectReference">group-h4</val>'
        '</propSet>'
        '<propSet>'
          '<name>resourcePool</name>'
          '<val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-7</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="ResourcePool">resgroup-181</obj>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">QA</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-7</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="ResourcePool">resgroup-537</obj>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">Proserv</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-7</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="ResourcePool">resgroup-50</obj>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">Franks</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-7</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="ResourcePool">resgroup-51</obj>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">General</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="ResourcePool" xsi:type="ManagedObjectReference">resgroup-7</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="Datacenter">datacenter-2</obj>'
        '<propSet>'
          '<name>datastore</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-16</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-18</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-20</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-559</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-563</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-565</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-887</ManagedObjectReference>'
            '<ManagedObjectReference type="Datastore" xsi:type="ManagedObjectReference">datastore-884</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>hostFolder</name>'
          '<val type="Folder" xsi:type="ManagedObjectReference">group-h4</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">rPath</val>'
        '</propSet>'
        '<propSet>'
          '<name>network</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="Network" xsi:type="ManagedObjectReference">network-22</ManagedObjectReference>'
            '<ManagedObjectReference type="DistributedVirtualPortgroup" xsi:type="ManagedObjectReference">dvportgroup-9986</ManagedObjectReference>'
            '<ManagedObjectReference type="DistributedVirtualPortgroup" xsi:type="ManagedObjectReference">dvportgroup-9987</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>vmFolder</name>'
          '<val type="Folder" xsi:type="ManagedObjectReference">group-v3</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="Network">network-22</obj>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">VM Network</val>'
        '</propSet>'
        '<propSet>'
          '<name>host</name>'
          '<val xsi:type="ArrayOfManagedObjectReference"/>'
        '</propSet>'
        '<propSet>'
          '<name>tag</name>'
          '<val xsi:type="ArrayOfTag"/>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="DistributedVirtualPortgroup">dvportgroup-9986</obj>'
        '<propSet>'
          '<name>host</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-879</ManagedObjectReference>'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-206</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">esx trunk uplink</val>'
        '</propSet>'
        '<propSet>'
          '<name>tag</name>'
          '<val xsi:type="ArrayOfTag">'
            '<Tag xsi:type="Tag">'
              '<key>SYSTEM/DVS.UPLINKPG</key>'
            '</Tag>'
          '</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="DistributedVirtualPortgroup">dvportgroup-9987</obj>'
        '<propSet>'
          '<name>host</name>'
          '<val xsi:type="ArrayOfManagedObjectReference">'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-879</ManagedObjectReference>'
            '<ManagedObjectReference type="HostSystem" xsi:type="ManagedObjectReference">host-206</ManagedObjectReference>'
          '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">Engineering lab</val>'
        '</propSet>'
        '<propSet>'
          '<name>tag</name>'
          '<val xsi:type="ArrayOfTag"/>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="Folder">group-v3</obj>'
        '<propSet>'
          '<name>childType</name>'
          '<val xsi:type="ArrayOfString">'
            '<string xsi:type="xsd:string">Folder</string>'
            '<string xsi:type="xsd:string">VirtualMachine</string>'
            '<string xsi:type="xsd:string">VirtualApp</string>'
         '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">vm</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="Datacenter" xsi:type="ManagedObjectReference">datacenter-2</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="Folder">group-v31</obj>'
        '<propSet>'
          '<name>childType</name>'
          '<val xsi:type="ArrayOfString">'
            '<string xsi:type="xsd:string">Folder</string>'
            '<string xsi:type="xsd:string">VirtualMachine</string>'
            '<string xsi:type="xsd:string">VirtualApp</string>'
         '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">subfolder1</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="Folder" xsi:type="ManagedObjectReference">group-v3</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="Folder">group-v32</obj>'
        '<propSet>'
          '<name>childType</name>'
          '<val xsi:type="ArrayOfString">'
            '<string xsi:type="xsd:string">Folder</string>'
            '<string xsi:type="xsd:string">VirtualMachine</string>'
            '<string xsi:type="xsd:string">VirtualApp</string>'
         '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">subfolder2</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="Folder" xsi:type="ManagedObjectReference">group-v3</val>'
        '</propSet>'
      '</returnval>'
      '<returnval>'
        '<obj type="Folder">group-v311</obj>'
        '<propSet>'
          '<name>childType</name>'
          '<val xsi:type="ArrayOfString">'
            '<string xsi:type="xsd:string">Folder</string>'
            '<string xsi:type="xsd:string">VirtualMachine</string>'
            '<string xsi:type="xsd:string">VirtualApp</string>'
         '</val>'
        '</propSet>'
        '<propSet>'
          '<name>name</name>'
          '<val xsi:type="xsd:string">subfolder11</val>'
        '</propSet>'
        '<propSet>'
          '<name>parent</name>'
          '<val type="Folder" xsi:type="ManagedObjectReference">group-v31</val>'
        '</propSet>'
      '</returnval>'
    '</RetrievePropertiesResponse>'
  '</soapenv:Body>'
'</soapenv:Envelope>'
)

vmwareRetrievePropertiesHttpNfcLeaseReq = _vmwareReqRetrievePropertiesSimpleTemplate % dict(
        klass = 'HttpNfcLease', path = 'info',
        value = 'session[%s]%s' % vmwareHttpNfcLeaseSession1)

vmwareRetrievePropertiesHttpNfcLeaseResp = HTTPResponse(
    _vmwareRespRetrievePropertiesTemplate % (
"""
      <returnval>
        <obj type="HttpNfcLease">session[%(uuid1)s]%(uuid2)s</obj>
        <propSet>
          <name>info</name>
          <val xsi:type="HttpNfcLeaseInfo">
            <lease type="HttpNfcLease">session[%(uuid1)s]%(uuid2)s</lease>
            <entity type="VirtualMachine">vm-987</entity>
            <deviceUrl>
              <key>/vm-15091/VirtualLsiLogicController0:0</key>
              <importKey>/vm-name-goes-here/VirtualLsiLogicController0:0</importKey>
              <url>https://esx02.eng.rpath.com/nfc/e91f006b-7d61-4592-8a9f-1ad90e907fa2/disk-0.vmdk</url>
              <sslThumbprint/>
            </deviceUrl>
            <totalDiskCapacityInKB>2580480</totalDiskCapacityInKB>
            <leaseTimeout>300</leaseTimeout>
          </val>
        </propSet>
      </returnval>
""" % dict(uuid1 = vmwareHttpNfcLeaseSession1[0],
    uuid2 = vmwareHttpNfcLeaseSession1[1])))

vmwareRetrievePropertiesVMReq = vmwareReqGetVirtualMachineProps1.replace(
 '<propSet xsi:type="ns1:PropertySpec">'
   '<ns1:type>VirtualMachine</ns1:type>'
   '<ns1:all>false</ns1:all>'
   '<ns1:pathSet>name</ns1:pathSet>'
   '<ns1:pathSet>config.annotation</ns1:pathSet>'
   '<ns1:pathSet>config.template</ns1:pathSet>'
   '<ns1:pathSet>runtime.powerState</ns1:pathSet>'
   '<ns1:pathSet>runtime.bootTime</ns1:pathSet>'
   '<ns1:pathSet>config.uuid</ns1:pathSet>'
   '<ns1:pathSet>guest.ipAddress</ns1:pathSet>'
 '</propSet>',
 '<propSet xsi:type="ns1:PropertySpec"><ns1:type>VirtualMachine</ns1:type><ns1:all>false</ns1:all>%s</propSet>'
 ).replace(
    '<obj type="Folder">group-d1</obj>',
    '<obj type="VirtualMachine" xsi:type="ns1:ManagedObjectReference">vm-4739</obj>')

vmwareRetrievePropertiesVMReq35 = vmwareReqGetVirtualMachineProps35.replace(
 '<propSet xsi:type="ns1:PropertySpec">'
   '<ns1:type>VirtualMachine</ns1:type>'
   '<ns1:all>false</ns1:all>'
   '<ns1:pathSet>name</ns1:pathSet>'
   '<ns1:pathSet>config.annotation</ns1:pathSet>'
   '<ns1:pathSet>config.template</ns1:pathSet>'
   '<ns1:pathSet>runtime.powerState</ns1:pathSet>'
   '<ns1:pathSet>runtime.bootTime</ns1:pathSet>'
   '<ns1:pathSet>config.uuid</ns1:pathSet>'
   '<ns1:pathSet>guest.ipAddress</ns1:pathSet>'
 '</propSet>',
 '<propSet xsi:type="ns1:PropertySpec"><ns1:type>VirtualMachine</ns1:type><ns1:all>false</ns1:all>%s</propSet>'
 ).replace(
    '<obj type="Folder">group-d1</obj>',
    '<obj type="VirtualMachine" xsi:type="ns1:ManagedObjectReference">vm-4739</obj>')

vmwarePropVMPathSet2 = "<ns1:pathSet>config.uuid</ns1:pathSet>"
vmwarePropVMPathSet3 = "<ns1:pathSet>config.hardware.device</ns1:pathSet>"
vmwarePropVMPathSet4 = "<ns1:pathSet>config.name</ns1:pathSet>"

vmwarePropVMPathSet1 = vmwarePropVMPathSet3 + vmwarePropVMPathSet4

vmwareRetrievePropertiesVMReq2 = (
    vmwareRetrievePropertiesVMReq % vmwarePropVMPathSet1).replace(
    ' xsi:type="ns1:ManagedObjectReference">vm-4739<',
    '>vm-987<')

vmwareRetrievePropertiesVMReq22 = (
    vmwareRetrievePropertiesVMReq % vmwarePropVMPathSet2).replace(
    ' xsi:type="ns1:ManagedObjectReference">vm-4739<',
    '>vm-987<')

vmwareRetrievePropertiesVMReq2_hwdev = (
    vmwareRetrievePropertiesVMReq % vmwarePropVMPathSet3).replace(
        '<selectSet><ns1:name>dcToNetwork</ns1:name></selectSet>', '').replace(
        '<selectSet xsi:type="ns1:TraversalSpec">'
          '<ns1:name>dcToNetwork</ns1:name>'
          '<ns1:type>Datacenter</ns1:type>'
          '<ns1:path>networkFolder</ns1:path>'
          '<ns1:skip>false</ns1:skip>'
          '<selectSet>'
            '<ns1:name>visitFolders</ns1:name>'
          '</selectSet>'
        '</selectSet>',
        '')
        
vmwareRetrievePropertiesVMReq2_hwdev2 = vmwareRetrievePropertiesVMReq2_hwdev.replace(
        '</propSet>',
        '<ns1:pathSet>config.name</ns1:pathSet></propSet>')

vmwareRetrievePropertiesVMReq35_2 = (
    vmwareRetrievePropertiesVMReq35 % vmwarePropVMPathSet1).replace(
    ' xsi:type="ns1:ManagedObjectReference">vm-4739<',
    '>vm-987<')

vmwareRetrievePropertiesVMReq35_22 = (
    vmwareRetrievePropertiesVMReq35 % vmwarePropVMPathSet2).replace(
    ' xsi:type="ns1:ManagedObjectReference">vm-4739<',
    '>vm-987<')

vmwareRetrievePropertiesVMReq35_hwdev = (
    vmwareRetrievePropertiesVMReq35 % vmwarePropVMPathSet3).replace(
    ' xsi:type="ns1:ManagedObjectReference">vm-4739<',
    '>vm-987<').replace(
        '<selectSet><ns1:name>HToVm</ns1:name></selectSet>'
        '<selectSet><ns1:name>rpToVm</ns1:name></selectSet>',
        '<selectSet><ns1:name>HToVm</ns1:name></selectSet>'
        '<selectSet><ns1:name>rpToVm</ns1:name></selectSet>'
        '<selectSet><ns1:name>dcToNetwork</ns1:name></selectSet>').replace(
    '</objectSet>',
    '<selectSet xsi:type="ns1:TraversalSpec">'
      '<ns1:name>dcToNetwork</ns1:name>'
      '<ns1:type>Datacenter</ns1:type>'
      '<ns1:path>networkFolder</ns1:path>'
      '<ns1:skip>false</ns1:skip>'
      '<selectSet>'
        '<ns1:name>visitFolders</ns1:name>'
      '</selectSet>'
    '</selectSet>'
    '</objectSet>')

vmwareRetrievePropertiesVMReq35_hwdev2 = vmwareRetrievePropertiesVMReq35_hwdev.replace(
        '</propSet>',
        '<ns1:pathSet>config.name</ns1:pathSet></propSet>').replace(
        '>vm-987<',
        ' xsi:type="ns1:ManagedObjectReference">vm-4739<')


vmwarePropRespSet1 = """<propSet><name>config.hardware.device</name><val xsi:type="ArrayOfVirtualDevice"><VirtualDevice xsi:type="VirtualIDEController"><key>200</key><deviceInfo><label>IDE 0</label><summary>IDE 0</summary></deviceInfo><busNumber>0</busNumber></VirtualDevice><VirtualDevice xsi:type="VirtualIDEController"><key>201</key><deviceInfo><label>IDE 1</label><summary>IDE 1</summary></deviceInfo><busNumber>1</busNumber></VirtualDevice><VirtualDevice xsi:type="VirtualPS2Controller"><key>300</key><deviceInfo><label>PS2 Controller </label><summary>PS2 Controller</summary></deviceInfo><busNumber>0</busNumber><device>600</device><device>700</device></VirtualDevice><VirtualDevice xsi:type="VirtualPCIController"><key>100</key><deviceInfo><label>PCI Controller </label><summary>PCI Controller</summary></deviceInfo><busNumber>0</busNumber><device>500</device><device>4000</device><device>1000</device></VirtualDevice><VirtualDevice xsi:type="VirtualSIOController"><key>400</key><deviceInfo><label>SIO Controller </label><summary>SIO Controller</summary></deviceInfo><busNumber>0</busNumber></VirtualDevice><VirtualDevice xsi:type="VirtualKeyboard"><key>600</key><deviceInfo><label>Keyboard </label><summary>Keyboard</summary></deviceInfo><controllerKey>300</controllerKey><unitNumber>0</unitNumber></VirtualDevice><VirtualDevice xsi:type="VirtualPointingDevice"><key>700</key><deviceInfo><label>Pointing Device</label><summary>Pointing device; Device</summary></deviceInfo><backing xsi:type="VirtualPointingDeviceDeviceBackingInfo"><deviceName></deviceName><useAutoDetect>false</useAutoDetect><hostPointingDevice>autodetect</hostPointingDevice></backing><controllerKey>300</controllerKey><unitNumber>1</unitNumber></VirtualDevice><VirtualDevice xsi:type="VirtualMachineVideoCard"><key>500</key><deviceInfo><label>Video Card </label><summary>Video Card</summary></deviceInfo><controllerKey>100</controllerKey><unitNumber>0</unitNumber><videoRamSizeInKB>4096</videoRamSizeInKB></VirtualDevice><VirtualDevice xsi:type="VirtualPCNet32"><key>4000</key><deviceInfo><label>Network Adapter 1</label><summary>VM Network</summary></deviceInfo><backing xsi:type="VirtualEthernetCardNetworkBackingInfo"><deviceName>VM Network</deviceName><useAutoDetect>false</useAutoDetect><network type="Network">network-22</network></backing><connectable><startConnected>true</startConnected><allowGuestControl>true</allowGuestControl><connected>true</connected></connectable><controllerKey>100</controllerKey><unitNumber>7</unitNumber><addressType>assigned</addressType><macAddress>00:50:56:b4:31:33</macAddress><wakeOnLanEnabled>true</wakeOnLanEnabled></VirtualDevice><VirtualDevice xsi:type="VirtualLsiLogicController"><key>1000</key><deviceInfo><label>SCSI Controller 0</label><summary>LSI Logic</summary></deviceInfo><controllerKey>100</controllerKey><unitNumber>3</unitNumber><busNumber>0</busNumber><device>2000</device><hotAddRemove>true</hotAddRemove><sharedBus>noSharing</sharedBus><scsiCtlrUnitNumber>7</scsiCtlrUnitNumber></VirtualDevice><VirtualDevice xsi:type="VirtualDisk"><key>2000</key><deviceInfo><label>Hard Disk 1</label><summary>2,183,168 KB</summary></deviceInfo><backing xsi:type="VirtualDiskFlatVer2BackingInfo"><fileName>[nas1-iscsi] misa-remote-update-4/misa-remote-update-4.vmdk</fileName><datastore type="Datastore">datastore-18</datastore><diskMode>persistent</diskMode><split>false</split><writeThrough>true</writeThrough><thinProvisioned>false</thinProvisioned><uuid>6000C290-83ef-1049-4e36-62fc24f0deef</uuid></backing><controllerKey>1000</controllerKey><unitNumber>0</unitNumber><capacityInKB>2183168</capacityInKB><shares><shares>1000</shares><level>normal</level></shares></VirtualDevice></val></propSet><propSet><name>config.name</name><val xsi:type="xsd:string">misa-remote-update-4</val></propSet>"""
vmwarePropRespSet1Len = 465 + len(vmwarePropRespSet1)

vmwarePropRespSet2 = """<propSet><name>config.uuid</name><val xsi:type="xsd:string">vmuuid10</val></propSet>"""
vmwarePropRespSet2Len = 465 + len(vmwarePropRespSet2)

vmwareRetrievePropertiesVMResp = """\
HTTP/1.1 200 OK
Date: Fri, 22 May 2009 20:33:32 GMT
Cache-Control: no-cache
Content-Type: text/xml; charset=utf-8
Content-Length: %d

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
<RetrievePropertiesResponse xmlns="urn:vim25"><returnval><obj type="VirtualMachine">vm-4739</obj>%s</returnval></RetrievePropertiesResponse>
</soapenv:Body>
</soapenv:Envelope>
"""

vmwareRetrievePropertiesVMResp2 = (vmwareRetrievePropertiesVMResp %
    (vmwarePropRespSet1Len, vmwarePropRespSet1)).replace(
    'vm-4739', 'vm-987')

vmwareRetrievePropertiesVMResp22 = (vmwareRetrievePropertiesVMResp %
    (vmwarePropRespSet2Len, vmwarePropRespSet2)).replace(
    'vm-4739', 'vm-987')

vmwareRetrievePropertiesVMResp2_hwdev = (vmwareRetrievePropertiesVMResp %
    (vmwarePropRespSet1Len, vmwarePropRespSet1))

vmwareRetrievePropertiesDatacenterVmFolderReq = \
    _vmwareReqRetrievePropertiesSimpleTemplate % dict(
        klass = 'Datacenter', path = 'vmFolder', value = 'datacenter-2')

vmwareRetrievePropertiesDatacenterVmFolderResp = """\
HTTP/1.1 200 OK
Date: Fri, 22 May 2009 20:20:26 GMT
Cache-Control: no-cache
Content-Type: text/xml; charset=utf-8
Content-Length: 575

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
<RetrievePropertiesResponse xmlns="urn:vim25"><returnval><obj type="Datacenter">datacenter-2</obj><propSet><name>hostFolder</name><val type="Folder" xsi:type="ManagedObjectReference">group-h4</val></propSet></returnval></RetrievePropertiesResponse>
</soapenv:Body>
</soapenv:Envelope>
"""

 # START RESPONSE - auth timeout
vmwareRegisterVMreqAuthTimeout = """\
HTTP/1.1 500 Internal Server Error
Date: Mon, 3 Nov 2008 19:23:19 GMT
Cache-Control: no-cache
Content-Type: text/xml; charset=utf-8
Content-Length: 649

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
<soapenv:Fault><faultcode>ServerFaultCode</faultcode>
<faultstring>The session is not authenticated.</faultstring>
<detail>
<NotAuthenticatedFault xmlns="urn:vim25" xsi:type="NotAuthenticated">
<object type="VirtualMachine">vm-1234</object>
<privilegeId>1234</privilegeId>
</NotAuthenticatedFault></detail></soapenv:Fault>
</soapenv:Body>
</soapenv:Envelope>"""

vmwareFindVmByUuidReq = (
 '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"'
 ' xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"'
 ' xmlns:ZSI="http://www.zolera.com/schemas/ZSI/"'
 ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
 ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
 '<SOAP-ENV:Header></SOAP-ENV:Header>'
 '<SOAP-ENV:Body xmlns:ns1="urn:vim25"><ns1:FindByUuid>'
 '<_this type="SearchIndex">SearchIndex</_this>'
 '<ns1:uuid>%s</ns1:uuid>'
 '<ns1:vmSearch>true</ns1:vmSearch>'
 '</ns1:FindByUuid>'
 '</SOAP-ENV:Body>'
 '</SOAP-ENV:Envelope>'
)

vmwareFindVmByUuidResp = (
 'HTTP/1.1 200 OK\r\n'
 'Date: Mon, 3 Nov 2008 19:18:20 GMT\r\n'
 'Cache-Control: no-cache\r\n'
 'Content-Type: text/xml; charset=utf-8\r\n'
 'Content-Length: 438\r\n'
 '\r\n'
 '<?xml version="1.0" encoding="UTF-8"?>\n'
 '<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"\n'
 ' xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"\n'
 ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"\n'
 ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
 '<soapenv:Body>\n'
 '<FindByUuidResponse xmlns="urn:vim25">'
 '<returnval type="VirtualMachine">%s</returnval>'
 '</FindByUuidResponse>\n'
 '</soapenv:Body>\n'
 '</soapenv:Envelope>'
)

vmwareFindVmByUuidRespNoMatch = """\
HTTP/1.1 200 OK\r
Date: Mon, 3 Nov 2008 19:18:20 GMT\r
Cache-Control: no-cache\r
Content-Type: text/xml; charset=utf-8\r
Content-Length: 382\r
\r
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:xsd="http://www.w3.org/2001/XMLSchema"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
<FindByUuidResponse xmlns="urn:vim25"></FindByUuidResponse>
</soapenv:Body></soapenv:Envelope>"""

  # START RESPONSE - get environment browser property
vmwareRetrievePropertiesEnvBrowserResp = HTTPResponse('<?xml version="1.0" encoding="UTF-8"?>\n<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"\n xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"\n xmlns:xsd="http://www.w3.org/2001/XMLSchema"\n xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n<soapenv:Body>\n<RetrievePropertiesResponse xmlns="urn:vim25"><returnval><obj type="ClusterComputeResource">domain-c5</obj><propSet><name>environmentBrowser</name><val type="EnvironmentBrowser" xsi:type="ManagedObjectReference">envbrowser-5</val></propSet></returnval></RetrievePropertiesResponse>\n</soapenv:Body>\n</soapenv:Envelope>')
 # END RESPONSE - get environment browser property

vmwareRetrievePropertiesDatastoreSummaryReq = \
    _vmwareReqRetrievePropertiesSimpleTemplate % dict(
        klass = 'Datastore', path = 'summary', value = 'datastore-18')

vmwareRetrievePropertiesDatastoreSummaryResponse = HTTPResponse("""\
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Body>
    <RetrievePropertiesResponse xmlns="urn:vim25">
      <returnval>
        <obj type="Datastore">datastore-18</obj>
        <propSet>
          <name>summary</name>
          <val xsi:type="DatastoreSummary">
            <datastore type="Datastore">datastore-18</datastore>
            <name>nas2-nfs</name>
            <url>netfs://172.16.160.167//mnt/vg00/nfs-storage/vmware-images/</url>
            <capacity>724236845056</capacity>
            <freeSpace>407087947776</freeSpace>
            <accessible>true</accessible>
            <multipleHostAccess>true</multipleHostAccess>
            <type>NFS</type>
          </val>
        </propSet>
      </returnval>
    </RetrievePropertiesResponse>
  </soapenv:Body>
</soapenv:Envelope>
""")

 # START REQUEST - get environment browser property
vmwareRetrievePropertiesEnvBrowserReq = \
    _vmwareReqRetrievePropertiesSimpleTemplate % dict(
        klass = 'ClusterComputeResource', path = 'environmentBrowser', value = 'domain-c5')

vmwareRetrievePropertiesEnvBrowserRespDisabledCR = 'HTTP/1.1 200 OK\r\nDate: Wed, 25 Mar 2009 17:23:46 GMT\r\nCache-Control: no-cache\r\nContent-Type: text/xml; charset=utf-8\r\nContent-Length: 531\r\n\r\n<?xml version="1.0" encoding="UTF-8"?>\n<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"\n xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"\n xmlns:xsd="http://www.w3.org/2001/XMLSchema"\n xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n<soapenv:Body>\n<RetrievePropertiesResponse xmlns="urn:vim25"><returnval><obj type="ClusterComputeResource">domain-c5</obj><propSet><name>environmentBrowser</name><val/></propSet></returnval></RetrievePropertiesResponse>\n</soapenv:Body>\n</soapenv:Envelope>'

vmwareRetrieveServiceContentRequest = (
 '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" '
        'xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
  '<SOAP-ENV:Header></SOAP-ENV:Header>'
  '<SOAP-ENV:Body xmlns:ns1="urn:vim25">'
    '<ns1:RetrieveServiceContent>'
      '<_this type="ServiceInstance">ServiceInstance</_this>'
    '</ns1:RetrieveServiceContent>'
  '</SOAP-ENV:Body></SOAP-ENV:Envelope>'
)

# Latest version of vsphere we support
vmwareRetrieveServiceContentResponse = HTTPResponse(
 '<?xml version="1.0" encoding="UTF-8"?>\n'
 '<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"\n '
 'xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"\n '
 'xmlns:xsd="http://www.w3.org/2001/XMLSchema"\n '
 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
 '<soapenv:Body>\n'
 '<RetrieveServiceContentResponse xmlns="urn:vim25"><returnval>'
 '<rootFolder type="Folder">group-d1</rootFolder>'
 '<propertyCollector type="PropertyCollector">propertyCollector</propertyCollector>'
 '<viewManager type="ViewManager">ViewManager</viewManager>'
 '<about><name>VMware VirtualCenter</name>'
 '<fullName>VMware VMware vCenter Server 4.0.0 build-208111</fullName>'
 '<vendor>VMware, Inc.</vendor>'
 '<version>4.0.0</version>'
 '<build>208111</build>'
 '<localeVersion>INTL</localeVersion>'
 '<localeBuild>000</localeBuild>'
 '<osType>win32-x86</osType>'
 '<productLineId>vpx</productLineId>'
 '<apiType>VirtualCenter</apiType>'
 '<instanceUuid>08263877-EAC1-4A69-974B-25B06D1785F1</instanceUuid>'
 '<licenseProductName>VMware VirtualCenter Server</licenseProductName>'
 '<licenseProductVersion>4.0</licenseProductVersion>'
 '<apiVersion>4.0</apiVersion>'
 '</about>'
 '<setting type="OptionManager">VpxSettings</setting>'
 '<userDirectory type="UserDirectory">UserDirectory</userDirectory>'
 '<sessionManager type="SessionManager">SessionManager</sessionManager>'
 '<authorizationManager type="AuthorizationManager">AuthorizationManager</authorizationManager>'
 '<perfManager type="PerformanceManager">PerfMgr</perfManager>'
 '<scheduledTaskManager type="ScheduledTaskManager">ScheduledTaskManager</scheduledTaskManager>'
 '<alarmManager type="AlarmManager">AlarmManager</alarmManager>'
 '<eventManager type="EventManager">EventManager</eventManager>'
 '<taskManager type="TaskManager">TaskManager</taskManager>'
 '<extensionManager type="ExtensionManager">ExtensionManager</extensionManager>'
 '<customizationSpecManager type="CustomizationSpecManager">CustomizationSpecManager</customizationSpecManager>'
 '<customFieldsManager type="CustomFieldsManager">CustomFieldsManager</customFieldsManager>'
 '<diagnosticManager type="DiagnosticManager">DiagMgr</diagnosticManager>'
 '<licenseManager type="LicenseManager">LicenseManager</licenseManager>'
 '<searchIndex type="SearchIndex">SearchIndex</searchIndex>'
 '<fileManager type="FileManager">FileManager</fileManager>'
 '<virtualizationManager type="VirtualizationManager">VirtualizationManager</virtualizationManager>'
 '<ovfManager type="OvfManager">OvfManager</ovfManager>'
 '</returnval>'
 '</RetrieveServiceContentResponse>\n'
 '</soapenv:Body>\n'
 '</soapenv:Envelope>',
    extraHeaders = [ ('Set-Cookie' , 'vmware_soap_session="5213d175-09ff-8e02-485d-e500034010fa"; Path=/;') ]
)

# Latest ESX
vmwareRetrieveServiceContentResponseESX = HTTPResponse(
    vmwareRetrieveServiceContentResponse.data.replace(
            '<productLineId>vpx</productLineId>',
            '<productLineId>embeddedEsx</productLineId>'),
    extraHeaders = [ ('Set-Cookie' , 'vmware_soap_session="5213d175-09ff-8e02-485d-e500034010fa"; Path=/;') ]
)

# ESX 3.5
vmwareRetrieveServiceContentResponseESX35 = HTTPResponse(
    vmwareRetrieveServiceContentResponseESX.data.replace(
        '<version>4.0.0</version>',
        '<version>2.5.0</version>'),
    extraHeaders = [ ('Set-Cookie' , 'vmware_soap_session="5213d175-09ff-8e02-485d-e500034010fa"; Path=/;') ]
)

# vSphere 3.5
vmwareRetrieveServiceContentResponse35 = HTTPResponse(
    vmwareRetrieveServiceContentResponse.data.replace(
        '<version>4.0.0</version>',
        '<version>2.5.0</version>'),
    extraHeaders = [ ('Set-Cookie' , 'vmware_soap_session="5213d175-09ff-8e02-485d-e500034010fa"; Path=/;') ]
)

# vSphere 5.0
vmwareRetrieveServiceContentResponse50 = HTTPResponse(
    vmwareRetrieveServiceContentResponse.data.replace(
        '<version>4.0.0</version>',
        '<version>5.0.0</version>'),
    extraHeaders = [ ('Set-Cookie' , 'vmware_soap_session="5213d175-09ff-8e02-485d-e500034010fa"; Path=/;') ]
)

vmwareOvfDescriptor1 = """\
<?xml version="1.0" encoding="UTF-8"?>
<ovf:Envelope  xmlns:cim="http://schemas.dmtf.org/wbem/wscim/1/common" xmlns:ovf="http://www.vmware.com/schema/ovf/1/envelope" xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData" xmlns:vmw="http://www.vmware.com/schema/ovf" xmlns:vssd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ovf:version="0.9">
  <References>
    <File ovf:href="misa-remote-update-centos5-1-x86_64.vmdk" ovf:id="file1" ovf:size="152453120"/>
  </References>
  <Section xsi:type="ovf:DiskSection_Type">
    <Info>Meta-information about the virtual disks</Info>
    <Disk ovf:capacity="2642411520" ovf:diskId="vmdisk1" ovf:fileRef="file1" ovf:format="http://www.vmware.com/specifications/vmdk.html#sparse"/>
  </Section>
  <Section xsi:type="ovf:NetworkSection_Type">
    <Info>The list of logical networks</Info>
    <Network ovf:name="bridged">
      <Description>The bridged network</Description>
    </Network>
  </Section>
  <Content ovf:id="misa-remote-update-centos5 Appliance" xsi:type="ovf:VirtualSystem_Type">
    <Info>A virtual machine</Info>
    <Section ovf:id="107" xsi:type="ovf:OperatingSystemSection_Type">
      <Info>The kind of installed guest operating system</Info>
    </Section>
    <Section xsi:type="ovf:VirtualHardwareSection_Type">
      <Info>Virtual hardware requirements for a virtual machine</Info>
      <System>
        <vssd:InstanceId>0</vssd:InstanceId>
        <vssd:VirtualSystemIdentifier>misa-remote-update-centos5 Appliance</vssd:VirtualSystemIdentifier>
        <vssd:VirtualSystemType>vmx-04</vssd:VirtualSystemType>
      </System>
      <Item>
        <rasd:Caption>1 virtual CPU(s)</rasd:Caption>
        <rasd:Description>Number of Virtual CPUs</rasd:Description>
        <rasd:InstanceId>1</rasd:InstanceId>
        <rasd:ResourceType>3</rasd:ResourceType>
        <rasd:AllocationUnits>MegaHertz</rasd:AllocationUnits>
        <rasd:VirtualQuantity>1</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:Caption>256MB of memory</rasd:Caption>
        <rasd:Description>Memory Size</rasd:Description>
        <rasd:InstanceId>2</rasd:InstanceId>
        <rasd:ResourceType>4</rasd:ResourceType>
        <rasd:AllocationUnits>MegaBytes</rasd:AllocationUnits>
        <rasd:VirtualQuantity>256</rasd:VirtualQuantity>
      </Item>
      <Item ovf:required="false">
        <rasd:Caption>usb</rasd:Caption>
        <rasd:Description>USB Controller</rasd:Description>
        <rasd:InstanceId>3</rasd:InstanceId>
        <rasd:ResourceType>23</rasd:ResourceType>
        <rasd:Address>0</rasd:Address>
        <rasd:BusNumber>0</rasd:BusNumber>
      </Item>
      <Item>
        <rasd:Caption>scsiController0</rasd:Caption>
        <rasd:Description>SCSI Controller</rasd:Description>
        <rasd:InstanceId>4</rasd:InstanceId>
        <rasd:ResourceType>6</rasd:ResourceType>
        <rasd:ResourceSubType>lsilogic</rasd:ResourceSubType>
        <rasd:Address>0</rasd:Address>
        <rasd:BusNumber>0</rasd:BusNumber>
      </Item>
      <Item>
        <rasd:Caption>ideController1</rasd:Caption>
        <rasd:Description>IDE Controller</rasd:Description>
        <rasd:InstanceId>5</rasd:InstanceId>
        <rasd:ResourceType>5</rasd:ResourceType>
        <rasd:Address>1</rasd:Address>
        <rasd:BusNumber>1</rasd:BusNumber>
      </Item>
      <Item ovf:required="false">
        <rasd:Caption>cdrom1</rasd:Caption>
        <rasd:InstanceId>6</rasd:InstanceId>
        <rasd:ResourceType>15</rasd:ResourceType>
        <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
        <rasd:Parent>5</rasd:Parent>
        <rasd:AddressOnParent>0</rasd:AddressOnParent>
      </Item>
      <Item>
        <rasd:Caption>disk1</rasd:Caption>
        <rasd:InstanceId>1001</rasd:InstanceId>
        <rasd:ResourceType>17</rasd:ResourceType>
        <rasd:HostResource>/disk/vmdisk1</rasd:HostResource>
        <rasd:Parent>4</rasd:Parent>
        <rasd:AddressOnParent>0</rasd:AddressOnParent>
      </Item>
<!--
      <Item>
        <rasd:Caption>ethernet0</rasd:Caption>
        <rasd:Description>PCNet32 ethernet adapter on &quot;bridged&quot;</rasd:Description>
        <rasd:InstanceId>8</rasd:InstanceId>
        <rasd:ResourceType>10</rasd:ResourceType>
        <rasd:ResourceSubType>PCNet32</rasd:ResourceSubType>
        <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
        <rasd:Connection>bridged</rasd:Connection>
        <rasd:AddressOnParent>2</rasd:AddressOnParent>
      </Item>
-->
      <Item><rasd:Caption>ethernet0</rasd:Caption><rasd:Description>E1000 ethernet adapter</rasd:Description><rasd:InstanceId>1002</rasd:InstanceId><rasd:ResourceType>10</rasd:ResourceType><rasd:ResourceSubType>E1000</rasd:ResourceSubType><rasd:AutomaticAllocation>true</rasd:AutomaticAllocation><rasd:Connection>bridged</rasd:Connection></Item>
    </Section>
    <Section ovf:required="false" xsi:type="ovf:AnnotationSection_Type">
      <Info>A human-readable annotation</Info>
      <Annotation></Annotation>
    </Section>
  </Content>
</ovf:Envelope>
"""

vmwareParseDescriptorRequestTemplate = (
'<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
 '<SOAP-ENV:Header></SOAP-ENV:Header>'
 '<SOAP-ENV:Body xmlns:ns1="urn:vim25">'
   '<ns1:ParseDescriptor>'
     '<_this type="OvfManager">OvfManager</_this>'
     '<ns1:ovfDescriptor>'
     '%s'
     '</ns1:ovfDescriptor>'
     '<pdp xsi:type="ns1:OvfParseDescriptorParams">'
       '<ns1:locale></ns1:locale>'
       '<ns1:deploymentOption></ns1:deploymentOption>'
     '</pdp>'
   '</ns1:ParseDescriptor>'
 '</SOAP-ENV:Body>'
'</SOAP-ENV:Envelope>')

from catalogService.libs.viclient import client
vmwareParseDescriptorRequest1 = vmwareParseDescriptorRequestTemplate % \
    xmlEscape(client.VimService.sanitizeOvfDescriptor(vmwareOvfDescriptor1))

vmwareParseDescriptorResponse1 = HTTPResponse("""\
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Body>
    <ParseDescriptorResponse xmlns="urn:vim25">
      <returnval>
        <network>
          <name>bridged</name>
          <description>The bridged network</description>
        </network>
        <annotation/>
        <approximateDownloadSize>152453120</approximateDownloadSize>
        <approximateFlatDeploymentSize>2642411520</approximateFlatDeploymentSize>
        <approximateSparseDeploymentSize>0</approximateSparseDeploymentSize>
        <defaultEntityName>misa-remote-update-centos5 Appliance</defaultEntityName>
        <virtualApp>false</virtualApp>
        <defaultDeploymentOption/>
      </returnval>
    </ParseDescriptorResponse>
  </soapenv:Body>
</soapenv:Envelope>
""")

vmwareCreateImportSpecRequestTemplate = (
'<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
 '<SOAP-ENV:Header></SOAP-ENV:Header>'
 '<SOAP-ENV:Body xmlns:ns1="urn:vim25">'
   '<ns1:CreateImportSpec>'
     '<_this type="OvfManager">OvfManager</_this>'
     '<ns1:ovfDescriptor>'
     '%s'
     '</ns1:ovfDescriptor>'
     '<resourcePool type="ResourcePool">resgroup-50</resourcePool>'
     '<datastore type="Datastore">datastore-18</datastore>'
     '<cisp xsi:type="ns1:OvfCreateImportSpecParams">'
       '<ns1:locale></ns1:locale>'
       '<ns1:deploymentOption></ns1:deploymentOption>'
       '<ns1:entityName>template-some-file-6-1-x86-1</ns1:entityName>'
       '<networkMapping>'
         '<ns1:name>bridged</ns1:name>'
         '<network type="DistributedVirtualPortgroup">dvportgroup-9987</network>'
       '</networkMapping>'
     '</cisp>'
   '</ns1:CreateImportSpec>'
 '</SOAP-ENV:Body>'
'</SOAP-ENV:Envelope>')

vmwareCreateImportSpecRequest1 = vmwareCreateImportSpecRequestTemplate % \
    xmlEscape(client.VimService.sanitizeOvfDescriptor(vmwareOvfDescriptor1))

vmwareCreateImportSpecRequest2 = vmwareCreateImportSpecRequest1.replace(
    '<ns1:entityName>template-some-file-6-1-x86-1</ns1:entityName>',
    '<ns1:entityName>instance-foo</ns1:entityName>')

vmwareConfigSpec1 = (
          '<configSpec>'
            '<ns1:name>template-some-file-6-1-x86-1</ns1:name>'
            '<ns1:version>vmx-04</ns1:version>'
            '<ns1:guestId>otherLinux64Guest</ns1:guestId>'
            '<ns1:annotation></ns1:annotation>'
            '<files>'
              '<ns1:vmPathName>[nas1 target2]</ns1:vmPathName>'
            '</files>'
            '<tools>'
              '<ns1:afterPowerOn>true</ns1:afterPowerOn>'
              '<ns1:afterResume>true</ns1:afterResume>'
              '<ns1:beforeGuestStandby>true</ns1:beforeGuestStandby>'
              '<ns1:beforeGuestShutdown>true</ns1:beforeGuestShutdown>'
              '<ns1:beforeGuestReboot>true</ns1:beforeGuestReboot>'
            '</tools>'
            '<ns1:numCPUs>1</ns1:numCPUs>'
            '<ns1:memoryMB>1024</ns1:memoryMB>'
            '<deviceChange>'
              '<operation>add</operation>'
              '<device xsi:type="ns1:VirtualCdrom">'
                '<ns1:key>-100</ns1:key>'
                '<backing xsi:type="ns1:VirtualCdromAtapiBackingInfo">'
                  '<ns1:deviceName>cdrom1</ns1:deviceName>'
                '</backing>'
                '<connectable>'
                  '<ns1:startConnected>true</ns1:startConnected>'
                  '<ns1:allowGuestControl>true</ns1:allowGuestControl>'
                  '<ns1:connected>true</ns1:connected>'
                '</connectable>'
                '<ns1:controllerKey>201</ns1:controllerKey>'
                '<ns1:unitNumber>0</ns1:unitNumber>'
              '</device>'
            '</deviceChange>'
            '<deviceChange>'
              '<operation>add</operation>'
              '<device xsi:type="ns1:VirtualIDEController">'
                '<ns1:key>201</ns1:key>'
                '<connectable>'
                  '<ns1:startConnected>true</ns1:startConnected>'
                  '<ns1:allowGuestControl>false</ns1:allowGuestControl>'
                  '<ns1:connected>true</ns1:connected>'
                '</connectable>'
                '<ns1:busNumber>1</ns1:busNumber>'
                '<ns1:device>-100</ns1:device>'
              '</device>'
            '</deviceChange>'
            '<deviceChange>'
              '<operation>add</operation>'
              '<device xsi:type="ns1:VirtualUSBController">'
                '<ns1:key>-101</ns1:key>'
                '<connectable>'
                  '<ns1:startConnected>true</ns1:startConnected>'
                  '<ns1:allowGuestControl>false</ns1:allowGuestControl>'
                  '<ns1:connected>true</ns1:connected>'
                '</connectable>'
                '<ns1:unitNumber>4</ns1:unitNumber>'
                '<ns1:busNumber>0</ns1:busNumber>'
              '</device>'
            '</deviceChange>'
            '<deviceChange>'
              '<operation>add</operation>'
              '<fileOperation>create</fileOperation>'
              '<device xsi:type="ns1:VirtualDisk">'
                '<ns1:key>-103</ns1:key>'
                '<backing xsi:type="ns1:VirtualDiskFlatVer2BackingInfo">'
                  '<ns1:fileName></ns1:fileName>'
                  '<ns1:diskMode>persistent</ns1:diskMode>'
                  '<ns1:split>false</ns1:split>'
                '</backing>'
                '<connectable>'
                  '<ns1:startConnected>true</ns1:startConnected>'
                  '<ns1:allowGuestControl>false</ns1:allowGuestControl>'
                  '<ns1:connected>true</ns1:connected>'
                '</connectable>'
                '<ns1:controllerKey>-102</ns1:controllerKey>'
                '<ns1:unitNumber>0</ns1:unitNumber>'
                '<ns1:capacityInKB>2580480</ns1:capacityInKB>'
              '</device>'
            '</deviceChange>'
            '<deviceChange>'
              '<operation>add</operation>'
              '<device xsi:type="ns1:VirtualLsiLogicController">'
                '<ns1:key>-102</ns1:key>'
                '<connectable>'
                  '<ns1:startConnected>true</ns1:startConnected>'
                  '<ns1:allowGuestControl>false</ns1:allowGuestControl>'
                  '<ns1:connected>true</ns1:connected>'
                '</connectable>'
                '<ns1:busNumber>0</ns1:busNumber>'
                '<ns1:device>-103</ns1:device>'
                '<sharedBus>noSharing</sharedBus>'
              '</device>'
            '</deviceChange>'
            '<cpuAllocation>'
              '<ns1:reservation>0</ns1:reservation>'
              '<ns1:limit>-1</ns1:limit>'
              '<shares>'
                '<ns1:shares>-1</ns1:shares>'
                '<level>normal</level>'
              '</shares>'
            '</cpuAllocation>'
            '<memoryAllocation>'
              '<ns1:reservation>0</ns1:reservation>'
              '<ns1:limit>-1</ns1:limit>'
              '<shares>'
                '<ns1:shares>-1</ns1:shares>'
                '<level>normal</level>'
              '</shares>'
            '</memoryAllocation>'
            '<vAppConfig>'
              '<ns1:installBootRequired>false</ns1:installBootRequired>'
              '<ns1:installBootStopDelay>0</ns1:installBootStopDelay>'
            '</vAppConfig>'
          '</configSpec>'
)

vmwareCreateImportSpecResponseTemplate = """\
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Body>
    <CreateImportSpecResponse xmlns="urn:vim25">
      <returnval>
       <importSpec xsi:type="VirtualMachineImportSpec">
        %s
        </importSpec>
        <fileItem>
          <deviceId>/vm-name-goes-here/VirtualLsiLogicController0:0</deviceId>
          <path>some-file-6-1-x86.vmdk</path>
          <compressionMethod/>
          <size>152453120</size>
          <cimType>17</cimType>
          <create>false</create>
        </fileItem>
      </returnval>
    </CreateImportSpecResponse>
  </soapenv:Body>
</soapenv:Envelope>
"""

vmwareCreateImportSpecResponse1 = HTTPResponse(
    vmwareCreateImportSpecResponseTemplate % vmwareConfigSpec1.replace('ns1:', ''))

vmwareImportVAppRequest1 = (
'<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
 '<SOAP-ENV:Header></SOAP-ENV:Header>'
 '<SOAP-ENV:Body xmlns:ns1="urn:vim25">'
   '<ns1:ImportVApp>'
     '<_this type="ResourcePool">resgroup-50</_this>'
     '<spec xsi:type="ns1:VirtualMachineImportSpec">'
       '%s'
     '</spec>'
     '<folder type="Folder">group-v3</folder>'
   '</ns1:ImportVApp>'
 '</SOAP-ENV:Body>'
'</SOAP-ENV:Envelope>') % vmwareConfigSpec1

vmwareImportVAppResponseTemplate = """\
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Body>
    <ImportVAppResponse xmlns="urn:vim25">
      <returnval type="HttpNfcLease">session[%s]%s</returnval>
    </ImportVAppResponse>
  </soapenv:Body>
</soapenv:Envelope>
"""

vmwareImportVAppResponse1 = HTTPResponse(
    vmwareImportVAppResponseTemplate % vmwareHttpNfcLeaseSession1)

vmwareWaitForUpdatesRequestTemplate = (
 '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"'
   ' xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"'
   ' xmlns:ZSI="http://www.zolera.com/schemas/ZSI/"'
   ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
   ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
 '<SOAP-ENV:Header></SOAP-ENV:Header>'
 '<SOAP-ENV:Body xmlns:ns1="urn:vim25">'
 '<ns1:WaitForUpdates>'
 '<_this type="PropertyCollector">propertyCollector</_this>'
 '<ns1:version>%(version)s</ns1:version>'
 '</ns1:WaitForUpdates>'
 '</SOAP-ENV:Body>'
 '</SOAP-ENV:Envelope>')

vmwareWaitForUpdatesRequest1 = vmwareWaitForUpdatesRequestTemplate % dict(
    version='')

vmwareWaitForUpdatesRequest2 = vmwareWaitForUpdatesRequestTemplate % dict(
    version='1')

vmwareWaitForUpdatesRequestR1 = vmwareWaitForUpdatesRequestTemplate % dict(
    version='41')

vmwareWaitForUpdatesResponseTemplate = """\
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Body>
    <WaitForUpdatesResponse xmlns="urn:vim25">
      <returnval>
        <version>%(version)s</version>
        <filterSet>
          <filter type="PropertyFilter">session[%(uuid1)s]%(uuid2)s</filter>
          <objectSet>
            <kind>modify</kind>
            <obj type="%(klass)s">%(objectId)s</obj>
            <changeSet>
              <name>%(path)s</name>
              <op>assign</op>
              <val xsi:type="%(rklass)s">%(value)s</val>
            </changeSet>
          </objectSet>
        </filterSet>
      </returnval>
    </WaitForUpdatesResponse>
  </soapenv:Body>
</soapenv:Envelope>
"""

vmwareWaitForUpdatesResponse1 = HTTPResponse(
  vmwareWaitForUpdatesResponseTemplate % dict(
    version = 1, uuid1 = 'uuidA1', uuid2 = 'uuidA1',
    klass = 'Task', rklass = 'TaskInfoState',
    objectId = 'session[uuidA1]uuidA1', path = 'state',
    value = 'ready'))

vmwareWaitForUpdatesResponseReconfigVM1 = HTTPResponse(
  vmwareWaitForUpdatesResponseTemplate % dict(
    version = 41, uuid1 = 'uuid48', uuid2 = 'uuid48',
    klass = 'Task', rklass = 'TaskInfoState',
    objectId = 'task-48', path = 'info.state',
    value = 'success'))

vmwareWaitForUpdatesResponseCloneVM1 = HTTPResponse(
  vmwareWaitForUpdatesResponseTemplate % dict(
    version = 81, uuid1 = 'uuid48', uuid2 = 'uuid48',
    klass = 'Task', rklass = 'TaskInfoState',
    objectId = 'task-48', path = 'info.state',
    value = 'success'))

vmwareWaitForUpdatesResponseRegisterVM1 = vmwareWaitForUpdatesResponseCloneVM1

vmwareWaitForUpdatesResponsePowerOnVM1 = HTTPResponse(
  vmwareWaitForUpdatesResponseTemplate % dict(
    version = 81, uuid1 = 'uuid48', uuid2 = 'uuid48',
    klass = 'Task', rklass = 'TaskInfoState',
    objectId = 'task-48', path = 'info.state',
    value = 'success'))


vmwareWaitForUpdatesResponse2 = HTTPResponse(
  vmwareWaitForUpdatesResponseTemplate % dict(
    version = 1, uuid1 = '5415DDE-AC82-4570-85A7-2452ADB499D5',
    uuid2 = '57A98DF2-7E62-4BF7-88D1-BA0500C0233A',
    klass = 'Task', rklass = 'TaskInfoState',
    objectId = 'task-6535', path = 'state',
    value = 'success'))

vmwareHttpNfcLeaseCompleteReqTemplate = (
'<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
  '<SOAP-ENV:Header></SOAP-ENV:Header>'
  '<SOAP-ENV:Body xmlns:ns1="urn:vim25">'
    '<ns1:HttpNfcLeaseComplete>'
      '<_this type="HttpNfcLease">session[%s]%s</_this>'
    '</ns1:HttpNfcLeaseComplete>'
  '</SOAP-ENV:Body>'
'</SOAP-ENV:Envelope>')

vmwareHttpNfcLeaseCompleteReq = vmwareHttpNfcLeaseCompleteReqTemplate % \
    vmwareHttpNfcLeaseSession1

vmwareHttpNfcLeaseCompleteResp = HTTPResponse("""\
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
  <HttpNfcLeaseCompleteResponse xmlns="urn:vim25"></HttpNfcLeaseCompleteResponse>
</soapenv:Body>
</soapenv:Envelope>
""")

vmwareHttpNfcLeaseProgressReqTemplate = (
'<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
  '<SOAP-ENV:Header></SOAP-ENV:Header>'
  '<SOAP-ENV:Body xmlns:ns1="urn:vim25">'
    '<ns1:HttpNfcLeaseProgress>'
      '<_this type="HttpNfcLease">session[%(uuid1)s]%(uuid2)s</_this>'
      '<ns1:percent>%(percent)s</ns1:percent>'
    '</ns1:HttpNfcLeaseProgress>'
  '</SOAP-ENV:Body>'
'</SOAP-ENV:Envelope>'
)

vmwareHttpNfcLeaseProgressResp = HTTPResponse("""\
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
  <HttpNfcLeaseProgressResponse xmlns="urn:vim25"></HttpNfcLeaseProgressResponse>
</soapenv:Body>
</soapenv:Envelope>
""")

_params = [ ('uuid1', vmwareHttpNfcLeaseSession1[0]),
            ('uuid2', vmwareHttpNfcLeaseSession1[1]) ]
_d = [ vmwareHttpNfcLeaseProgressReqTemplate % dict(
    _params + [ ('percent', 10 * i ) ]) for i in range(11) ]

vmwarePowerOffVMReq1 = (
 '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"'
 ' xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"'
 ' xmlns:ZSI="http://www.zolera.com/schemas/ZSI/"'
 ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
 ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
 '<SOAP-ENV:Header></SOAP-ENV:Header>'
 '<SOAP-ENV:Body xmlns:ns1="urn:vim25">'
 '<ns1:PowerOffVM_Task>'
 '<_this type="VirtualMachine">vm-1201</_this>'
 '</ns1:PowerOffVM_Task>'
 '</SOAP-ENV:Body></SOAP-ENV:Envelope>'
)

vmwarePowerOffResp1 = HTTPResponse(
 '<?xml version="1.0" encoding="UTF-8"?>\n'
 '<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"\n'
 ' xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"\n'
 ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"\n'
 ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
 '<soapenv:Body>\n'
 '<PowerOffVM_TaskResponse xmlns="urn:vim25">'
 '<returnval type="Task">task-6536</returnval>'
 '</PowerOffVM_TaskResponse>\n'
 '</soapenv:Body>\n'
 '</soapenv:Envelope>'
)

vmwareQueryConfigTargetReq1 = ('<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    '<SOAP-ENV:Header></SOAP-ENV:Header>'
    '<SOAP-ENV:Body xmlns:ns1="urn:vim25">'
      '<ns1:QueryConfigTarget>'
        '<_this type="EnvironmentBrowser" xsi:type="ns1:ManagedObjectReference">envbrowser-5</_this>'
      '</ns1:QueryConfigTarget>'
    '</SOAP-ENV:Body>'
'</SOAP-ENV:Envelope>')

vmwareQueryConfigTargetResp1 = HTTPResponse("""\
<?xml version="1.0" encoding="UTF-8"?> <soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
 <QueryConfigTargetResponse xmlns="urn:vim25">
  <returnval>
    <numCpus>16</numCpus>
    <numCpuCores>16</numCpuCores>
    <numNumaNodes>5</numNumaNodes>
    <datastore>
      <name>nas2-nfs</name>
      <datastore>
        <datastore type="Datastore">datastore-16</datastore>
        <name>nas2-nfs</name>
        <url>netfs://172.16.160.167//mnt/vg00/nfs-storage/vmware-images/</url>
        <capacity>724236845056</capacity>
        <freeSpace>409254006784</freeSpace>
        <uncommitted>0</uncommitted>
        <accessible>true</accessible>
        <multipleHostAccess>true</multipleHostAccess>
        <type>NFS</type>
      </datastore>
      <capability>
        <directoryHierarchySupported>true</directoryHierarchySupported>
        <rawDiskMappingsSupported>false</rawDiskMappingsSupported>
        <perFileThinProvisioningSupported>false</perFileThinProvisioningSupported>
      </capability>
      <maxFileSize>9223372036854775807</maxFileSize>
      <mode>readOnly</mode>
    </datastore>
    <datastore>
      <name>nas1-iscsi</name>
      <datastore>
        <datastore type="Datastore">datastore-18</datastore>
        <name>nas1-iscsi</name>
        <url>sanfs://vmfs_uuid:47e71a3d-1cac6286-f0fe-00188b3fb778/</url>
        <capacity>1749662302208</capacity>
        <freeSpace>264553627648</freeSpace>
        <uncommitted>0</uncommitted>
        <accessible>true</accessible>
        <multipleHostAccess>true</multipleHostAccess>
        <type>VMFS</type>
      </datastore>
      <capability>
        <directoryHierarchySupported>true</directoryHierarchySupported>
        <rawDiskMappingsSupported>true</rawDiskMappingsSupported>
        <perFileThinProvisioningSupported>true</perFileThinProvisioningSupported>
      </capability>
      <maxFileSize>274877906944</maxFileSize>
      <mode>readWrite</mode>
    </datastore>
    <datastore>
      <name>nas2-iscsi</name>
      <datastore>
        <datastore type="Datastore">datastore-20</datastore>
        <name>nas2-iscsi</name>
        <url>sanfs://vmfs_uuid:47e71a7f-82d08548-2178-00188b3fb778/</url>
        <capacity>8749662302208</capacity>
        <freeSpace>942972884992</freeSpace>
        <uncommitted>942972884992</uncommitted>
        <accessible>true</accessible>
        <multipleHostAccess>true</multipleHostAccess>
        <type>VMFS</type>
      </datastore>
      <capability>
        <directoryHierarchySupported>true</directoryHierarchySupported>
        <rawDiskMappingsSupported>true</rawDiskMappingsSupported>
        <perFileThinProvisioningSupported>true</perFileThinProvisioningSupported>
      </capability>
      <maxFileSize>274877906944</maxFileSize>
      <mode>readWrite</mode>
    </datastore>
    <datastore>
      <name>esx03-local</name>
      <datastore>
        <datastore type="Datastore">datastore-563</datastore>
        <name>esx03-local</name>
        <url>sanfs://vmfs_uuid:48b4718e-0713c17a-5df1-00188b4020e0/</url>
        <capacity>151129161728</capacity>
        <freeSpace>147722338304</freeSpace>
        <uncommitted>147722338304</uncommitted>
        <accessible>true</accessible>
        <multipleHostAccess>false</multipleHostAccess>
        <type>VMFS</type>
      </datastore>
      <capability>
        <directoryHierarchySupported>true</directoryHierarchySupported>
        <rawDiskMappingsSupported>true</rawDiskMappingsSupported>
        <perFileThinProvisioningSupported>true</perFileThinProvisioningSupported>
      </capability>
      <maxFileSize>274877906944</maxFileSize>
      <mode>readWrite</mode>
    </datastore>
    <datastore>
      <name>esx04-local</name>
      <datastore>
        <datastore type="Datastore">datastore-565</datastore>
        <name>esx04-local</name>
        <url>sanfs://vmfs_uuid:48b47438-b1c642ee-0930-00188b3faa0f/</url>
        <capacity>151129161728</capacity>
        <freeSpace>141145669632</freeSpace>
        <uncommitted>1000</uncommitted>
        <accessible>true</accessible>
        <multipleHostAccess>false</multipleHostAccess>
        <type>VMFS</type>
      </datastore>
      <capability>
        <directoryHierarchySupported>true</directoryHierarchySupported>
        <rawDiskMappingsSupported>true</rawDiskMappingsSupported>
        <perFileThinProvisioningSupported>true</perFileThinProvisioningSupported>
      </capability>
      <maxFileSize>274877906944</maxFileSize>
      <mode>readWrite</mode>
    </datastore>
    <datastore>
      <name>esx02-local</name>
      <datastore>
        <datastore type="Datastore">datastore-884</datastore>
        <name>esx02-local</name>
        <url>sanfs://vmfs_uuid:48c6cc03-ab28edb0-cac5-00188b3fb776/</url>
        <capacity>154350387200</capacity>
        <freeSpace>147264110592</freeSpace>
        <uncommitted>247264110592</uncommitted>
        <accessible>true</accessible>
        <multipleHostAccess>false</multipleHostAccess>
        <type>VMFS</type>
      </datastore>
      <capability>
        <directoryHierarchySupported>true</directoryHierarchySupported>
        <rawDiskMappingsSupported>true</rawDiskMappingsSupported>
        <perFileThinProvisioningSupported>true</perFileThinProvisioningSupported>
      </capability>
      <maxFileSize>274877906944</maxFileSize>
      <mode>readWrite</mode>
    </datastore>
    <datastore>
      <name>esx05-local</name>
      <datastore>
        <datastore type="Datastore">datastore-887</datastore>
        <name>esx05-local</name>
        <url>sanfs://vmfs_uuid:48c69614-086355b0-c0af-00188b3fa806/</url>
        <capacity>153813516288</capacity>
        <freeSpace>144366895104</freeSpace>
        <uncommitted>244366895104</uncommitted>
        <accessible>true</accessible>
        <multipleHostAccess>false</multipleHostAccess>
        <type>VMFS</type>
      </datastore>
      <capability>
        <directoryHierarchySupported>true</directoryHierarchySupported>
        <rawDiskMappingsSupported>true</rawDiskMappingsSupported>
        <perFileThinProvisioningSupported>true</perFileThinProvisioningSupported>
      </capability>
      <maxFileSize>274877906944</maxFileSize>
      <mode>readWrite</mode>
    </datastore>
    <datastore>
      <name>esx01-local</name>
      <datastore>
        <datastore type="Datastore">datastore-559</datastore>
        <name>esx01-local</name>
        <url>sanfs://vmfs_uuid:48b47134-c01805f0-6371-00188b401fd1/</url>
        <capacity>310579822592</capacity>
        <freeSpace>305246765056</freeSpace>
        <uncommitted>605246765056</uncommitted>
        <accessible>true</accessible>
        <multipleHostAccess>false</multipleHostAccess>
        <type>VMFS</type>
      </datastore>
      <capability>
        <directoryHierarchySupported>true</directoryHierarchySupported>
        <rawDiskMappingsSupported>true</rawDiskMappingsSupported>
        <perFileThinProvisioningSupported>true</perFileThinProvisioningSupported>
      </capability>
      <maxFileSize>274877906944</maxFileSize>
      <mode>readWrite</mode>
    </datastore>
    <distributedVirtualPortgroup>
      <switchName>ESX trunk</switchName>
      <switchUuid>19 e9 34 50 73 a6 9e 1d-12 1b 2c 4b b9 5a 62 17</switchUuid>
      <portgroupName>esx trunk uplink</portgroupName>
      <portgroupKey>dvportgroup-9986</portgroupKey>
      <portgroupType>earlyBinding</portgroupType>
      <uplinkPortgroup>true</uplinkPortgroup>
      <portgroup type="DistributedVirtualPortgroup">dvportgroup-9986</portgroup>
    </distributedVirtualPortgroup>
    <distributedVirtualPortgroup>
      <switchName>ESX trunk</switchName>
      <switchUuid>19 e9 34 50 73 a6 9e 1d-12 1b 2c 4b b9 5a 62 17</switchUuid>
      <portgroupName>Engineering Lab</portgroupName>
      <portgroupKey>dvportgroup-9987</portgroupKey>
      <portgroupType>earlyBinding</portgroupType>
      <uplinkPortgroup>false</uplinkPortgroup>
      <portgroup type="DistributedVirtualPortgroup">dvportgroup-9987</portgroup>
    </distributedVirtualPortgroup>
    <distributedVirtualSwitch>
      <switchName>ESX trunk</switchName>
      <switchUuid>19 e9 34 50 73 a6 9e 1d-12 1b 2c 4b b9 5a 62 17</switchUuid>
      <distributedVirtualSwitch type="VmwareDistributedVirtualSwitch">dvs-9985</distributedVirtualSwitch>
    </distributedVirtualSwitch>
    <network>
      <name>VM Network</name>
      <network>
        <network type="Network">network-22</network>
        <name>VM Network</name>
        <accessible>false</accessible>
      </network>
    </network>
    <cdRom>
      <name>/dev/hda</name>
    </cdRom>
    <cdRom>
      <name>/dev/scd0</name>
    </cdRom>
    <cdRom>
      <name>/dev/scd1</name>
    </cdRom>
    <cdRom>
      <name>/dev/scd2</name>
    </cdRom>
    <cdRom>
      <name>/dev/scd3</name>
    </cdRom>
    <cdRom>
      <name>/dev/scd4</name>
    </cdRom>
    <cdRom>
      <name>/dev/scd5</name>
    </cdRom>
    <cdRom>
      <name>/dev/scd6</name>
    </cdRom>
    <cdRom>
      <name>/dev/scd7</name>
    </cdRom>
    <cdRom>
      <name>/vmfs/devices/genide/vmhba0:0:0</name>
    </cdRom>
    <serial>
      <name>/dev/ttyS0</name>
    </serial>
    <serial>
      <name>/dev/ttyS1</name>
    </serial>
    <usb>
      <name>435890192344555</name>
      <description>My funky USB dongle</description>
      <vendor>0</vendor>
      <product>0</product>
      <physicalPath/>
    </usb>
    <usb>
      <name>43589324325534</name>
      <description>Digital SEC FVRW Doohickey</description>
      <vendor>0</vendor>
      <product>0</product>
      <physicalPath/>
    </usb>
    <usb>
      <name>435890192344555</name>
      <description>My funky USB dongle</description>
      <vendor>0</vendor>
      <product>0</product>
      <physicalPath/>
    </usb>
    <usb>
      <name>43589324325534</name>
      <description>Digital SEC FVRW Doohickey</description>
      <vendor>0</vendor>
      <product>0</product>
      <physicalPath/>
    </usb>
    <usb>
      <name>435890192344555</name>
      <description>My funky USB dongle</description>
      <vendor>0</vendor>
      <product>0</product>
      <physicalPath/>
    </usb>
    <usb>
      <name>43589324325534</name>
      <description>Digital SEC FVRW Doohickey</description>
      <vendor>0</vendor>
      <product>0</product>
      <physicalPath/>
    </usb>
    <usb>
      <name>435890192344555</name>
      <description>My funky USB dongle</description>
      <vendor>0</vendor>
      <product>0</product>
      <physicalPath/>
    </usb>
    <usb>
      <name>43589324325534</name>
      <description>Digital SEC FVRW Doohickey</description>
      <vendor>0</vendor>
      <product>0</product>
      <physicalPath/>
    </usb>
    <usb>
      <name>435890192344555</name>
      <description>My funky USB dongle</description>
      <vendor>0</vendor>
      <product>0</product>
      <physicalPath/>
    </usb>
    <usb>
      <name>43589324325534</name>
      <description>Digital SEC FVRW Doohickey</description>
      <vendor>0</vendor>
      <product>0</product>
      <physicalPath/>
    </usb>
    <maxMemMBOptimalPerf>8191</maxMemMBOptimalPerf>
  </returnval>
 </QueryConfigTargetResponse>
</soapenv:Body>
</soapenv:Envelope>""")

vmwareQueryConfigTargetResp10 = HTTPResponse("""\
<?xml version="1.0" encoding="UTF-8"?> <soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<soapenv:Body>
 <QueryConfigTargetResponse xmlns="urn:vim25">
  <returnval>
    <numCpus>16</numCpus>
    <numCpuCores>16</numCpuCores>
    <numNumaNodes>5</numNumaNodes>
    <datastore>
      <name>datastore 100</name>
      <datastore>
        <datastore type="Datastore">datastore-100</datastore>
        <name>datastore 100</name>
        <url>sanfs://vmfs_uuid:00000000-00000000-0000-100000000000/</url>
        <capacity>724236845056</capacity>
        <freeSpace>409254006784</freeSpace>
        <accessible>true</accessible>
        <multipleHostAccess>true</multipleHostAccess>
        <type>VMFS</type>
      </datastore>
      <capability>
        <directoryHierarchySupported>true</directoryHierarchySupported>
        <rawDiskMappingsSupported>true</rawDiskMappingsSupported>
        <perFileThinProvisioningSupported>true</perFileThinProvisioningSupported>
      </capability>
      <maxFileSize>9223372036854775807</maxFileSize>
      <mode>readOnly</mode>
    </datastore>
    <datastore>
      <name>datastore 101</name>
      <datastore>
        <datastore type="Datastore">datastore-101</datastore>
        <name>datastore 101</name>
        <url>sanfs://vmfs_uuid:00000000-00000000-0000-101000000000/</url>
        <capacity>724236845056</capacity>
        <freeSpace>409254006784</freeSpace>
        <accessible>true</accessible>
        <multipleHostAccess>true</multipleHostAccess>
        <type>VMFS</type>
      </datastore>
      <capability>
        <directoryHierarchySupported>true</directoryHierarchySupported>
        <rawDiskMappingsSupported>true</rawDiskMappingsSupported>
        <perFileThinProvisioningSupported>true</perFileThinProvisioningSupported>
      </capability>
      <maxFileSize>9223372036854775807</maxFileSize>
      <mode>readWrite</mode>
    </datastore>
    <datastore>
      <name>datastore 102</name>
      <datastore>
        <datastore type="Datastore">datastore-102</datastore>
        <name>datastore 102</name>
        <url>sanfs://vmfs_uuid:00000000-00000000-0000-102000000000/</url>
        <capacity>724236845056</capacity>
        <freeSpace>409254006784</freeSpace>
        <accessible>true</accessible>
        <multipleHostAccess>true</multipleHostAccess>
        <type>VMFS</type>
      </datastore>
      <capability>
        <directoryHierarchySupported>true</directoryHierarchySupported>
        <rawDiskMappingsSupported>true</rawDiskMappingsSupported>
        <perFileThinProvisioningSupported>true</perFileThinProvisioningSupported>
      </capability>
      <maxFileSize>9223372036854775807</maxFileSize>
      <mode>readWrite</mode>
    </datastore>
    <distributedVirtualPortgroup>
      <switchName>ESX trunk</switchName>
      <switchUuid>00 00 00 00 00 00 00 00-00 00 00 00 00 00 10 00</switchUuid>
      <portgroupName>esx trunk uplink 10</portgroupName>
      <portgroupKey>dvportgroup-100</portgroupKey>
      <portgroupType>earlyBinding</portgroupType>
      <uplinkPortgroup>true</uplinkPortgroup>
      <portgroup type="DistributedVirtualPortgroup">dvportgroup-100</portgroup>
    </distributedVirtualPortgroup>
    <distributedVirtualPortgroup>
      <switchName>ESX trunk</switchName>
      <switchUuid>00 00 00 00 00 00 00 00-00 00 00 00 00 00 10 00</switchUuid>
      <portgroupName>Engineering Lab 10</portgroupName>
      <portgroupKey>dvportgroup-101</portgroupKey>
      <portgroupType>earlyBinding</portgroupType>
      <uplinkPortgroup>true</uplinkPortgroup>
      <portgroup type="DistributedVirtualPortgroup">dvportgroup-101</portgroup>
    </distributedVirtualPortgroup>
    <network>
      <name>VM Network</name>
      <network>
        <network type="Network">network-10</network>
        <name>VM Network 10</name>
        <accessible>false</accessible>
      </network>
    </network>
    <cdRom>
      <name>/dev/scd0</name>
    </cdRom>
    <serial>
      <name>/dev/ttyS0</name>
    </serial>
    <serial>
      <name>/dev/ttyS1</name>
    </serial>
    <maxMemMBOptimalPerf>8191</maxMemMBOptimalPerf>
  </returnval>
 </QueryConfigTargetResponse>
</soapenv:Body>
</soapenv:Envelope>""")

vmwareQueryConfigTargetResp20 = HTTPResponse(
    vmwareQueryConfigTargetResp10.data.replace('10', '20'))

vmwareSoapData = dict((x, vmwareHttpNfcLeaseProgressResp) for x in _d)
vmwareSoapData.update({
 vmwareRetrieveServiceContentRequest : vmwareRetrieveServiceContentResponse,
 vmwareParseDescriptorRequest1 : vmwareParseDescriptorResponse1,
 vmwareCreateImportSpecRequest1 : vmwareCreateImportSpecResponse1,
 vmwareCreateImportSpecRequest2 : vmwareCreateImportSpecResponse1,
 vmwareImportVAppRequest1 : vmwareImportVAppResponse1,
 vmwareCreateFilterForHttpNfcLeaseReq1 : vmwareCreateFilterForHttpNfcLeaseResp1,
 vmwareRetrievePropertiesHttpNfcLeaseReq : vmwareRetrievePropertiesHttpNfcLeaseResp,
 vmwareHttpNfcLeaseCompleteReq : vmwareHttpNfcLeaseCompleteResp,
 vmwareRetrievePropertiesVMNetworkReq1 : vmwareRetrievePropertiesVMNetworkResp1,
 vmwareRetrievePropertiesVMNetworkReq2 : vmwareRetrievePropertiesVMNetworkResp1,

 # BEGIN REQUEST - login
 '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" '
 'xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" '
 'xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" '
 'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
 '<SOAP-ENV:Header></SOAP-ENV:Header>'
 '<SOAP-ENV:Body xmlns:ns1="urn:vim25"><ns1:Login>'
 '<_this type="SessionManager">SessionManager</_this>'
 '<ns1:userName>abc</ns1:userName>'
 '<ns1:password>12345678</ns1:password>'
 '<ns1:locale>en_US</ns1:locale>'
 '</ns1:Login>'
 '</SOAP-ENV:Body></SOAP-ENV:Envelope>'
 # END REQUEST
 :

 # BEGIN RESPONSE - login
 'HTTP/1.1 200 OK\r\n'
 'Date: Fri, 31 Oct 2008 19:20:36 GMT\r\n'
 'Cache-Control: no-cache\r\n'
 'Content-Type: text/xml; charset=utf-8\r\n'
 'Content-Length: 653\r\n'
 '\r\n'
 '<?xml version="1.0" encoding="UTF-8"?>\n'
 '<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"\n '
 'xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"\n '
 'xmlns:xsd="http://www.w3.org/2001/XMLSchema"\n '
 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
 '<soapenv:Body>\n'
 '<LoginResponse xmlns="urn:vim25">'
 '<returnval>'
 '<key>FED518EE-8D40-475B-9A7E-31D107FCFC95</key>'
 '<userName>abc</userName>'
 '<fullName>abc</fullName>'
 '<loginTime>2008-10-31T19:20:36.625Z</loginTime>'
 '<lastActiveTime>2008-10-31T19:20:36.625Z</lastActiveTime>'
 '<locale>en_US</locale>'
 '<messageLocale>en</messageLocale>'
 '</returnval></LoginResponse>\n'
 '</soapenv:Body>\n'
 '</soapenv:Envelope>'
 # END RESPONSE
 ,

 # BEGIN REQUEST - logout
 '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" '
 'xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" '
 'xmlns:ZSI="http://www.zolera.com/schemas/ZSI/" '
 'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
 '<SOAP-ENV:Header></SOAP-ENV:Header>'
 '<SOAP-ENV:Body xmlns:ns1="urn:vim25">'
 '<ns1:Logout>'
 '<_this type="SessionManager">SessionManager</_this>'
 '</ns1:Logout>'
 '</SOAP-ENV:Body></SOAP-ENV:Envelope>'
 # END REQUEST
 :

 # BEGIN RESPONSE - logout
 'HTTP/1.1 200 OK\r\n'
 'Date: Fri, 31 Oct 2008 19:20:36 GMT\r\n'
 'Cache-Control: no-cache\r\n'
 'Content-Type: text/xml; charset=utf-8\r\n'
 'Content-Length: 378\r\n'
 '\r\n'
 '<?xml version="1.0" encoding="UTF-8"?>\n'
 '<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"\n '
 'xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"\n '
 'xmlns:xsd="http://www.w3.org/2001/XMLSchema"\n '
 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
 '<soapenv:Body>\n'
 '<LogoutResponse xmlns="urn:vim25"></LogoutResponse>\n'
 '</soapenv:Body>\n'
 '</soapenv:Envelope>'
 # END RESPONSE - logout
 ,

vmwareReqGetVirtualMachineProps1 : vmwareResponseGetVirtualMachineProps,
vmwareReqGetVirtualMachineProps35 : vmwareResponseGetVirtualMachineProps,
vmwareReqGetVirtualMachineProps2 : vmwareResponseGetVirtualMachineProps,
vmwareReqGetVirtualMachineProps35_2 : vmwareResponseGetVirtualMachineProps,

 (vmwareFindVmByUuidReq % '50344408-f9b7-3927-417b-14258d839e26') :
    (vmwareFindVmByUuidResp % 'vm-1201'),
 (vmwareFindVmByUuidReq % '00000000-0000-0000-0000-000000000000') :
    (vmwareFindVmByUuidResp % 'vm-1201'),
 (vmwareFindVmByUuidReq % 'vmuuid10') :
    (vmwareFindVmByUuidResp % 'vm-1201'),

 # START REQUEST - shut down via tools
 '<SOAP-ENV:Envelope xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"'
 ' xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"'
 ' xmlns:ZSI="http://www.zolera.com/schemas/ZSI/"'
 ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
 ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
 '<SOAP-ENV:Header></SOAP-ENV:Header>'
 '<SOAP-ENV:Body xmlns:ns1="urn:vim25"><ns1:ShutdownGuest>'
 '<_this type="VirtualMachine">vm-1201</_this>'
 '</ns1:ShutdownGuest>'
 '</SOAP-ENV:Body>'
 '</SOAP-ENV:Envelope>'
 # END REQUEST - shut down via tools
 :

 # START RESPONSE - shut down via tools
 'HTTP/1.1 500 Internal Server Error\r\n'
 'Date: Mon, 3 Nov 2008 19:23:19 GMT\r\n'
 'Cache-Control: no-cache\r\n'
 'Content-Type: text/xml; charset=utf-8\r\n'
 'Content-Length: 609\r\n'
 '\r\n'
 '<?xml version="1.0" encoding="UTF-8"?>\n'
 '<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"\n'
 ' xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"\n'
 ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"\n'
 ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
 '<soapenv:Body>\n'
 '<soapenv:Fault><faultcode>ServerFaultCode</faultcode>'
 '<faultstring>Operation failed since VMware tools are not running in this virtual machine.</faultstring>'
 '<detail>'
 '<ToolsUnavailableFault xmlns="urn:vim25" xsi:type="ToolsUnavailable">'
 '</ToolsUnavailableFault></detail></soapenv:Fault>\n'
 '</soapenv:Body>\n'
 '</soapenv:Envelope>'
 ,

 vmwarePowerOffVMReq1 : vmwarePowerOffResp1,
 (vmwareCreateFilterForTaskReq % 'task-6536') :
    HTTPResponse( vmwareCreateFilterForTaskRespTmpl %
     ('75415DDE-AC82-4570-85A7-2452ADB499D5',
        '57A98DF2-7E62-4BF7-88D1-BA0500C0233A')),
 (vmwareCreateFilterForTaskReq % 'task-42') :
     HTTPResponse(vmwareCreateFilterForTaskRespTmpl % ('uuid1', 'uuid2')),
 (vmwareCreateFilterForTaskReq % 'task-43') :
     HTTPResponse(vmwareCreateFilterForTaskRespTmpl % ('uuid3', 'uuid4')),
 (vmwareCreateFilterForTaskReq % 'task-44') :
     HTTPResponse(vmwareCreateFilterForTaskRespTmpl % ('uuid5', 'uuid6')),
 (vmwareCreateFilterForTaskReq % 'task-46') :
     HTTPResponse(vmwareCreateFilterForTaskRespTmpl % ('uuid7', 'uuid8')),
 (vmwareCreateFilterForTaskReq % 'task-48') :
     HTTPResponse(vmwareCreateFilterForTaskRespTmpl % ('uuid48', 'uuid48')),
 (vmwareCreateFilterForTaskReq % 'task-51') :
     HTTPResponse(vmwareCreateFilterForTaskRespTmpl % ('uuidA', 'uuidB')),

 (vmwareRetrievePropertiesTaskReq % 'task-42'):
    vmwareRetrievePropertiesTaskResp,
 (vmwareRetrievePropertiesTaskReq % 'task-44'):
    vmwareRetrievePropertiesTaskResp,
 (vmwareRetrievePropertiesTaskReq % 'task-46'):
    vmwareRetrievePropertiesTaskResp,
 (vmwareRetrievePropertiesTaskReq % 'task-6536'):
    vmwareRetrievePropertiesTaskResp,

  vmwareRetrievePropertiesDVSConfigReq :
    vmwareRetrievePropertiesDVSConfigResp,

  vmwareRetrievePropertiesDVSUuidReq :
    vmwareRetrievePropertiesDVSUuidResp,

  vmwareRetrievePropertiesDatacenterReq :
     vmwareRetrievePropertiesDatacenterResp,
  vmwareRetrievePropertiesDatacenterVmFolderReq :
     vmwareRetrievePropertiesDatacenterVmFolderResp,

 vmwareReconfigVMTaskReq : vmwareReconfigVMTaskResp % 'task-43',
 vmwareReconfigVMTaskReq2 : vmwareReconfigVMTaskResp % 'task-46',
 vmwareReconfigVMTaskReq3 : vmwareReconfigVMTaskResp % 'task-46',
 vmwareReconfigVMTaskReq4 : vmwareReconfigVMTaskResp % 'task-46',
 vmwareReconfigVMTaskReq5 : vmwareReconfigVMTaskResp % 'task-48',
 vmwareReconfigVMTaskReq6 : vmwareReconfigVMTaskResp % 'task-48',
 vmwareReconfigVMTaskReq7 : vmwareReconfigVMTaskResp % 'task-48',
 vmwareReconfigVMTaskReq8 : vmwareReconfigVMTaskResp % 'task-48',
 vmwareMarkAsTemplateReq1 : vmwareMarkAsTemplateResp,
 vmwareMarkAsTemplateReq2 : vmwareMarkAsTemplateResp,

 vmwareCloneVMTaskReq : vmwareCloneVMTaskResp % 'task-44',
 vmwareCloneVMTaskReq2 : vmwareCloneVMTaskResp % 'task-44',
 vmwareCloneVMTaskReq3 : vmwareCloneVMTaskResp % 'task-44',
 vmwareWaitForUpdatesRequest1 : HTTPResponse(
    [ vmwareWaitForUpdatesResponse1,
      vmwareWaitForUpdatesResponseReconfigVM1,
      vmwareWaitForUpdatesResponseCloneVM1,
      vmwareWaitForUpdatesResponseReconfigVM1,
      vmwareWaitForUpdatesResponsePowerOnVM1,
     ]),
 vmwareWaitForUpdatesRequest2 : vmwareWaitForUpdatesResponse2,

 (vmwareDestroyFilterReq % (
    "75415DDE-AC82-4570-85A7-2452ADB499D5",
    "57A98DF2-7E62-4BF7-88D1-BA0500C0233A")) :
  vmwareDestroyFilterResp,
 (vmwareDestroyFilterReq % ('uuid1', 'uuid2')) : vmwareDestroyFilterResp,
 (vmwareDestroyFilterReq % ('uuid3', 'uuid4')) : vmwareDestroyFilterResp,
 (vmwareDestroyFilterReq % ('uuid5', 'uuid6')) : vmwareDestroyFilterResp,
 (vmwareDestroyFilterReq % ('uuid7', 'uuid8')) : vmwareDestroyFilterResp,
 (vmwareDestroyFilterReq % ('uuidA', 'uuidB')) : vmwareDestroyFilterResp,
 (vmwareDestroyFilterReq % ('uuidA1', 'uuidA1')) : vmwareDestroyFilterResp,
 (vmwareDestroyFilterReq % ('uuid48', 'uuid48')) : vmwareDestroyFilterResp,

 vmwareQueryConfigTargetReq1 : vmwareQueryConfigTargetResp1,
 vmwareRetrievePropertiesReq1 : vmwareRetrievePropertiesResp1,
 vmwareRetrievePropertiesReq35 : vmwareRetrievePropertiesResp1,
 vmwareRetrievePropertiesEnvBrowserReq : vmwareRetrievePropertiesEnvBrowserResp,

 vmwareRetrievePropertiesDatastoreSummaryReq : vmwareRetrievePropertiesDatastoreSummaryResponse,
 vmwareFindByInventoryPathReq % 'template-some-file-6-1-x86' :
     vmwareFindByInventoryPathResp % 'vm-4732',
 vmwareFindByInventoryPathReq % 'template-some-file-6-1-x86-1' :
     vmwareFindByInventoryPathRespFail,
 vmwareFindByInventoryPathReq % 'instance-foo' :
     vmwareFindByInventoryPathRespFail,
 vmwareRegisterVMreq : vmwareRegisterVMresp,
 vmwareRegisterVMreq2 : vmwareRegisterVMresp,
 vmwareRetrievePropertiesHostReq : vmwareRetrievePropertiesHostResp,
 vmwareRetrievePropertiesHostReq35 : vmwareRetrievePropertiesHostResp,
 vmwareQueryConfigOptionReq : vmwareQueryConfigOptionResp,
 (vmwareRetrievePropertiesVMReq % vmwarePropVMPathSet1) :
    (vmwareRetrievePropertiesVMResp % (vmwarePropRespSet1Len,
        vmwarePropRespSet1)),
 (vmwareRetrievePropertiesVMReq % vmwarePropVMPathSet2) :
    (vmwareRetrievePropertiesVMResp % (vmwarePropRespSet2Len,
        vmwarePropRespSet2)),
 (vmwareRetrievePropertiesVMReq35 % vmwarePropVMPathSet1) :
    (vmwareRetrievePropertiesVMResp % (vmwarePropRespSet1Len,
        vmwarePropRespSet1)),
 (vmwareRetrievePropertiesVMReq35 % vmwarePropVMPathSet2) :
    (vmwareRetrievePropertiesVMResp % (vmwarePropRespSet2Len,
        vmwarePropRespSet2)),
 vmwareRetrievePropertiesVMReq2 : vmwareRetrievePropertiesVMResp2,
 vmwareRetrievePropertiesVMReq22 : vmwareRetrievePropertiesVMResp22,
 vmwareRetrievePropertiesVMReq35_2 : vmwareRetrievePropertiesVMResp2,
 vmwareRetrievePropertiesVMReq35_22 : vmwareRetrievePropertiesVMResp22,
 vmwareRetrievePropertiesVMReq2_hwdev : vmwareRetrievePropertiesVMResp2_hwdev,
 vmwareRetrievePropertiesVMReq2_hwdev2 : vmwareRetrievePropertiesVMResp2_hwdev,
 vmwareRetrievePropertiesVMReq35_hwdev : vmwareRetrievePropertiesVMResp2,
 vmwareRetrievePropertiesVMReq35_hwdev2 : vmwareRetrievePropertiesVMResp2,
 (vmwarePowerOnVMTaskReqTempl % 'vm-4739') :
     vmwarePowerOnVMTaskResp % (436, 'task-51'),
 (vmwarePowerOnVMTaskReqTempl2 % 'vm-1201') :
     vmwarePowerOnVMTaskResp % (436, 'task-51'),
 (vmwarePowerOnVMTaskReqTempl2 % 'vm-987') :
     vmwarePowerOnVMTaskResp % (436, 'task-51'),
 })


DUMMY_CERT = '-----BEGIN CERTIFICATE-----\n-----END CERTIFICATE-----\n'
DUMMY_KEY = '-----BEGIN PRIVATE KEY-----\n-----END PRIVATE KEY-----\n'

x509_cert = """\
-----BEGIN CERTIFICATE-----
MIICizCCAXOgAwIBAgIBATANBgkqhkiG9w0BAQUFADAAMB4XDTA5MDYwNDE0NDk1
MloXDTA5MDYxMTE0NDk1MlowADCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoC
ggEBAJ1IZaAvkz7wMT41AbdG0IyHLTVsYQ+TmZzf/QO5I0x9bEX/L3gnalR1487M
grVozAfjKi2DiNG0mSgoflFBbkUmT4Tfr+iaX99MgBX7LqBcGnsj5HwQHgetdhaS
6yTh5k72hnERZ11g/vmZW0RRNd6bAEUG3Ls8obe91YMYxcoupSURILKxxTSl3bQY
OThn1WWud5ac+IiJyxpX3OmYViVJBNbYXuxWpxVpfwtRxs2GRG2gIcV4pN2eEszy
UHiqSNa9hTinc+irPErAyC0bopw59YkHmz/akU3if/I12xiK5LqfcU/R//pQ059a
5XOQmJ2ElCSGA6wL9X69V/FywhMCAwEAAaMQMA4wDAYDVR0TAQH/BAIwADANBgkq
hkiG9w0BAQUFAAOCAQEAHXi47wYthgCRmbgIheqCIQNGyWSCFbbZn9Az4NkaAlIn
bu/LrWx1xb3ekz4iBXyEbBQ6sr4ersA3JOfaJ35I39L5myxG7n4P5Abk9YNS5ZFL
FzX1QwkX4f6/J+OcysXAn3HiHdNv09QAr0JPCfFPOtrW8lDlu9KnZdt1LCiNEl2z
fCXKzJKu+F0QSq1IVCLRBGd2kLmeQwNZwPJPeYetyK0T1xuve9PMBmhspl9orCqg
HV4PwrVMYsEGVLrCuwJJknDY/1daJW/z81DI5tdyYFW9FntRy9UnB785S3vUkDso
hNwHzg9ZFyHDDWfqYAMrpZ3WKchD1Se6TyGZxan/sA==
-----END CERTIFICATE-----"""
