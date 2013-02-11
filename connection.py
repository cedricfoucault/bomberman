from mixins import *

import packets
import socket_utils
import select
import socket
import sys

# debug = True
debug = False

class TaskConnectionHandle(TaskShutdownMixIn):
    """Base class for connection handles, using Panda3D tasks.
    A connection handle is an object that identifies a client-server connection,
    other processes will use this object as an interface."""
    # time interval between poll checks (in s)
    # if this is 0, the poll checks will be done once every frame
    poll_interval = 0
    # the packet received from this connection should be read as instances of this class
    packet_class = packets.GamePacket
    
    def __init__(self, conn, addr, start=True, no_init=False):
        super(TaskConnectionHandle, self).__init__()
        if not no_init:
            self.conn        = conn # the socket for the connection
            self.addr        = addr # the socket's destination address
            self.packet_to_send = None # a "buffer" where the packet to send
                                       # will be put
            if start:
                self.start_handling()

    def start_handling(self):
        """Start processing (polling) the connection"""
        if debug: print "handling " + str(self.addr)
        self.do_task(self._poll, self.poll_interval)
    
    def _poll(self):
        """Poll this connection non-blockingly.
        Check if there are data to read from the connection
        and, if there are data to send, attempt to send them."""
        # read poll
        self._poll_read()
        # write poll
        if self.packet_to_send:
            was_sent = self._poll_write(self.packet_to_send)
            if was_sent: self.packet_to_send = None
    
    def _poll_write(self, packet):
        """Check if data can be sent through the connected socket, and if yes,
        send whatever is to be sent.
        Returns True if data has been sent, False otherwise."""
        # check if data can be sent
        ready_to_write = select.select([], [self.conn], [], 0)[1]
        if self.conn in ready_to_write:
            try:
                # try to send the packet
                packet.send(self.conn)
                if debug: print "Sent " + str(packet) + " to " + str(self.addr)
                return True
            except socket.error, e:
                # if the connection was closed on the client side,
                # shut down the process
                if debug: print >> sys.stderr, str(e)
                self.shutdown()
                return False
        else:
            return False
    
    def _poll_read(self):
        """Check if there are some data to read from the connection, and if yes,
        read it."""
        # check there are some data to read
        ready_to_read = select.select([self.conn], [], [], 0)[0]
        if self.conn in ready_to_read:
            # read it
            try:
                # try to read the packet
                packet = self.__class__.packet_class.recv(self.conn)
                if debug: print "Received: " + str(packet) + " from " + str(self.addr)
                # process it
                self._process_packet(packet)
            except socket.error, e:
                # if the connection was closed on the client side,
                # shut down the process
                if debug: print >> sys.stderr, str(e)
                self.shutdown()
            except packets.PacketMismatch, e:
                if debug: print >> sys.stderr, str(e)

    def _process_packet(self, packet):
        """Process a packet which was received from this connection.
        May be overriden."""
        pass
        
    def _do_on_shutdown(self):
        """On shutdown, properly close the socket."""
        if debug: print "shutting down " + str(self.addr)
        self.close_connection()

    def close_connection(self):
        """Close the socket doing the connection"""
        socket_utils.shutdown_close(self.conn)
    
    def send(self, packet):
        """Send a packet to the other end of the connection.
        This function actually just poses a request to send the given packet,
        it will be send on the next write poll if the socket is available.
        It overrides any previous send request which has not been processed."""
        self.packet_to_send = packet

