import enum

NUM_PLAYERS = 4

# BOARD_WIDTH = 170
BOARD_WIDTH = 17
# BOARD_HEIGHT = 150
BOARD_HEIGHT = 15
# BLOCK_SIZE = 10 # 1 block = 10*10 board unit
# TILE_HEIGHT = BOARD_WIDTH / BLOCK_SIZE
# TILE_WIDTH = BOARD_HEIGHT / BLOCK_SIZE

# ROUND_INTERVAL = 50 # 50 ms
TURN_LENGTH = 0.2 # in s

BOMB_COUNTER_INIT = 12
BOMB_RADIUS = 3

DEBUG = False

# DUMP_OLD_PACKET = False
DUMP_OLD_PACKET = True

USE_MONITORING = False
# USE_MONITORING = True
DELAY = 100
JITTER = 100


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
