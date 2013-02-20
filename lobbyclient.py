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
    

# class TaskShutdownMixIn(object):
#     """Mix-In class to execute a task to be called once each frame
#     until a shutdown request is emitted"""
#     
#     def __init__(self):
#         # Flag to tell if this task has been shutdown
#         self._is_shut_down = False
#             
#     def do_task(self, fun, time_interval=None, name='No Name'):
#         """Add to the task manager a task which calls fun().
#         If time_interval is given, the task will be done once each
#         time_interval seconds, otherwise it will be done once each frame."""
#         self._is_shut_down = False
#         if time_interval:
#             def fun_task(task):
#                 fun()
#                 return Task.again
#             self.task = taskMgr.doMethodLater(time_interval, fun_task, name)
#         else:
#             def fun_task(task):
#                 fun()
#                 return Task.cont
#             self.task = taskMgr.add(fun_task, name)
#     
#     def _do_on_shutdown(self):
#         """This function is called just before the process is shut-downed.
#         
#         May be overriden"""
#         pass
#         
#     def shutdown(self, silent=False):
#         """Stop the server from accepting new connections"""
#         # if the silent option is true, the process will be shut down
#         # without calling the usual _do_on_shutdown
#         taskMgr.remove(self.task)
#         self._is_shut_down = True
#         if not silent:
#             self._do_on_shutdown()
#     
#     def is_shut_down(self):
#         return self._is_shut_down

# class TaskConnectionHandle(TaskShutdownMixIn):
#     """Base class for connection handles, using Panda3D tasks.
#     A connection handle is an object that identifies a client-server connection,
#     other processes will use this object as an interface."""
#     # time interval between poll checks (in s)
#     # if this is 0, the poll checks will be done once every frame
#     poll_interval = 0
#     # the packet received from this connection should be read as instances of this class
#     packet_class = packets.GamePacket
#     
#     def __init__(self, conn, addr, start=True, no_init=False):
#         super(TaskConnectionHandle, self).__init__()
#         if not no_init:
#             self.conn        = conn # the socket for the connection
#             self.addr        = addr # the socket's destination address
#             self.packet_to_send = None # a "buffer" where the packet to send
#                                        # will be put
#             if start:
#                 self.start_handling()
# 
#     def start_handling(self):
#         """Start processing (polling) the connection"""
#         if VERBOSE: print "handling " + str(self.addr)
#         self.do_task(self._poll, self.poll_interval)
#     
#     def _poll(self):
#         """Poll this connection non-blockingly.
#         Check if there are data to read from the connection
#         and, if there are data to send, attempt to send them."""
#         # read poll
#         self._poll_read()
#         # write poll
#         if self.packet_to_send:
#             was_sent = self._poll_write(self.packet_to_send)
#             if was_sent: self.packet_to_send = None
#     
#     def _poll_write(self, packet):
#         """Check if data can be sent through the connected socket, and if yes,
#         send whatever is to be sent.
#         Returns True if data has been sent, False otherwise."""
#         # check if data can be sent
#         ready_to_write = select.select([], [self.conn], [], 0)[1]
#         if self.conn in ready_to_write:
#             try:
#                 # try to send the packet
#                 packet.send(self.conn)
#                 if PRINT_PACKETS: print "Sent " + str(packet) + " to " + str(self.addr)
#                 return True
#             except socket.error, e:
#                 # if the connection was closed on the client side,
#                 # shut down the process
#                 if debug: print >> sys.stderr, str(e)
#                 self.shutdown()
#                 return False
#         else:
#             return False
#     
#     def _poll_read(self):
#         """Check if there are some data to read from the connection, and if yes,
#         read it."""
#         # check there are some data to read
#         ready_to_read = select.select([self.conn], [], [], 0)[0]
#         if self.conn in ready_to_read:
#             # read it
#             try:
#                 # try to read the packet
#                 packet = self.__class__.packet_class.recv(self.conn)
#                 if debug: print "Received: " + str(packet) + " from " + str(self.addr)
#                 # process it
#                 self._process_packet(packet)
#             except socket.error, e:
#                 # if the connection was closed on the client side,
#                 # shut down the process
#                 if debug: print >> sys.stderr, str(e)
#                 self.shutdown()
#             except packets.PacketMismatch, e:
#                 if debug: print >> sys.stderr, str(e)
# 
#     def _process_packet(self, packet):
#         """Process a packet which was received from this connection.
#         May be overriden."""
#         pass
#         
#     def _do_on_shutdown(self):
#         """On shutdown, properly close the socket."""
#         if debug: print "shutting down " + str(self.addr)
#         self.close_connection()
# 
#     def close_connection(self):
#         """Close the socket doing the connection"""
#         socket_utils.shutdown_close(self.conn)
#     
#     def send(self, packet):
#         """Send a packet to the other end of the connection.
#         This function actually just poses a request to send the given packet,
#         it will be send on the next write poll if the socket is available.
#         It overrides any previous send request which has not been processed."""
#         self.packet_to_send = packet


