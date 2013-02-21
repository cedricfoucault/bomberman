from thread_shutdown import ThreadShutdownMixIn as ShutdownMixIn
from thread_connection import *
import packets
import mapgen
from gameconst import *

import socket
import socket_utils
import select
import sys
import threading
import time
import subprocess


class Server(ShutdownMixIn):
    """Base class for the server"""
    # use IPv4 adresses
    address_family = socket.AF_INET
    # use TCP sockets
    socket_type = socket.SOCK_STREAM
    # the max number of connection request that can be queued
    request_queue_size = 5
    # the class to instance connection handle objects
    ConnectionHandle = ThreadConnectionHandle
    # time interval between checks to a shutdown request (in secs)
    poll_interval = 0.5
    # tells whether the server should be shut down when the main thread is done
    daemon_threads = True
    
    def __init__(self, address, bind_and_listen=True, no_init=False):
        super(Server, self).__init__()
        if not no_init:
            # the server's address
            self.address = address
            # the server's listener socket
            self.socket = socket.socket(self.address_family, self.socket_type)
            # "free" the socket as soon as it is closed
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # disable Naggle
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            # a maintained list of active connections
            self._active_connections = []
            # a lock used to access safely the active connections list
            self._active_connections_lock = threading.Lock()
            if bind_and_listen:
                self.bind()
                self.listen()
    
    def bind(self):
        """Bind the server socket to the given server address"""
        self.socket.bind(self.address)
        self.address = self.socket.getsockname()
        
    def listen(self):
        """Listen to incoming connections and put them in the queue"""
        self.socket.listen(self.request_queue_size)

    def serve_forever(self, poll_interval=poll_interval):
        """Accept and handle one connection at a time until
        a request to shut down the server is emitted.

        Polls for shutdown request every poll_interval seconds.
        """
        self.do_while_not_shut_down(
            iter_fun=self._accept_connection,
                args=(poll_interval, )
        )
        
    def _accept_connection(self, timeout):
        """Wait for a connection request.
        If a request was received before timeout,
        accept the new client and handle the connection."""
        ready_to_read = select.select([self.socket], [], [], timeout)[0]
        if self.socket in ready_to_read:
            try:
                conn, client_addr = self.socket.accept()
                if VERBOSE: print "accepted " + str(client_addr)
                self.handle_connection(conn, client_addr)
            except socket.error, e:
                if VERBOSE: print >> sys.stderr, str(e)
                
    def close_server(self):
        """Close the server (closes the listener socket)"""
        socket_utils.shutdown_close(self.socket)
    
    def handle_connection(self, conn, client_addr):
        """Handle a new client connection"""
        # create a new handle for this connection
        # and start the handling process immediately
        handle = self.ConnectionHandle(conn, client_addr, self, start=True)
        # add the handle to the list of active connections
        self._add_active_connection(handle)
    
    def get_active_connections(self):
        """Get the list of active connections"""
        self._active_connections_lock.acquire()
        # ------ enter critical section ------
        # copy the list of active connections
        active_connections_copy = list(self._active_connections)
        # ------ exit critical section -------
        self._active_connections_lock.release()
        # return the copy
        return active_connections_copy
    
    def _add_active_connection(self, handle):
        """Add a new connection to the list of active connections"""
        self._active_connections_lock.acquire()
        # ------ enter critical section ------
        # append the new connection handle to the list of active connections
        self._active_connections.append(handle)
        # ------ exit critical section -------
        self._active_connections_lock.release()
    
    def _remove_connection(self, handle):
        """Remove a connection from the list of active connections"""
        self._active_connections_lock.acquire()
        # ------ enter critical section ------
        # remove the given connection handle from the list of active connections
        self._active_connections.remove(handle)
        if not self._active_connections:
            self._active_connections = []
        # ------ exit critical section -------
        self._active_connections_lock.release()
    
    def notice_connection_shutdown(self, handle):
        """This function is called when a connection handle is
        about to be shut-down."""
        self._cleanup_connection(handle)
    
    def _cleanup_connection(self, handle):
        """Close the connection represented by handle
        and remove it from the list of active connections."""
        handle.close_connection()
        self._remove_connection(handle)
    
    def _cleanup_connections(self):
        """Close all shut-downed connections
        and remove them from the list of active connections"""
        for handle in self.get_active_connections():
            if handle.is_shut_down():
                handle.close_connection()
                self._remove_connection(handle)
    
    def close_all(self):
        """Close the server and all open connections"""
        for handle in self.get_active_connections():
            handle.shutdown()
            handle.close_connection()
        self.close_server()
        
    def send_to_all(self, packet):
        """Broadcast a packet to every client currently connected"""
        for handle in self.get_active_connections():
            handle.send_client(packet)
    
    def _do_on_shutdown(self):
        self.close_all()
    

