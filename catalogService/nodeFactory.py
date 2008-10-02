#
# Copyright (c) 2008 rPath, Inc.
#

class NodeFactory(object):
    baseUrl = None

    def __init__(self, cloudFactory = None, imageFactory = None,
                 instanceFactory = None):
        self.cloudFactory = cloudFactory
        self.imageFactory = imageFactory
        self.instanceFactory = instanceFactory

    def newCloud(self, *args, **kwargs):
        node = self.cloudFactory(*args, **kwargs)
        node.setId(self.getCloudUrl(node))
        return node

    def newImage(self, *args, **kwargs):
        node = self.imageFactory(*args, **kwargs)
        node.setId(self.getImageUrl(node))
        return node

    def newInstance(self, *args, **kwargs):
        node = self.instanceFactory(*args, **kwargs)
        node.setId(self.getInstanceUrl(node))
        return node

    @classmethod
    def join(cls, *args):
        """Join the arguments into a URL"""
        return '/'.join(args)

    @classmethod
    def getCloudUrl(cls, node):
        return cls.join(cls.baseUrl, 'clouds', node.getCloudType(), node.getCloudName())

    @classmethod
    def getImageUrl(cls, node):
        return cls.join(cls.getCloudUrl(node), 'images', node.getId())

    @classmethod
    def getInstanceUrl(cls, node):
        return cls.join(cls.getCloudUrl(node), 'instances', node.getId())
