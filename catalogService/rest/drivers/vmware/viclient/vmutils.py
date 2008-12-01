#!/usr/bin/python2.4
# -*- python -*-
#
# Copyright (c) 2008 rPath, Inc.  All Rights Reserved.
#

import glob, os
import httplib
import urllib
import socket
import pprint

from conary.lib import util

BUFSIZE=256 * 1024

class HTTPConnection(httplib.HTTPConnection):
    def send(self, buf):
        if self.debuglevel > 0:
            print 'send: ',
            pprint.pprint(buf)
        self.sock.sendall(buf)

class HTTPSConnection(httplib.HTTPSConnection):
    def send(self, buf):
        if self.debuglevel > 0:
            print 'send: ',
            pprint.pprint(buf)
        self.sock.sendall(buf)

def _putFile(inPath, outUrl, session=None):
    size = os.stat(inPath).st_size
    inFile = open(inPath)
    protocol, uri = urllib.splittype(outUrl)
    assert(protocol in ('http', 'https'))
    host, selector = urllib.splithost(uri)
    host, port = urllib.splitport(host)

    if protocol == 'http':
        r = HTTPConnection(host, port)
    else:
        r = HTTPSConnection(host, port)

    #r.set_debuglevel(1)
    r.connect()
    r.putrequest('PUT', selector)
    r.putheader('Content-type', 'application/octet-stream')
    r.putheader('Content-length', str(size))
    if session:
        r.putheader('Cookie', 'vmware_soap_session=%s; $Path=/' % session)
    try:
        r.endheaders()
        util.copyfileobj(inFile, r, bufSize=BUFSIZE, sizeLimit=size)
    except socket.error, e:
        response = None
        try:
            response = r.getresponse()
            r.close()
        except Exception, e:
            pass
        if response:
            raise RuntimeError('PUT failed: %d - %s' %(response.status,
                                                       response.reason))
        else:
            raise RuntimeError('PUT failed')
    resp = r.getresponse()
    r.close()

def uploadVMFiles(v, path, vmName=None, dataCenter=None, dataStore=None):
    vmx = glob.glob(os.path.join(path, '*.vmx'))
    if not vmx:
        raise RuntimeError('no .vmx file found in %s' %path)
    if len(vmx) != 1:
        raise RuntimeError('more than one .vmx file found in %s' %path)
    f = open(vmx[0])

    # steal cookies from the binding's cookiejar
    session = v.getSessionUUID()
    urlBase = v.getUrlBase()
    urlPattern = '%sfolder/%s/%%s?dcPath=%s&dsName=%s' %(
        urlBase, urllib.quote(vmName), urllib.quote(dataCenter),
        urllib.quote(dataStore))

    if not dataStore:
        raise RuntimeError('dataStore currently required')
    if not dataCenter:
        raise RuntimeError('dataCenter currently required')

    for fn in os.listdir(path):
        fn = urllib.quote(fn)
        _putFile(os.path.join(path, fn), urlPattern % fn, session)
    vmx = '[%s]/%s/%s' %(dataStore, vmName, os.path.basename(vmx))
    return vmx
