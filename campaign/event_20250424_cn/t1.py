from .campaign_base import CampaignBase
from module.map.map_base import CampaignMap
from module.map.map_grids import SelectedGrids, RoadGrids
from module.logger import logger

MAP = CampaignMap('T1')
MAP.shape = 'I7'
MAP.camera_data = ['D2', 'F2', 'F5']
MAP.camera_data_spawn_point = ['D5']
MAP.map_data = """
    Me -- Me -- -- -- ++ ++ ++
    -- Me -- ++ ME -- ME -- --
    -- ++ -- -- -- -- -- ME --
    -- ++ MS -- ME -- ME ++ ++
    -- -- __ MS -- -- -- -- ++
    SP -- -- ++ ++ ME -- -- ME
    -- SP -- MB ++ -- ME ME --
"""
MAP.weight_data = """
    50 50 50 50 50 50 50 50 50
    50 50 50 50 50 50 50 50 50
    50 50 50 50 50 50 50 50 50
    50 50 50 50 50 50 50 50 50
    50 50 50 50 50 50 50 50 50
    50 50 50 50 50 50 50 50 50
    50 50 50 50 50 50 50 50 50
"""
MAP.spawn_data = [
    {'battle': 0, 'enemy': 2, 'siren': 1},
    {'battle': 1, 'enemy': 2},
    {'battle': 2, 'enemy': 1},
    {'battle': 3, 'enemy': 1},
    {'battle': 4, 'boss': 1},
]
A1, B1, C1, D1, E1, F1, G1, H1, I1, \
A2, B2, C2, D2, E2, F2, G2, H2, I2, \
A3, B3, C3, D3, E3, F3, G3, H3, I3, \
A4, B4, C4, D4, E4, F4, G4, H4, I4, \
A5, B5, C5, D5, E5, F5, G5, H5, I5, \
A6, B6, C6, D6, E6, F6, G6, H6, I6, \
A7, B7, C7, D7, E7, F7, G7, H7, I7, \
    = MAP.flatten()


class Config:
    # ===== Start of generated config =====
    MAP_SIREN_TEMPLATE = ['DD', 'CL']
    MOVABLE_ENEMY_TURN = (2,)
    MAP_HAS_SIREN = True
    MAP_HAS_MOVABLE_ENEMY = True
    MAP_HAS_MAP_STORY = False
    MAP_HAS_FLEET_STEP = True
    MAP_HAS_AMBUSH = False
    MAP_HAS_MYSTERY = False
    # ===== End of generated config =====

    MAP_CHAPTER_SWITCH_20241219_SP = True
    MAP_HAS_MODE_SWITCH = True
    STAGE_ENTRANCE = ['half', '20240725']
    INTERNAL_LINES_FIND_PEAKS_PARAMETERS = {
        'height': (80, 255 - 33),
        'width': (0.9, 10),
        'prominence': 10,
        'distance': 35,
    }
    EDGE_LINES_FIND_PEAKS_PARAMETERS = {
        'height': (255 - 33, 255),
        'prominence': 10,
        'distance': 50,
        # 'width': (0, 7),
        'wlen': 1000
    }
    MAP_ENEMY_GENRE_DETECTION_SCALING = {
        'DD': 1.111,
        'CL': 1.111,
        'CA': 1.111,
        'CV': 1.111,
        'BB': 1.111,
    }
    MAP_SWIPE_MULTIPLY = (1.124, 1.145)
    MAP_SWIPE_MULTIPLY_MINITOUCH = (1.087, 1.107)
    MAP_SWIPE_MULTIPLY_MAATOUCH = (1.055, 1.074)
    STAGE_INCREASE_CUSTOM = [
        'T1 > T2 > T3 > HT1 > HT2 > HT3',
    ] 


class Campaign(CampaignBase):
    MAP = MAP
    ENEMY_FILTER = '1L > 1M > 1E > 1C > 2L > 2M > 2E > 2C > 3L > 3M > 3E > 3C'

    def battle_0(self):
        if self.clear_siren():
            return True
        if self.clear_filter_enemy(self.ENEMY_FILTER, preserve=0):
            return True

        return self.battle_default()

    def battle_4(self):
        return self.clear_boss()
