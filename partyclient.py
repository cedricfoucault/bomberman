from gameconst import *
from direct.showbase.ShowBase import ShowBase
from direct.showbase import DirectObject
from direct.actor.Actor import Actor
from direct.task import Task
from panda3d.core import *
from direct.gui.DirectGui import *
from direct.gui.OnscreenText import OnscreenText
from direct.task import Task
import game

from task_connection import TaskConnectionHandle
import packets
import socket
import socket_utils
import select
import sys


class PartyClientConnectionHandle(TaskConnectionHandle):
    """Class for client to party-server connections."""
    
    def __init__(self, conn, addr, client, start=True):
        super(PartyClientConnectionHandle, self).__init__(conn, addr, start)
        self.client = client # a reference to the client owning the connection
    
    def _process_packet(self, packet):
        if self.client.is_ingame:
            self._process_ingame_packet(packet)
        else:
            self._process_pending_packet(packet)
    
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
            self.client.controller.execute_turn(actions_packet.turn, actions_packet.actions)
    
    def _do_on_shutdown(self):
        """On shutdown, notice the client."""
        super(PartyClientConnectionHandle, self)._do_on_shutdown()
        self.client.notice_connection_shutdown(self)

class PartyClient(object, ShowBase):
    # use IPv4 adresses
    address_family = socket.AF_INET
    # use TCP sockets
    socket_type = socket.SOCK_STREAM
    
    def __init__(self):
        ShowBase.__init__(self)
        # the connection handle to the server
        self.conn = None
        # the game controller for the client
        # initally None, but it will be set when the game starts
        self.controller = None
        # self.key_handler = PartyKeyHandler(self)
        # boolean flag to tell if the game has started
        self.is_ingame = False
        # init the world view
        self.init_window()
        
    
    def init_window(self):
        # set the background
        base.setBackgroundColor(0.0, 0.0, 0.0)
        # set a text info on top of the screen to tell the current party status
        # (i.e. number of players connected / total expected)
        self.status_text = OnscreenText(text='connecting...',
            pos=(0.0, 0.9),
            scale=0.1,
            fg=(1.0, 1.0, 1.0, 1.0),
            mayChange=True)
    
    def connect(self, addr):
        """Connect the client with the server located at the given address."""
        sock = socket.socket(self.address_family, self.socket_type)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.connect(addr)
        if VERBOSE: print "Connected to " + str(addr)
        self.conn = PartyClientConnectionHandle(sock, addr, self)
    
    def update_party_status(self, status):
        """Update the current party status info"""
        text = "status: %d/%d" % (status.n_players, status.max_players)
        self.update_status_text(text)
        
    def update_status_text(self, text):
        """Update the status text displayed above on the screen"""
        self.status_text.setText(text)
    
    def start_game(self, init):
        """Start the game with the given initialization packet"""
        text = "status: %d/%d" % (init.n_players, init.n_players)
        self.update_status_text(text)
        self.controller = game.GameController(self, init.width, init.height,
            init.turn_length, init.tiles, init.positions, init.player_ID)
        self.is_ingame = True
    
    def send_action_request(self, action):
        """Send an action request packet to the server."""
        action_packet = packets.ActionRequestPacket(self.controller.turn, action).wrap()
        self.conn.send(action_packet)
    
    def notice_connection_shutdown(self, handle):
        if VERBOSE: print "The connection to " + str(handle.addr) + " was shut down\nQuitting..."
        self.quit()
        
    def quit(self):
        """Quit the client, shutting down the whole process."""
        self.shutdown()
        self.userExit()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print "Usage: partyclient server_ip server_port"
        sys.exit(-1)
    
    ip = sys.argv[1]
    port = int(sys.argv[2])
    partyclient = PartyClient()
    partyclient.connect((ip, port))
    partyclient.run()

