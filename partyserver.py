from server import Server
from thread_connection import *
import packets
from gameconst import *
import mapgen

import time


class PartyConnectionHandle(ThreadConnectionHandle):
    def _process_client_packet(self, packet):
        """Record any received ingame packet, else ignore it."""
        if self.master.is_ingame:
            self.master.record_packet(packet, self)

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
        # if we are using the monitoring tool, we have to launch it on an arbitrary port
        # so that the connection to this server can be delayed, and keep this port in memory
        if USE_MONITORING:
            _, port = new.address
            new.monitoring_port = port + 1
            # open the monitoring tool in a sub-process
            subprocess.Popen(['monitor/monitor', 'tcp', ip, str(port),
                str(new.monitoring_port), str(DELAY), str(JITTER)])
        return new
        
    def get_info(self):
        """Returns the PartyInfo object matching this server."""
        idp = self.id
        ip, port = self.address
        # if we use the montoring tool, give the monitoring port to the clients
        if USE_MONITORING:
            port = self.monitoring_port
        # n_players = len(self.get_active_connections())
        n_players = self.n_players
        max_players = self.max_players
        return packets.PartyInfo(idp, ip, port, n_players, max_players)
    
    def handle_connection(self, conn, client_addr):
        """Handle a new client connection."""
        super(PartyServer, self).handle_connection(conn, client_addr)
        self.n_players += 1
        if VERBOSE: print str(self.n_players) + " players currently connected"
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
        if DEBUG: print commit_packet
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
            action_packet = packets.ActionRequestPacket.decode(packet.payload)
        # process the packet if it is not outdated (given turn is the current turn)
        # or if DUMP_OLD_PACKET was set to False
            if self.current_turn == action_packet.turn or (not DUMP_OLD_PACKET):
                action = action_packet.action
                # save the action
                self._action_record_lock.acquire()
                # ------ enter critical section ------
                # if there's no action already committed for this client,
                # comit this action
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
            for client in self.players
            # for client in self.get_active_connections()
        }
        # ------ exit critical section -------
        self._action_record_lock.release()
