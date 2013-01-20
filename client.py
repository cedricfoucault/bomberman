import socket
import threading
import select
import sys
import packets
import time
import random

class Client(object):
    """Base class for the client"""
    # use IPv4 adresses
    address_family = socket.AF_INET
    # use TCP sockets
    socket_type = socket.SOCK_STREAM
    
    def __init__(self):
        super(Client, self).__init__()
        # the socket that will connect this client to a server
        self.socket = socket.socket(self.address_family, self.socket_type)
    
    def connect(self, server_address, server_port):
        """Connect the client
        with the server located at the given address and port"""
        self.socket.connect((server_address, server_port))
        
    def send_server(self, packet):
        """Send a packet to the server"""
        packet.send(self.socket)
        

def main():
    """Main client process"""
    PORT = 2049 # arbitrary port number to connect on for the chat
    LOCALHOST = '127.0.0.1' # ip adress of localhost
    client = Client()
    client.connect(LOCALHOST, PORT)
    print "connected"
    while True:
        spacket = packets.RequestPacket.random()
        client.send_server(spacket)
        print "Sent: " + str(spacket)
        # rpacket = packets.RequestPacket.recv(client.socket)
        rpacket = packets.ResponsePacket.recv(client.socket)
        print "Received: " + str(rpacket)
        # time.sleep(random.randint(1, 5))

if __name__ == "__main__":
    main()


