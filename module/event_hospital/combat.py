import re
from module.config.deep import deep_get
from module.base.decorator import run_once
from module.base.timer import Timer
from module.campaign.campaign_event import CampaignEvent
from module.combat.combat import BATTLE_PREPARATION, Combat
from module.event_hospital.assets import HOSPITAL_BATTLE_PREPARE
from module.event_hospital.ui import HospitalUI
from module.exception import OilExhausted, RequestHumanTakeover
from module.logger import logger
from module.map.assets import *
from module.map.map_fleet_preparation import FleetOperator
from module.raid.assets import RAID_FLEET_PREPARATION


class HospitalCombat(Combat, HospitalUI, CampaignEvent):
    def handle_fleet_recommend(self, recommend=True):
        """
        Args:
            recommend:

        Returns:
            bool: If clicked
        """
        fleet_1 = FleetOperator(
            choose=FLEET_1_CHOOSE, advice=FLEET_1_ADVICE, bar=FLEET_1_BAR, clear=FLEET_1_CLEAR,
            in_use=FLEET_1_IN_USE, hard_satisfied=FLEET_1_HARD_SATIESFIED, main=self)
        if fleet_1.in_use():
            return False

        if recommend:
            logger.info('Recommend fleet')
            fleet_1.recommend()
            return True
        else:
            logger.error('Fleet not prepared and fleet recommend is not enabled, '
                         'please prepare fleets manually before running')
            raise RequestHumanTakeover

    def combat_preparation(self, balance_hp=False, emotion_reduce=False, auto='combat_auto', fleet_index=1):
        """
        Args:
            balance_hp (bool):
            emotion_reduce (bool):
            auto (bool):
            fleet_index (int):
        """
        logger.info('Combat preparation.')
        skip_first_screenshot = True

        # No need, already waited in `raid_execute_once()`
        # if emotion_reduce:
        #     self.emotion.wait(fleet_index)

        @run_once
        def check_oil():
            if self.get_oil() < max(500, self.config.StopCondition_OilLimit):
                logger.hr('Triggered oil limit')
                raise OilExhausted

        @run_once
        def check_coin():
            if self.config.TaskBalancer_Enable and self.triggered_task_balancer():
                logger.hr('Triggered stop condition: Coin limit')
                self.handle_task_balancer()
                return True

        for _ in self.loop():

            if self.appear(BATTLE_PREPARATION, offset=(30, 20)):
                if self.handle_combat_automation_set(auto=auto == 'combat_auto'):
                    continue
                check_oil()
                check_coin()
            if self.handle_retirement():
                continue
            if self.handle_combat_low_emotion():
                continue
            if self.appear_then_click(BATTLE_PREPARATION, offset=(30, 20), interval=2):
                continue
            if self.handle_combat_automation_confirm():
                continue
            if self.handle_story_skip():
                continue
            # Handle fleet preparation
            if self.appear(RAID_FLEET_PREPARATION, offset=(30, 30), interval=2):
                if self.handle_fleet_recommend(recommend=self.config.Hospital_UseRecommendFleet):
                    self.interval_clear(RAID_FLEET_PREPARATION)
                    continue
                self.device.click(RAID_FLEET_PREPARATION)
                continue
            if self.appear_then_click(HOSPITAL_BATTLE_PREPARE, offset=(20, 20), interval=2):
                continue

            # End
            pause = self.is_combat_executing()
            if pause:
                logger.attr('BattleUI', pause)
                if emotion_reduce:
                    self.emotion.reduce(fleet_index)
                break

    in_clue_confirm = Timer(0.5, count=2)

    def hospital_expected_end(self):
        """
        Returns:
            bool: If combat ended
        """
        if self.handle_clue_exit():
            return False
        if self.is_in_clue():
            self.in_clue_confirm.start()
            if self.in_clue_confirm.reached():
                return True
        else:
            self.in_clue_confirm.reset()
        return False
    
    def hospital_expected_end_combat(self):
        """
        Returns:
            bool: If combat ended
        """
        if self.handle_combat_exit():
            return False
        return False
        
    def hospital_combat(self):
        """
        Pages:
            in: FLEET_PREPARATION
            out: is_in_clue
        """
        self.combat(balance_hp=False, expected_end=self.hospital_expected_end)

    def detect_low_emotion(self,name='Hospital'):
        from module.ocr.ocr import Ocr
        from module.notify import handle_notify
        from module.exception import ScriptEnd, GamePageUnknownError
        from module.handler.assets import LOW_EMOTION_LEFT
        EMOTION_TIP_L1=Button(area=(352, 311, 929, 348), color=(), button=(352, 311, 929, 348))
        EMOTION_TIP_L2=Button(area=(352, 350, 929, 387), color=(), button=(352, 350, 929, 387))
        EMOTION_TIP_L3=Button(area=(352, 390, 929, 427), color=(), button=(352, 390, 929, 427))
        # 获取识别结果
        result =  Ocr(EMOTION_TIP_L1, lang= 'cnocr').ocr(self.device.image)
        result += Ocr(EMOTION_TIP_L2, lang= 'cnocr').ocr(self.device.image)
        result += Ocr(EMOTION_TIP_L3, lang= 'cnocr').ocr(self.device.image)
        logger.info(result)
        if "强制" in result or "继续出击" in result:
            logger.warning("=====舰队心情低=====")

            logger.warning(f"{name} emotion recorded is :{self.emotion.fleet_1.current}")
            if self.emotion.fleet_1.current > 75:    
                handle_notify(
                    self.config.Error_OnePushConfig,
                    title=f"Alas <{self.config.config_name}> {name} Emotion calculate error ",
                    content=f"<{self.config.config_name}> emotion recorded is {self.emotion.fleet_1.current},Emotion calculate error"
                )
            self.emotion.fleet_1.current = 0
            self.emotion.record()
            self.emotion.show()
            try:
                self.emotion.check_reduce(battle=1)
            except ScriptEnd as e:#delay success
                logger.hr('Script end')
                logger.info(str(e))
                if self.appear_then_click(LOW_EMOTION_LEFT, offset=(30, 30), interval=3):#back
                    return True
                else:
                    raise GamePageUnknownError(f'LOW EMOTION TIP FOUND, BUT NO LEFT button')
                
    def event_pt_limit_triggered(self):
        """
        Returns:
            bool:

        Pages:
            in: page_event or page_sp
        """
        tasks =  ['Hospital']
        pt_limit = int(re.sub(r'[,.\'"，。]', '',
                        str(deep_get(self.config.data, 'EventGeneral.EventGeneral.PtLimit'))))
        logger.warning(f'=======ptlimit: {pt_limit}========')   
        if pt_limit <= 0:
            self.get_event_pt()
            return False
        pt = self.get_event_pt()
        logger.attr('Event_PT_limit', f'{pt}/{pt_limit}')
        if pt >= pt_limit:
            logger.hr(f'Reach event PT limit: {pt_limit}')
            self._disable_tasks(tasks)
            return True
        else:
            return False