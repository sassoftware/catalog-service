from restlib import controller

class BaseController(controller.RestController):
    def __init__(self, parent, path, cfg):
        self.cfg = cfg
        controller.RestController.__init__(self, parent, path, [cfg])
