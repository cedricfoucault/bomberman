from server import Server
from thread_connection import *
import packets
from gameconst import *
from partyserver import *

import time

class LobbyConnectionHandle(ThreadConnectionHandle):
    """This type of connection will listen for 'create new party' packets
    (type 15) and ignore any other packet."""
    packet_class = packets.GamePacket
    
    def _process_client_packet(self, packet):
        if packet.type == packets.PacketType.CREATE_PARTY:
            self.master.create_party()

class LobbyServer(Server):
    """The lobby server maintains a list of pending parties, and creates a new
    party if it receives a packet of appropriate type by a client.
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
        new_party.do_in_thread(fun=new_party.serve_forever)
        new_party.do_in_thread(fun=new_party.send_loop)
        
        self._parties_lock.acquire()
        # ------ enter critical section ------
        # add the new party server to the list of current pending parties
        self._parties.append(new_party)
        # ------ exit critical section -------
        self._parties_lock.release()
        if VERBOSE: print "new party created"
        
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
    
    def send_loop(self):
        """Periodically send to all clients the list pending parties."""
        while not self.is_shut_down():
            self.send_parties()
            time.sleep(self.__class__.SEND_INTERVAL)
        if VERBOSE: print "stop sending parties"
    
    
