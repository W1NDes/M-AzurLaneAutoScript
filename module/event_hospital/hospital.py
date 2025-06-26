from module.base.timer import Timer
from module.base.utils import random_rectangle_vector
from module.config.config import TaskEnd
from module.event_hospital.assets import *
from module.event_hospital.clue import HospitalClue
from module.event_hospital.combat import HospitalCombat
from module.exception import OilExhausted, ScriptEnd
from module.logger import logger
from module.ui.page import page_hospital, page_campaign_menu
from module.ui.switch import Switch


class HospitalSwitch(Switch):
    def get(self, main):
        """
        Args:
            main (ModuleBase):

        Returns:
            str: state name or 'unknown'.
        """
        for data in self.state_list:
            if main.image_color_count(data['check_button'], color=(33, 77, 189), threshold=221, count=100):
                return data['state']

        return 'unknown'


HOSPITAL_TAB = HospitalSwitch('HOSPITAL_ASIDE', is_selector=True)
HOSPITAL_TAB.add_state('LOCATION', check_button=TAB_LOCATION)
HOSPITAL_TAB.add_state('CHARACTER', check_button=TAB_CHARACTER)
HOSPITAL_TAB.add_state('RECORD', check_button=TAB_RECORD)
HOSPITAL_TAB.add_state('SECRET', check_button=TAB_SECRET)

HOSPITAL_SIDEBAR = HospitalSwitch('HOSPITAL_SIDEBAR', is_selector=True)
HOSPITAL_SIDEBAR.add_state('MORNING', check_button=SIDEBAR_MORNING)
HOSPITAL_SIDEBAR.add_state('NOON', check_button=SIDEBAR_NOON)
HOSPITAL_SIDEBAR.add_state('NIGHT', check_button=SIDEBAR_NIGHT)
T1 = Button(area=(370, 268, 390, 290), color=(), button=(370, 268, 390, 290),name='T1')
T2 = Button(area=(250, 400, 270, 420), color=(), button=(250, 400, 270, 420),name='T2')
T3 = Button(area=(640, 530, 660, 550), color=(), button=(640, 530, 660, 550),name='T3')
T4 = Button(area=(990, 400, 1010, 420), color=(), button=(990, 400, 1010, 420),name='T4')


class Hospital(HospitalClue, HospitalCombat):
    def daily_red_dot_appear(self):
        return self.image_color_count(DAILY_RED_DOT, color=(189, 69, 66), threshold=221, count=35)

    def daily_reward_receive_appear(self):
        return self.image_color_count(DAILY_REWARD_RECEIVE, color=(41, 73, 198), threshold=221, count=200)

    def is_in_daily_reward(self, interval=0):
        return self.match_template_color(HOSIPITAL_CLUE_CHECK, offset=(30, 30), interval=interval)

    def daily_reward_receive(self):
        """"
        Returns:
            bool: If received

        Pages:
            in: page_hospital
        """
        if self.daily_red_dot_appear():
            logger.info('Daily red dot appear')
        else:
            logger.info('No daily red dot')
            return False

        logger.hr('Daily reward receive', level=2)
        # Enter reward
        logger.info('Daily reward enter')
        skip_first_screenshot = True
        self.interval_clear(page_hospital.check_button)
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()
            if self.is_in_daily_reward():
                break
            if self.ui_page_appear(page_hospital, interval=2):
                logger.info(f'{page_hospital} -> {HOSPITAL_GOTO_DAILY}')
                self.device.click(HOSPITAL_GOTO_DAILY)
                continue

        # Claim reward
        logger.info('Daily reward receive')
        skip_first_screenshot = True
        self.interval_clear(HOSIPITAL_CLUE_CHECK)
        timeout = Timer(1.5, count=6).start()
        clicked = False
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()
            if timeout.reached():
                logger.warning('Daily reward receive timeout')
                break
            if clicked and self.is_in_daily_reward():
                if not self.daily_reward_receive_appear():
                    break
            if self.is_in_daily_reward(interval=2):
                if self.daily_reward_receive_appear():
                    self.device.click(DAILY_REWARD_RECEIVE)
                    continue
            if self.handle_get_items():
                timeout.reset()
                clicked = True
                continue

        # Claim reward
        logger.info('Daily reward exit')
        skip_first_screenshot = True
        self.interval_clear(HOSIPITAL_CLUE_CHECK)
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            if self.ui_page_appear(page_hospital):
                break
            if self.is_in_daily_reward(interval=2):
                self.device.click(HOSIPITAL_CLUE_CHECK)
                logger.info(f'is_in_daily_reward -> {HOSIPITAL_CLUE_CHECK}')
                continue

        return True

    def loop_invest(self):
        """
        Do all invest in page
        """
        self.config.override(Fleet_FleetOrder='fleet1_all_fleet2_standby')
        while 1:
            logger.hr('Loop hospital invest', level=2)
            # Scheduler
            # May raise ScriptEnd
            self.emotion.check_reduce(battle=1)

            entered = self.invest_enter()
            if not entered:
                break
            self.hospital_combat()

            # Scheduler
            # May raise TaskEnd
            if self.config.task_switched():
                self.config.task_stop()

            # Aside reset after combat, so we should loop in aside again
            break

        self.claim_invest_reward()
        logger.info('Loop hospital invest end')

    def invest_reward_appear(self) -> bool:
        return self.image_color_count(INVEST_REWARD_RECEIVE, color=(33, 77, 189), threshold=221, count=100)

    def claim_invest_reward(self):
        if self.invest_reward_appear():
            logger.info('Invest reward appear')
        else:
            if HOSPITAL_TAB.get(main=self) == 'RECORD':
                while 1:
                    self.device.screenshot()
                    if self.appear_then_click(RECORD_COLLECT,interval=1,similarity=0.95):
                        continue
                    if self.appear_then_click(RECORD_END,interval=1,similarity=0.9):
                        continue
                    # if reocrd is not None and self.is_record_selected(reocrd):
                    #     return True
                    reocrd = next(self.iter_record(), None)
                    if reocrd is None:
                        logger.info('No more reocrd')
                        return False
                    logger.info(f'is_in_record -> {reocrd}')
                    self.device.click(reocrd)
            else:
                logger.info('No invest reward')
                return False
        # Get reward
        skip_first_screenshot = True
        clicked = True
        self.interval_clear(HOSIPITAL_CLUE_CHECK)
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            if clicked:
                if self.is_in_clue() and not self.invest_reward_appear():
                    return True
            if self.handle_get_items():
                clicked = True
                continue
            if self.is_in_clue(interval=2):
                if self.invest_reward_appear():
                    self.device.click(INVEST_REWARD_RECEIVE)
                    continue
            if self.handle_story_skip():
                continue

    def secret_collect(self):
        """
        Collect secret reward
        """
        if self.invest_reward_appear():
            return True
        if self.match_template_color(INVEST_REWARD_RECEIVE,similarity=0.95,threshold=221):
            pass
        else:
            return True
        secret_collect_button_1 = Button(area=(280, 300, 290, 320), color=(), button=(280, 300, 290, 320),name='SECRET_COLLECT_BUTTON_1')
        secret_collect_button_2 = Button(area=(623, 248, 640, 260), color=(), button=(623, 248, 640, 260),name='SECRET_COLLECT_BUTTON_2')
        secret_collect_button_3 = Button(area=(980, 300, 990, 320), color=(), button=(980, 300, 990, 320),name='SECRET_COLLECT_BUTTON_3')
        secret_collect_button_4 = Button(area=(440, 510, 450, 520), color=(), button=(440, 510, 450, 520),name='SECRET_COLLECT_BUTTON_4')
        secret_collect_button_5 = Button(area=(800, 500, 810, 510), color=(), button=(800, 500, 810, 510),name='SECRET_COLLECT_BUTTON_5')
        next_secret_page_button = Button(area=(1180, 350, 1215, 400), color=(), button=(1180, 350, 1215, 400),name='NEXT_SECRET_PAGE_BUTTON')
        secret_collect_button_6 = Button(area=(343, 295, 350, 300), color=(), button=(343, 295, 350, 300),name='SECRET_COLLECT_BUTTON_6')  
        secret_collect_button_7 = Button(area=(790, 266, 800, 270), color=(), button=(790, 266, 800, 270),name='SECRET_COLLECT_BUTTON_7')
        secret_collect_button_8 = Button(area=(542, 523, 550, 530), color=(), button=(542, 523, 550, 530),name='SECRET_COLLECT_BUTTON_8')
        secret_collect_button_9 = Button(area=(970, 480, 980, 490), color=(), button=(970, 480, 980, 490),name='SECRET_COLLECT_BUTTON_9')
        secret_collect_button_list = [secret_collect_button_1, secret_collect_button_2, secret_collect_button_3, secret_collect_button_4, secret_collect_button_5, next_secret_page_button,secret_collect_button_6, secret_collect_button_7, secret_collect_button_8, secret_collect_button_9]   
        for button in secret_collect_button_list:
            while 1:
                self.device.screenshot()
                if self.handle_story_skip():
                    continue
                if self.is_in_daily_reward(interval=1) and button.name != 'NEXT_SECRET_PAGE_BUTTON':
                    self.device.click(button)
                    self.device.sleep(2)
                    break
                if button.name  == 'NEXT_SECRET_PAGE_BUTTON' and self.is_in_daily_reward() and self.appear(NEXT_SECRET_PAGE_BUTTON):
                    self.device.click(NEXT_SECRET_PAGE_BUTTON)
                    break
        while 1:  # Handle the last story
            self.device.screenshot()        
            if self.handle_story_skip():
                self.device.sleep(2)
                break
        return True

    def loop_aside(self):
        """
        Do all aside in page
        """
        while 1:
            logger.hr('Loop hospital aside', level=1)
            HOSPITAL_TAB.set('LOCATION', main=self)
            selected = self.select_aside()
            if not selected:
                break
            self.loop_invest()

        while 1:
            logger.hr('Loop hospital aside', level=1)
            HOSPITAL_TAB.set('CHARACTER', main=self)
            selected = self.select_aside()
            if not selected:
                break
            self.loop_invest()

        while 1:
            logger.hr('Loop hospital aside', level=1)
            HOSPITAL_TAB.set('CHARACTER', main=self)
            self.aside_swipe_down()
            selected = self.select_aside()
            if not selected:
                break
            self.loop_invest()

        while 1:
            logger.hr('Loop hospital aside', level=1)
            HOSPITAL_TAB.set('RECORD', main=self)
            selected = self.select_aside()
            if not selected:
                break
            self.loop_invest()
            
        while 1:
            logger.hr('Loop hospital aside', level=1)
            HOSPITAL_TAB.set('SECRET', main=self)
            # selected = self.select_aside()
            # if not selected:
            #     break
            if self.secret_collect():
                self.device.screenshot()
                self.loop_invest()
                break

        logger.info('Loop hospital aside end')

    def aside_swipe_down(self, skip_first_screenshot=True):
        """
        Swipe til no ASIDE_NEXT_PAGE
        """
        logger.info('Aside swipe down')
        swiped = False
        interval = Timer(2, count=6)
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            if swiped and not self.appear(ASIDE_NEXT_PAGE, offset=(20, 20)):
                logger.info('Aside reached end')
                break
            if interval.reached():
                p1, p2 = random_rectangle_vector(
                    vector=(0, -200), box=CLUE_LIST.area, random_range=(-20, -10, 20, 10))
                self.device.swipe(p1, p2)
                interval.reset()
                swiped = True
                continue

    def hospital_expected_end_combat(self):
        """
        Returns:
            bool: If combat ended
        """
        if self.handle_combat_exit():
            return True
        return False

    def ptRun(self):
        time_map = {'1': 'MORNING', '2': 'NOON', '3': 'NIGHT'}
        button_map = {'T1': T1, 'T2': T2, 'T3': T3, 'T4': T4}
        time_period = self.config.Hospital_mapName.split('-')[0]
        map_name = self.config.Hospital_mapName.split('-')[1].strip()


        while 1:
            self.device.screenshot()

            if self.event_time_limit_triggered():
                self.config.task_stop()

            # Log
            logger.hr(f'{time_map.get(time_period)}_{map_name}', level=2)
            # UI switches
            if self.handle_combat_exit():
                continue
            if self.ui_ensure(page_hospital):
                continue
            if self.event_pt_limit_triggered():
                logger.hr('Triggered stop condition: Event PT limit')
                break
            HOSPITAL_SIDEBAR.set(time_map.get(time_period), main=self)
            self.device.click(button_map.get(map_name))

            self.device.stuck_record_clear()
            self.device.click_record_clear()
            try:
                from module.exception import GameStuckError
                self.combat(balance_hp=False, expected_end=self.hospital_expected_end_combat)
                self.handle_combat_exit()
            except ScriptEnd as e:
                logger.hr('Script end')
                logger.info(str(e))
                break
            except GameStuckError as e:
               if self.detect_low_emotion():
                   return False
            # Scheduler
            if self.config.task_switched():
                self.config.task_stop()

    def run(self):
        # Check if event available
        if self.event_time_limit_triggered():
            self.config.task_stop()
        self.ui_ensure(page_campaign_menu)
        if self.is_event_entrance_available():
            self.ui_goto(page_hospital)

        # Receive rewards
        self.daily_reward_receive()

        # Run
        self.clue_enter()
        delay = True
        try:
            if not self.config.Hospital_mapName.endswith("Q"):
                self.loop_aside()
            if not self.config.Hospital_mapName.startswith("0"):
                self.clue_exit()
                if not self.ptRun():
                    delay = False

            # Scheduler
            if delay:
                self.config.task_delay(server_update=True)
        except OilExhausted:
            self.clue_exit()
            logger.hr('Triggered stop condition: Oil limit')
            self.config.task_delay(minute=(120, 240))
        except ScriptEnd as e:
            logger.hr('Script end')
            logger.info(str(e))
            self.clue_exit()
        except TaskEnd:
            self.clue_exit()
            raise


if __name__ == '__main__':
    self = Hospital('alas')
    self.device.screenshot()
    self.loop_aside()
