from restlib import handler

class BaseHandler(handler.RestHandler):
    def __init__(self, parent, path, cfg, mintClient):
        self.mintClient = mintClient
        self.cfg = cfg
        handler.RestHandler.__init__(self, parent, path, [cfg, mintClient])


class BaseModelHandler(handler.RestModelHandler):
    def __init__(self, parent, path, driver, cfg, mintClient):
        self.driver = driver
        self.cfg = cfg
        self.mintClient = mintClient
        handler.RestModelHandler.__init__(self, parent, path, 
                                          [driver, cfg, mintClient])
