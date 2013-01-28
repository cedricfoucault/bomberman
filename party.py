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
    SEND_INTERVAL = 1
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
    
    def send_loop(self):
        if self.is_ingame:
            self.send_actions()
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

        turn = 0
        # create a packet to commit these actions
        commit_packet = packets.ActionsCommitPacket(turn, actions)
        response = packets.ResponsePacket(packets.ActionsCommitPacket.TYPE,
                                            commit_packet.get_raw_data())
        # send it to every client in the party
        self.send_to_all(response)
    
    def start_game(self):
        """This function is called when a room is full and starts a new game,
        sending an init packet to all players and becomes an (ingame) party
        server."""
        # send the init packet to all clients
        pID = 0
        k = self.max_players
        dturn = IngamePartyServer.SEND_INTERVAL * 1000 # (in ms)
        n = BOARD_WIDTH
        m = BOARD_HEIGHT
        game_map = mapgen.generate(n, m)
        tiles = game_map.get_tiles()
        poss = [(0, 0), (n - 1, 0), (0, m - 1), (n - 1, m - 1)]
        for handle in self.get_active_connections():
            tiles = game_map.get_tiles()
            packet = packets.InitPacket(pID, k, dturn, n, m, tiles, poss).wrap()
            handle.send_client(packet)
            pID += 1
            
        # notice the server that this party is full and no longer accepts
        # new clients
        self.lobby.notice_party_shutdown(self)
        
        # morph into the "in-game" server
        self.start_ingame()
    
    def start_ingame(self):
        # stop accepting new connections
        self.shutdown(silent=True)
        self.is_ingame = True
    
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
        if self._action_record.get(client, packets.Action.DO_NOTHING) == packets.Action.DO_NOTHING:
            self._action_record = action
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

