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

from catalogService.rest.models import images

class ImagesTest(testsuite.TestCase):
    def testFreezeThaw(self):
        hndlr = images.Handler()

        instId = "ec2-adfadf"
        instLongName = "ec2/name"
        instShortName = instLongName.split('/')[-1]

        image = images.BaseImage(id = instId)

        self.failUnlessEqual(image.getId(), instId)
        self.failUnlessEqual(image.getLongName(), None)
        self.failUnlessEqual(image.getShortName(), None)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.failUnlessEqual(ret,
            """<?xml version='1.0' encoding='UTF-8'?>\n<image id="ec2-adfadf" xmlNodeHash="295449fb28b0843c498e30f655cdc1b2a48e26cf"/>""")
        x = hndlr.parseString(ret)
        self.failUnlessEqual(x.getId(), instId)
        self.failUnlessEqual(x.getLongName(), None)
        self.failUnlessEqual(x.getShortName(), None)

        image = images.BaseImage(longName = instLongName)
        self.failUnlessEqual(image.getId(), None)
        self.failUnlessEqual(image.getLongName(), instLongName)
        self.failUnlessEqual(image.getShortName(), instShortName)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image xmlNodeHash="71468fdb7f1d1350cb10f60c879145dc2c9288f0"><longName>ec2/name</longName><shortName>name</shortName></image>""")
        x = hndlr.parseString(ret)
        self.failUnlessEqual(x.getId(), None)
        self.failUnlessEqual(x.getLongName(), instLongName)
        self.failUnlessEqual(x.getShortName(), instShortName)

        image = images.BaseImage(id = instId, longName = instLongName)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image id="ec2-adfadf" xmlNodeHash="f7a727dd8f7670f86336961efa5dbea453506764"><longName>ec2/name</longName><shortName>name</shortName></image>""")

        x = hndlr.parseString(ret)
        self.failUnlessEqual(x.getId(), instId)
        self.failUnlessEqual(x.getLongName(), instLongName)
        self.failUnlessEqual(x.getShortName(), instShortName)

        image = images.BaseImage(id = instId, isPublic = False)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image id="ec2-adfadf" xmlNodeHash="4112ded7a1d493c4f3d1fcc0dd8ec39ee938dfb4"><isPublic>false</isPublic></image>""")

        x = hndlr.parseString(ret)
        self.failUnlessEqual(x.getId(), instId)
        self.failUnlessEqual(x.getIsPublic(), False)

        image = images.BaseImage(id = instId, imageId = instLongName)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image id="ec2-adfadf" xmlNodeHash="7d26c204f8b90ac956ea8c97ce43c2808682d3f6"><imageId>ec2/name</imageId></image>""")

        x = hndlr.parseString(ret)
        self.failUnlessEqual(x.getId(), instId)
        self.failUnlessEqual(x.getImageId(), instLongName)

        image = images.BaseImage(id = instId, ownerId = instLongName)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image id="ec2-adfadf" xmlNodeHash="8fe7e337659748428c3a9375667663a65fdfd43b"><ownerId>ec2/name</ownerId></image>""")

        x = hndlr.parseString(ret)
        self.failUnlessEqual(x.getId(), instId)
        self.failUnlessEqual(x.getOwnerId(), instLongName)

    def testContradictingNames(self):
        # shortName is treated as a view on longName and not as a separate
        # entity. prove that shortName always follows longName
        hndlr = images.Handler()

        instLongName = "ec2/name"
        instShortName = instLongName.split('/')[-1]
        bogusShortName = 'foo'

        # if shortName is supplied, it will be corrected to follow longName
        image = images.BaseImage(longName = instLongName,
                shortName = bogusShortName)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image xmlNodeHash="71468fdb7f1d1350cb10f60c879145dc2c9288f0"><longName>ec2/name</longName><shortName>name</shortName></image>""")

        # if shortName is supplied and longName isn't, shortName will be deleted
        image = images.BaseImage(shortName = bogusShortName)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image xmlNodeHash="e8b0622a7ad86f91edb907989bae2ff5903de6dd"/>""")

        # if shortName isn't supplied, and longName is, shortName will follow
        image = images.BaseImage(longName = instLongName)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image xmlNodeHash="71468fdb7f1d1350cb10f60c879145dc2c9288f0"><longName>ec2/name</longName><shortName>name</shortName></image>""")

    def testFreezeThawCollection(self):
        hndlr = images.Handler()

        instId = "ec2-adfadf"
        instLongName = "ec2/name"
        instShortName = instLongName.split('/')[-1]

        image = images.BaseImage(id = instId, longName = instLongName)

        coll = images.BaseImages()
        coll.append(image)
        ret = hndlr.toXml(coll, prettyPrint = False)
        self.failUnlessEqual(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<images><image id="ec2-adfadf" xmlNodeHash="f7a727dd8f7670f86336961efa5dbea453506764"><longName>ec2/name</longName><shortName>name</shortName></image></images>""")

        imgs = hndlr.parseString(ret)
        self.assertEquals(imgs[0].longName.getText(), instLongName)
        self.assertEquals(imgs[0].shortName.getText(), instShortName)
        self.assertEquals(imgs[0].id, instId)

        # now text replace the shortName tag to prove it gets ignored.
        # it's a view on longName, not a separate value
        newData = ret.replace('<shortName>name</shortName>',
                '<shortName>sir_robin</shortName>')

        imgs = hndlr.parseString(newData)
        self.assertEquals(imgs[0].shortName.getText(), 'sir_robin')

    def testProductDescription(self):
        hndlr = images.Handler()
        desc = 'fooooo'

        image = images.BaseImage(productDescription = desc)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.assertEquals(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image xmlNodeHash="7a7de34fcecfba8ba60ad4ac2c4633949d8e2092"><productDescription>fooooo</productDescription></image>""")

        newImage =  hndlr.parseString(ret)
        self.assertEquals(newImage.productDescription.getText(), desc)

    def testBuildDescription(self):
        hndlr = images.Handler()
        desc = 'fooooo'

        image = images.BaseImage(buildDescription = desc)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.assertEquals(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image xmlNodeHash="bcbf7c7ddfc913488d348c5351e48177a676c384"><buildDescription>fooooo</buildDescription></image>""")

        newImage =  hndlr.parseString(ret)
        self.assertEquals(newImage.buildDescription.getText(), desc)

    def testProductName(self):
        hndlr = images.Handler()
        prodName = 'testname'

        image = images.BaseImage(productName = prodName)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.assertEquals(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image xmlNodeHash="61284b86b1ed8a67acc074a94877fc579a54b451"><productName>testname</productName></image>""")

        newImage =  hndlr.parseString(ret)
        self.assertEquals(newImage.productName.getText(), prodName)

    def testRole(self):
        hndlr = images.Handler()
        roleName = 'owner'

        image = images.BaseImage(role = roleName)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.assertEquals(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image xmlNodeHash="4dcf068ea855eff9649361166394c37d289558a6"><role>owner</role></image>""")

        newImage =  hndlr.parseString(ret)
        self.assertEquals(newImage.role.getText(), roleName)

    def testPublisher(self):
        hndlr = images.Handler()
        publisherName = 'bob'

        image = images.BaseImage(publisher = publisherName)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.assertEquals(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image xmlNodeHash="4aca82986c5f83d1a6f9d785479082b999b8c844"><publisher>bob</publisher></image>""")

        newImage =  hndlr.parseString(ret)
        self.assertEquals(newImage.publisher.getText(), publisherName)

    def testAwsAccountNumber(self):
        hndlr = images.Handler()
        awsAcct = 'somerandomacct'

        image = images.BaseImage(awsAccountNumber = awsAcct)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.assertEquals(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image xmlNodeHash="60ffbf426e747dcbd47f2c49835cc67bf04de504"><awsAccountNumber>somerandomacct</awsAccountNumber></image>""")

        newImage =  hndlr.parseString(ret)
        self.assertEquals(newImage.awsAccountNumber.getText(), awsAcct)

    def testBuildName(self):
        hndlr = images.Handler()
        bldName = 'test build'

        image = images.BaseImage(buildName = bldName)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.assertEquals(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image xmlNodeHash="f86ebbe0ad75b425a132cd7820573c06411c984e"><buildName>test build</buildName></image>""")

        newImage =  hndlr.parseString(ret)
        self.assertEquals(newImage.buildName.getText(), bldName)

    def testIsPrivate_rBuilder(self):
        hndlr = images.Handler()
        private = True

        image = images.BaseImage(isPrivate_rBuilder = private)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.assertEquals(ret, """<?xml version='1.0' encoding='UTF-8'?>\n<image xmlNodeHash="31bcb37a0b7e503677f7443481b823c4e540d15a"><isPrivate_rBuilder>true</isPrivate_rBuilder></image>""")

        newImage =  hndlr.parseString(ret)
        self.assertEquals(newImage.isPrivate_rBuilder.getText(), 'true')
        self.assertEquals(newImage.getIsPrivate_rBuilder(), True)

    def testProductCodes(self):
        hndlr = images.Handler()
        productCodes = [("a", "aa"),
                        ("b", "bb"),
                        ("c", "cc")]
        image = images.BaseImage(productCode = productCodes)
        ret = hndlr.toXml(image, prettyPrint = False)
        self.assertEquals(ret, """<?xml version=\'1.0\' encoding=\'UTF-8\'?>\n<image xmlNodeHash="9cc1b06978e42d8cdb83397ce89339357ed7b49f"><productCode><code>a</code><url>aa</url></productCode><productCode><code>b</code><url>bb</url></productCode><productCode><code>c</code><url>cc</url></productCode></image>""")

        newImage = hndlr.parseString(ret)
        self.failUnless(isinstance(newImage.productCode,
                                   images.xmlNode.MultiItemList),
                                   newImage.productCode)
        self.assertEquals(
            [ (x.code.getText(), x.url.getText())
                for x in newImage.getProductCode()],
            productCodes)

if __name__ == "__main__":
    testsuite.main()
