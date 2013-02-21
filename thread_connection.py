from thread_shutdown import *
from gameconst import *

import packets
import socket_utils
import select
import socket
import sys

class ThreadConnectionHandle(ThreadShutdownMixIn):
    """Base class for connection handles.
    A connection handle is an object that identifies a client-master connection,
    other processes will use this object as an interface."""
    # tells whether the connection should be shut down when the main thread is done
    daemon_threads = True
    # time interval between checks to a shutdown request (in secs)
    poll_interval = 0.5
    # timeout (in sec) to shut down the connection automatically
    # if no activity is detected
    timeout = 600
    # the packet received from this connection should be read as instances of this class
    packet_class = packets.GamePacket
    # dumb client counter, incremented every time a new client is instanced
    _client_counter = 0
    
    def __init__(self, conn, addr, master, start=True, no_init=False):
        super(ThreadConnectionHandle, self).__init__()
        if not no_init:
            self.conn        = conn # the socket doing the connection
            self.addr = addr # the address the socket is connected to
            self.master      = master # a reference to the owner of the connection
            self.thread      = threading.Thread( # the receiver thread
                target=self._process_connection,
                  args=()
            )
            self.thread.daemon = self.__class__.daemon_threads
            # a lock preventing two threads from writing at the same time
            self._write_lock  = threading.Lock()
            # get a client id
            self.id = self.__class__._get_new_id()
            if start:
                self.start_handling()

    @classmethod
    def from_instance(cls, handle, start=True):
        """Create a new connection handle from an existing one."""
        new = cls(None, None, None, None, no_init=True)
        new.conn        = handle.conn # the socket connecting the master with the client
        new.addr = handle.addr # the client's address
        new.master      = handle.master # a reference to the master owning the connection
        new.thread      = threading.thread( # the receiver thread
            target=new._process_connection,
            args=()
        )
        new.thread.daemon = cls.daemon_threads
        new._write_lock = handle.thread
        new.id          = handle.id # the client id
        if start:
            new.start_handling()
        return new

    def start_handling(self):
        """Start processing the connection"""
        if VERBOSE: print "handling " + str(self.addr)
        self.thread.start()
        
    def _process_connection(self, poll_interval=poll_interval):
        """Function to be run in a new thread while the connection is active"""
        self._time_left = self.timeout
        self.do_while_not_shut_down(iter_fun=self._process_connection_iter)
        
    def _process_connection_iter(self):
        """Processing done in one iteration of the processing loop"""
        if self._time_left < 0:
            # if the time is over, shut down the process
            self.shutdown(non_blocking=True)
        else:
            # wait to receive a new client packet
            ready_to_read = select.select([self.conn], [], [], self.__class__.poll_interval)[0]
            if self.conn in ready_to_read:
                try:
                    # try to read the packet
                    packet = self.__class__.packet_class.recv(self.conn)
                    if PRINT_PACKETS:
                        print "Received: " + str(packet) + " from " + str(self.addr)
                    # process it
                    self._process_client_packet(packet)
                    # this client is active, reset _time_left countdown
                    self._time_left = self.__class__.timeout
                except socket.error, e:
                    # if the connection was closed on the client side,
                    # shut down the process
                    self.shutdown(non_blocking=True)
                except packets.PacketMismatch, e:
                    if VERBOSE: print >> sys.stderr, str(e)
            else:
                # no activity has been detected thus far,
                # decrement the _time_left countdown
                self._time_left -= self.__class__.poll_interval

    def _process_client_packet(self, packet):
        """Process a packet which was sent by the client.
        May be overriden."""
        pass
        
    def _do_on_shutdown(self):
        """On shutdown, notice the master."""
        if VERBOSE: print "shutting down " + str(self.addr)
        self.master.notice_connection_shutdown(self)

    def close_connection(self):
        """Close the socket doing the connection"""
        socket_utils.shutdown_close(self.conn)
    
    def send_client(self, packet):
        """Send a packet to the connected client"""
        self._write_lock.acquire()
        # ------ enter critical section ------
        # send the packet through the connected socket
        try:
            packet.send(self.conn)
            if PRINT_PACKETS:
                print "Sent " + str(packet) + " to " + str(self.addr)
        except socket.error, e:
            self.shutdown(non_blocking=True)
        # ------ exit critical section -------
        self._write_lock.release()
    
    @classmethod
    def _get_new_id(cls):
        """create a fresh id for a new client"""
        cls._client_counter += 1
        return cls._client_counter

