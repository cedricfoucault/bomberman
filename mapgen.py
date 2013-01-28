import packets
import random
from gameconst import *

WALL = 1
EMPTY = 0

class GridMap(object):
    """docstring for MapGrid"""
    def __init__(self, height, width):
        super(GridMap, self).__init__()
        self.height = height
        self.width = width
        self.init_grid()
    
    def init_grid(self):
        """docstring for init_grid"""
        # random grid
        self.grid = [ [ WALL if self.is_fixed_wall(i, j) else 
                        EMPTY if self.is_fixed_empty(i, j) else
                        self.random_tile()
                        for j in range(self.width)] 
                    for i in range(self.height)]
    
    def random_tile(self):
        i = random.randrange(100)
        # fact = 30
        fact = 60
        return WALL if i > fact else EMPTY
        # return random.getrandbits(1)
    
    def is_fixed(self, i, j):
        """docstring for is_fixed"""
        return (self.is_fixed_wall(i, j) or self.is_fixed_empty(i, j))
    
    def is_fixed_wall(self, i, j):
        return (self.is_border(i, j) or self.is_indestructible_wall(i, j))
    
    def is_border(self, i, j):
        return ((i == 0) or (i == self.height - 1) or
               (j == 0) or (j == self.width - 1))
    
    def is_indestructible_wall(self, i, j):
        return ((i % 2 == 0) and (j % 2 == 0))
    
    def is_fixed_empty(self, i, j):
        # player tiles must be empty (corner + 2 adjacent)
        top_left = (i == 1 and (j == 1 or j == 2)) or (i == 2 and j == 1)
        top_right = (i == 1 and (j == self.width - 2 or j == self.width - 3)) or (i == 2 and j == self.width - 2)
        bottom_left = (i == self.height - 2 and (j == 1 or j == 2)) or (i == self.height - 3 and j == 1)
        bottom_right = (i == self.height - 2 and (j == self.width - 2 or j == self.width - 3)) or (i == self.height - 3 and j == self.width - 2)
        # if top_left:
        #     print "top left %d, %d" % (i, j)
        # elif top_right:
        #     print "top right %d, %d" % (i, j)
        # elif bottom_left:
        #     print "bottom left %d, %d" % (i, j)
        # elif bottom_right:
        #     print "bottom right %d, %d" % (i, j)
        return (top_left or top_right or bottom_left or bottom_right)
        # b = (
        #     ((i == 1 and (j == 1 or j == 2)) or (i == 2 and j == 1)) or # top left
        #     ((i == 1 and (j == self.width - 1 or j == self.width - 2)) or (i == 2 and j == self.width - 1)) or # top right
        #        ((i == self.height - 1 and (j == 1 or j == 2)) or (i == self.height - 2 and j == 1)) or # bottom left
        #        ((i == self.height - 1 and (j == self.width - 1 or j == self.width - 2)) or (i == self.height - 2 and j == self.width - 1))) # bottom right
        # if b:
        #     print "is fixed empty: " + str((i, j))
        # return b

    
    def adj_empty_count(self, i, j):
        n = 0
        for ii in [i - 1, i, i + 1]:
            for jj in [j - 1, j, j + 1]:
                if self.grid[ii][jj] == EMPTY:
                    n += 1
        return n
    
    def next_gen(self):
        for i in range(0, self.height):
            for j in range(0, self.width):
                if not self.is_fixed(i, j):
                    # rule 2-4
                    # if self.adj_empty_count(i, j) in [2, 3]:
                    if self.adj_empty_count(i, j) in [2, 4]:
                        self.grid[i][j] = EMPTY
                    else:
                        self.grid[i][j] = WALL
    
    def iter_next_gen(self, n):
        for i in range(n):
            self.next_gen()
    
    def __str__(self):
        return '\n'.join([' '.join(['.' if t == EMPTY else '#' for t in row]) for row in self.grid])
    

class GameMap(object):
    """docstring for GameMap"""
    def __init__(self, tiles):
        super(GameMap, self).__init__()
        self.tiles = tiles
    
    def get_tiles(self):
        """Return the flattened array of tiles' content (enum)."""
        return self.tiles
    
def generate(n, m):
    # self.grid = [ [ WALL if self.is_fixed_wall(i, j) else 
    #                 EMPTY if self.is_fixed_empty(i, j) else
    #                 self.random_tile()
    #                 for j in range(self.width)] 
    #             for i in range(self.height)]
    gridmap = GridMap(n + 2, m + 2)
    gridmap.iter_next_gen(2)
    tiles = []
    for i in range(n):
        for j in range(m):
            if gridmap.is_fixed_wall(i + 1, j + 1):
                content = packets.TileContent.HARD_BLOCK
            elif gridmap.grid[i + 1][j + 1] == WALL:
                content = packets.TileContent.SOFT_BLOCK
            else:
                content = packets.TileContent.FREE
            tiles.append(content)
    # tiles = [ packets.TileContent.FREE if x == EMPTY
    #           else packets.TileContent.WALL
    #             for x in row for row in gridmap.grid ]
    # tiles = [packets.TileContent.FREE] * (n * m)
    return GameMap(tiles)

if __name__ == '__main__':
    # m = GridMap(TILE_HEIGHT + 2, TILE_WIDTH + 2)
    m = GridMap(BOARD_HEIGHT + 2, BOARD_WIDTH + 2)
    print m
    m.iter_next_gen(1)
    print "\n MAP (1)"
    print m
    m.iter_next_gen(1)
    print "\n MAP (2)"
    print m
    m.iter_next_gen(1)
    print "\n MAP (3)"
    print m
    # m.iter_next_gen(2)
    # print "\n MAP (4)"
    # print m

