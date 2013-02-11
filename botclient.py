import packets
import socket
import socket_utils
import sys
import time

debug = True

class BotClient(object):
    """Class for the lobby client."""
    # use IPv4 adresses
    address_family = socket.AF_INET
    # use TCP sockets
    socket_type = socket.SOCK_STREAM
    # time interval to print current pendingparties
    PRINT_INTERVAL = 3
    
    def __init__(self):
        super(BotClient, self).__init__()
    
    def connect(self, addr):
        """Connect the client with the server located at the given address."""
        sock = socket.socket(self.address_family, self.socket_type)
        sock.connect(addr)
        if debug: print "Connected to " + str(addr)
        self.sock = sock
        
    def reconnect(self, addr):
        self.close_connection()
        self.connect(addr)
    
    def get_party_addr(self, party_no):
        """Get the server address of the party under the given no"""
        # Get the first incoming packet from the lobby
        p = packets.GamePacket.recv(self.sock)
        if p.type == packets.LobbyPacket.TYPE:
            # find the party under the given no and return its address
            p = packets.LobbyPacket.process_raw_data(p.payload)
            for party in p.parties:
                if party.id == party_no:
                    return (party.ip, party.port)
        # return False if the party was not found, 
        return False
            
    def close_connection(self):
        if debug: print "Shutting down connection with " + str(self.sock.getpeername())
        socket_utils.shutdown_close(self.sock)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print "Usage: lobbyclient server_ip server_port party_no"
        sys.exit(-1)
    # the lobby server ip and port to connect on
    ip = sys.argv[1]
    port = int(sys.argv[2])
    # the party id (no) to connect to
    party_no = int(sys.argv[3])
    # instance the bot
    bot = BotClient()
    # connect to the lobby
    bot.connect((ip, port))
    # find the party server address
    addr = bot.get_party_addr(party_no)
    if addr:
        # connect to the party server
        bot.reconnect(addr)
        # wait forever or until the connection is shut down by the server
        try:
            while True: packets.GamePacket.recv(bot.sock)
        except socket.error, e:
            # if the connection was shut down, stop the bot
            pass
    else:
        print "no party found"
