#!/usr/bin/env python

import sys
import os
import time
import signal

from chatserver.medusa import asyncore_25 as asyncore
from chatserver.helpers import Helpers

class ChatServerStates:
    RUNNING = 1
    SHUTDOWN = -1

class ChatServer:

    def __init__(self, helpers):
        self.helpers = helpers

    def main(self):
        self.run()

    def run(self):
        try:
            self.helpers.openchatserver(self)
            self.helpers.setsignals()
            self.helpers.daemonize()
            self.helpers.write_pidfile()
            self.runforever()
        finally:
            self.helpers.cleanup()

    def runforever(self):
        timeout = 1

        socket_map = self.helpers.get_socket_map()
        self.helpers.mood = ChatServerStates.RUNNING

        while 1:

            self.helpers.broadcast_messages()
            self.helpers.clear_data_map()

            combined_map = {}
            combined_map.update(socket_map)

            if self.helpers.mood < ChatServerStates.RUNNING:
                raise asyncore.ExitNow

            for fd, dispatcher in combined_map.items():
                if dispatcher.readable():
                    self.helpers.poller.register_readable(fd)
                if dispatcher.writable():
                    self.helpers.poller.register_writable(fd)

            r, w = self.helpers.poller.poll(timeout)

            for fd in r:
                if fd in combined_map:
                    try:
                        dispatcher = combined_map[fd]
                        self.helpers.logger.log('read event caused by %s' % dispatcher.repr())
                        dispatcher.handle_read_event()
                    except asyncore.ExitNow:
                        self.helpers.logger.log("ExitNow\n")
                        raise
                    except:
                        combined_map[fd].handle_error()

            for fd in w:
                if fd in combined_map:
                    try:
                        dispatcher = combined_map[fd]
                        self.helpers.logger.log('write event caused by %s' % dispatcher.repr())
                        dispatcher.handle_write_event()
                    except asyncore.ExitNow:
                        self.helpers.logger.log("ExitNow\n")
                        raise
                    except:
                        combined_map[fd].handle_error()

            self.handle_signal()

    def handle_signal(self):
        sig = self.helpers.get_signal()
        if sig:
            if sig in (signal.SIGTERM):
                self.helpers.logger.log('received SIGTERM indicating exit request')
                self.helpers.mood = SupervisorStates.SHUTDOWN

# Main program
def main():
    assert os.name == "posix", "This code makes Unix-specific assumptions"
    sys.path.append(os.getcwd())
    while 1:
        helpers = Helpers()
        helpers.getopts()
        d = ChatServer(helpers)

        try:
            d.main()
        except asyncore.ExitNow:
            pass

        helpers.close_chatserver()
        helpers.close_logger()

        if helpers.mood < ChatServerStates.SHUTDOWN:
            break

if __name__ == "__main__":
    main()