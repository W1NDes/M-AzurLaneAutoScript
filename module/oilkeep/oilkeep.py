
from module.logger import logger
from module.oilkeep.assets import *
from module.ui.ui import UI
from module.base.timer import Timer
from module.combat.assets import GET_ITEMS_1, GET_ITEMS_2
from module.freebies.assets import *
from module.logger import logger
from module.ui.page import GOTO_MAIN_WHITE, MAIN_GOTO_CAMPAIGN_WHITE, page_mail, page_main, page_main_white
from module.ui.ui import UI
from module.campaign.assets import OCR_OIL, OCR_OIL_LIMIT, OCR_OIL_CHECK
from module.log_res.log_res import LogRes
from module.base.utils import color_similar, get_color
from module.ocr.ocr import Digit
class Oilkeep(UI):
    def _mail_enter_and_get_oil(self,oilLine,nowOil, skip_first_screenshot=True):
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
            
    def _get_num(self, _button, name):
        # Update offset
        _ = self.appear(OCR_OIL_CHECK)

        color = get_color(self.device.image, OCR_OIL_CHECK.button)
        if color_similar(color, OCR_OIL_CHECK.color):
            # Original color
            ocr = Digit(_button, name=name, letter=(247, 247, 247), threshold=128)
        elif color_similar(color, (59, 59, 64)):
            # With black overlay
            ocr = Digit(_button, name=name, letter=(165, 165, 165), threshold=128)
        else:
            logger.warning(f'Unexpected OCR_OIL_CHECK color')
            ocr = Digit(_button, name=name, letter=(247, 247, 247), threshold=128)

        return ocr.ocr(self.device.image)      
       
    def get_oil(self, skip_first_screenshot=True, update=False):
        """
        Returns:
            int: Oil amount
        """
        _oil = {}
        timeout = Timer(1, count=2).start()
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            if not self.appear(OCR_OIL_CHECK, offset=(10, 2)):
                logger.info('No oil icon')
                self.device.sleep(2)

            if timeout.reached():
                logger.warning('Get oil timeout')
                break

            _oil = {
                'Value': self._get_num(OCR_OIL, 'OCR_OIL'),
                'Limit': self._get_num(OCR_OIL_LIMIT, 'OCR_OIL_LIMIT')
            }
            if _oil['Value'] >= 100:
                break
        LogRes(self.config).Oil = _oil
        if update:
            self.config.update()

        return _oil['Value']
    def update_oil(self):
        self.ui_ensure(page_main)
        if self.appear_then_click(MAIN_GOTO_CAMPAIGN_WHITE, offset=(30, 30), interval=3):
            logger.info('MAIN_GOTO_CAMPAIGN_WHITE')
        oilOcr = self.get_oil()
        logger.info(f'Oil now: {oilOcr}')
        self.ui_ensure(page_main)
        return oilOcr
    
    def pageCheck(self):
        self.ui_ensure(page_main)
        if self.appear(page_main_white.check_button, offset=(30, 30)):
            logger.info('pageCheck: At page_main_white')
            return True
        elif self.appear(page_main.check_button, offset=(5, 5)):
            logger.warning('At page_main, cannot enter mail page from old UI')
            return False
        else:
            logger.warning('Unknown page_main, cannot enter mail page')
            return False
        
    def run(self):
        logger.hr('Oil Keep', level=1)
        OilkeepLine = self.config.Oilkeep_OilkeepLevel
        oilOcrNow = self.update_oil()
        if self.pageCheck() is True and oilOcrNow != 0 and oilOcrNow < OilkeepLine -100:
            self._mail_enter_and_get_oil(OilkeepLine, oilOcrNow)
            self._mail_quit()
            self.update_oil()
        self.config.task_delay(server_update=True)