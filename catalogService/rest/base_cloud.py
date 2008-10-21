from restlib import controller

class BaseCloudController(controller.RestController):
    def __init__(self, parent, path, driver, cfg):
        self.cfg = cfg
        self.driver = driver
        controller.RestController.__init__(self, parent, path, [driver, cfg])
