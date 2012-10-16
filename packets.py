import socket
import struct
import socket_utils
import inspect
import enum

NUM_PLAYERS = 4

def get_user_attributes(cls):
    boring = dir(type('dummy', (object,), {}))
    return [item
            for item in inspect.getmembers(cls)
            if item[0] not in boring and not callable(getattr(cls, item[0]))]

Action = enum.enum("Action",
    ERROR = 0,
    DEATH = 1,
    
    DO_NOTHING = 16,
    MOVE_RIGHT = 17,
    MOVE_UP    = 18,
    MOVE_LEFT  = 19,
    MOVE_DOWN  = 20,
    
    POSE_BOMB  = 32
)

PacketType = enum.enum("PacketType",
    ACTION = 42
)

# class Action:
#     ERROR = 0
#     DEATH = 1
#     
#     DO_NOTHING = 16
#     MOVE_RIGHT = 17
#     MOVE_UP    = 18
#     MOVE_LEFT  = 19
#     MOVE_DOWN  = 20
#     
#     POSE_BOMB  = 32
#     
#     @classmethod
#     def to_str(cls, action):
#         return cls.str_values[action]
#         # the str_values dict is created just after the class declaration
#         # and defined below
# 
# # str_values is a dictionary that matches an action with its string representation
# # (e.g. str_values[32] == "pose bomb")
# Action.str_values = dict( (value, name.lower().replace('_', ' '))
#     for name, value in get_user_attributes(Action)
# )
# 
# class PacketType:
#     ACTION = 42
#     
#     @classmethod
#     def to_str(cls, action):
#         return cls.str_values[action]
#         
# PacketType.str_values = dict( (value, name.lower().replace('_', ' '))
#     for name, value in get_user_attributes(PacketType)
# )


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
    
    def __repr__(self):
        return "(%s | %s)" % (repr(self.turn), repr(self.action))
        
    def __str__(self):
        return "(turn: %s | action: %s)" % (str(self.turn), Action.to_str(self.action))
    
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
    
    def __repr__(self):
        return "(%s | %s)" % (repr(self.turn), repr(self.actions))
        
    def __str__(self):
        actions_str = ["player %d: %s" % (index + 1, Action.to_str(action))
            for index, action in enumerate(self.actions)
        ]
        return "(turn: %s | actions: (%s))" % (str(self.turn), ", ".join(actions_str))
    
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
        
    def __repr__(self):
        return "(%s | %s)" % (repr(self.type), repr(self.payload))
        
    def __str__(self):
        return "(type: %s | payload: %s)" % (PacketType.to_str(self.type), str(self.payload))
    
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

        