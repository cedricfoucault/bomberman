import packets
import mapgen
from gameconst import *

import socket
import socket_utils
import select
import sys
import threading
import time

debug = DEBUG
# debug = True
# debug = False

class ShutdownMixIn(object):
    """Mix-In class to execute a task forever until a shutdown request is emitted"""
    
    def __init__(self):
        # flag set to True if a request for shutdown was emitted
        self._shutdown_request = False
        self._silent_shutdown = False
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
            if not self._silent_shutdown:
                self._do_on_shutdown()
            self._is_shut_down.set()
            
    def _do_on_shutdown(self):
        """This function is called just before the process is shut-downed.
        
        May be overriden"""
        pass
        
    def shutdown(self, non_blocking=False, silent=False):
        """Stop the server from accepting new connections"""
        # if the silent option is true, the process will be shut down
        # without calling the usual _do_on_shutdown
        self._silent_shutdown = silent
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
    
    def __init__(self, conn, client_addr, server, start=True, no_init=False):
        super(BaseConnectionHandle, self).__init__()
        if not no_init:
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

    @classmethod
    def from_instance(cls, handle, start=True):
        """Create a new connection handle from an existing one."""
        new = cls(None, None, None, None, no_init=True)
        new.conn        = handle.conn # the socket connecting the server with the client
        new.client_addr = handle.client_addr # the client's address
        new.server      = handle.server # a reference to the server owning the connection
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
        if debug: print "handling " + str(self.client_addr)
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
                    if debug:
                        print "Received: " + str(packet) + " from " + str(self.client_addr)
                    # process it
                    self._process_client_packet(packet)
                    # this client is active, reset _time_left countdown
                    self._time_left = self.__class__.timeout
                except socket.error, e:
                    # if the connection was closed on the client side,
                    # shut down the process
                    self.shutdown(non_blocking=True)
                except packets.PacketMismatch, e:
                    if debug: print >> sys.stderr, str(e)
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
        if debug: print "shutting down " + str(self.client_addr)
        self.server.notice_connection_shutdown(self)

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
            if debug:
                print "Sent " + str(packet) + " to " + str(self.client_addr)
        except socket.error, e:
            self.shutdown(non_blocking=True)
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
    
    # @classmethod
    def from_server(cls, server):
        """Create a new instance from an existing one, taking its
        active connections and server socket."""
        new = cls(None, no_init=True)
        # the server's address
        new.address = server.address
        # the server's listener socket
        new.socket = server.socket
        # the list of active connections:
        # convert the handle class used to process the connections
        for handle in server._active_connections:
            handle.shutdown(silent=True)
        new._active_connections = [ cls.ConnectionHandle.from_instance(handle)
            for handle in server._active_connections ]
        # the lock used to access safely the active connections list
        new._active_connections_lock = server._active_connections_lock
        return new
    
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
                if debug: print "accepted " + str(client_addr)
                self.handle_connection(conn, client_addr)
            except socket.error, e:
                if debug: print >> sys.stderr, str(e)
                
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
    
    def __init__(self, address, bind_and_listen=True, no_init=False):
        # init the superclass's fields
        super(LobbyServer, self).__init__(address, bind_and_listen, no_init)
        if not no_init:
            # init the new fields
            # a list of current pending parties
            self._parties = []
            # a lock to access and update this resource safely
            self._parties_lock = threading.Lock()
    
    def create_party(self):
        """Creates a new party."""
        # instance a new party server
        # new_party = PendingPartyServer.create_new(self)
        new_party = PartyServer.create_new(self)
        t = threading.Thread(
            target=new_party.serve_forever,
            args=()
        )
        t.daemon = True
        t.start()
        t = threading.Thread(
            target=new_party.send_loop,
            args=()
        )
        t.daemon = True
        t.start()
        
        self._parties_lock.acquire()
        # ------ enter critical section ------
        # add the new party server to the list of current pending parties
        self._parties.append(new_party)
        # ------ exit critical section -------
        self._parties_lock.release()
        if debug: print "new party created"
        
    def notice_party_shutdown(self, party):
        """When a party server shutdowns, it will inform the lobby server by
        calling this function with itself as argument."""
        self._parties_lock.acquire()
        # ------ enter critical section ------
        # remove the given party server from the list of pending parties
        self._parties = [p for p in self._parties if p != party]
        # self._parties = self._parties.remove(party)
        #         if not self._parties:
        #             self._parties = []
        # ------ exit critical section -------
        self._parties_lock.release()
    
    def get_parties(self):
        self._parties_lock.acquire()
        # ------ enter critical section ------
        # get a copy of this resource
        parties_copy = list(self._parties)
        # ------ exit critical section -------
        self._parties_lock.release()
        # safely return the copy
        return parties_copy
    
    def send_parties(self):
        """Send to all clients connected to the lobby the list of pending
        parties."""
        parties = self.get_parties()
        parties_info = [p.get_info() for p in parties]
        packet = packets.LobbyPacket(parties_info).wrap()
        self.send_to_all(packet)
    
    def send_parties_periodically(self):
        """Periodically send to all clients the list pending parties."""
        while not self.is_shut_down():
            self.send_parties()
            time.sleep(self.__class__.SEND_INTERVAL)
        if debug: print "stop sending parties"
    
# # change PendingPartyServer to IngamePartyServer?
# class PendingPartyServer(Server):
#     """A PendingPartyServer is a waiting room for the players before
#     a new game can start. It waits until the room is full, sending the current
#     status of the party periodically to all players in the room."""
#     # ID count
#     next_id = 0
#     SEND_INTERVAL = 1
#     
#     def __init__(self, address, lobby, bind_and_listen=True, no_init=False, max_players=NUM_PLAYERS):
#         super(PendingPartyServer, self).__init__(address, bind_and_listen, no_init)
#         if not no_init:
#             # assign the next available id and increment the global counter
#             self.lobby = lobby
#             self.id = self.__class__.next_id
#             self.__class__.next_id += 1
#             self.max_players = max_players
#             self.n_players = 0
#         
#     @classmethod
#     def create_new(cls, lobby):
#         """Creates a new PendingPartyServer, picking any available port
#         the OS will give us."""
#         # Take the same IP as lobby and let the OS pick a random available port
#         ip = lobby.address[0]
#         new = cls((ip, 0), lobby)
#         # update the address and party info
#         new.address = new.socket.getsockname()
#         return new
#         
#     def get_info(self):
#         """Returns the PartyInfo object matching this server."""
#         idp = self.id
#         ip, port = self.address
#         # n_players = len(self.get_active_connections())
#         n_players = self.n_players
#         max_players = self.max_players
#         return packets.PartyInfo(idp, ip, port, n_players, max_players)
#     
#     def handle_connection(self, conn, client_addr):
#         """Handle a new client connection."""
#         super(PendingPartyServer, self).handle_connection(conn, client_addr)
#         self.n_players += 1
#         if debug: print str(self.n_players) + " players currently connected"
#         if self.n_players == self.max_players:
#             self.start_game()
#     
#     def notice_connection_shutdown(self, handle):
#         """This function is called when a connection about to be shut-down."""
#         super(PendingPartyServer, self).notice_connection_shutdown(handle)
#         self.n_players -= 1
#     
#     def send_status(self):
#         """Send to all connected players the current party status
#         (# players / # total expected)."""
#         # n_players = len(self.get_active_connections())
#         packet = packets.PartyStatusPacket(self.n_players, self.max_players).wrap()
#         self.send_to_all(packet)
#     
#     def send_status_periodically(self):
#         """Periodically call send_status."""
#         while not self.is_shut_down():
#             self.send_status()
#             time.sleep(self.__class__.SEND_INTERVAL)
#             
#     def start_game(self):
#         """This function is called when a room is full and starts a new game,
#         sending an init packet to all players and becomes an (ingame) party
#         server."""
#         # send the init packet to all clients
#         pID = 0
#         k = self.max_players
#         dturn = IngamePartyServer.SEND_INTERVAL * 1000 # (in ms)
#         n = BOARD_WIDTH
#         m = BOARD_HEIGHT
#         game_map = mapgen.generate(n, m)
#         tiles = game_map.get_tiles()
#         poss = [(0, 0), (n - 1, 0), (0, m - 1), (n - 1, m - 1)]
#         for handle in self.get_active_connections():
#             tiles = game_map.get_tiles()
#             packet = packets.InitPacket(pID, k, dturn, n, m, tiles, poss).wrap()
#             handle.send_client(packet)
#             pID += 1
#             
#         # notice the server that this party is full and no longer accepts
#         # new clients
#         self.lobby.notice_party_shutdown(self)
#         
#         # morph into the "in-game" server
#         self.start_ingame()
#     
#     def start_ingame(self):
#         """docstring for start_ingame"""
#         # stop accepting new connections
#         self.shutdown(silent=True)
#         # create an IngamePartyServer instance from self
#         ingame_server = IngamePartyServer.from_server(self)
#         # ingame_server.send_actions_periodically()
#         # start the ingame server's loop in a new thread
#         t = threading.Thread(
#             target=ingame_server.send_actions_periodically,
#             args=()
#         )
#         t.daemon = True
#         t.start()
#     
# 
# # change IngamePartyServer to IngamePartyServer/GameServer?
# class IngamePartyServer(Server):
#     ConnectionHandle = RecordConnectionHandle
#     # SEND_INTERVAL = ROUND_INTERVAL / 1000
#     SEND_INTERVAL = 1 # (in s)
#     
#     def __init__(self, address, bind_and_listen=True, no_init=False):
#         # init the superclass's fields
#         super(PartyServer, self).__init__(address, bind_and_listen, no_init)
#         if not no_init:
#             # init the new fields
#             # a record of the client actions
#             self._action_record = {}
#             # a lock to access and update this resource safely
#             self._action_record_lock = threading.Lock()
#     
#     @classmethod
#     def from_server(cls, server):
#         new = super(cls).from_server(cls, server)
#         new._action_record = {}
#         self._action_record_lock = threading.Lock()
#     
#     def record_packet(self, packet, client):
#         """Save a client action packet in the action record"""
#         # process the received packet to retrieve the requested action
#         if (packet.type == packets.ActionRequestPacket.TYPE):
#             action_packet = packets.ActionRequestPacket.process_raw_data(packet.payload)
#         action = action_packet.action
#         # save the action
#         self._action_record_lock.acquire()
#         # ------ enter critical section ------
#         # if there's no action already committed for this client,
#         # comit this action
#         if self._action_record.get(client, packets.Action.DO_NOTHING) == packets.Action.DO_NOTHING:
#             self._action_record = action
#         # else, ignore the packet
#         # ------ exit critical section -------
#         self._action_record_lock.release()
#     
#     def get_action_record(self):
#         """Get the current packet record"""
#         """Save a client packet in the record"""
#         self._action_record_lock.acquire()
#         # ------ enter critical section ------
#         # return a copy of the packet record
#         record = self._action_record.copy()
#         # else, ignore the packet
#         # ------ exit critical section -------
#         self._action_record_lock.release()
#         return record
#     
#     def _flush_record(self):
#         """Empty the current packet record"""
#         self._action_record_lock.acquire()
#         # ------ enter critical section ------
#         self._action_record = {
#             client: packets.Action.DO_NOTHING
#             for client in self.get_active_connections()
#         }
#         # ------ exit critical section -------
#         self._action_record_lock.release()
#     
#     def send_actions_periodically(self):
#         """Periodically send to all players their list of committed actions."""
#         # while not self.is_shut_down():
#         #             self.send_actions()
#         #             time.sleep(self.__class__.SEND_INTERVAL)
#         self.do_while_not_shut_down(
#             iter_fun=self.send_actions(),
#                 args=(self.__class__.SEND_INTERVAL, )
#         )
#     
#     def send_actions(self, sleeptime):
#         # get the commited packets and flush the record
#         record = self.get_action_record()
#         self._flush_record()
#         # retrieve the actions in appropriate order
#         clients = sorted(record.iterkeys(), cmp=lambda c1, c2: c1.id - c2.id)
#         actions = [packets.Action.DO_NOTHING] * NUM_PLAYERS
#         for i, c in enumerate(clients[:NUM_PLAYERS]):
#             actions[i] = record[c]
# 
#         turn = 0
#         # create a packet to commit these actions
#         commit_packet = packets.ActionsCommitPacket(turn, actions)
#         response = packets.ResponsePacket(packets.ActionsCommitPacket.TYPE,
#                                             commit_packet.get_raw_data())
#         # send it to every client in the party
#         self.send_to_all(response)
#         
#         time.sleep(sleeptime)


class PartyConnectionHandle(BaseConnectionHandle):
    def _process_client_packet(self, packet):
        """Record any received ingame packet, else ignore it."""
        if self.server.is_ingame:
            self.server.record_packet(packet, self)

class PartyServer(Server):
    """A PartyServer is a waiting room for the players before
    a new game can start. It waits until the room is full, sending the current
    status of the party periodically to all players in the room."""
    ConnectionHandle = PartyConnectionHandle
    SEND_INTERVAL = TURN_LENGTH
    # SEND_INTERVAL = 0.4
    # ID count
    next_id = 0
    
    def __init__(self, address, lobby, bind_and_listen=True, no_init=False, max_players=NUM_PLAYERS):
        super(PartyServer, self).__init__(address, bind_and_listen, no_init)
        if not no_init:
            # assign the next available id and increment the global counter
            self.lobby = lobby
            self.id = self.__class__.next_id
            self.__class__.next_id += 1
            self.max_players = max_players
            self.n_players = 0
            self.is_ingame = False
            # a record of the client actions
            self._action_record = {}
            # a lock to access and update this resource safely
            self._action_record_lock = threading.Lock()
        
    @classmethod
    def create_new(cls, lobby):
        """Creates a new PartyServer, picking any available port
        the OS will give us."""
        # Take the same IP as lobby and let the OS pick a random available port
        ip = lobby.address[0]
        new = cls((ip, 0), lobby)
        # update the address and party info
        new.address = new.socket.getsockname()
        return new
        
    def get_info(self):
        """Returns the PartyInfo object matching this server."""
        idp = self.id
        ip, port = self.address
        # n_players = len(self.get_active_connections())
        n_players = self.n_players
        max_players = self.max_players
        return packets.PartyInfo(idp, ip, port, n_players, max_players)
    
    def handle_connection(self, conn, client_addr):
        """Handle a new client connection."""
        super(PartyServer, self).handle_connection(conn, client_addr)
        self.n_players += 1
        if debug: print str(self.n_players) + " players currently connected"
        if self.n_players == self.max_players:
            self.start_game()
    
    def notice_connection_shutdown(self, handle):
        """This function is called when a connection about to be shut-down."""
        super(PartyServer, self).notice_connection_shutdown(handle)
        self.n_players -= 1
        # shut down the party server if it is ingame and there is no player left
        if self.n_players == 0 and self.is_ingame:
            self.shutdown()
    
    def send_loop(self):
        while True:
            if self.is_ingame:
                if self.n_players != 0:
                    self.send_actions()
                    self.current_turn += 1
                else: # stop the loop if there is no player left
                    break
            else:
                self.send_status()
            time.sleep(self.__class__.SEND_INTERVAL)
    
    def send_status(self):
        """Send to all connected players the current party status
        (# players / # total expected)."""
        # n_players = len(self.get_active_connections())
        packet = packets.PartyStatusPacket(self.n_players, self.max_players).wrap()
        self.send_to_all(packet)
    
    def send_actions(self):
        # get the commited packets and flush the record
        record = self.get_action_record()
        self._flush_record()
        # retrieve the actions in appropriate order
        clients = sorted(record.iterkeys(), cmp=lambda c1, c2: c1.id - c2.id)
        actions = [packets.Action.DO_NOTHING] * NUM_PLAYERS
        for i, c in enumerate(clients[:NUM_PLAYERS]):
            actions[i] = record[c]

        # create a packet to commit these actions
        commit_packet = packets.ActionsCommitPacket(self.current_turn, actions)
        if debug: print commit_packet
        # response = packets.ResponsePacket(packets.ActionsCommitPacket.TYPE,
        #                                             commit_packet.get_raw_data())
        response = commit_packet.wrap()
        # send it to every client in the party
        self.send_to_all(response)
    
    def start_game(self):
        """This function is called when a room is full and starts a new game,
        sending an init packet to all players and becomes an (ingame) party
        server."""
        # send the init packet to all clients
        k = self.max_players
        dturn = self.SEND_INTERVAL * 1000 # (in ms)
        n = BOARD_WIDTH
        m = BOARD_HEIGHT
        # game_map = mapgen.generate(n, m)
        # tiles = game_map.get_tiles()
        tiles = mapgen.generate(n, m)
        poss = [(0, 0), (n - 1, 0), (0, m - 1), (n - 1, m - 1)]
        pID = 0
        self.players = self.get_active_connections()
        for handle in self.players:
            packet = packets.InitPacket(pID, k, dturn, n, m, tiles, poss).wrap()
            handle.send_client(packet)
            pID += 1
        
        # notice the server that this party is full and no longer accepts
        # new clients
        self.lobby.notice_party_shutdown(self)
        
        # morph into the "in-game" server
        self.start_ingame()
    
    def start_ingame(self):
        # self.current_turn = 0
        self.current_turn = 1
        self.is_ingame = True
        # stop accepting new connections
        self.shutdown(silent=True)
        # flush the record
        self._flush_record()
    
    def record_packet(self, packet, client):
        """Save a client action packet in the action record"""
        # process the received packet to retrieve the requested action
        if (packet.type == packets.ActionRequestPacket.TYPE):
            action_packet = packets.ActionRequestPacket.process_raw_data(packet.payload)
        # process the packet if it is not outdated (given turn is the current turn)
        # or if DUMP_OLD_PACKET was set to False
            if self.current_turn == action_packet.turn or (not DUMP_OLD_PACKET):
                action = action_packet.action
                # save the action
                self._action_record_lock.acquire()
                # ------ enter critical section ------
                # if there's no action already committed for this client,
                # comit this action
                # print self._action_record
                #         if (self._action_record.get(client, default=packets.Action.DO_NOTHING)) == packets.Action.DO_NOTHING:
                #             self._action_record = action
                if self._action_record[client] == packets.Action.DO_NOTHING:
                    self._action_record[client] = action
                # else, ignore the packet
                # ------ exit critical section -------
                self._action_record_lock.release()
        # ... or process it anyway if DUMP_OLD_PACKET was set to False
    
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
            for client in self.players
            # for client in self.get_active_connections()
        }
        # ------ exit critical section -------
        self._action_record_lock.release()


# def main():
#     """Main server process"""
#     PORT = 2049 # arbitrary port number to connect on for the chat
#     LOCALHOST = '127.0.0.1' # ip adress of localhost
#     # server = ParrotServer((LOCALHOST, PORT))
#     server = IngamePartyServer((LOCALHOST, PORT))
#     # server.serve_forever()
#     threading.Thread(target=server.serve_forever).start()
#     server.send_actions_periodically()
#     
# if __name__ == "__main__":
#     main()


