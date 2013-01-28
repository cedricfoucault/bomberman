import socket
import struct
import socket_utils
import inspect
import enum
import random
from gameconst import *

UINT32_MAX = pow(2, 32) - 1

def get_user_attributes(cls):
    boring = dir(type('dummy', (object,), {}))
    return [item
            for item in inspect.getmembers(cls)
            if item[0] not in boring and not callable(getattr(cls, item[0]))]

PacketType = enum.enum("PacketType",
    LOBBY = 1,
    CREATE_PARTY = 15,

    PARTY_STATUS = 21,
    INIT = 32,

    ACTION = 42
)

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

TileContent = enum.enum("TileContent",
    FREE = 0,
    SOFT_BLOCK = 1,
    HARD_BLOCK = 2,
    BOMB = 3
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

class PartyInfo(object):
    """Represents a pending party, waiting for players"""
    SIZE = struct.calcsize("<IBBBBHII")
    
    def __init__(self, idp, ip, port, n_players, max_players):
        self.id = idp
        self.ip = ip
        self.port = port
        self.n_players = n_players
        self.max_players = max_players

    def __repr__(self):
        return "(%d | (%s, %d) | %d / %d)" % (self.id, self.ip, self.port,
            self.n_players, self.max_players)

    def __str__(self):
        return "(id: %d | address: (%s, %d) | %d player(s) / %d max)" % (
            self.id, self.ip, self.port, self.n_players, self.max_players)

    def encode(self):
        """Encode a single party"""
        data = struct.pack("<I", self.id)
        data += socket.inet_aton(self.ip)
        data += struct.pack("<HII", self.port, self.n_players, self.max_players)
        return data
        # return (struct.pack("<I", self.id) + socket.inet_aton(self.ip) +
        #             struct.pack("<H<I<I", self.port, self.n_players, self.max_players))
    
    @classmethod
    def decode(cls, data):
        idp = struct.unpack("<I", data[:4])[0]
        ip = socket.inet_ntoa(data[4:8])
        port, n_p, max_p = struct.unpack("<HII", data[8:])
        # idp, ip, port, n_p, max_p = struct.unpack("<IBBB<H<I<I", data)
        return cls(idp, ip, port, n_p, max_p)
    

class SubPacket(object):
    # TYPE
    def wrap(self):
        return GamePacket(self.TYPE, self.get_raw_data())
        
    

class LobbyPacket(SubPacket):
    """A lobby packet is composed of:
    - a 4-byte integer for the number of pending parties
    - for each pending party:
        * a 4-byte ID
        * the IP of the server hosting the party (4 bytes)
        * the port of the server hosting the party (2 bytes)
        * a 4-byte integer for the number of players currently in the party
        * a 4-byte integer for the max number of players expected in the party"""
    TYPE = PacketType.LOBBY
    
    def __init__(self, parties):
        # the total number of parties
        self.n_parties = len(parties)
        # the list of all the pending parties
        self.parties = parties
        
    
    def __repr__(self):
        return "(%d | %s)" % (self.n_parties, repr(self.parties))

    def __str__(self):
        return "(num parties: %d | parties: %s)" % (self.n_parties, str(self.parties))
    
    def get_raw_data(self):
        data = struct.pack("<I", self.n_parties)
        for p in self.parties:
            data += p.encode()
        return data
    
    @classmethod
    def process_raw_data(cls, data):
        n_parties = struct.unpack("<I", data[:4])[0]
        parties = [ PartyInfo.decode(
            data[4 + PartyInfo.SIZE * i : 4 + PartyInfo.SIZE * (i + 1)])
            for i in range(n_parties) ]
        
        return cls(parties)
        
class CreatePartyPacket(SubPacket):
    """A packet sent by a client to create a new party."""
    TYPE = PacketType.CREATE_PARTY
    
    def __init__(self):
        pass
    
    def get_raw_data(self):
        return ""
        
    @classmethod
    def process_raw_data(cls, data):
        return cls()

class PartyStatusPacket(SubPacket):
    """The server hosting the party regularly send a party status packet
    to inform the players of its current status.
    It is composed of:
    - a 4-byte integer for the current number of players in the party
    - a 4-byte integer for the max. number of players expected to be
    in the party before the game starts"""
    TYPE = PacketType.PARTY_STATUS

    def __init__(self, n_players, max_players):
        self.n_players = n_players
        self.max_players = max_players

    def get_raw_data(self):
        return struct.pack("<II", self.n_players, self.max_players)

    @classmethod
    def process_raw_data(cls, data):
        n_players, max_players = struct.unpack("<II", data)
        return cls(n_players, max_players)
        
    def __repr__(self):
        return "(%d / %d)" % (self.n_players, self.max_players)

    def __str__(self):
        return "(%d player(s) / %d)" % (self.n_players, self.max_players)

class InitPacket(SubPacket):
    """The server hosting the party send an init packet to each player
    which marks the start of the game. It contains all the necessary
    information to initialize the game state:
    - a 4-byte integer to let the receiver know its player ID
    - a 4-byte integer for the total number of players k
    - a 4-byte integer which tells the length of each turn (in ms)
    - a 4-byte integer for the width n of the map
    - a 4-byte integer for the height m of the map
    - the concatenated (n x m) tile info
    - the concatenated k (xi, yi) initial position of each player"""
    TYPE = PacketType.INIT
    
    def __init__(self, pID, k, dturn, n, m, tiles, poss):
        self.player_ID = pID
        self.n_players = k
        self.turn_length = dturn
        self.width = n
        self.height = m
        # tiles should be a flattened array of n * m TileContent enum
        self.tiles = tiles
        # positions should be a list of k (x, y) couples
        self.positions = poss
    
    def __repr__(self):
        return "(%d | %d | %d | %d | %d | %s | %s)" % (
            self.player_ID, self.n_players, self.turn_length,
            self.width, self.height, repr(self.tiles), repr(self.positions))

    def __str__(self):
        return ("(id: %d | num. players: %d | turn length: %d ms | " +
            "board size: (%dx%d) | tiles: %s | player positions: %s)") % (
            self.player_ID, self.n_players, self.turn_length,
            self.width, self.height, str(self.tiles), str(self.positions))
    
    def get_raw_data(self):
        data = struct.pack("<IIIII", self.player_ID, self.n_players,
            self.turn_length, self.width, self.height)
        for t in self.tiles:
            data += struct.pack("B", t)
        for x, y in self.positions:
            data += struct.pack("<II", x, y)
        return data

    @classmethod
    def process_raw_data(cls, data):
        pID, k, dturn, n, m = struct.unpack("<IIIII", data[:20])
        data = data[20:]
        tiles = [ struct.unpack("B", data[i])[0]
            for i in range(n * m) ]
        data = data[(n * m):]
        positions = [ struct.unpack("<II", data[i * 8: (i + 1) * 8])
            for i in range(k)]
        return cls(pID, k, dturn, n, m, tiles, positions)

class ActionRequestPacket(SubPacket):
    """An action packet is composed of:
    - the turn number when the action was requested 
    (a 4-byte unsigned integer, little endian)
    - the action (turn left, drop bomb, etc...)
    represented by a single byte unsigned integer"""
    TYPE = PacketType.ACTION
    SIZE = 5
    
    def __init__(self, turn, action):
        self.turn = turn
        self.action = action
    
    def __repr__(self):
        return "(%s | %s)" % (repr(self.turn), repr(self.action))
        
    def __str__(self):
        return "(turn: %s | action: %s)" % (str(self.turn), Action.to_str(self.action))
    
    @classmethod
    def random(cls):
        turn = random.randint(0, UINT32_MAX)
        action = random.choice(Action.values)
        return cls(turn, action)
    
    def get_raw_data(self):
        return struct.pack("<IB", self.turn, self.action)
    
    @classmethod
    def process_raw_data(cls, data):
        turn, action = struct.unpack("<IB", data)
        return cls(turn, action)

class ActionsCommitPacket(SubPacket):
    """An actions commit packet is composed of:
    - the turn number when the actions are to be committed
    (a 4-byte unsigned integer, little endian)
    - the list of actions performed by each player
    (each action being represented by a single bye unsigned integer)"""
    TYPE = 42
    SIZE = 8 + NUM_PLAYERS
    
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
        return struct.pack('<II' + 'B' * NUM_PLAYERS, self.turn, NUM_PLAYERS, *self.actions)
        
    @classmethod
    def process_raw_data(cls, data):
        items = struct.unpack('<II' + 'B' * NUM_PLAYERS, data)
        turn = items[0]
        assert items[1] == NUM_PLAYERS
        actions = items[2:]
        return cls(turn, actions)

class PacketMismatch(Exception): 
    """Exception raised for errors on a packet's data format."""
    pass

class GamePacket(object):
    """A game packet is composed of a header including:
    - a 4-bytes little endian integer for the length of the packet
    (without the 4 bytes)
    - 1 byte for the packet type code
    and a payload (raw data)"""
    # payload_classes = {} # may be overriden by derived classes
    payload_classes = {
        PacketType.LOBBY: LobbyPacket,
        PacketType.CREATE_PARTY: CreatePartyPacket,
        
        PacketType.PARTY_STATUS: PartyStatusPacket,
        PacketType.INIT: InitPacket,
    }
    
    def __init__(self, ptype, payload):
        self.len = 1 + (len(payload) if payload else 0)
        self.type = ptype
        self.payload = payload
        
    def __repr__(self):
        return "(%s | %s)" % (repr(self.type), repr(self.payload))
        
    def __str__(self):
        if self.type in self.__class__.payload_classes:
            PayloadClass = self.__class__.payload_classes[self.type]
            processed_payload = PayloadClass.process_raw_data(self.payload)
            return "(type: %s | payload: %s)" % (PacketType.to_str(self.type), str(processed_payload))
        else:
            return "(type: %d | payload: junk)" % (self.type)
        # return "(type: %s | payload: %s)" % (PacketType.to_str(self.type), str(self.payload))
    
    @classmethod
    def random(cls):
        ptype = random.choice(cls.payload_classes.keys())
        PayloadClass = cls.payload_classes[ptype]
        if "random" in dir(PayloadClass):
            payload = PayloadClass.random().get_raw_data()
        else:
            payload = PayloadClass().get_raw_data()
        return cls(ptype, payload)
    
    def send(self, socket):
        packet = struct.pack("<IB", self.len, self.type) + self.payload
        socket_utils.send(socket, packet)
            
    @classmethod
    def recv(cls, socket):
        # read the packet's length
        length = cls._read_len(socket)
        # receive the whole packet (without the length)
        packet = socket_utils.recv(socket, length)
        # decode the packet type, leave payload as is
        ptype = struct.unpack("B", packet[0])[0]
        payload = packet[1:] if length >= 2 else ''
        # if length >= 2:
        #             ptype, payload = struct.unpack("Bs", packet)
        #         else:
        #             ptype = struct.unpack("B", packet)[0]
        #             payload = None
        # # read the packet's type
        # ptype = cls._read_type(socket)
        # # read the packet's payload
        # if ptype not in cls.payload_classes:
        #     # raise a PacketMismatch exception
        #     # if the type read was not any of the expected type
        #     valid_ptypes = [str(pt) for pt in cls.payload_classes.keys()]
        #     err_msg = "Packet type not recognized.\n"
        #     err_msg += "Received: %d\n" % ptype
        #     err_msg += "Expected: %s" % (" or ".join(valid_ptypes))
        #     raise PacketMismatch(err_msg)
        # else:
        #     payload = def recv(sock, size):
        #         # call socket.recv() until we have actually received data of size "size"
        #         data = ''
        #         while len(data) < size:
        #             chunk = sock.recv(size - len(data))
        #             if not chunk:
        #                 raise socket.error("socket connection broken")
        #             data += chunk
        #         return data
        #     # the payload's length is inferred from the packet's type
        #     payload = socket_utils.recv(socket, cls.payload_classes[ptype].SIZE)
        # return a new packet instance
        return cls(ptype, payload)
    
    @classmethod
    def _read_len(cls, sock):
        # the first byte of the packet should indicate its length
        len_encoded = socket_utils.recv(sock, 4)
        return struct.unpack("<I", len_encoded)[0]
    
    @classmethod
    def _read_type(cls, sock):
        # the second byte of the packet should index its type
        ptype_encoded = sock.recv(1)
        if not ptype:
            raise socket.error("socket connection broken")
        else:
            return struct.unpack("B", ptype_encoded)[0]

# class RequestPacket(GamePacket):
#     """A request packet is a game packet designed to be a client request
#     to server"""
#     payload_classes = {
#         PacketType.ACTION: ActionRequestPacket
#     }
# 
# class ResponsePacket(GamePacket):
#     """A commit packet is a game packet designed to be a server response"""
#     payload_classes = {
#         PacketType.ACTION: ActionsCommitPacket
#     }

        