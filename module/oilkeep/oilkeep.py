
from module.logger import logger
from module.oilkeep.assets import *
from module.base.timer import Timer
from module.combat.assets import GET_ITEMS_1, GET_ITEMS_2
from module.freebies.assets import *
from module.logger import logger
from module.ui.page import GOTO_MAIN_WHITE, MAIN_GOTO_CAMPAIGN_WHITE, page_mail, page_main, page_main_white
from module.ui.page import page_campaign
from module.campaign.campaign_status import CampaignStatus
import time
class Oilkeep(CampaignStatus):
    def _mail_enter_and_get_oil(self,oilLine,nowOil, OilMaxGet, skip_first_screenshot=True):
        """
        Returns:
            int: If having mails

        Page:
            in: page_main_white or MAIL_MANAGE
            out: MAIL_BATCH_CLAIM
        """
        logger.info('Mail enter')
        self.interval_clear([
            MAIL_MANAGE
        ])
        timeout = Timer(0.6, count=1)
        has_mail = False
        mail_oil_add_count = 0
        oil_add_need = 0
        if nowOil < oilLine:
            if (oilLine - nowOil) > OilMaxGet:
                oil_add_need = OilMaxGet // 100
            else:
                oil_add_need = (oilLine - nowOil) // 100
            logger.info(f'Need oil add count: {oil_add_need} ')
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            # End
            if self.appear(MAIL_BATCH_CLAIM, offset=(20, 20)):
                logger.info('Mail entered')
                return True
            # if self.appear(MAIL_WHITE_EMPTY, offset=(20, 20)):
            #     logger.info('Mail empty')
            #     return False
            # if not has_mail and self.appear(GOTO_MAIN_WHITE, offset=(20, 20)):
            #     timeout.start()
            #     if timeout.reached():
            #         logger.info('Mail empty, wait GOTO_MAIN_WHITE timeout')
            #         return False

            # Click
            if self.appear_then_click(MAIL_OIL, offset=(30, 30), interval=3):
                logger.info('MAIL_OIL entered')
                continue
            if mail_oil_add_count <= oil_add_need-1 and self.appear_then_click_nocheck(MAIL_OIL_ADD, offset=(30, 30), interval=0.3):
                mail_oil_add_count += 1
                logger.info('MAIL_OIL_ADD')
                continue
            if mail_oil_add_count >= oil_add_need:
                if self.appear_then_click(MAIL_OIL_GET, offset=(30, 30), interval=3):
                    logger.info('MAIL_OIL_GET')
                if self.appear_then_click(NO_OIL_GET, offset=(2, 2), interval=3):   
                    logger.warning('there is no oil in mailroom')
                    break
                if self.appear_then_click(MAIL_OIL_GET_ENSURE, offset=(30, 30), interval=3):   
                    logger.info('MAIL_OIL_GET_ENSURE')
                    break
            if self.ui_main_appear_then_click(page_mail, offset=(30, 30), interval=3):
                continue
        return False
    
    def _mail_quit(self, skip_first_screenshot=True):
        """
        Page:
            in: Any page in page_mail
            out: page_main_white
        """
        logger.info('Mail quit')
        self.interval_clear([
            MAIL_BATCH_CLAIM,
            GOTO_MAIN_WHITE,
            GET_ITEMS_1,
            GET_ITEMS_2,
        ])
        self.popup_interval_clear()
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            # End
            if self.ui_page_appear(page_main):
                logger.info('Mail quit to page_main')
                break

            # Click
            if self.handle_popup_confirm('MAIL_QUIT'):
                continue
            if self.appear(MAIL_BATCH_CLAIM, offset=(30, 30), interval=3):
                logger.info(f'{MAIL_BATCH_CLAIM} -> {MAIL_MANAGE}')
                self.device.click(MAIL_MANAGE)
                continue
            if self.appear_then_click(GOTO_MAIN_WHITE, offset=(30, 30), interval=3):
                continue
            
    def update_oil(self):
        self.ui_ensure(page_campaign)
        oilOcr_values = []
        for attempt in range(3):  # 尝试3次
            oilOcr = self.get_oil(skip_first_screenshot=False)
            logger.info(f'Attempt {attempt + 1} - Oil now: {oilOcr}')
            
            if oilOcr == 0:
                logger.warning('Oil value is 0.')
                return False
            
            oilOcr_values.append(oilOcr)
            
            # 检查是否所有获取的值都相同
            if len(set(oilOcr_values)) != 1:
                logger.warning('Inconsistent oil readings detected.')
                return False
            
            if attempt < 2:  
                time.sleep(1)  
        
        self.ui_ensure(page_main)
        logger.info('Oil readings are consistent and non-zero.')
        return oilOcr_values[0] 
    
    def pageCheck(self):
        self.ui_ensure(page_main)
        if self.appear(page_main_white.check_button, offset=(30, 30)):
            logger.info('pageCheck: At page_main_white')
            return True
        elif self.appear(page_main.check_button, offset=(5, 5)):
            logger.info('At page_main')
            pass
        else:
            logger.warning('Unknown page_main, cannot enter mail page')
            return False
        
    def run(self):
        logger.hr('Oil Keep', level=1)
        OilkeepLine = self.config.Oilkeep_OilkeepLevel
        OilMaxGet = self.config.Oilkeep_OilMaxGet
        for attempt in range(3):  # 
            oilOcrNow = self.update_oil()
            if oilOcrNow is not False:
                break  
            elif attempt == 2:  
                return False  
            time.sleep(1) 
        if self.pageCheck() is True and oilOcrNow != 0 and oilOcrNow < OilkeepLine -100:
            self._mail_enter_and_get_oil(OilkeepLine, oilOcrNow, OilMaxGet)
            self._mail_quit()
            self.update_oil()
        self.config.task_delay(server_update=True)