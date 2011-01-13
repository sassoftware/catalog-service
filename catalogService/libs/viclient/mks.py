class Unused:
    def acquireMksTicket(self, vm):
        req = AcquireMksTicketRequestMsg()
        _this = req.new__this(vm)
        _this.set_attribute_type('VirtualMachine')
        req.set_element__this(_this)
        ret = self._service.AcquireMksTicket(req)
        ticket = ret.get_element_returnval()
        d = dict(cfgFile=ticket.get_element_cfgFile(),
                 port=ticket.get_element_port(),
                 ticket=ticket.get_element_ticket())
        return d

    def mksConnect(self, d):
        import socket
        import M2Crypto

        s = socket.socket()
        s.connect((d['host'], d['port']))
        msg = s.recv(1000)
        print msg
        while '\n' not in msg:
            msg = s.recv(1000)
            print msg
        ctx = M2Crypto.SSL.Context('sslv3')
        ssl = M2Crypto.SSL.Connection(ctx, sock=s)
        ssl.setup_ssl()
        ssl.set_connect_state()
        ssl.connect_ssl()
        ssl.send('USER %(ticket)s\r\n' %d)
        msg = ssl.recv(200)
        print msg
        ssl.send('PASS %(ticket)s\r\n' %d)
        msg = ssl.recv(200)
        print msg
        ssl.send('CONNECT %(cfgFile)s mks\r\n' %d)
        msg = ssl.recv(200)
        print msg
        if msg.startswith('630'):
            ticket = msg.split(' ')[2]
            ticket, host, port = ticket.split(',')
            d.update(dict(ticket=ticket,
                          host=host,
                          port=int(port)))
            self.mksConnect(d)
        else:
            # reset SSL connection
            ssl2 = M2Crypto.SSL.Connection(ctx, sock=s)
            ssl2.setup_ssl()
            ssl2.set_connect_state()
            ssl2.connect_ssl()
            # listen on a local socket
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('', 5901))
            s.listen(1)
            conn, addr = s.accept()

            rdlist, _, _ = select.select([conn], [], [], 1)
            if rdlist:
                msg = conn.recv(100)
                print msg
                if msg.startswith('<policy-file-request/>'):
                    conn.send("""<?xml version="1.0"?>
    <!DOCTYPE cross-domain-policy SYSTEM 
    "http://www.macromedia.com/xml/dtds/cross-domain-policy.dtd">
    <cross-domain-policy>
      <allow-access-from domain="*" to-ports="5190-6000" />
    </cross-domain-policy>""")

            conn.send('RFB 003.007\n')
            msg = conn.recv(100)
            vers = msg.strip().rsplit('.', 1)[1]
            if vers == '003':
                conn.send(struct.pack('>L', 1))
            else:
                # auth types supported: 1 (None)
                conn.send(chr(01)+chr(01))
                # client selects None
                conn.recv(1)
            # client init
            #  shared desktop flag
            conn.recv(1)
            #ssl2.setblocking(False)
            while 1:
                if ssl2.pending():
                    # if there is pending SSL data, go ahead and
                    # process it, don't bother with select (as the
                    # underlying socket will not be in the rdset)
                    rdlist = [ ssl2 ]
                else:
                    # otherwise use select to determine if there
                    # is data to proxy
                    rdlist = [ ssl2, conn ]
                    rdlist, _, _ = select.select(rdlist, [], [], 1)
                if rdlist:
                    if ssl2 in rdlist:
                        # server -> client
                        data = ssl2.recv(1500)
                        if data:
                            print 's->c', len(data)
                            conn.send(data)
                    if conn in rdlist:
                        # client -> server
                        data = conn.recv(1500)
                        if data:
                            print 'c->s', len(data)
                            ssl2.send(data)
                            print repr(data)

    def getProperties(self, containerType='Folder'):
        req = RetrievePropertiesRequestMsg()
        propFilterSpec = req.new_specSet()

        # access the PropertyCollector object
        req.set_element__this(self._propCol)

        # build a traversal spec
        traversalSpec = ns0.TraversalSpec_Def('').pyclass()
        traversalSpec.set_element_type(containerType)
        traversalSpec.set_element_name('traverseChild')
        traversalSpec.set_element_path('childEntity')
        traversalSpec.set_element_skip(False)
        # add additional selection spec to the traversal spec
        dc2f = ns0.TraversalSpec_Def('').pyclass()
        dc2f.set_element_type('Datacenter')
        dc2f.set_element_path('vmFolder')
        dc2f.set_element_skip(False)
        selectSpec = traversalSpec.new_selectSet()
        selectSpec.set_element_name('traverseChild')
        dc2f.set_element_selectSet([ selectSpec ])
        selectSpec = traversalSpec.new_selectSet()
        selectSpec.set_element_name('traverseChild')
        selectSet = [ selectSpec, dc2f ]
        traversalSpec.set_element_selectSet(selectSet)

        # build the property spec
        propSpec = propFilterSpec.new_propSet()
        propSpec.set_element_all(False)
        propSpec.set_element_pathSet([ 'name' ])
        propSpec.set_element_type('ManagedEntity')
        propSet = [ propSpec ]
        # add the property spec to the property filter spec
        propFilterSpec.set_element_propSet(propSet)

        # build the object spec
        objSpec = propFilterSpec.new_objectSet()
        objSpec.set_element_obj(self._rootFolder)
        objSpec.set_element_skip(False)
        selectSet = [ traversalSpec ]
        objSpec.set_element_selectSet(selectSet)
        objectSet = [ objSpec ]
        # add the object set to the property filter
        propFilterSpec.set_element_objectSet(objectSet)

        specSet = [ propFilterSpec ]
        req.set_element_specSet(specSet)
        resp = self._service.RetrieveProperties(req)
        return resp.get_element_returnval()

    def printProperties(self, objprops):
        if objprops is None:
            print 'Nothing to display'
        else:
            for objprop in objprops:
                obj = objprop.get_element_obj()
                props = objprop.get_element_propSet()
                print 'Type: ' + obj.get_attribute_type()
                print 'Value: ' + obj
                if not props:
                    continue
                for prop in props:
                    name = prop.get_element_name()
                    val = prop.get_element_val()
                    if hasattr(val, '__iter__'):
                        val = ', '.join(val)
                    print '  %s: %s' %(name, val)
