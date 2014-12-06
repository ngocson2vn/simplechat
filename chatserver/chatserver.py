# python modules
import os
import sys
import time
import socket

# medusa modules
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

    def __repr__(self):
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
            # --- Save a Trip to Your Service Provider ---
            # It's possible for a process to eat up all the memory of
            # the machine, and put it in an extremely wedged state,
            # where medusa keeps running and can't be shut down.  This
            # is where MemoryError tends to get thrown, though of
            # course it could get thrown elsewhere.
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

    SERVER_IDENT = 'Chat Server(V%s)' % VERSION_STRING

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
        self.exceptions = counter()
        self.bytes_out = counter()
        self.bytes_in  = counter()

        self.log_info(
                'Medusa(V%s) started at %s'
                '\n\tHostname: %s'
                '\n\tPort:%d'
                '\n' %(
                        VERSION_STRING,
                        time.ctime(time.time()),
                        self.server_name,
                        port,
                        )
                )

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
        except socket.error:
            # linux: on rare occasions we get a bogus socket back from
            # accept.  socketmodule.c:makesockaddr complains that the
            # address family is unknown.  We don't want the whole server
            # to shut down because of this.
            self.log_info('warning: server accept() threw an exception', 'warning')
            return
        except TypeError:
            # unpack non-sequence.  this can happen when a read event
            # fires on a listening socket, but when we call accept()
            # we get EWOULDBLOCK, so dispatcher.accept() returns None.
            # Seen on FreeBSD3.
            self.log_info('warning: server accept() threw EWOULDBLOCK', 'warning')
            return

        chat_channel(self, conn, addr, self.logger)

    def install_handler(self, handler, back=0):
        if back:
            self.handlers.append(handler)
        else:
            self.handlers.insert(0, handler)

    def remove_handler(self, handler):
        self.handlers.remove(handler)

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
        self.total_requests = counter()
        self.exceptions = counter()
        self.bytes_out = counter()
        self.bytes_in  = counter()

        self.log_info(
                'Medusa(V%s) started at %s'
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
    """ AF_INET version of  Chat server """

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
                raise ValueError(
                    'Could not determine IP address for hostname %s, '
                    'please try setting an explicit IP address in the "port" '
                    'setting of your [inet_http_server] section.  For example, '
                    'instead of "port = 9001", try "port = 127.0.0.1:9001."'
                    % hostname)
        try:
            self.server_name = socket.gethostbyaddr(ip)[0]
        except socket.error:
            self.log_info('Cannot do reverse lookup', 'warning')
            self.server_name = ip       # use the IP address as the "hostname"

        self.postbind()

def make_server(helpers, chatserverd):
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
    sys.stdout.write("Chat server is listening on port %d\n" % port)

    servers.append((config, hs))

    return servers