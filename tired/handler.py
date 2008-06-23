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

        if self.path == '/crossdomain.xml':
            return self.serveCrossDomainFile()
        if self.path == '/%s/clouds/ec2/images' % self.server.toplevel:
            return self.enumerateImages()
        if self.path == '/%s/clouds/ec2/instances' % self.server.toplevel:
            return self.enumerateInstances()
        if self.path == '/%s/clouds/ec2/instanceTypes' % self.server.toplevel:
            return self.enumerateInstanceTypes()


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
        if 'Host' not in self.headers:
            # Missing Host: header
            self.send_error(400)
            return

        self.host = self.headers['Host']
        self.port = self.server.server_port

    def _auth(self):
        pass

    def enumerateImages(self):
        import images
        import driver_ec2

        awsPublicKey = '16CVNRTTWQG9MZ517782'
        awsPrivateKey = 'B/kKJ5K+jcr3/Sr2DSMRx6dMXzqdaEv+4yFwOUj/'

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        hostport = self.host
        if self.port != 80 and ':' not in hostport:
            hostport = "%s:%s" % (self.host, self.port)
        prefix = "http://%s/%s/clouds/ec2/images/" % (hostport,
                self.server.toplevel)
        imgList = drv.getAllImages(prefix = prefix)

        node = driver_ec2.Images()
        node.extend(imgList)
        hndlr = images.Handler()
        data = hndlr.toXml(node)

        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def enumerateInstances(self):
        import images
        import driver_ec2

        awsPublicKey = '16CVNRTTWQG9MZ517782'
        awsPrivateKey = 'B/kKJ5K+jcr3/Sr2DSMRx6dMXzqdaEv+4yFwOUj/'

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        hostport = self.host
        if self.port != 80 and ':' not in hostport:
            hostport = "%s:%s" % (self.host, self.port)
        prefix = "http://%s/%s/clouds/ec2/instances/" % (hostport,
                self.server.toplevel)
        instList = drv.getAllInstances(prefix = prefix)

        node = driver_ec2.Instances()
        node.extend(instList)
        hndlr = images.Handler()
        data = hndlr.toXml(node)

        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def enumerateInstanceTypes(self):
        import images
        import driver_ec2

        awsPublicKey = '16CVNRTTWQG9MZ517782'
        awsPrivateKey = 'B/kKJ5K+jcr3/Sr2DSMRx6dMXzqdaEv+4yFwOUj/'

        cfg = driver_ec2.Config(awsPublicKey, awsPrivateKey)

        drv = driver_ec2.Driver(cfg)

        hostport = self.host
        if self.port != 80 and ':' not in hostport:
            hostport = "%s:%s" % (self.host, self.port)
        prefix = "http://%s/%s/clouds/ec2/instanceTypes/" % (hostport,
                self.server.toplevel)
        node = drv.getAllInstanceTypes(prefix=prefix)

        hndlr = images.Handler()
        data = hndlr.toXml(node)

        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)


    def serveCrossDomainFile(self):
        path = "crossdomain.xml"
        f = open(path)
        f.seek(2)
        fileSize = f.tell()
        f.seek(0)

        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", fileSize)
        self.end_headers()
        while 1:
            buf = f.read(16384)
            if not buf:
                break
            self.wfile.write(buf)

class HTTPServer(BaseHTTPServer.HTTPServer):
    toplevel = 'TOPLEVEL'

if __name__ == '__main__':
    h = HTTPServer(("", 1234), BaseRESTHandler)
    h.serve_forever()
