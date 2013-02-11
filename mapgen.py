import random
from gameconst import *


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
        self.grid = [ [ TileContent.HARD_BLOCK if self.is_fixed_block(i, j) else 
                        TileContent.FREE if self.is_fixed_free(i, j) else
                        self.random_tile()
                        for j in xrange(self.width)] 
                    for i in xrange(self.height)]
    
    def random_tile(self):
        i = random.randrange(100)
        # fact = 30
        fact = 70
        return TileContent.SOFT_BLOCK if i > fact else TileContent.FREE
        # return random.getrandbits(1)
    
    def is_fixed(self, i, j):
        """docstring for is_fixed"""
        return (self.is_fixed_block(i, j) or self.is_fixed_free(i, j))
    
    def is_fixed_block(self, i, j):
        return (self.is_border(i, j) or self.is_hard_block(i, j))
    
    def is_border(self, i, j):
        return ((i == 0) or (i == self.height - 1) or
               (j == 0) or (j == self.width - 1))
    
    def is_hard_block(self, i, j):
        return ((i % 2 == 0) and (j % 2 == 0))
    
    def is_fixed_free(self, i, j):
        # player tiles must be TileContent.FREE (corner + 2 adjacent)
        # top_left = (i == 1 and (j == 1 or j == 2)) or (i == 2 and j == 1)
        top_left = (i == 1 and (j == 1 or j == 2 or j == 3)) or (i == 2 and j == 1)
        # top_right = (i == 1 and (j == self.width - 2 or j == self.width - 3)) or (i == 2 and j == self.width - 2)
        top_right = (i == 1 and (j == self.width - 2 or j == self.width - 3)) or (i == 2 and j == self.width - 2) or (i == 3 and j == self.width - 2)
        # bottom_left = (i == self.height - 2 and (j == 1 or j == 2)) or (i == self.height - 3 and j == 1)
        bottom_left = (i == self.height - 2 and (j == 1 or j == 2)) or (i == self.height - 3 and j == 1) or (i == self.height - 4 and j == 1)
        # bottom_right = (i == self.height - 2 and (j == self.width - 2 or j == self.width - 3)) or (i == self.height - 3 and j == self.width - 2)
        bottom_right = (i == self.height - 2 and (j == self.width - 2 or j == self.width - 3 or j == self.width - 4)) or (i == self.height - 3 and j == self.width - 2)
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
        #     print "is fixed FREE: " + str((i, j))
        # return b

    
    def count_adj_free(self, i, j):
        n = 0
        for ii in [i - 1, i, i + 1]:
            for jj in [j - 1, j, j + 1]:
                if self.grid[ii][jj] == TileContent.FREE:
                    n += 1
        return n
    
    def next_gen(self):
        for i in range(0, self.height):
            for j in range(0, self.width):
                if not self.is_fixed(i, j):
                    # rule 3-4
                    # if self.count_adj_free(i, j) in [2, 3]:
                    if self.count_adj_free(i, j) in [2, 4]:
                    # if self.count_adj_free(i, j) in [3, 4]:
                        self.grid[i][j] = TileContent.FREE
                    else:
                        self.grid[i][j] = TileContent.SOFT_BLOCK
    
    def iter_next_gen(self, n):
        for i in range(n):
            self.next_gen()
    
    def __str__(self):
        return '\n'.join([' '.join(['.' if t == TileContent.FREE
                else ('x' if t == TileContent.HARD_BLOCK else '#')
                for t in row]) for row in self.grid])


def generate(n, m):
    gridmap = GridMap(n + 2, m + 2)
    gridmap.iter_next_gen(2)
    return [gridmap.grid[i + 1][j + 1] for j in xrange(m) for i in xrange(n)]

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

