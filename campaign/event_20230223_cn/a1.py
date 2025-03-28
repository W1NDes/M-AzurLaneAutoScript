from module.campaign.campaign_base import CampaignBase
from module.map.map_base import CampaignMap
from module.map.map_grids import SelectedGrids, RoadGrids
from module.logger import logger

MAP = CampaignMap('A1')
MAP.shape = 'H8'
MAP.camera_data = ['D2', 'D5', 'E2', 'E5']
MAP.camera_data_spawn_point = ['D6']
MAP.map_data = """
    ++ -- -- -- ME -- ME --
    -- MB -- ME ++ ME -- ++
    ME -- -- Me ++ Me -- ME
    ME -- -- -- MS -- -- --
    -- ME Me -- -- __ ++ ++
    -- ++ ++ ++ Me -- MS ++
    -- -- Me -- -- -- -- --
    ++ -- -- SP SP -- -- --
"""
MAP.weight_data = """
    50 50 50 50 50 50 50 50
    50 50 50 50 50 50 50 50
    50 50 50 50 50 50 50 50
    50 50 50 50 50 50 50 50
    50 50 50 50 50 50 50 50
    50 50 50 50 50 50 50 50
    50 50 50 50 50 50 50 50
    50 50 50 50 50 50 50 50
"""
MAP.spawn_data = [
    {'battle': 0, 'enemy': 2, 'siren': 1},
    {'battle': 1, 'enemy': 1},
    {'battle': 2, 'enemy': 1},
    {'battle': 3, 'enemy': 1, 'boss': 1},
    {'battle': 4, 'enemy': 1},
]
A1, B1, C1, D1, E1, F1, G1, H1, \
A2, B2, C2, D2, E2, F2, G2, H2, \
A3, B3, C3, D3, E3, F3, G3, H3, \
A4, B4, C4, D4, E4, F4, G4, H4, \
A5, B5, C5, D5, E5, F5, G5, H5, \
A6, B6, C6, D6, E6, F6, G6, H6, \
A7, B7, C7, D7, E7, F7, G7, H7, \
A8, B8, C8, D8, E8, F8, G8, H8, \
    = MAP.flatten()


class Config:
    # ===== Start of generated config =====
    MAP_SIREN_TEMPLATE = ['Joffre']
    MOVABLE_ENEMY_TURN = (2,)
    MAP_HAS_SIREN = True
    MAP_HAS_MOVABLE_ENEMY = True
    MAP_HAS_MAP_STORY = True
    MAP_HAS_FLEET_STEP = True
    MAP_HAS_AMBUSH = False
    MAP_HAS_MYSTERY = False
    # ===== End of generated config =====

    MAP_SWIPE_MULTIPLY = (0.993, 1.011)
    MAP_SWIPE_MULTIPLY_MINITOUCH = (0.960, 0.978)
    MAP_SWIPE_MULTIPLY_MAATOUCH = (0.932, 0.949)
    STAGE_INCREASE_CUSTOM = [
        'A1 > A2 > A3 > B1 > B2 > B3 > C1 > C2 > C3 > D1 > D2 > D3',
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

    def battle_3(self):
        return self.clear_boss()
