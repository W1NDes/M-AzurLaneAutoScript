import sys


sys.path.append(r'C:/Users/W1NDe/Documents/GitHub/M-AzurLaneAutoScript')
from module.base.button import  ButtonGrid
from module.logger import logger
from module.ocr.ocr import Ocr
from module.retire.scanner import LevelScanner
from module.combat.level import LevelOcr
from module.ui.page import page_fleet,page_main
from module.equipment.fleet_equipment import FleetEquipment
from module.equipment.assets import *

MAIN_LEVEL_GRIDS = ButtonGrid(origin=(157, 156), delta=(186, 0), button_shape=(51, 22), grid_shape=(3, 1))
VANGUARD_LEVEL_GRIDS = ButtonGrid(origin=(781, 156), delta=(186, 0), button_shape=(51, 22), grid_shape=(3, 1))
MAIN_NAME_GRIDS = ButtonGrid(origin=(63, 462), delta=(186+1/3, 0), button_shape=(153, 23), grid_shape=(3, 1))
VANGUARD_NAME_GRIDS = ButtonGrid(origin=(688, 462), delta=(186+1/3, 0), button_shape=(153, 23), grid_shape=(3, 1))
# MAIN_NAME_GRIDS.show_mask()
class FleetLevelScanner(LevelScanner):
    def __init__(self, grids):
        super().__init__()
        self.grids = grids
        self.ocr_model=LevelOcr(self.grids.buttons,name=grids._name, threshold=64)

class FleetInfoCheck(FleetEquipment):
    def fleet_info_ocr(self):
        self.device.screenshot()
        main_name = Ocr(MAIN_NAME_GRIDS.buttons,name='MAIN_NAME',lang='cnocr', threshold=150).ocr(self.device.image)
        vanguard_name = Ocr(VANGUARD_NAME_GRIDS.buttons,name='VANGUARD_NAME',lang='cnocr', threshold=150).ocr(self.device.image)
        main_level = FleetLevelScanner(MAIN_LEVEL_GRIDS).scan(self.device.image)
        vanguard_level = FleetLevelScanner(VANGUARD_LEVEL_GRIDS).scan(self.device.image)
        return main_name, vanguard_name, main_level, vanguard_level

    def get_fleet_info(self,fleet_index):
        self.device.screenshot()
        self.fleet_enter(fleet_index)
        self.ui_click(FLEET_DETAIL, appear_button=page_fleet.check_button,
                      check_button=FLEET_DETAIL_CHECK, skip_first_screenshot=True)
        main_name, vanguard_name, main_level, vanguard_level = self.fleet_info_ocr()
        self.config.cross_set(f'Main2.RegularInspections.FleetInspectInfo', f'{main_name},{vanguard_name}\n{main_level},{vanguard_level}')
        self.fleet_back()
        self.ui_ensure(page_main)

    def run(self):
        self.get_fleet_info(5)
        
if __name__ == "__main__":
    self = FleetInfoCheck('zTTT')
    self.run()