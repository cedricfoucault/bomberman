import server
import socket
import socket_utils
import threading
import select
import sys
import packets
import time
import random
import threading

# debug = True
debug = False

class ConnectionHandle(server.ShutdownMixIn):
    """Base class for connection handles.
    A connection handle is an object that identifies a client-server connection,
    other processes will use this object as an interface."""
    # tells whether the connection should be shut down when the main thread is done
    daemon_threads = False
    # time interval between checks to a shutdown request (in secs)
    poll_interval = 0.5
    # the packet received from this connection should be read as instances of this class
    packet_class = packets.GamePacket
    
    def __init__(self, conn, addr, start=True, no_init=False):
        super(ConnectionHandle, self).__init__()
        if not no_init:
            self.conn        = conn # the socket for the connection
            self.addr        = addr # the socket's destination address
            self.thread      = threading.Thread( # the receiver thread
                target=self._process_connection,
                  args=()
            )
            self.thread.daemon = self.__class__.daemon_threads
            # a lock preventing two threads from sending at the same time
            self._write_lock  = threading.Lock()
            if start:
                self.start_handling()

    def start_handling(self):
        """Start processing the connection"""
        if debug: print "handling " + str(self.addr)
        self.thread.start()
        
    def _process_connection(self, poll_interval=poll_interval):
        """Function to be run in a new thread while the connection is active"""
        self.do_while_not_shut_down(iter_fun=self._process_connection_iter)
        
    def _process_connection_iter(self):
        """Processing done in one iteration of the processing loop"""
        # wait to receive a new packet
        ready_to_read = select.select([self.conn], [], [], self.__class__.poll_interval)[0]
        if self.conn in ready_to_read:
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
                self.shutdown(non_blocking=True)
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
        """Send a packet to the other end of the connection"""
        self._write_lock.acquire()
        # ------ enter critical section ------
        # send the packet through the connected socket
        try:
            packet.send(self.conn)
            if debug: print "Sent " + str(packet) + " to " + str(self.addr)
        except socket.error, e:
            if debug: print >> sys.stderr, str(e)
            self.shutdown(non_blocking=True)
        # ------ exit critical section -------
        self._write_lock.release()

class LobbyClientConnectionHandle(ConnectionHandle):
    """Class for client to lobby connections."""

    def __init__(self, conn, addr, client, start=True, no_init=False):
        super(LobbyClientConnectionHandle, self).__init__(conn, addr, start, no_init)
        if not no_init:
            self.client = client # a reference to the client owning the connection

    def _process_packet(self, packet):
        """Get the current parties with their status from the received packet.
        Update the client's list of parties accordingly."""
        if packet.type == packets.PacketType.LOBBY:
            packet = packets.LobbyPacket.process_raw_data(packet.payload)
            self.client.update_parties(packet.parties)

    def _do_on_shutdown(self):
        """On shutdown, notice the client."""
        self.client.notice_connection_shutdown(self)
        super(LobbyClientConnectionHandle, self)._do_on_shutdown()

class PendingPartyClientConnectionHandle(ConnectionHandle):
    """Class for client to pending party connections."""
    
    def __init__(self, conn, addr, client, start=True, no_init=False):
        super(PendingPartyClientConnectionHandle, self).__init__(conn, addr, start, no_init)
        if not no_init:
            self.client = client # a reference to the client owning the connection
    
    def _process_packet(self, packet):
        if self.client.is_ingame:
            self._process_ingame_packet(packet)
        else:
            self._process_pending_packet(packet)
        # if packet.type == packets.PacketType.PARTY_STATUS:
        #             party_status = packets.PartyStatusPacket.process_raw_data(packet.payload)
        #             self.client.update_party_status(party_status)
        #         elif packet.type == packets.PacketType.INIT:
        #             init_packet = packets.InitPacket.process_raw_data(packet.payload)
        #             self.client.start_game(init_packet)
    
    def _process_pending_packet(self, packet):
        """Get either the party status or the game initialization
        from the received packet.
        Update the client's observed party status accordingly or
        tell the client to start the game."""
        if packet.type == packets.PacketType.PARTY_STATUS:
            party_status = packets.PartyStatusPacket.process_raw_data(packet.payload)
            self.client.update_party_status(party_status)
        elif packet.type == packets.PacketType.INIT:
            init_packet = packets.InitPacket.process_raw_data(packet.payload)
            self.client.start_game(init_packet)
    
    def _process_ingame_packet(self, packet):
        """Get the actions and the turn number from the received packet and
        ask the client to commit them."""
        if packet.type == packets.PacketType.ACTION:
            actions_packet = packets.ActionsCommitPacket.process_raw_data(packet.payload)
            self.client.commit_actions(actions_packet.turn, actions_packet.actions)
    
    def _do_on_shutdown(self):
        """On shutdown, notice the client."""
        self.client.notice_connection_shutdown(self)
        super(PendingPartyClientConnectionHandle, self)._do_on_shutdown()

class LobbyClient(server.ShutdownMixIn):
    """Class for the lobby client."""
    # use IPv4 adresses
    address_family = socket.AF_INET
    # use TCP sockets
    socket_type = socket.SOCK_STREAM
    # time interval to print current pendingparties
    PRINT_INTERVAL = 3
    
    def __init__(self):
        super(LobbyClient, self).__init__()
        # the current pending parties (fetched from the lobby server)
        self._parties = []
        # a read/write lock to this resource
        self._parties_lock = threading.Lock()
        self.conn = None
    
    def connect(self, addr):
        """Connect the client with the server located at the given address."""
        sock = socket.socket(self.address_family, self.socket_type)
        sock.connect(addr)
        if debug: print "Connected to " + str(addr)
        self.conn = LobbyClientConnectionHandle(sock, addr, self)
    
    def notice_connection_shutdown(self, handle):
        print "The connection to " + str(handle.addr) + " was shut down\nQuitting..."
        self.shutdown(non_blocking=True)
    
    # def reconnect(self, server_address, server_port):
    #         socket_utils.shutdown_close(self.socket)
    #         self.socket = socket.socket(self.address_family, self.socket_type)
    #         self.socket.connect((server_address, server_port))
    
    def send_create_party_request(self):
        """Send a create party request to the server."""
        createparty_packet = packets.CreatePartyPacket().wrap()
        self.conn.send(createparty_packet)
    
    # def recv_server_packet(self):
    #     packet = packets.GamePacket.recv(self.socket)
    #     self._process_server_packet(packet)
    #     return packet
    # 
    # def _process_server_packet(self, packet):
    #     if packet.type == packets.LobbyPacket.TYPE:
    #         packet = packets.LobbyPacket.process_raw_data(packet.payload)
    #         return packet
    
    def get_parties(self):
        self._parties_lock.acquire()
        # ------ enter critical section ------
        parties = list(self._parties)
        # ------ exit critical section -------
        self._parties_lock.release()
        return parties
    
    def update_parties(self, parties):
        self._parties_lock.acquire()
        # ------ enter critical section ------
        self._parties = parties
        # ------ exit critical section -------
        self._parties_lock.release()
    
    def print_parties_periodically(self):
        self.do_while_not_shut_down(
            iter_fun=self.print_parties,
            args=(self.PRINT_INTERVAL, )
        )
    
    def print_parties(self, sleeptime):
        print self.get_parties()
        time.sleep(sleeptime)
    
    def _do_on_shutdown(self):
        if self.conn: self.conn.shutdown()
    

class PartyClient(server.ShutdownMixIn):
    """Class for the party client."""
    # use IPv4 adresses
    address_family = socket.AF_INET
    # use TCP sockets
    socket_type = socket.SOCK_STREAM
    # time interval to print current pendingparties
    PRINT_INTERVAL = 3
    
    def __init__(self):
        super(PartyClient, self).__init__()
        # the status of the party this client joined
        self._party_status = []
        # a read/write lock to this resource
        self._party_status_lock = threading.Lock()
        # boolean flag to switch to ingame
        self.is_ingame = False
        self.conn = None
    
    def connect(self, addr):
        """Connect the client with the server located at the given address."""
        sock = socket.socket(self.address_family, self.socket_type)
        sock.connect(addr)
        if debug: print "Connected to " + str(addr)
        self.conn = PendingPartyClientConnectionHandle(sock, addr, self)
    
    def start_game(self, init_packet):
        self.is_ingame = True
    
    def notice_connection_shutdown(self, handle):
        print "The connection to " + str(handle.addr) + " was shut down\nQuitting..."
        self.shutdown(non_blocking=True)
    
    def get_party_status(self):
        self._party_status_lock.acquire()
        # ------ enter critical section ------
        party_status = self._party_status
        # ------ exit critical section -------
        self._party_status_lock.release()
        return party_status
    
    def update_party_status(self, status):
        self._party_status_lock.acquire()
        # ------ enter critical section ------
        self._party_status = status
        # ------ exit critical section -------
        self._party_status_lock.release()
    
    def print_party_status_periodically(self):
        self.do_while_not_shut_down(
            iter_fun=self.client_loop,
            args=(self.PRINT_INTERVAL, )
        )
    
    def client_loop(self, sleeptime):
        if self.is_ingame:
            pass
        else:
            self.print_party_status()
        time.sleep(sleeptime)
    
    def print_party_status(self):
        print self.get_party_status()
    
    def print_turn(self):
        print self.turn
    
    def _do_on_shutdown(self):
        if self.conn: self.conn.shutdown()
    
    def commit_actions(self, turn, actions):
        self.turn = turn
    

def main():
    """Main client process"""
    PORT = 42042 # arbitrary port number to connect on for the chat
    LOCALHOST = '127.0.0.1' # ip adress of localhost
    # ip = LOCALHOST
    ip = '192.168.1.2'
    client = LobbyClient()
    client.connect((ip, PORT))
    print_thread = threading.Thread(
        target=client.print_parties_periodically
    )
    print_thread.start()
    # time.sleep(4)
    client.send_create_party_request()
    time.sleep(4)
    # client.send_create_party_request()
    # time.sleep(4)
    
    party = client.get_parties()[0]
    client.shutdown()
    
    if debug: print "connect to party"
    party_client = PartyClient()
    party_client.connect((party.ip, party.port))
    party_client.print_party_status_periodically()
    
    # createparty_packet = packets.CreatePartyPacket().wrap()
    # while True:
    #         # spacket = packets.RequestPacket.random()
    #         client.send_server(createparty_packet)
    #         print "Sent: " + str(createparty_packet)
    #         # rpacket = packets.RequestPacket.recv(client.socket)
    #         lobbypacket = client.recv_server_packet()
    #         print "Received: " + str(lobbypacket)
    #         time.sleep(random.randint(1, 5) / 10)
    # client.send_server(createparty_packet)
    # print "Sent: " + str(createparty_packet)
    # time.sleep(2)
    # packet = client.recv_server_packet()
    # print "Received: " + str(packet)
    # assert packet.type == packets.LobbyPacket.TYPE
    # lobbypacket = packets.LobbyPacket.process_raw_data(packet.payload)
    # assert lobbypacket.n_parties > 0
    # partyinfo = lobbypacket.parties[0]
    # print "connect to (%s, %d)" % (partyinfo.ip, partyinfo.port)
    # client.reconnect(partyinfo.ip, partyinfo.port)
    # print "wait for packet"
    # packet = client.recv_server_packet()
    # print "Received: " + str(packet)

if __name__ == "__main__":
    main()

