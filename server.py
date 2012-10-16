import socket
import threading
import select
import sys
import packets

class ShutdownMixIn:
    """Mix-In class to execute a task forever until a shutdown request is emitted"""
    
    def __init__(self):
        # flag set to True if a request for shutdown was emitted
        self._shutdown_request = False
        # this event enables an other process to wait
        # until this process is effectively shut down
        self._is_shut_down = threading.Event()
        
    def do_while_not_shut_down(self, iter_fun=(lambda: None), args=()):
        """Iter calls to fun(args) until a shutdown request is emitted"""
        self._is_shut_down.clear()
        try:
            while not self._shutdown_request:
                iter_fun(*args)
        finally:
            self._shutdown_request = False
            self._do_on_shutdown()
            self._is_shut_down.set()
            
    def _do_on_shutdown():
        """This function is called just before the process is shut-downed.
        
        May be overriden"""
        pass
        
    def shutdown(self, non_blocking=False):
        """Stop the server from accepting new connections"""
        self._shutdown_request = True
        if not non_blocking:
            self._is_shut_down.wait()
    
    def is_shut_down(self):
        return _is_shut_down.is_set()
    

class BaseConnectionHandle(ShutdownMixIn):
    """Base class for connection handles.
    A connection handle is an object that identifies a client-server connection,
    other processes will use this object as an interface."""
    # tells whether the connection should be shut down when the main thread is done
    daemon_threads = False
    # time interval between checks to a shutdown request (in secs)
    poll_interval = 0.5
    # timeout (in sec) to shut down the connection automatically
    # if no activity is detected
    timeout = 60
    # the packet received from this connection should be read as instances of this class
    packet_class = packets.RequestPacket
    
    def __init__(self, conn, client_addr, server, start=True):
        super(BaseConnectionHandle, self).__init__()
        self.conn        = conn # the socket connecting the server with the client
        self.client_addr = addr # the client's address
        self.server      = server # a reference to the server owning the connection
        self.thread      = threading.Thread( # the receiver thread
            target=self._process_connection,
              args=()
        )
        self.thread.daemon = daemon_threads
        # a lock preventing two threads from writing at the same time
        self._write_lock  = threading.Lock()
        if start:
            self.start_handling()

    def start_handling(self):
        """Start processing the connection"""
        self.thread.start()
        
    def _process_connection(self, poll_interval=poll_interval):
        """Function to be run in a new thread while the connection is active"""
        self._time_left = self.timeout
        self.do_while_not_shut_down(iter_fun=_process_connection_iter)
        
    def _process_connection_iter(self):
        """Processing done in one iteration of the processing loop"""
        if self._time_left < 0:
            # if the time is over, shut down the process
            self.shutdown(non_blocking=True)
        else:
            # wait to receive a new client packet
            ready_to_read = select.select([self.conn], [], [], self.__class__.poll_interval)
            if self.conn in ready_to_read:
                try:
                    # try to read the packet
                    packet = self.__class__.packet_class.recv(conn)
                    # process it
                    self._process_client_packet(packet)
                    # this client is active, reset _time_left countdown
                    self._time_left = self.__class__.timeout
                except socket.error:
                    # if the connection was closed on the client side,
                    # shut down the process
                    self.shutdown(non_blocking=True)
                except packet.PacketMismatch, e:
                    print >> sys.stderr, str(e)
            else:
                # no activity has been detected thus far,
                # decrement the _time_left countdown
                self._time_left -= self.__class__.poll_interval

    def _process_client_packet(self, packet):
        """Process a packet which was sent by the client.
        May be overriden."""
        pass
        
    def _do_on_shutdown(self):
        """On shutdown, notice the server."""
        self.server.notice_connection_shutdown(self)

    def close_connection(self):
        """Close the socket doing the connection"""
        socket_utils.shutdown_close(self.conn)
    
    def send_client(self, packet):
        """Send a packet to the connected client"""
        self._write_lock.acquire()
        # ------ enter critical section ------
        # send the packet through the connected socket
        packet.send(self.conn)
        # ------ exit critical section -------
        self._write_lock.release()

class ParrotConnectionHandle(BaseConnectionHandle):
    """This connection will send back to the client
    every packet the server received from it."""
    
    def _process_client_packet(self, packet):
        self.send_client(packet)
        

class Server(ShutdownMixIn):
    """Base class for the server"""
    # use IPv4 adresses
    address_family = socket.AF_INET
    # use TCP sockets
    socket_type = socket.SOCK_STREAM
    # the max number of connection request that can be queued
    request_queue_size = 5
    # the class to instance connection handle objects
    ConnectionHandle = BaseConnectionHandle
    # time interval between checks to a shutdown request (in secs)
    poll_interval = 0.5
    
    def __init__(self, address, bind_and_listen=True):
        super(Server, self).__init__()
        # the server's address
        self.address = address
        # the server's listener socket
        self.socket = socket.socket(self.address_family, self.socket_type)
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
                args=poll_interval
        )
        
    def _accept_connection(self, timeout):
        """Wait for a connection request.
        If a request was received before timeout,
        accept the new client and handle the connection."""
        ready_to_read = select.select([self.socket], [], [], timeout)
        if self.socket in ready_to_read:
            try:
                conn, client_addr = self.socket.accept()
            except socket.error, e:
                print >> sys.stderr, str(e)
                
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
        # ------ exit critical section -------
        self._active_connections_lock.release()
    
    def notice_connection_shutdown(self, handle):
        """This function is called when a connection handle is
        about to be shut-down."""
        self._cleanup_connection(handle)
    
    def _cleanup_connections(self):
        """Close all shut-downed connections
        and remove them from the list of active connections"""
        for handle in self.get_active_connections():
            if handle.is_shut_down():
                handle.close_connection()
                self._remove_connection(handle)
                
    def _cleanup_connection(self, handle):
        """Close the connection represented by handle
        and remove it from the list of active connections."""
        handle.close_connection()
        self._remove_connection(handle)
    
    def close_all(self):
        """Close the server and all open connections"""
        for handle in self.get_active_connections():
            handle.shutdown()
            handle.close_connection()
        self.close_server()

    # def _close_connection(conn):
    #     """Close a connection with a client"""
    #     try:
    #         conn.shutdown(socket.SHUT_WR)
    #     except socket.error, e:
    #         print >> sys.stderr, str(e)
    #     conn.close()
        
    # def serve_forever(self, poll_interval=0.5):
    #     """Accept and handle one connection at a time until shutdown.
    #     
    #     Polls for shutdown request every poll_interval seconds.
    #     """
    #     self._is_shut_down.clear()
    #     try:
    #         while not self._shutdown_request:
    #             r = select.select([self.socket], [], [], poll_interval)
    #             if self.socket in r:
    #                 try:
    #                     conn, client_addr = self.socket.accept()
    #                     self.handle_connection(conn, client_addr)
    #                 except socket.error, e:
    #                     print >> sys.stderr, str(e)
    #     finally:
    #         self._shutdown_request = False
    #         self._is_shut_down.set()
    # 
    # def shutdown(self):
    #     """Stop the server from accepting new connections"""
    #     self._shutdown_request = True
    #     self._is_shut_down.wait()


