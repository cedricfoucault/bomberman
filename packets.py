import socket
import struct
import socket_utils

NUM_PLAYERS = 4

class ActionRequestPacket:
    """An action packet is composed of:
    - the turn number when the action was requested 
    (a 4-byte unsigned integer, little endian)
    - the action (turn left, drop bomb, etc...)
    represented by a single byte unsigned integer"""
    TYPE = 42
    SIZE = 5
    
    def __init__(self, turn, action):
        self.turn = turn
        self.action = action
    
    def get_raw_data(self):
        return struct.pack("<IB", self.turn, self.action)
    
    @classmethod
    def process_raw_data(cls, data):
        turn, action = struct.unpack("<IB", data)
        return cls(turn, action)

class ActionsCommitPacket:
    """An actions commit packet is composed of:
    - the turn number when the actions are to be committed
    (a 4-byte unsigned integer, little endian)
    - the list of actions performed by each player
    (each action being represented by a single bye unsigned integer)"""
    TYPE = 42
    SIZE = 4 + NUM_PLAYERS
    
    def __init__(self, turn, actions):
        self.turn = turn
        self.actions = actions
    
    def get_raw_data(self):
        return struct.pack('<I' + 'B' * NUM_PLAYERS, self.turn, *self.actions)
        
    @classmethod
    def process_raw_data(cls, data):
        items = struct.unpack('<I' + 'B' * NUM_PLAYERS, data)
        turn = items[0]
        actions = items[1 : NUM_PLAYERS]
        return cls(turn, actions)

class PacketMismatch(Exception): 
    """Exception raised for errors on a packet's data format."""
    pass

class GamePacket:
    """A game packet is composed of a packet type header (a single byte integer)
    and a payload (raw data)"""
    packet_classes = {} # may be overriden by derived classes
    
    def __init__(self, ptype, payload):
        self.type = ptype
        self.payload = payload

    def send(self, socket):
        packet = struck.pack("B", self.ptype) + self.payload
        socket_utils.send(socket, packet)
            
    @classmethod
    def recv(cls, socket):
        # read the packet's type
        ptype = cls._read_type(socket)
        # read the packet's payload
        if ptype not in cls.packet_classes:
            # raise a PacketMismatch exception
            # if the type read was not any of the expected type
            valid_ptypes = [str(pt) for pt in cls.packet_classes.keys()]
            err_msg = "Packet type not recognized.\n"
            err_msg += "Received: %d" % ptype
            err_msg += "Expected: %s" % (" or ".join(valid_ptypes))
            raise PacketMismatch(err_msg)
        else:
            # the payload's length is inferred from the packet's type
            payload = socket_utils.recv(socket, cls.packet_classes[ptype].SIZE)
        # return a new packet instance
        return cls(ptype, payload)
        
    @classmethod
    def _read_type(cls, socket):
        # the first byte of the packet should index its type
        ptype = socket.recv(1)
        if not t:
            raise socket.error("socket connection broken")
        else:
            return ptype


class RequestPacket(GamePacket):
    """A request packet is a game packet designed to be a client request
    to server"""
    packet_classes = {
        42: ActionRequestPacket
    }

class ResponsePacket(GamePacket):
    """A commit packet is a game packet designed to be a server response"""
    packet_classes = {
        42: ActionsCommitPacket
    }

        