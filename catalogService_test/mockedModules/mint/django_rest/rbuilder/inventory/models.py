class System(object):
    def __init__(self, **kwargs):
        self.__dict__ = kwargs
        self.pk = None
