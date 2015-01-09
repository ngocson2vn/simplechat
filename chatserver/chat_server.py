# python modules
import os
import sys
import time
import socket

from chatserver.medusa import text_socket
from chatserver.medusa import asyncore_25 as asyncore
from chatserver.medusa import asynchat_25 as asynchat
from chatserver.medusa.counter import counter

VERSION_STRING = '1.0'


# ===========================================================================
#                            Chat Channel Object
# ===========================================================================

class chat_channel(asynchat.async_chat):

    # use a larger default output buffer
    ac_out_buffer_size = 1<<16

    def __init__(self, server, conn, addr, logger_object):
        asynchat.async_chat.__init__(self, conn)
        self.server = server
        self.addr = addr
        self.logger = logger_object
        self.in_buffer = ''
        self.creation_time = int(time.time())
        self.set_terminator(None)
        self.collect_incoming_data("I'm online now!!!\n")

    def repr(self):
        ar = asynchat.async_chat.__repr__(self)[1:-1]
        return '<%s>' %(ar)

    # this information needs to get into the request object,
    def send(self, data):
        result = asynchat.async_chat.send(self, data)
        return result

    def recv(self, buffer_size):
        try:
            result = asynchat.async_chat.recv(self, buffer_size)
            return result
        except MemoryError:
            sys.exit("Out of Memory!")

    def handle_error(self):
        t, v = sys.exc_info()[:2]
        if t is SystemExit:
            raise t(v)
        else:
            asynchat.async_chat.handle_error(self)

    def push_data(self, data):
        self.ac_out_buffer = self.ac_out_buffer + data

    def writable(self):
        if len(self.ac_out_buffer) > 0:
            return True
        else:
            return False

    # --------------------------------------------------
    # async_chat methods
    # --------------------------------------------------

    def collect_incoming_data(self, data):
        recv_msg = '[%s:%d]: ' % self.addr + data
        self.add_data(recv_msg)
        # self.logger.log(recv_msg)


# ===========================================================================
#                            Chat Server Object
# ===========================================================================

class chat_server(asyncore.dispatcher):

    SERVER_IDENT = 'Chat Server (V%s)' % VERSION_STRING

    def __init__(self, ip, port, resolver=None, logger_object=None):
        self.ip = ip
        self.port = port
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)

        self.handlers = []

        self.set_reuse_addr()
        self.bind((ip, port))

        # lower this to 5 if your OS complains
        self.listen(1024)

        host, port = self.socket.getsockname()
        if not ip:
            self.log_info('Computing default hostname', 'warning')
            ip = socket.gethostbyname(socket.gethostname())
        try:
            self.server_name = socket.gethostbyaddr(ip)[0]
        except socket.error:
            self.log_info('Cannot do reverse lookup', 'warning')
            self.server_name = ip       # use the IP address as the "hostname"

        self.server_port = port
        self.total_clients = counter()

        self.log_info(
                'Chat Server (V%s) started at %s'
                '\n\tHostname: %s'
                '\n\tPort:%d'
                '\n' %(
                        VERSION_STRING,
                        time.ctime(time.time()),
                        self.server_name,
                        port,
                        )
                )

    def repr(self):
        ar = asyncore.dispatcher.__repr__(self)[1:-1]
        return '<%s>' %(ar)

    def writable(self):
        return 0

    def handle_read(self):
        pass

    def readable(self):
        return self.accepting

    def handle_connect(self):
        pass

    def handle_accept(self):
        self.total_clients.increment()
        try:
            conn, addr = self.accept()
            self.logger.log("handle_accept addr = %s" % str(addr))
            self.logger.log("handle_accept peername = %s" % str(conn.getpeername()))
        except socket.error:
            self.log_info('warning: server accept() threw an exception', 'warning')
            return
        except TypeError:
            self.log_info('warning: server accept() threw EWOULDBLOCK', 'warning')
            return

        chat_channel(self, conn, addr, self.logger)

    def prebind(self, sock, logger_object):
        self.logger = logger_object

        asyncore.dispatcher.__init__(self)
        self.set_socket(sock)

        self.handlers = []

        sock.setblocking(0)
        self.set_reuse_addr()

    def postbind(self):
        self.listen(1024)

        self.total_clients = counter()

        self.log_info(
                'Chat Server (V%s) started at %s'
                '\n\tHostname: %s'
                '\n\tPort:%s'
                '\n' %(
                        VERSION_STRING,
                        time.ctime(time.time()),
                        self.server_name,
                        self.port,
                        )
                )

    def log_info(self, message, type='info'):
        ip = ''
        if getattr(self, 'ip', None) is not None:
            ip = self.ip
        self.logger.log("%s %s" % (ip, message))

class af_inet_server(chat_server):
    """ AF_INET version of  Chat Server """

    def __init__(self, ip, port, logger_object):
        self.ip = ip
        self.port = port
        sock = text_socket.text_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.prebind(sock, logger_object)
        self.bind((ip, port))

        if not ip:
            self.log_info('Computing default hostname', 'warning')
            hostname = socket.gethostname()
            try:
                ip = socket.gethostbyname(hostname)
            except socket.error:
                raise ValueError('Could not determine IP address for hostname %s' % hostname)

        try:
            self.server_name = socket.gethostbyaddr(ip)[0]
        except socket.error:
            self.log_info('Cannot do reverse lookup', 'warning')
            self.server_name = ip       # use the IP address as the "hostname"

        self.postbind()

def make_server(helpers):
    servers = []
    class LogWrapper:
        def log(self, msg):
            if msg.endswith('\n'):
                msg = msg[:-1]
            helpers.logger.log(msg)
    wrapper = LogWrapper()

    config = helpers.server_config
    host, port = config['host'], config['port']
    hs = af_inet_server(host, port, logger_object=wrapper)
    sys.stdout.write("Chat Server is listening on port %d\n" % port)

    servers.append((config, hs))

    return servers