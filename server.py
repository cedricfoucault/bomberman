import socket
import socket_utils
import threading
import select
import sys
import packets
import time
from gameconst import *

class ShutdownMixIn(object):
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
            
    def _do_on_shutdown(self):
        """This function is called just before the process is shut-downed.
        
        May be overriden"""
        pass
        
    def shutdown(self, non_blocking=False):
        """Stop the server from accepting new connections"""
        self._shutdown_request = True
        if not non_blocking:
            self._is_shut_down.wait()
    
    def is_shut_down(self):
        return self._is_shut_down.is_set()
    

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
    # dumb client counter, incremented every time a new client is instanced
    _client_counter = 0
    
    def __init__(self, conn, client_addr, server, start=True):
        super(BaseConnectionHandle, self).__init__()
        self.conn        = conn # the socket connecting the server with the client
        self.client_addr = client_addr # the client's address
        self.server      = server # a reference to the server owning the connection
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

    def start_handling(self):
        """Start processing the connection"""
        print "handling " + str(self.client_addr)
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
                    print "Received: " + str(packet)
                    # process it
                    self._process_client_packet(packet)
                    # this client is active, reset _time_left countdown
                    self._time_left = self.__class__.timeout
                except socket.error, e:
                    # if the connection was closed on the client side,
                    # shut down the process
                    self.shutdown(non_blocking=True)
                except packets.PacketMismatch, e:
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
        print "shutting down " + str(self.client_addr)
        self.server.notice_connection_shutdown(self)

    def close_connection(self):
        """Close the socket doing the connection"""
        socket_utils.shutdown_close(self.conn)
    
    def send_client(self, packet):
        """Send a packet to the connected client"""
        self._write_lock.acquire()
        # ------ enter critical section ------
        # send the packet through the connected socket
        print "Sending " + str(packet)
        packet.send(self.conn)
        # ------ exit critical section -------
        self._write_lock.release()
    
    @classmethod
    def _get_new_id(cls):
        """create a fresh id for a new client"""
        cls._client_counter += 1
        return cls._client_counter

class ParrotConnectionHandle(BaseConnectionHandle):
    """This type of connection will send back to the client
    every packet the server received from it."""
    
    def _process_client_packet(self, packet):
        self.send_client(packet)

class RecordConnectionHandle(BaseConnectionHandle):
    """This type of connection will keep track of the received packets
    in some way in a record maintained by the server"""
    
    def _process_client_packet(self, packet):
        """Record any received packet"""
        self.server.record_packet(packet, self)
        
class LobbyConnectionHandle(BaseConnectionHandle):
    """This type of connection will listen for 'create new party' packets
    (type 15) and ignore any other packet."""
    packet_class = packets.GamePacket
    
    def _process_client_packet(self, packet):
        if packet.type == packets.PacketType.CREATE_PARTY:
            self.server.create_party()

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
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
                args=(poll_interval, )
        )
        
    def _accept_connection(self, timeout):
        """Wait for a connection request.
        If a request was received before timeout,
        accept the new client and handle the connection."""
        ready_to_read = select.select([self.socket], [], [], timeout)[0]
        if self.socket in ready_to_read:
            sys.stdout.flush()
            try:
                conn, client_addr = self.socket.accept()
                print "accepted " + str(client_addr)
                sys.stdout.flush()
                self.handle_connection(conn, client_addr)
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
        
    def send_to_all(self, packet):
        """Broadcast a packet to every client currently connected"""
        for handle in self.get_active_connections():
            handle.send_client(packet)
    
    def _do_on_shutdown(self):
        self.close_all()
    
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

class ParrotServer(Server):
    """A server that sends back to the client everything it receives from it"""
    ConnectionHandle = ParrotConnectionHandle

class LobbyServer(Server):
    """The lobby server maintains a list of pending parties, and creates a new
    party if it recieves a packet of appropriate type by a client.
    The lobby server also periodically sends to the connected clients
    the list of current pending parties and their status."""
    ConnectionHandle = LobbyConnectionHandle
    SEND_INTERVAL = 0.5
    
    def __init__(self, address, bind_and_listen=True):
        # init the superclass's fields
        super(LobbyServer, self).__init__(address, bind_and_listen)
        # init the new fields
        # a list of current pending parties
        self._parties = []
        # a lock to access and update this resource safely
        self._parties_lock = threading.Lock()
    
    def create_party(self):
        """Creates a new party."""
        new_party = PendingPartyServer()
        
        self._parties_lock.acquire()
        # ------ enter critical section ------
        # add the new party server to the list of current pending parties
        self._parties.append(new_party)
        # ------ exit critical section -------
        self._parties_lock.release()
        
    def notice_party_shutdown(self, party):
        """When a party server shutdowns, it will inform the lobby server by
        calling this function with itself as argument."""
        self._parties_lock.acquire()
        # ------ enter critical section ------
        # remove the given party server from the list of pending parties
        self._parties = [p for p in self._parties if p != party]
        # ------ exit critical section -------
        self._parties_lock.release()
    
    def get_parties(self):
        self._parties_lock.acquire()
        # ------ enter critical section ------
        # get a copy of this resource
        parties_copy = parties.copy()
        # ------ exit critical section -------
        self._parties_lock.release()
        # safely return the copy
        return parties_copy
    
    def send_parties(self):
        """Send to all clients connected to the lobby the list of pending
        parties."""
        parties = self.get_parties()
        parties_info = [p.get_info() for p in parties]
        packet = packets.LobbyPacket(parties).wrap()
        self.send_to_all(packet)
    
    def send_parties_periodically(self):
        """Periodically send to all clients the list pending parties."""
        while not self.is_shut_down():
            self.send_parties()
            time.sleep(self.__class__.SEND_INTERVAL)
    
# change PendingPartyServer to PartyServer?
class PendingPartyServer(Server):
    """A PendingPartyServer is a waiting room for the players before
    a new game can start. It waits until the room is full, sending the current
    status of the party periodically to all players in the room."""
    # ID count
    next_id = 0
    SEND_INTERVAL = 1
    
    def __init__(self, address, bind_and_listen=True, max_players=4):
        super(PendingPartyServer, self).__init__(address, bind_and_listen)
        # assign the next available id and increment the global counter
        self.id = self.__class__.next_id
        self.__class__.next_id += 1
        self.max_players = max_players
        
    @classmethod
    def create_new(cls):
        """Creates a new PendingPartyServer, picking any available port
        the OS will give us."""
        # Let the OS pick a random available port
        cls(('', 0), True)
        # update the address and party info
        ip, port = self.socket.getsockname()
        self.address = ip, port
        
    def get_info(self):
        """Returns the PartyInfo object matching this server."""
        idp = self.id
        ip, port = self.address
        n_players = len(self.get_active_connections())
        max_players = self.max_players
        return PartyInfo(idp, ip, port, n_players, max_players)
    
    def send_parties(self):
        """Send to all connected players the current party status
        (# players / # total expected)."""
        n_players = len(self.get_active_connections())
        packet = packets.PartyStatusPacket(n_players, self.max_players).wrap()
        self.send_to_all(packet)
    
    def send_parties_periodically(self):
        """Periodically call send_parties."""
        while not self.is_shut_down():
            self.send_parties()
            time.sleep(self.__class__.SEND_INTERVAL)
    

# change PartyServer to GameServer?
class PartyServer(Server):
    ConnectionHandle = RecordConnectionHandle
    # SEND_INTERVAL = ROUND_INTERVAL / 1000
    SEND_INTERVAL = 1
    
    def __init__(self, address, bind_and_listen=True):
        # init the superclass's fields
        super(PartyServer, self).__init__(address, bind_and_listen)
        # init the new fields
        # a record of the client actions
        self._action_record = {}
        # a lock to access and update this resource safely
        self._action_record_lock = threading.Lock()
        pass
    
    def record_packet(self, packet, client):
        """Save a client action packet in the action record"""
        # process the received packet to retrieve the requested action
        if (packet.type == packets.ActionRequestPacket.TYPE):
            action_packet = packets.ActionRequestPacket.process_raw_data(packet.payload)
        action = action_packet.action
        # save the action
        self._action_record_lock.acquire()
        # ------ enter critical section ------
        # if there's no action already committed for this client,
        # comit this action
        if client not in self._action_record:
            self._action_record[client] = action
        elif self._action_record[client] == packets.Action.DO_NOTHING:
            self._action_record[client] = action
        # else, ignore the packet
        # ------ exit critical section -------
        self._action_record_lock.release()
    
    def get_action_record(self):
        """Get the current packet record"""
        """Save a client packet in the record"""
        self._action_record_lock.acquire()
        # ------ enter critical section ------
        # return a copy of the packet record
        record = self._action_record.copy()
        # else, ignore the packet
        # ------ exit critical section -------
        self._action_record_lock.release()
        return record
    
    def _flush_record(self):
        """Empty the current packet record"""
        self._action_record_lock.acquire()
        # ------ enter critical section ------
        self._action_record = {
            client: packets.Action.DO_NOTHING
            for client in self.get_active_connections()
        }
        # ------ exit critical section -------
        self._action_record_lock.release()
    
    def send_actions_periodically(self):
        """Periodically send to all players their list of committed actions."""
        while not self.is_shut_down():
            self.send_actions()
            time.sleep(self.__class__.SEND_INTERVAL)
    
    def send_actions(self):
        # get the commited packets and flush the record
        record = self.get_action_record()
        self._flush_record()
        # retrieve the actions in appropriate order
        clients = sorted(record.iterkeys(), cmp=lambda c1, c2: c1.id - c2.id)
        actions = [packets.Action.DO_NOTHING] * NUM_PLAYERS
        for i, c in enumerate(clients[:NUM_PLAYERS]):
            actions[i] = record[c]

        turn = 0
        # create a packet to commit these actions
        commit_packet = packets.ActionsCommitPacket(turn, actions)
        response = packets.ResponsePacket(packets.ActionsCommitPacket.TYPE,
                                            commit_packet.get_raw_data())
        # send it to every client in the party
        self.send_to_all(response)


def main():
    """Main server process"""
    PORT = 2049 # arbitrary port number to connect on for the chat
    LOCALHOST = '127.0.0.1' # ip adress of localhost
    # server = ParrotServer((LOCALHOST, PORT))
    server = PartyServer((LOCALHOST, PORT))
    # server.serve_forever()
    threading.Thread(target=server.serve_forever).start()
    server.send_actions_periodically()
    
if __name__ == "__main__":
    main()

