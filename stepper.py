import time
import random

from collections import namedtuple
from s2sphere import CellId, LatLng
from google.protobuf.internal import encoder
from pgoapi.utilities import f2i, h2f

def _encode(cellid):
    output = []
    encoder._VarintEncoder()(output.append, cellid)
    return ''.join(output)

def _get_cellid(lat, long):
    origin = CellId.from_lat_lng(LatLng.from_degrees(lat, long)).parent(15)
    walk = [origin.id()]

    # 10 before and 10 after
    next = origin.next()
    prev = origin.prev()
    for i in range(10):
        walk.append(prev.id())
        walk.append(next.id())
        next = next.next()
        prev = prev.prev()
    return ''.join(map(_encode, sorted(walk)))

Position = namedtuple('Position', 'lat lon alt')

METER_TO_DEG = 1. / (60 * 1852)

def fuzz(pos, tolerance=5):
    n0 = random.normalvariate(0, tolerance * METER_TO_DEG)
    n1 = random.normalvariate(0, tolerance * METER_TO_DEG)
    return Position(pos.lat + n0, pos.lon + n1, pos.alt)

class Stepper(object):

    def __init__(self, bot):
        self.bot = bot
        self.api = bot.api
        self.config = bot.config

        self.pos = 1
        self.x = 0
        self.y = 0
        self.dx = 0
        self.dy = -1
        self.steplimit=self.config.maxsteps
        self.steplimit2 = self.steplimit**2
        self.origin_lat = self.bot.position[0]
        self.origin_lon = self.bot.position[1]
    def walking_hook(own,i):
        print '\rwalking hook ',i,
    def take_step(self):
        position=(self.origin_lat,self.origin_lon,0.0)
        for step in range(self.steplimit2):
            #starting at 0 index
            print('[#] Scanning area for objects ({} / {})'.format((step+1), self.steplimit**2))

            # get map objects call
            # ----------------------
            timestamp = "\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000"
            cellid = _get_cellid(position[0], position[1])
            self.api.get_map_objects(latitude=f2i(position[0]), longitude=f2i(position[1]), since_timestamp_ms=timestamp, cell_id=cellid)

            response_dict = self.api.call()
            #print('Response dictionary: \n\r{}'.format(json.dumps(response_dict, indent=2)))
            if response_dict and 'responses' in response_dict and \
                'GET_MAP_OBJECTS' in response_dict['responses'] and \
                'status' in response_dict['responses']['GET_MAP_OBJECTS'] and \
                response_dict['responses']['GET_MAP_OBJECTS']['status'] is 1:
                #print('got the maps')
                map_cells=response_dict['responses']['GET_MAP_OBJECTS']['map_cells']
                print('map_cells are {}'.format(len(map_cells)))
                for cell in map_cells:
                    self.bot.work_on_cell(cell,position)

            if self.config.debug:
                print('steplimit: {} x: {} y: {} pos: {} dx: {} dy {}'.format(self.steplimit2, self.x, self.y, self.pos, self.dx, self.dy))
            # Scan location math
            if -self.steplimit2 / 2 < self.x <= self.steplimit2 / 2 and -self.steplimit2 / 2 < self.y <= self.steplimit2 / 2:
                position = (self.x * 0.0025 + self.origin_lat, self.y * 0.0025 + self.origin_lon, 0)
                if self.config.walk > 0:
                    self.api.walk(self.config.walk, *position,walking_hook=self.walking_hook)
                else:
                    self.api.set_position(*position)
                print(position)
            if self.x == self.y or self.x < 0 and self.x == -self.y or self.x > 0 and self.x == 1 - self.y:
                (self.dx, self.dy) = (-self.dy, self.dx)

            (self.x, self.y) = (self.x + self.dx, self.y + self.dy)
            time.sleep(10)

class RandomStepper:
    def __init__(self, bot, step_dist=15):
        self.bot = bot
        self.api = bot.api
        self.config = bot.config
        self.pos = Position(*self.bot.position)
        self.step_dist = step_dist

    def take_step(self):
        self.pos = fuzz(self.pos, tolerance=self.step_dist)

        self.bot.log.info('Position: {}, Walk Speed: {}'\
                          .format(self.pos, self.config.walk))
        self.api.walk(self.config.walk, *self.pos)

        timestamp = "\000" * 21
        cellid = _get_cellid(self.pos.lat, self.pos.lon)
        self.api.get_map_objects(latitude=f2i(self.pos.lat),
                                 longitude=f2i(self.pos.lon),
                                 since_timestamp_ms=timestamp,
                                 cell_id=cellid)
        res = self.api.call()
        try:
            map_cells = res['responses']['GET_MAP_OBJECTS']['map_cells']

            cell_forts = [c for c in map_cells if 'forts' in map_cells]
            cell_no_forts = [c for c in map_cells if 'forts' not in map_cells]

            for cell in cell_no_forts:
                self.bot.work_on_cell(cell, self.pos)
            for cell in cell_forts:
                self.bot.work_on_cell(cell, self.pos)

        except KeyError:
            print "get_map_objects returning incorrectly!"

        time.sleep(5)
