import enum

# display information in console
VERBOSE = True
PRINT_PACKETS = True # display every packet sent/received on the console
DEBUG = True

# monitoring tool
USE_MONITORING = False # switch to True to use it
DELAY = 200
JITTER = 50

# game constants
NUM_PLAYERS = 4

BOARD_WIDTH = 17
BOARD_HEIGHT = 15

TURN_LENGTH = 0.2 # in seconds
BOMB_COUNTER_INIT = 12 # number of turns
BOMB_RADIUS = 3


DUMP_OLD_PACKET = False # switch to True to use the old version of the protocol

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
