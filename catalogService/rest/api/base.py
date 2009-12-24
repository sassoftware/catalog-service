from restlib import controller

class BaseGenericController(controller.RestController):
    pass

class BaseController(BaseGenericController):
    def __init__(self, parent, path, cfg):
        self.cfg = cfg
        BaseGenericController.__init__(self, parent, path, [ cfg ])

class BaseCloudController(BaseGenericController):
    def __init__(self, parent, path, driver, cfg):
        self.cfg = cfg
        self.driver = driver
        BaseGenericController.__init__(self, parent, path, [driver, cfg])
