import socket
import getopt
import os
import sys
import errno
import signal

from chatserver.medusa import asyncore_25 as asyncore
from chatserver import poller
from chatserver import logger
from chatserver.chatserver import chat_channel

VERSION = '1.0'

class SignalReceiver:
    def __init__(self):
        self._signals_recvd = []

    def receive(self, sig, frame):
        if sig not in self._signals_recvd:
            self._signals_recvd.append(sig)

    def get_signal(self):
        if self._signals_recvd:
            sig = self._signals_recvd.pop(0)
        else:
            sig = None
        return sig

class Helpers:
    stderr = sys.stderr
    stdout = sys.stdout
    exit = sys.exit

    progname = sys.argv[0]

    def __init__(self):
        self.poller = poller.Poller(self)
        self.logger = logger.Logger()
        self.signal_receiver = SignalReceiver()
        self.server_config = {}
        self.server_config['host'] = ''
        self.server_config['port'] = 9001
        self.umask = 22
        self.pidfile = '/tmp/chatserver.pid'

    def usage(self, msg):
        self.stderr.write("Error: %s\n" % str(msg))
        self.stderr.write("Please use %s --port=<port>\n" % self.progname)
        self.exit(2)

    def getopts(self):
        args = sys.argv[1:]
        progname = sys.argv[0]
        self.progname = progname

        options = []
        a = []

        # Call getopt
        try:
            options, a = getopt.getopt(args, 'p', ["port="])
        except getopt.error as exc:
            self.usage(repr(exc))

        is_valid = False
        for opt, val in options:
            if opt == '--port':
                self.server_config['port'] = int(val)
                is_valid = True

        if not is_valid:
            self.usage("invalid options")

    def daemonize(self):
        self.poller.before_daemonize()
        self._daemonize()
        self.poller.after_daemonize()

    def _daemonize(self):
        pid = os.fork()

        if pid != 0:
            # Parent
            sys.stdout.write("Chat server is daemonized\n")
            os._exit(0)

        # Child
        os.close(0)
        self.stdin = sys.stdin = sys.__stdin__ = open("/dev/null")
        os.close(1)
        self.stdout = sys.stdout = sys.__stdout__ = open("/dev/null", "w")
        os.close(2)
        self.stderr = sys.stderr = sys.__stderr__ = open("/dev/null", "w")
        os.setsid()
        os.umask(self.umask)

    def write_pidfile(self):
        pid = os.getpid()
        try:
            with open(self.pidfile, 'w') as f:
                f.write('%s\n' % pid)
        except (IOError, OSError):
            self.logger.log('could not write pidfile %s' % self.pidfile)
        else:
            self.logger.log('chatserverd started with pid %s' % pid)

    def cleanup(self):
        self._try_unlink(self.pidfile)

    def _try_unlink(self, path):
        try:
            os.unlink(path)
        except OSError:
            pass

    def close_chatserver(self):
        dispatcher_servers = []
        server = self.chatserver
        server.close()

        # server._map is a reference to the asyncore socket_map
        for dispatcher in self.get_socket_map().values():
            dispatcher_server = getattr(dispatcher, 'server', None)
            if dispatcher_server is server:
                dispatcher_servers.append(dispatcher)

        for server in dispatcher_servers:
            server.close()

    def close_logger(self):
        self.logger.close()

    def setsignals(self):
        receive = self.signal_receiver.receive
        signal.signal(signal.SIGTERM, receive)
        signal.signal(signal.SIGINT, receive)
        signal.signal(signal.SIGQUIT, receive)
        signal.signal(signal.SIGHUP, receive)
        signal.signal(signal.SIGCHLD, receive)
        signal.signal(signal.SIGUSR2, receive)

    def get_signal(self):
        return self.signal_receiver.get_signal()

    def openchatserver(self, chatserverd):
        try:
            self.chatserver = self.make_chat_server(chatserverd)
        except socket.error as why:
            if why.args[0] == errno.EADDRINUSE:
                self.usage('Another program is already listening on '
                           'a port that our chat server is '
                           'configured to use.  Shut this program '
                           'down first before starting chat server.')
            else:
                help = 'Cannot open an chat server: socket.error reported'
                errorname = errno.errorcode.get(why.args[0])
                if errorname is None:
                    self.usage('%s %s' % (help, why.args[0]))
                else:
                    self.usage('%s errno.%s (%d)' %
                               (help, errorname, why.args[0]))
            self.unlink_socketfiles = False
        except ValueError as why:
            self.usage(why.args[0])

    def broadcast_message(self):
        for key in asyncore.data_map.keys():
            message = asyncore.data_map[key]

            for fd in asyncore.socket_map.keys():
                dp = asyncore.socket_map[fd]
                # self.logger.log("%d, %d" % (key, fd) + "\n")
                if fd != key and isinstance(dp, chat_channel):
                    dp.push_data(message)

    def get_socket_map(self):
        return asyncore.socket_map

    def clear_data_map(self):
        asyncore.data_map.clear()

    def make_chat_server(self, chatserverd):
        from chatserver.chatserver import make_server
        return make_server(self, chatserverd)