import packets
import socket_utils
from gameconst import *
from task_connection import TaskConnectionHandle

from direct.showbase.ShowBase import ShowBase
from direct.showbase import DirectObject
from direct.gui.DirectGui import *

import socket
import select
import sys
import os

class LobbyClientConnectionHandle(TaskConnectionHandle):
    """Class for client to lobby connections."""

    def __init__(self, conn, addr, client, start=True):
        super(LobbyClientConnectionHandle, self).__init__(conn, addr, start)
        self.client = client # a reference to the client owning the connection

    def _process_packet(self, packet):
        """Get the current parties with their status from the received packet.
        Update the client's list of parties accordingly."""
        if packet.type == packets.PacketType.LOBBY:
            packet = packets.LobbyPacket.process_raw_data(packet.payload)
            self.client.update_parties(packet.parties)

    def _do_on_shutdown(self):
        """On shutdown, notice the client."""
        super(LobbyClientConnectionHandle, self)._do_on_shutdown()
        self.client.notice_connection_shutdown(self)

class LobbyClient(object, ShowBase):
    """Class for the lobby client."""
    # use IPv4 adresses
    address_family = socket.AF_INET
    # use TCP sockets
    socket_type = socket.SOCK_STREAM
    
    def __init__(self, partyfile):
        ShowBase.__init__(self)
        super(LobbyClient, self).__init__()
        # the connection handle to the server
        self.conn = None
        # the list of buttons for the current pending parties
        # (fetched from the lobby server)
        self.buttons = []
        self.key_handler = LobbyKeyHandler(self)
        self.partyfile = partyfile
        base.setBackgroundColor(0.0, 0.0, 0.0)
    
    def connect(self, addr):
        """Connect the client with the server located at the given address."""
        sock = socket.socket(self.address_family, self.socket_type)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.connect(addr)
        if VERBOSE: print "Connected to " + str(addr)
        self.conn = LobbyClientConnectionHandle(sock, addr, self)
    
    def notice_connection_shutdown(self, handle):
        if VERBOSE: print "The connection to " + str(handle.addr) + " was shut down\nQuitting..."
        self.quit()
    
    def send_create_party_request(self):
        """Send a create party request to the server."""
        createparty_packet = packets.CreatePartyPacket().wrap()
        self.conn.send(createparty_packet)
        
    def create_button(self, label, action, args, y_top):
        y_text = y_top - 0.06
        b = DirectButton(text=label,
            command=action,
            extraArgs=args,
            text_pos=(0, y_text, 0),
            text_fg=(0, 0, 0, 1.0),
            text_scale=0.05,
            frameSize=(-0.4, 0.4, y_top - 0.1, y_top),
            textMayChange=1)
        self.buttons.append(b)
        
    def update_parties(self, parties):
        """Update, add, remove the appropriate party buttons"""
        # update or add the party buttons
        for i, p in enumerate(parties):
            label = "party %d: %d/%d" % (p.id, p.n_players, p.max_players)
            action = self.connect_to_party
            args = ((p.ip, p.port), )
            if i < len(self.buttons):
                self.buttons[i]['text'] = label
                self.buttons[i]['command'] = action
                self.buttons[i]['extraArgs'] = args
            else:
                y_top = 0.9 - i * 0.15
                self.create_button(label, action, args, y_top)
        # remove the out-of-range party buttons
        for i in xrange(len(parties), len(self.buttons)):
            self.buttons[i].destroy()
        self.buttons = self.buttons[:len(parties)]
    
    def connect_to_party(self, addr):
        ip, port = addr
        self.partyfile.write("%s\n" % ip)
        self.partyfile.write("%d\n" % port)
        if VERBOSE: print "quitting lobby client"
        self.quit()
    
    def quit(self):
        self.shutdown()
        self.userExit()
    

class LobbyKeyHandler(DirectObject.DirectObject):
    def __init__(self, master):
        # keep reference to the game controller and "me" player
        self.master = master
        # init the handler send the actions corresponding to the key pressed
        self.accept('c', self.create_party)
    
    def create_party(self):
        self.master.send_create_party_request()
    
    def destroy(self):
        """Get rid of this handler"""
        self.ignoreAll()
        

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print "Usage: lobbyclient server_ip server_port party_fd"
        sys.exit(-1)
    # the server ip and port to connect on
    ip = sys.argv[1]
    port = int(sys.argv[2])
    # we will write the party server address to connect on in this file
    # this file will be read by the parent process
    party_file = os.fdopen(int(sys.argv[3]), 'w')
    # instance the lobby client with the given file
    lobbyclient = LobbyClient(party_file)
    lobbyclient.connect((ip, port))
    lobbyclient.run()
    

