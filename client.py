import socket
import threading
import select
import sys
import packets

class Client(object):
    """Base class for the client"""
    # use IPv4 adresses
    address_family = socket.AF_INET
    # use TCP sockets
    socket_type = socket.SOCK_STREAM
    
    def __init__(self):
        super(Client, self).__init__()
        # the socket that will connect this clioent to a server
        self.socket = socket.socket(self.address_family, self.socket_type)
    
    def connect(self, server_address, server_port):
        """Connect the client
        with the server located at the given address and port"""
        self.socket.connect((server_address, server_port))

