import re

from module.campaign.campaign_event import CampaignEvent
from module.coalition.assets import *
from module.coalition.combat import CoalitionCombat
from module.exception import ScriptError, ScriptEnd, GameTooManyClickError
from module.logger import logger
from module.ocr.ocr import Digit
from module.log_res.log_res import LogRes
from module.campaign.assets import OCR_OIL, OCR_OIL_CHECK
from module.base.utils import  get_color
import module.config.server as server
from module.notify import handle_notify

class AcademyPtOcr(Digit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.alphabet += ':'

    def after_process(self, result):
        logger.attr(self.name, result)
        try:
            # 累计: 840
            result = result.rsplit(':')[1]
        except IndexError:
            pass
        return super().after_process(result)


class Coalition(CoalitionCombat, CampaignEvent):
    run_count: int
    run_limit: int

    def get_event_pt(self):
        """
        Returns:
            int: PT amount, or 0 if unable to parse
        """
        event = self.config.Campaign_Event
        if event == 'coalition_20230323':
            ocr = Digit(FROSTFALL_OCR_PT, name='OCR_PT', letter=(198, 158, 82), threshold=128)
        elif event == 'coalition_20240627':
            ocr = AcademyPtOcr(ACADEMY_PT_OCR, name='OCR_PT', letter=(255, 255, 255), threshold=128)
        elif event == 'coalition_20250626':
            # use generic ocr model
            ocr = Digit(NEONCITY_PT_OCR, name='OCR_PT', lang='cnocr', letter=(208, 208, 208), threshold=128)
        else:
            logger.error(f'ocr object is not defined in event {event}')
            raise ScriptError

        pt = ocr.ocr(self.device.image)
        LogRes(self.config).Pt = pt
        self.config.update()
        return pt

    def _get_oil(self):
        logger.info("using coalition_get_num")
        # Update offset
        _ = self.appear(OCR_OIL_CHECK)

        color = get_color(self.device.image, OCR_OIL_CHECK.button)
        ocr = Digit(OCR_OIL, name='OCR_OIL', letter=(165, 165, 165), threshold=152)

        return ocr.ocr(self.device.image)
    
    def triggered_stop_condition(self, oil_check=False, pt_check=False):
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
        # Oil limit
        if oil_check:
            if self.get_oil() < max(500, self.config.StopCondition_OilLimit):
                logger.hr('Triggered stop condition: Oil limit')
                self.config.task_delay(minute=(120, 240))
                return True
        # Event limit
        if pt_check:
            if self.event_pt_limit_triggered():
                logger.hr('Triggered stop condition: Event PT limit')
                return True
        # TaskBalancer
        if self.run_count >= 1:
            if self.config.TaskBalancer_Enable and self.triggered_task_balancer():
                logger.hr('Triggered stop condition: Coin limit')
                self.handle_task_balancer()
                return True

        return False

    def coalition_execute_once(self, event, stage, fleet):
        """
        Args:
            event:
            stage:
            fleet:

        Pages:
            in: in_coalition
            out: in_coalition
        """
        self.config.override(
            Campaign_Name=f'{event}_{stage}',
            Campaign_UseAutoSearch=False,
            Fleet_FleetOrder='fleet1_all_fleet2_standby',
        )
        if self.config.Coalition_Fleet == 'single' and self.config.Emotion_Fleet1Control == 'prevent_red_face':
            logger.warning('AL does not allow single coalition with emotion < 30, '
                           'emotion control is forced to prevent_yellow_face')
            self.config.override(Emotion_Fleet1Control='prevent_yellow_face')
        if stage == 'sp':
            # Multiple fleets are required in SP
            self.config.override(
                Coalition_Fleet='multi',
            )
        try:
            self.emotion.check_reduce(battle=self.coalition_get_battles(event, stage))
        except ScriptEnd:
            self.coalition_map_exit(event)
            raise

        self.enter_map(event=event, stage=stage, mode=fleet)
        if self.triggered_stop_condition(oil_check=True):
            self.coalition_map_exit(event)
            raise ScriptEnd
        self.coalition_combat()

    @staticmethod
    def handle_stage_name(event, stage):
        stage = re.sub('[ \t\n]', '', str(stage)).lower()
        if event == 'coalition_20230323':
            stage = stage.replace('-', '')

        return event, stage
    
    def get_run_info(self, event, mode, fleet):
        event = event if event else self.config.Campaign_Event
        mode = mode if mode else self.config.Coalition_Mode
        fleet = fleet if fleet else self.config.Coalition_Fleet
        if not event or not mode or not fleet:
            raise ScriptError(f'Coalition arguments unfilled. name={event}, mode={mode}, fleet={fleet}')
        event, mode = self.handle_stage_name(event, mode)
        return event, mode, fleet
    
    def solve_emotion_error(self, event, stage):
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
        logger.warning(f"{event}_{stage} recorded {fleet} is :{getattr(self.emotion, fleet).current}")
        if getattr(self.emotion, fleet).current > 75:    
            handle_notify(
                self.config.Error_OnePushConfig,
                title=f"Alas <{self.config.config_name}> {event}_{stage} Emotion calculate error ",
                content=f"<{self.config.config_name}> {fleet} recorded is {getattr(self.emotion, fleet).current},Emotion calculate error"
            )
        setattr(getattr(self.emotion, fleet), 'current', 0)
        self.emotion.record()
        self.emotion.show()
        try:
            self.emotion.check_reduce(battle=self.coalition_get_battles(event, stage))
        except ScriptEnd as e:
            logger.hr('Script end')
            logger.info(str(e))
            
    def run(self, event='', mode='', fleet='', total=0):
        event, mode, fleet = self.get_run_info(event, mode, fleet)

        self.run_count = 0
        self.run_limit = self.config.StopCondition_RunCount
        while 1:
            # End
            if total and self.run_count == total:
                break
            if self.event_time_limit_triggered():
                self.config.task_stop()

            # Log
            logger.hr(f'{event}_{mode}', level=2)
            if self.config.StopCondition_RunCount > 0:
                logger.info(f'Count remain: {self.config.StopCondition_RunCount}')
            else:
                logger.info(f'Count: {self.run_count}')

            # UI switches
            self.device.stuck_record_clear()
            self.device.click_record_clear()
            self.ui_goto_coalition()
            self.coalition_ensure_mode(event, 'battle')

            # End
            if self.triggered_stop_condition(pt_check=True):
                break

            # Run
            self.device.stuck_record_clear()
            self.device.click_record_clear()
            try:
                self.coalition_execute_once(event=event, stage=mode, fleet=fleet)
            except ScriptEnd as e:
                logger.hr('Script end')
                logger.info(str(e))
                break
            except GameTooManyClickError as e:
               if self.appear(COALITION_LOW_EMOTION, offset=(20, 20)):
                   logger.warning("连战舰队心情低")
                   self.solve_emotion_error(event=event, stage=mode)
                   break
            # After run
            self.run_count += 1
            if self.config.StopCondition_RunCount:
                self.config.StopCondition_RunCount -= 1
            # End
        

            if self.config.StopCondition_StageIncrease:
                prev_stage = self.config.Coalition_Mode
                next_stage = self.coalition_name_increase(prev_stage)
                if next_stage != prev_stage:
                    logger.info(f'Stage {prev_stage} increases to {next_stage}')
                    self.config.Coalition_Mode = next_stage
                    event, mode, fleet = self.get_run_info(event, self.config.Coalition_Mode, fleet)
                    continue
                elif self.config.EventPt_EventPtSwitch:
                    if not self.config.is_task_enabled('CoalitionSp'):
                        self.config.task_call('CoalitionSp')
                    continue
            if self.triggered_stop_condition(pt_check=True):
                break
            # Scheduler
            if self.config.task_switched():
                self.config.task_stop()
