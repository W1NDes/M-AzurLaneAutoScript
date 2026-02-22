from module.base.timer import Timer
from module.campaign.campaign_event import CampaignEvent
from module.exception import ScriptEnd, ScriptError, GameStuckError
from module.logger import logger
from module.raid.assets import RAID_REWARDS
from module.raid.raid import Raid, raid_ocr
from module.ui.page import page_campaign_menu, page_raid, page_rpg_stage


class RaidRun(Raid, CampaignEvent):
    run_count: int
    run_limit: int

    def triggered_stop_condition(self, oil_check=False, pt_check=False, coin_check=False):
        """
        Returns:
            bool: If triggered a stop condition.
        """
        # Run count limit
        if self.run_limit and self.config.StopCondition_RunCount <= 0:
            logger.hr('Triggered stop condition: Run count')
            self.config.StopCondition_RunCount = 0
            self.config.Scheduler_Enable = False
            return True

        return super().triggered_stop_condition(oil_check=oil_check, pt_check=pt_check, coin_check=coin_check)

    def get_remain(self, mode, skip_first_screenshot=True):
        """
        Args:
            mode (str): easy, normal, hard, ex
            skip_first_screenshot (bool):

        Returns:
            int:
        """
        confirm_timer = Timer(0.3, count=0)
        prev = 30
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.sleep(0.5)
                self.device.screenshot()

            ocr = raid_ocr(raid=self.config.Campaign_Event, mode=mode)
            result = ocr.ocr(self.device.image)
            if mode == 'ex':
                remain = result
            else:
                remain, _, _ = result
            logger.attr(f'{mode.capitalize()} Remain', remain)

            if self.appear_then_click(RAID_REWARDS, offset=(30, 30), interval=3):
                confirm_timer.reset()
                continue

            # End
            if remain == prev:
                if confirm_timer.reached():
                    break
            else:
                confirm_timer.reset()

            prev = remain

        return remain

    def detect_low_emotion(self):
        from module.base.button import Button
        from module.ocr.ocr import Ocr
        from module.exception import GamePageUnknownError
        from module.handler.assets import LOW_EMOTION_LEFT
        EMOTION_TIP_L1 = Button(area=(352, 311, 929, 348), color=(), button=(352, 311, 929, 348))
        EMOTION_TIP_L2 = Button(area=(352, 350, 929, 387), color=(), button=(352, 350, 929, 387))
        EMOTION_TIP_L3 = Button(area=(352, 390, 929, 427), color=(), button=(352, 390, 929, 427))
        result = Ocr(EMOTION_TIP_L1, lang='cnocr').ocr(self.device.image)
        result += Ocr(EMOTION_TIP_L2, lang='cnocr').ocr(self.device.image)
        result += Ocr(EMOTION_TIP_L3, lang='cnocr').ocr(self.device.image)
        logger.info(result)
        if "强制" in result or "继续出击" in result:
            logger.warning("舰队心情低")
        else:
            logger.info("开始第二轮心情OCR识别")
            EMOTION_TIP_L4 = Button(area=(352, 290, 929, 325), color=(), button=(352, 290, 929, 325))
            EMOTION_TIP_L5 = Button(area=(352, 325, 929, 360), color=(), button=(352, 325, 929, 360))
            EMOTION_TIP_L6 = Button(area=(352, 360, 929, 395), color=(), button=(352, 360, 929, 395))
            result2 = Ocr(EMOTION_TIP_L4, lang='cnocr').ocr(self.device.image)
            result2 += Ocr(EMOTION_TIP_L5, lang='cnocr').ocr(self.device.image)
            result2 += Ocr(EMOTION_TIP_L6, lang='cnocr').ocr(self.device.image)
            if "强制" in result2 or "继续出击" in result2:
                logger.warning("舰队心情低")
            else:
                logger.warning("Game stuck, but not emotion error")
                raise GameStuckError('Wait too long but not emotion error')
        logger.warning(f"Raid emotion recorded is: {self.emotion.fleet_1.current}")
        if self.emotion.fleet_1.current > 75:
            from module.notify import handle_notify
            handle_notify(
                self.config.Error_OnePushConfig,
                title=f"Alas <{self.config.config_name}> Raid Emotion calculate error ",
                content=f"<{self.config.config_name}> fleet_1 recorded is {self.emotion.fleet_1.current},Emotion calculate error"
            )
        self.emotion.fleet_1.current = 0
        self.emotion.record()
        self.emotion.show()
        try:
            self.emotion.check_reduce(battle=1)
        except ScriptEnd as e:
            logger.hr('Script end')
            logger.info(str(e))
            if self.appear_then_click(LOW_EMOTION_LEFT, offset=(30, 30), interval=3):
                return True
            else:
                raise GamePageUnknownError('LOW EMOTION TIP FOUND, BUT NO LEFT button')
        return False

    def run(self, name='', mode='', total=0):
        """
        Args:
            name (str): Raid name, such as 'raid_20200624'
            mode (str): Raid mode, such as 'hard', 'normal', 'easy'
            total (int): Total run count
        """
        name = name if name else self.config.Campaign_Event
        mode = mode if mode else self.config.Raid_Mode
        if not name or not mode:
            raise ScriptError(f'RaidRun arguments unfilled. name={name}, mode={mode}')

        self.run_count = 0
        self.run_limit = self.config.StopCondition_RunCount
        while 1:
            # End
            if total and self.run_count == total:
                break
            if self.event_time_limit_triggered():
                self.config.task_stop()

            # Log
            logger.hr(f'{name}_{mode}', level=2)
            if self.config.StopCondition_RunCount > 0:
                logger.info(f'Count remain: {self.config.StopCondition_RunCount}')
            else:
                logger.info(f'Count: {self.run_count}')

            # UI switches
            if not self._raid_has_oil_icon:
                self.ui_ensure(page_campaign_menu)
                if self.triggered_stop_condition(oil_check=True, coin_check=True):
                    break

            # UI ensure
            self.device.stuck_record_clear()
            self.device.click_record_clear()
            if not self.is_raid_rpg():
                self.ui_ensure(page_raid)
            else:
                self.ui_ensure(page_rpg_stage)
                self.raid_rpg_swipe()
            self.disable_event_on_raid()

            # End for mode EX
            if mode == 'ex' and not self.is_raid_rpg():
                if not self.get_remain(mode):
                    logger.info('Triggered stop condition: Zero '
                                'raid tickets to do EX mode')
                    if self.config.task.command == 'Raid':
                        with self.config.multi_set():
                            self.config.StopCondition_RunCount = 0
                            self.config.Scheduler_Enable = False
                    break

            # Run
            self.device.stuck_record_clear()
            self.device.click_record_clear()
            try:
                self.raid_execute_once(mode=mode, raid=name)
            except ScriptEnd as e:
                logger.hr('Script end')
                logger.info(str(e))
                break
            except GameStuckError as e:
                if self.detect_low_emotion():
                    break

            # After run
            self.run_count += 1
            if self.config.StopCondition_RunCount:
                self.config.StopCondition_RunCount -= 1
            # End

            if self.config.StopCondition_StageIncrease:
                prev_mode = mode
                next_mode = self.raid_name_increase(prev_mode)
                if next_mode != prev_mode:
                    logger.info(f'Stage {prev_mode} increases to {next_mode}')
                    self.config.Raid_Mode = next_mode
                    mode = next_mode
                    continue
            if self.triggered_stop_condition():
                break
            # Scheduler
            if self.config.task_switched():
                self.config.task_stop()
