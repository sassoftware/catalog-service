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


class S3Wrapper(object):
    amazonEC2UserId = [ 'za-team-replacement', ]
    class UploadCallback(object):
        def __init__(self, callback, fileName, fileIdx, fileTotal,
                sizeCurrent, sizeTotal):
            self.fileName = fileName
            self.fileIdx = fileIdx
            self.fileTotal = fileTotal
            self.sizeCurrent = sizeCurrent
            self.sizeTotal = sizeTotal
            self._callback = callback

        def callback(self, currentBytes, totalBytes):
            self._callback(self.fileName, self.fileIdx, self.fileTotal,
                currentBytes, totalBytes,
                self.sizeCurrent + currentBytes, self.sizeTotal)

    @classmethod
    def createBucketBackend(cls, conn, bucketName, policy=None):
        # boto 2.0 enforces that bucket names don't have upper case
        bucketName = bucketName.lower()
        from boto.exception import S3CreateError
        try:
            bucket = conn.create_bucket(bucketName, policy=policy)
        except S3CreateError:
            bucket = conn.get_bucket(bucketName)
        return bucket

    @classmethod
    def uploadBundleBackend(cls, bundleItemGen, fileCount, totalSize,
            bucket, permittedUsers=None, callback=None, policy="private"):
        current = 0
        for i, (biName, biSize, biFileObj) in enumerate(bundleItemGen):
            key = bucket.new_key(biName)
            if callback:
                cb = cls.UploadCallback(callback, biName,
                    i + 1, fileCount, current, totalSize).callback
            else:
                cb = None
            current += biSize
            key.set_contents_from_file(biFileObj, cb=cb, policy=policy)
            if permittedUsers:
            # Grant additional permissions
                key = bucket.get_key(biName)
                acl = key.get_acl()
                for user in permittedUsers:
                    acl.acl.add_user_grant('READ', user)
                key.set_acl(acl)
