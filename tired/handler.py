#
# Copyright (c) 2008 rPath, Inc.
#

import BaseHTTPServer

class BaseRESTHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        pass

    def do_GET(self):
        self._validateHeaders()
        self._auth()
        print "Received", self.path

    def do_PUT(self):
        self._validateHeaders()
        self._auth()

    def do_POST(self):
        self._validateHeaders()
        self._auth()

    def do_DELETE(self):
        self._validateHeaders()
        self._auth()

    def _validateHeaders(self):
        if 'host' not in self.headers:
            # Missing Host: header
            self.send_error(400)
            return

    def _auth(self):
        pass

class HTTPServer(BaseHTTPServer.HTTPServer):
    pass

if __name__ == '__main__':
    h = HTTPServer(("", 1234), BaseRESTHandler)
    h.serve_forever()
