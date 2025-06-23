import copy
import importlib
import os
import random

from module.campaign.campaign_base import CampaignBase
from module.campaign.campaign_event import CampaignEvent
from module.shop.shop_status import ShopStatus
from module.campaign.campaign_ui import MODE_SWITCH_1
from module.config.config import AzurLaneConfig
from module.exception import CampaignEnd, RequestHumanTakeover, ScriptEnd
from module.handler.fast_forward import map_files, to_map_file_name
from module.logger import logger
from module.notify import handle_notify
from module.ui.page import page_campaign

from module.exception import GameStuckError,GamePageUnknownError
from module.handler.assets import LOW_EMOTION_LEFT
from module.base.button import Button
from module.ocr.ocr import Ocr

class CampaignRun(CampaignEvent, ShopStatus):
    folder: str
    name: str
    stage: str
    module = None
    config: AzurLaneConfig
    campaign: CampaignBase
    run_count: int
    run_limit: int
    is_stage_loop = False

    def load_campaign(self, name, folder='campaign_main'):
        """
        Args:
            name (str): Name of .py file under module.campaign.
            folder (str): Name of the file folder under campaign.

        Returns:
            bool: If load.
        """
        if hasattr(self, 'name') and name == self.name:
            return False

        self.name = name
        self.folder = folder

        if folder.startswith('campaign_'):
            self.stage = '-'.join(name.split('_')[1:3])
        if folder.startswith('event') or folder.startswith('war_archives'):
            self.stage = name

        try:
            self.module = importlib.import_module('.' + name, f'campaign.{folder}')
        except ModuleNotFoundError:
            logger.warning(f'Map file not found: campaign.{folder}.{name}')
            if not os.path.exists(f'./campaign/{folder}'):
                logger.warning(f'Folder not exists: ./campaign/{folder}')
            else:
                files = map_files(folder)
                logger.warning(f'Existing files: {files}')

            logger.critical(f'Possible reason #1: This event ({folder}) does not have {name}')
            logger.critical(f'Possible reason #2: You are using an old Alas, '
                            'please check for update, or make map files yourself using dev_tools/map_extractor.py')
            raise RequestHumanTakeover

        config = copy.deepcopy(self.config).merge(self.module.Config())
        device = self.device
        self.campaign = self.module.Campaign(config=config, device=device)

        return True

    def triggered_stop_condition(self, oil_check=True):
        """
        Returns:
            bool: If triggered a stop condition.
        """
        # Run count limit
        if self.run_limit and self.config.StopCondition_RunCount <= 0:
            logger.hr('Triggered stop condition: Run count')
            self.config.StopCondition_RunCount = 0
            self.config.Scheduler_Enable = False
            handle_notify(
                self.config.Error_OnePushConfig,
                title=f"Alas <{self.config.config_name}> campaign finished",
                content=f"<{self.config.config_name}> {self.name} reached run count limit"
            )
            return True
        # Lv120 limit
        if self.config.StopCondition_ReachLevel and self.campaign.config.LV_TRIGGERED:
            logger.hr(f'Triggered stop condition: Reach level {self.config.StopCondition_ReachLevel}')
            self.config.Scheduler_Enable = False
            handle_notify(
                self.config.Error_OnePushConfig,
                title=f"Alas <{self.config.config_name}> campaign finished",
                content=f"<{self.config.config_name}> {self.name} reached level limit"
            )
            return True
        # Oil limit
        if oil_check:
            self.status_get_gems()
            self.get_coin()
            _oil = self.get_oil()
            if _oil < max(500, self.config.StopCondition_OilLimit):
                logger.hr('Triggered stop condition: Oil limit')
                self.config.task_delay(minute=(120, 240))
                return True
        # Auto search oil limit
        if self.campaign.auto_search_oil_limit_triggered:
            logger.hr('Triggered stop condition: Auto search oil limit')
            self.config.task_delay(minute=(120, 240))
            return True
        # If Get a New Ship
        if self.config.StopCondition_GetNewShip and self.campaign.config.GET_SHIP_TRIGGERED:
            logger.hr('Triggered stop condition: Get new ship')
            self.config.Scheduler_Enable = False
            handle_notify(
                self.config.Error_OnePushConfig,
                title=f"Alas <{self.config.config_name}> campaign finished",
                content=f"<{self.config.config_name}> {self.name} got new ship"
            )
            return True
        # Event limit
        if oil_check and self.campaign.event_pt_limit_triggered():
            logger.hr('Triggered stop condition: Event PT limit')
            return True
        # Auto search TaskBalancer
        if self.config.TaskBalancer_Enable and self.campaign.auto_search_coin_limit_triggered:
            logger.hr('Triggered stop condition: Auto search coin limit')
            self.handle_task_balancer()
            return True
        # TaskBalancer
        if oil_check and self.run_count >= 1:
            if self.config.TaskBalancer_Enable and self.triggered_task_balancer():
                logger.hr('Triggered stop condition: Coin limit')
                self.handle_task_balancer()
                return True

        return False

    def _triggered_app_restart(self):
        """
        Returns:
            bool: If triggered a restart condition.
        """
        if not self.campaign.emotion.is_ignore:
            if self.campaign.emotion.triggered_bug():
                logger.info('Triggered restart avoid emotion bug')
                return True

        return False

    def handle_app_restart(self):
        if self._triggered_app_restart():
            self.config.task_call('Restart')
            return True

        return False

    def handle_stage_name(self, name, folder, mode='normal'):
        """
        Handle wrong stage names.
        In some events, the name of SP may be different, such as 'vsp', muse sp.
        To call them easier, their map files should named 'sp.py'.

        Args:
            name (str): Name of .py file.
            folder (str): Name of the file folder under campaign.

        Returns:
            str, str: name, folder
        """
        name = to_map_file_name(name)
        # For GemsFarming, auto choose events or main chapters
        if self.config.task.command == 'GemsFarming':
            if self.stage_is_main(name):
                logger.info(f'Stage name {name} is from campaign_main')
                folder = 'campaign_main'
            else:
                folder = self.config.cross_get('Event.Campaign.Event')
                if folder is not None:
                    logger.info(f'Stage name {name} is from event {folder}')
                else:
                    logger.warning(f'Cannot get the latest event, fallback to campaign_main')
                    folder = 'campaign_main'
        # Handle special names SP maps
        if folder == 'event_20201126_cn' and name == 'vsp':
            name = 'sp'
        if folder == 'event_20210723_cn' and name == 'vsp':
            name = 'sp'
        if folder == 'event_20220324_cn' and name == 'esp':
            name = 'sp'
        if folder == 'event_20220818_cn' and name == 'esp':
            name = 'sp'
        if folder == 'event_20221124_cn' and name in ['asp', 'a.sp']:
            name = 'sp'
        if folder == 'event_20240425_cn':
            if name in ['μsp', 'usp', 'iisp']:
                name = 'sp'
            name = name.replace('lsp', 'isp').replace('1sp', 'isp')
            if name == 'isp':
                name = 'isp1'
        # Convert to chapter T
        convert = {
            'a1': 't1',
            'a2': 't2',
            'a3': 't3',
            'a4': 't4',
            'a5': 't5',
            'a6': 't6',
            'sp1': 't1',
            'sp2': 't2',
            'sp3': 't3',
            'sp4': 't4',
            'sp5': 't5',
            'sp6': 't6',
        }
        if folder in [
            'event_20211125_cn',
            'event_20231026_cn',
            'event_20241024_cn',
            'event_20250424_cn',
        ]:
            name = convert.get(name, name)
        # Convert between A/B/C/D and T/HT
        convert = {
            'a1': 't1',
            'a2': 't2',
            'a3': 't3',
            'b1': 't4',
            'b2': 't5',
            'b3': 't6',
            'c1': 'ht1',
            'c2': 'ht2',
            'c3': 'ht3',
            'd1': 'ht4',
            'd2': 'ht5',
            'd3': 'ht6',
        }
        if folder in [
            'event_20200917_cn',
            'event_20221124_cn',
            'event_20230525_cn',
            'war_archives_20200917_cn',
            # chapter T
            'event_20211125_cn',
            'event_20231026_cn',
            'event_20231123_cn',
            'event_20240725_cn',
            'event_20240829_cn',
            'event_20241024_cn',
            'event_20241121_cn',
            'event_20250424_cn',
        ]:
            name = convert.get(name, name)
        else:
            reverse = {v: k for k, v in convert.items()}
            name = reverse.get(name, name)
        # The Alchemist and the Archipelago of Secrets
        # Handle typo
        if folder == 'event_20221124_cn':
            name = name.replace('ht', 'th')
        # Chapter TH has no map_percentage and no 3_stars
        if folder == 'event_20221124_cn' and name.startswith('th'):
            if self.config.StopCondition_MapAchievement != 'non_stop':
                logger.info(f'When running chapter TH of event_20221124_cn, '
                            f'StopCondition.MapAchievement is forced set to threat_safe')
                self.config.override(StopCondition_MapAchievement='threat_safe')
        # event_20211125_cn, TSS maps are on time maps
        if folder == 'event_20211125_cn' and 'tss' in name:
            self.config.override(
                StopCondition_OilLimit=0,  # No oil cost
                StopCondition_MapAchievement='100_percent_clear',
                StopCondition_StageIncrease=True,
                Emotion_Mode='ignore',  # No emotion cost
                Fleet_Fleet2=0,  # Has only one fleet
                Submarine_Fleet=0,  # No submarine
            )
        # event_20230817_cn story states
        if folder == 'event_20230817_cn':
            if name.startswith('e0'):
                name = 'a1'
        # event_20240829_cn, TP -> SP
        if folder == 'event_20240829_cn':
            if name == 'tp':
                name = 'sp'
        # Stage loop
        for alias, stages in self.config.STAGE_LOOP_ALIAS.items():
            alias_folder, alias = alias
            if folder == alias_folder and name == alias.lower():
                stages = [i.strip(' \t\r\n') for i in stages.split('>')]
                cycle = len(stages)
                count = int(self.config.StopCondition_RunCount)
                if count == 0:
                    stage = random.choice(stages)
                    logger.info(f'Loop stages in {name.upper()}, run random stage: {stage}')
                else:
                    index = count % cycle
                    index = 0 if index == 0 else cycle - index
                    stage = stages[index]
                    logger.info(f'Loop stages in {name.upper()} with remain run_count={count}, '
                                f'run ordered stage: {stage}')
                name = stage.lower()
                self.is_stage_loop = True
        # Convert campaign_main to campaign hard if mode is hard and file exists
        if mode == 'hard' and folder == 'campaign_main' and name in map_files('campaign_hard'):
            folder = 'campaign_hard'

        return name, folder

    def can_use_auto_search_continue(self):
        # Cannot update map info in auto search menu
        # Close it if map achievement is set
        if self.config.StopCondition_MapAchievement != 'non_stop':
            return False

        return self.run_count > 0 and self.campaign.map_is_auto_search

    def handle_commission_notice(self):
        """
        Check commission notice.
        If found, stop current task and call commission.

        Raises:
            TaskEnd: If found commission notice.

        Pages:
            in: page_campaign
        """
        if self.campaign.commission_notice_show_at_campaign():
            logger.info('Commission notice found')
            self.config.task_call('Commission', force_call=True)
            self.config.task_stop('Commission notice found')
            
    def sync_emotion(self):
        KEYS = ['.Emotion.Fleet1Value','.Emotion.Fleet1Record','.Emotion.Fleet1Recover','.Emotion.Fleet2Value','.Emotion.Fleet2Record','.Emotion.Fleet2Recover']
        DATA =[self.config.Emotion_Fleet1Value,self.config.Emotion_Fleet1Record,self.config.Emotion_Fleet1Recover,self.config.Emotion_Fleet2Value,self.config.Emotion_Fleet2Record,self.config.Emotion_Fleet2Recover]
        for i, key in enumerate(KEYS):
            data = DATA[i]
            self.config.cross_set(keys=f'Event2{key}', value=f'{data}')
        logger.hr('detect emotion delay,sync emotion to event2')    
    def solve_emotion_error(self,name):
        method = self.config.Fleet_FleetOrder
        if method == 'fleet1_mob_fleet2_boss':
            fleet = 'fleet_1'
        elif method == 'fleet1_boss_fleet2_mob':
            fleet = 'fleet_2'
        elif method == 'fleet1_all_fleet2_standby':
            fleet = 'fleet_1'
        elif method == 'fleet1_standby_fleet2_all':
            fleet = 'fleet_2'
        logger.info(f"now combat is {method}")    
        logger.warning(f"{name} recorded {fleet} is :{getattr(self.campaign.emotion, fleet).current}")
        if getattr(self.campaign.emotion, fleet).current > 75:    
            handle_notify(
                self.config.Error_OnePushConfig,
                title=f"Alas <{self.config.config_name}> {name} Emotion calculate error ",
                content=f"<{self.config.config_name}> {fleet} recorded is {getattr(self.campaign.emotion, fleet).current},Emotion calculate error"
            )
        setattr(getattr(self.campaign.emotion, fleet), 'current', 0)
        self.campaign.emotion.record()
        self.campaign.emotion.show()
        try:
            self.campaign.emotion.check_reduce(self.campaign._map_battle)
        except ScriptEnd as e:
            logger.hr('Script end')
            logger.info(str(e))
            if self.appear_then_click(LOW_EMOTION_LEFT, offset=(30, 30), interval=3):
                return True
            else:
                raise GamePageUnknownError(f'LOW EMOTION TIP FOUND, BUT NO LEFT button')      
            
    def detect_low_emotion(self,name):
        EMOTION_TIP_L1=Button(area=(352, 311, 929, 348), color=(), button=(352, 311, 929, 348))
        EMOTION_TIP_L2=Button(area=(352, 350, 929, 387), color=(), button=(352, 350, 929, 387))
        EMOTION_TIP_L3=Button(area=(352, 390, 929, 427), color=(), button=(352, 390, 929, 427))
        # 获取识别结果
        result =  Ocr(EMOTION_TIP_L1, lang= 'cnocr').ocr(self.device.image)
        result += Ocr(EMOTION_TIP_L2, lang= 'cnocr').ocr(self.device.image)
        result += Ocr(EMOTION_TIP_L3, lang= 'cnocr').ocr(self.device.image)
        logger.info(result)
        if "低心情" in result or "降低好感" in result:
            logger.warning("舰队心情低")
            self.solve_emotion_error(name)
        else:
            logger.info("开始第二轮心情OCR识别")
            EMOTION_TIP_L4=Button(area=(352, 290, 929, 325), color=(), button=(352, 290, 929, 325))
            EMOTION_TIP_L5=Button(area=(352, 325, 929, 360), color=(), button=(352, 325, 929, 360))
            EMOTION_TIP_L6=Button(area=(352, 360, 929, 395), color=(), button=(352, 360, 929, 395))

            result2 =  Ocr(EMOTION_TIP_L4, lang= 'cnocr').ocr(image)
            result2 += Ocr(EMOTION_TIP_L5, lang= 'cnocr').ocr(image)
            result2 += Ocr(EMOTION_TIP_L6, lang= 'cnocr').ocr(image)
            if "低心情" in result2 or "降低好感" in result2:
                logger.warning("舰队心情低")
                self.solve_emotion_error(name)
            else:
                logger.warning("Game stuck, but not emotion error")
                raise GameStuckError(f'Wait too long but not emotion error')  
        
    def run(self, name, folder='campaign_main', mode='normal', total=0,from_eventDaily=False):
        """
        Args:
            name (str): Name of .py file.
            folder (str): Name of the file folder under campaign.
            mode (str): `normal` or `hard`
            total (int):
        """
        name, folder = self.handle_stage_name(name, folder, mode=mode)
        self.config.override(Campaign_Name=name, Campaign_Event=folder)
        self.load_campaign(name, folder=folder)
        self.run_count = 0
        self.run_limit = self.config.StopCondition_RunCount
        while 1:
            # End
            if total and self.run_count >= total:
                break
            if self.campaign.event_time_limit_triggered():
                self.config.task_stop()

            # Log
            logger.hr(name, level=1)
            if self.config.StopCondition_RunCount > 0:
                logger.info(f'Count remain: {self.config.StopCondition_RunCount}')
            else:
                logger.info(f'Count: {self.run_count}')

            # UI ensure
            self.device.stuck_record_clear()
            self.device.click_record_clear()
            if not self.device.has_cached_image:
                self.device.screenshot()
            self.campaign.device.image = self.device.image
            if self.campaign.is_in_map():
                logger.info('Already in map, retreating.')
                try:
                    self.campaign.withdraw()
                except CampaignEnd:
                    pass
                ensure_campaign_ui_result = self.campaign.ensure_campaign_ui(name=self.stage, mode=mode)
            elif self.campaign.is_in_auto_search_menu():
                if self.can_use_auto_search_continue():
                    logger.info('In auto search menu, skip ensure_campaign_ui.')
                else:
                    logger.info('In auto search menu, closing.')
                    # Because event_20240725 task balancer delete self.campaign.ensure_auto_search_exit()
                    ensure_campaign_ui_result = self.campaign.ensure_campaign_ui(name=self.stage, mode=mode)
            else:
                ensure_campaign_ui_result = self.campaign.ensure_campaign_ui(name=self.stage, mode=mode)
            if ensure_campaign_ui_result is False:
                logger.info('Maybe Already pass the stage, goto next.')
                self.campaign.handle_map_stop()
                break
            self.disable_raid_on_event()
            self.handle_commission_notice()

            # if in hard mode, check remain times
            if self.ui_page_appear(page_campaign) and MODE_SWITCH_1.get(main=self) == 'normal':
                from module.hard.hard import OCR_HARD_REMAIN
                remain = OCR_HARD_REMAIN.ocr(self.device.image)
                if not remain:
                    logger.info('Remaining number of times of hard mode campaign_main is 0, delay task to next day')
                    self.config.task_delay(server_update=True)
                    break

            # End
            if self.triggered_stop_condition(oil_check=not self.campaign.is_in_auto_search_menu()):
                break

            # Update config
            if len(self.config.modified):
                logger.info('Updating config for dashboard')
                self.config.update()

            # Run
            self.device.stuck_record_clear()
            self.device.click_record_clear()
            try:
                self.campaign.run()
            except ScriptEnd as e:
                logger.hr('Script end')
                logger.info(str(e))
                if from_eventDaily == True:
                    if str(e) == 'Emotion control':
                        self.sync_emotion()
                break
            except GameStuckError as e:
               if self.detect_low_emotion(name):
                   break
                   
            # Update config
            if len(self.campaign.config.modified):
                logger.info('Updating config for dashboard')
                self.campaign.config.update()
            # After run
            self.run_count += 1
            if self.config.StopCondition_RunCount:
                self.config.StopCondition_RunCount -= 1
            # End
            if self.triggered_stop_condition(oil_check=False):
                break
            # One-time stage limit
            if self.campaign.config.MAP_IS_ONE_TIME_STAGE:
                if self.run_count >= 1:
                    logger.hr('Triggered one-time stage limit')
                    self.campaign.handle_map_stop()
                    break
            # Loop stages
            if self.is_stage_loop:
                if self.run_count >= 1:
                    logger.hr('Triggered loop stage switch')
                    break
            # Scheduler
            if self.config.task_switched():
                self.campaign.ensure_auto_search_exit()
                self.config.task_stop()

        self.campaign.ensure_auto_search_exit()


if __name__ == '__main__':
    import numpy as np
    from PIL import Image   
    # 初始化logger
    logger.hr('测试低心情检测')
    
    def detect_low_emotion_TEST(image: np.ndarray):
        EMOTION_TIP_L1=Button(area=(352, 311, 929, 348), color=(), button=(352, 311, 929, 348))
        EMOTION_TIP_L2=Button(area=(352, 350, 929, 387), color=(), button=(352, 350, 929, 387))
        EMOTION_TIP_L3=Button(area=(352, 390, 929, 427), color=(), button=(352, 390, 929, 427))

        logger.info("开始OCR识别")
        # 获取识别结果
        result =  Ocr(EMOTION_TIP_L1, lang= 'cnocr').ocr(image)
        result += Ocr(EMOTION_TIP_L2, lang= 'cnocr').ocr(image)
        result += Ocr(EMOTION_TIP_L3, lang= 'cnocr').ocr(image)
        logger.info(f"OCR识别结果: {result}")
        
        if "低心情" in result or "降低好感" in result:
            logger.warning("舰队心情低")
        else:
            logger.info("开始第二轮OCR识别")
            EMOTION_TIP_L4=Button(area=(352, 290, 929, 325), color=(), button=(352, 290, 929, 325))
            EMOTION_TIP_L5=Button(area=(352, 325, 929, 360), color=(), button=(352, 325, 929, 360))
            EMOTION_TIP_L6=Button(area=(352, 360, 929, 395), color=(), button=(352, 360, 929, 395))

            result2 =  Ocr(EMOTION_TIP_L4, lang= 'cnocr').ocr(image)
            result2 += Ocr(EMOTION_TIP_L5, lang= 'cnocr').ocr(image)
            result2 += Ocr(EMOTION_TIP_L6, lang= 'cnocr').ocr(image)
            if "低心情" in result2 or "降低好感" in result2:
                logger.warning("舰队心情低")
            else:
                logger.warning("Game stuck, but not emotion error")
                raise GameStuckError(f'Wait too long but not emotion error')  
    
    # 测试用例
    logger.info("正在读取测试图片")
    try:
        image = np.array(Image.open(r'C:\Users\W1NDe\Documents\GitHub\M-AzurLaneAutoScript\module\campaign\test.png').convert('RGB'))
        logger.info(f"成功读取图片,尺寸: {image.shape}")
        detect_low_emotion_TEST(image)
    except Exception as e:
        logger.warning(f"读取图片失败: {str(e)}")