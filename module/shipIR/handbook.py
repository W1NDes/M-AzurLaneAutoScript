import random
from module.retire.dock import Dock
from module.logger import logger
from module.base.decorator import cached_property
from module.ui.setting import Setting
from module.base.button import ButtonGrid
from module.ui.page import page_handbook
from module.coalition.assets import NEONCITY_FLEET_PREPARATION, NEONCITY_PREPARATION_EXIT
from module.combat.assets import GET_SHIP
from module.exercise.assets import EXERCISE_PREPARATION
from module.handler.assets import (AUTO_SEARCH_MENU_EXIT, GAME_TIPS,  LOGIN_CHECK, MAINTENANCE_ANNOUNCE)
from module.map.assets import (FLEET_PREPARATION, MAP_PREPARATION,MAP_PREPARATION_CANCEL, WITHDRAW)
from module.meowfficer.assets import MEOWFFICER_BUY
from module.os_handler.assets import AUTO_SEARCH_REWARD
from module.raid.assets import *
from module.ui.assets import *
from module.shipIR.assets import *
from module.logger import logger



class Handbook(Dock):

    def ui_additional(self, get_ship=True):
        """
        Handle all annoying popups during UI switching.

        Args:
            get_ship:
        """
        # Popups appear at page_os
        # Has a popup_confirm variant
        # so must take precedence
        if self.ui_page_os_popups():
            return True

        # Research popup, lost connection popup
        if self.handle_popup_confirm("UI_ADDITIONAL"):
            return True
        if self.handle_urgent_commission():
            return True

        # Popups appear at page_main, page_reward
        if self.ui_page_main_popups(get_ship=get_ship):
            return True

        # Story
        if self.handle_story_skip():
            return True

        # Game tips
        # Event commission in Vacation Lane.
        # 2025.05.29 game tips that infos skin feature when you enter dock
        if self.appear(GAME_TIPS, offset=(30, 30), interval=2):
            logger.info(f'UI additional: {GAME_TIPS} -> {GOTO_MAIN}')
            self.device.click(GOTO_MAIN)
            return True

        # Dorm popup
        if self.appear(DORM_INFO, offset=(30, 30), similarity=0.75, interval=3):
            self.device.click(DORM_INFO)
            return True
        if self.appear_then_click(DORM_FEED_CANCEL, offset=(30, 30), interval=3):
            return True
        if self.appear_then_click(DORM_TROPHY_CONFIRM, offset=(30, 30), interval=3):
            return True

        # Meowfficer popup
        if self.appear_then_click(MEOWFFICER_INFO, offset=(30, 30), interval=3):
            self.interval_reset(GET_SHIP)
            return True
        if self.appear(MEOWFFICER_BUY, offset=(30, 30), interval=3):
            logger.info(f'UI additional: {MEOWFFICER_BUY} -> {BACK_ARROW}')
            self.device.click(BACK_ARROW)
            self.interval_reset(GET_SHIP)
            return True

        # Campaign preparation
        if self.appear(MAP_PREPARATION, offset=(30, 30), interval=3) \
                or self.appear(FLEET_PREPARATION, offset=(20, 50), interval=3) \
                or self.appear(RAID_FLEET_PREPARATION, offset=(30, 30), interval=3):
            self.device.click(MAP_PREPARATION_CANCEL)
            return True
        if self.appear_then_click(AUTO_SEARCH_MENU_EXIT, offset=(200, 30), interval=3):
            return True
        if self.appear_then_click(AUTO_SEARCH_REWARD, offset=(50, 50), interval=3):
            return True
        if self.appear(WITHDRAW, offset=(30, 30), interval=3):
            # Poor wait here, to handle a game client bug after the game patch in 2022-04-07
            # To re-produce this game bug (100% success):
            # - Enter any stage, 12-4 for example
            # - Stop and restart game
            # - Run task `Main` in Alas
            # - Alas switches to page_campaign and retreat from an existing stage
            # - Game client freezes at page_campaign W12, clicking anywhere on the screen doesn't get responses
            # - Restart game client again fix the issue
            logger.info("WITHDRAW button found, wait until map loaded to prevent bugs in game client")
            self.device.sleep(2)
            self.device.screenshot()
            if self.appear_then_click(WITHDRAW, offset=(30, 30)):
                self.interval_reset(WITHDRAW)
                return True
            else:
                logger.warning("WITHDRAW button does not exist anymore")
                self.interval_reset(WITHDRAW)

        # Login
        if self.appear_then_click(LOGIN_CHECK, offset=(30, 30), interval=3):
            return True
        if self.appear_then_click(MAINTENANCE_ANNOUNCE, offset=(30, 30), interval=3):
            return True

        # Mistaken click
        if self.appear(EXERCISE_PREPARATION, interval=3):
            logger.info(f'UI additional: {EXERCISE_PREPARATION} -> {GOTO_MAIN}')
            self.device.click(GOTO_MAIN)
            return True


        # Neon city (coalition_20250626)
        if self.appear(NEONCITY_FLEET_PREPARATION, offset=(20, 20), interval=3):
            logger.info(f'{NEONCITY_FLEET_PREPARATION} -> {NEONCITY_PREPARATION_EXIT}')
            self.device.click(NEONCITY_PREPARATION_EXIT)
            return True

        # Idle page
        if self.handle_idle_page():
            return True

        return False

    def handbook_swipe(self,x,delay_time=0.3):
        self.device.drag((x+random.randint(-3,3),300),(x+random.randint(-3,3),220),control_check=False)
        # self.device.sleep(delay_time)
        self.device.sleep(delay_time)

    def dock_filter_enter(self):
        logger.info('Dock filter enter')
        for _ in self.loop():
            if self.appear(HANDBOOK_FILTER_CONFIRM, offset=(20, 20)):
                break
            if self.appear(HANDBOOK_CHECK, offset=(20, 20), interval=5):
                self.device.click(HANDBOOK_FILTER)
                continue

    def dock_filter_confirm(self, wait_loading=True, skip_first_screenshot=True):
        """
        Args:
            wait_loading: Default to True, use False on continuous operation
            skip_first_screenshot:
        """
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            # End
            # sometimes you have dock filter without black-blurred background
            # DOCK_FILTER_CONFIRM and DOCK_CHECK appears
            if not self.appear(HANDBOOK_FILTER_CONFIRM, offset=(20, 20)):
                if self.appear(HANDBOOK_CHECK, offset=(20, 20)):
                    break
            if self.appear_then_click(HANDBOOK_FILTER_CONFIRM, offset=(20, 20), interval=3):
                continue

        if wait_loading:
            self.handle_dock_cards_loading()

    @cached_property
    def dock_filter(self) -> Setting:
        delta = (147 + 1 / 3, 57)
        button_shape = (139, 42)
        setting = Setting(name='HANDBOOK', main=self)

        setting.add_setting(
            setting='index',
            option_buttons=ButtonGrid(
                origin=(218, 147), delta=delta, button_shape=button_shape, grid_shape=(7, 2), name='FILTER_INDEX'),
            option_names=['all', 'vanguard', 'main', 'dd', 'cl', 'ca', 'bb',
                          'cv', 'repair', 'ss', 'others', 'not_available', 'not_available', 'not_available'],
            option_default='all'
        )
        setting.add_setting(
            setting='faction',
            option_buttons=ButtonGrid(
                origin=(218, 277), delta=delta, button_shape=button_shape, grid_shape=(7, 2), name='FILTER_FACTION'),
            option_names=['all', 'eagle', 'royal', 'sakura', 'iron', 'dragon', 'sardegna',
                          'northern', 'iris', 'vichya', 'tulipa', 'meta', 'tempesta', 'other'],
            option_default='all'
        )
        setting.add_setting(
            setting='rarity',
            option_buttons=ButtonGrid(
                origin=(218, 407), delta=delta, button_shape=button_shape, grid_shape=(7, 1), name='FILTER_RARITY'),
            option_names=['all', 'common', 'rare', 'elite', 'super_rare', 'ultra', 'not_available'],
            option_default='all'
        )
        setting.add_setting(
            setting='extra',
            option_buttons=ButtonGrid(
                origin=(218, 480), delta=delta, button_shape=button_shape, grid_shape=(7, 1), name='FILTER_EXTRA'),
            option_names=['no_limit','special','un_get','not_available', 'not_available', 'not_available', 'not_available'],
            option_default='no_limit'
        )
        return setting
    
    def pageCheck(self):
        self.ui_ensure(page_handbook)
        if self.appear(page_handbook.check_button, offset=(30, 30)):
            logger.info('pageCheck: At page_handbook')
            return True
        else:
            logger.warning('Unknown page_handbook')
            return False