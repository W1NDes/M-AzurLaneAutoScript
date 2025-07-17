import sys

import re

from datetime import datetime
sys.path.append(r'C:/Users/W1NDe/Documents/GitHub/M-AzurLaneAutoScript')
from module.base.button import ButtonGrid
from module.ui.ui import UI
from module.ui.page import page_main
from module.smallevent.assets import * 
from module.handler.assets import POPUP_CONFIRM
from module.combat.assets import GET_ITEMS_1
from module.logger import logger
from module.base.timer import Timer
from module.log_res.log_res import LogRes
from module.base.utils import crop
from module.ocr.api_ocr import BaiduOcr, VolcOcr
class SmallEvent(UI):
    SEVEND_DATE = "20250320"  # 集中管理活动日期
    
    def GirlShow(self):
        SMALL_EVENT_20250227_ENTRY =Button(area=(20, 280, 200, 330), color=(), button=(20, 280, 200, 330))
        GIRL_GET =Button(area=(913, 138, 969, 186), color=(), button=(913, 138, 969, 186))
        _GIRL_1 =Button(area=(310, 260, 355, 355), color=(), button=(310, 260, 355, 355))

        self.ui_ensure(page_main_white)
        girlGetPage = 1
        skip_first_screenshot = True
        while 1:
            
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()
        
            if self.appear_then_click(EVENT_NOTIFY_ENTRY, offset=(5, 5), interval=3):
                continue
            if self.appear(EVENT_NOTIFY_PAGE, offset=(5, 5)) and not self.appear(SMALL_EVENT_20250227, offset=(5, 5)):
                self.device.click(SMALL_EVENT_20250227_ENTRY)
                continue
            if self.appear(SMALL_EVENT_20250227, offset=(5, 5)):
                if girlGetPage == 1:
                    self.device.click(_GIRL_1)
                    girlGetPage += 1
                    continue
                # self.device.sleep(1)
                if not self.appear(GIRL_GOT, offset=(10, 10),similarity=0.75):
                    logger.info("Girl not got")
                    self.device.click(GIRL_GET)
                if self.appear(GIRL_GOT, offset=(5, 5)):
                    if self.appear(ALL_GIRL_GOT, offset=(5, 5)):
                        break
                    self.device.sleep(1.5)
                    logger.warn(girlGetPage)
                    if self.appear(N_GIRL_2, offset=(5, 5),similarity=0.75) and girlGetPage == 2:
                        self.device.click(N_GIRL_2)
                        continue
                    if self.appear(N_GIRL_3, offset=(5, 5),similarity=0.75) and girlGetPage == 3:
                        self.device.click(N_GIRL_3)
                        continue
                    if self.appear(N_GIRL_4, offset=(5, 5),similarity=0.75) and girlGetPage == 4:
                        self.device.click(N_GIRL_4)
                        continue
                    if self.appear(N_GIRL_1, offset=(5, 5)):
                        self.device.click(N_GIRL_1)
                        girlGetPage += 1
                        continue

            if self.story_skip():
                continue   
            if self.appear_then_click(POPUP_CONFIRM,offset=(10, 10)):
                continue
            if self.appear_then_click(GET_ITEMS_1,offset=(10, 10)):
                continue              
        return True

    def SevenDayTask(self,SEVEND_TASK_ICON_MAIN,SEVEND_TASK_GET1,SEVEND_TASK_GET2,SEVEND_TASK_FINISH,SEVEND_TASK_UNGET1=None,SEVEND_TASK_UNGET2=None):
        self.ui_ensure(page_main)
        skip_first_screenshot = True
        CLICK_COUNT = 0
        NOCLICK_COUNT = 0
        NOCLICK_TIMER =Timer(3,count=10)
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()
            if self.appear_then_click(EVENT_NOTIFY_ENTRY, offset=(5, 5), interval=3):
                continue                
            if self.appear(EVENT_NOTIFY_PAGE, offset=(5, 5)) and CLICK_COUNT < 14 and not self.appear(SEVEND_TASK_ICON_MAIN, offset=(5, 5)):
                current_button = Button(area=(20, 110 + CLICK_COUNT * 30, 200, 170 + CLICK_COUNT * 30), 
                                       color=(), 
                                       button=(20, 110 + CLICK_COUNT * 30, 200, 170 + CLICK_COUNT * 30))# 创建一个动态调整y坐标的按钮
                self.device.click(current_button,control_check=False)
                self.device.sleep(0.3)
                logger.info(f"Clicking SMALL_EVENT_ENTRY count: {CLICK_COUNT}")
                CLICK_COUNT += 1
                continue    
            if self.appear_then_click(SEVEND_TASK_GET1, offset=(5, 5), interval=1):
                if LogRes(self.config).SevenDayStatus >= 15:
                    LogRes(self.config).SevenDayStatus = 0
                LogRes(self.config).SevenDayStatus += 1
                continue
            if self.appear_then_click(SEVEND_TASK_GET2, offset=(5, 5), interval=1):
                if LogRes(self.config).SevenDayStatus >= 15:
                    LogRes(self.config).SevenDayStatus = 0
                LogRes(self.config).SevenDayStatus += 1
                continue
            # if self.appear(SEVEND_TASK_UNGET1 , offset=(5, 5)) and self.appear(SEVEND_TASK_UNGET2, offset=(5, 5)):
            #     break
            if self.story_skip():
                continue   
            if self.appear_then_click(POPUP_CONFIRM,offset=(10, 10), interval=1):
                continue
            if self.appear_then_click(GET_ITEMS_1,offset=(10, 10), interval=1):
                continue 
            
            NOCLICK_TIMER.start()
            if NOCLICK_TIMER.reached():
                NOCLICK_COUNT += 1
                NOCLICK_TIMER.reset()
                if NOCLICK_COUNT >= 5:
                    logger.info("SEVEND_TASK No click TIMER REACHED")
                    # LogRes(self.config).SevenDayStatus = 0
                    break
            if self.appear(SEVEND_TASK_FINISH, offset=(5, 5),similarity=0.95):
                LogRes(self.config).SevenDayStatus = 15
                logger.info(f"SEVEND_TASK_{self.SEVEND_DATE} FINISH")
                break

    def recognize_text(self, image, area, ocr_api=None, model="general_basic"):
        """
        Use Baidu OCR API to recognize the text
        
        Args:
            image: Original image
            area: Crop area (x1, y1, x2, y2)
            model: Recognition model, can be "general_basic" or "accurate_basic"
        """
        original_crop = crop(image, area)
        
        result = ocr_api.request_ocr(image=original_crop,model=model)
        if result:
            if 'words_result' in result and len(result['words_result']) > 0:
                return result
            else:
                logger.info(result)
        return False
    
    def recognize_activity_page(self,image,area=(281, 79, 1254, 560),orc_api=None,model="general_basic"):
        result = self.recognize_text(image, area,orc_api,model)
        if result:
            all_words = "".join([word['words'] for word in result['words_result']])
            if any(word in all_words for word in ["每日0点","解锁2个任务","每天零点","完成七日活动"]):
                logger.info(f"发现七天小任务：{all_words}")
                return all_words
            logger.info('当前页未发现七天小任务')
            return False 
        else:
            logger.warning('Failed to recognize text')
            return False
        
    def recognize_activiy_status(self,text):
        if "进度" in text:
            progress_text = text.split("进度")[1]
            progress_number = progress_text.split("/")[0]
            progress_number = re.sub(r'[^0-9]', '', progress_number)#正则匹配掉非数字
            LogRes(self.config).SevenDayStatus = int(progress_number)
            logger.info(f"更新七天小任务进度：{progress_number}")
        #统计text中有几个领取，几个前往
        
        go_count = text.count("前往")
        got_count = text.count("已领取")
        get_count = text.count("领取") - got_count
        logger.info(f"发现{go_count}个前往按钮，发现{got_count}个已领取按钮，发现{get_count}个领取按钮")
        return go_count
    
    def locate_button_by_text(self,image,text,text_exclude=None,area=(281, 79, 1254, 560),interval=0,orc_api=None):
        if interval:
            timer = self.get_interval_timer(text, interval=interval, renew=True)
            if not timer.reached():
                return "cooldowning"
        result = self.recognize_text(image, area,orc_api,model="general")
        if result:
            for word in result['words_result']:
                if text in word['words'] and not any(text_exclude in word['words'] for text_exclude in text_exclude):
                    logger.info(f"发现{text}按钮：{word['words']}")
                    if interval:
                        self.get_interval_timer(text).reset()
                    return word['location']
        return None
    
    def location_2_button(self,location,name,base_loc):
        area = (base_loc[0] + location['left'], base_loc[1] + location['top'], base_loc[0] + location['left'] + location['width'], base_loc[1] + location['top'] + location['height'])
        logger.info(f"将{name}按钮的区域转换为：{area}")
        return Button(area=area, color=(), button=area,name=name)
    
    def get_reward(self,page_area,orc_api,skip_first_screenshot=True):
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            location = self.locate_button_by_text(self.device.image, "领取", ["已领取"], page_area,interval=5,orc_api=orc_api)
            if isinstance(location, dict):
                button = self.location_2_button(location, "领取", base_loc=page_area)
                self.device.click(button)
                continue
            elif location == "cooldowning":
                pass
                # logger.warning("领取按钮冷却中")
            else:
                logger.warning("领取按钮不存在")
                return False

            if self.story_skip():
                continue   
            if self.appear_then_click(POPUP_CONFIRM,offset=(10, 10), interval=1):
                continue
            if self.appear_then_click(GET_ITEMS_1,offset=(10, 10), interval=1):
                continue 

    def goto_sevenD_page(self,page_area,orc_api):
        self.ui_ensure(page_main)
        skip_first_screenshot = True
        CLICK_COUNT = 0
        NOCLICK_COUNT = 0
        NOCLICK_TIMER =Timer(3,count=10)
        button_list_length = 3
        event_grid = ButtonGrid(origin=(12, 121), delta=(0, 82), button_shape=(150, 29), grid_shape=(1, button_list_length))
        drag_down_timer = self.get_interval_timer("drag_down", interval=2, renew=True)
        too_low_drag = False
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()
            if self.appear_then_click(EVENT_NOTIFY_ENTRY, offset=(5, 5), interval=3):
                continue
            if button_list_length == 3:
                if self.appear(ACTIVITY_ONE_PAGE, offset=(5,3),similarity=0.95):
                    button_list_length = 5
                    event_grid = ButtonGrid(origin=(12, 121), delta=(0, 82), button_shape=(150, 29), grid_shape=(1, button_list_length))
            if CLICK_COUNT >=5:
                logger.info("reach the ACTIVITY_BOTTOM")
                break
            if CLICK_COUNT == button_list_length:
                if drag_down_timer.reached() or too_low_drag:
                    if not self.appear(ACTIVITY_BOTTOM,offset=(5,3),similarity=0.95) and \
                        not self.appear(ACTIVITY_BOTTOM_2,offset=(5,3),similarity=0.95):
                        logger.info("ACTIVITY_BOTTOM not appear")
                        self.device.drag((100,510),(105,400))
                        self.device.sleep(1)
                        self.get_interval_timer("drag_down").reset()
                        too_low_drag = False
                        continue
                    else:
                        logger.info("ACTIVITY_BOTTOM appear")
                        break
                if self.appear(ACTIVITY_SELECTED_GRID,offset=(10,400),similarity=0.75):
                    # if ACTIVITY_SELECTED_GRID.button[1] > 350:
                    #     logger.info("selected button too low")
                    #     too_low_drag = True
                    #     continue
                    event_grid = ButtonGrid(origin=(12,ACTIVITY_SELECTED_GRID.button[1]+27+82), delta=(0, 82), button_shape=(150, 29), grid_shape=(1, button_list_length))
                    CLICK_COUNT = 0
                    # logger.warning(
                    #     f"Selected grid updated, new area: (12, {ACTIVITY_SELECTED_GRID.button[1] + 27 + 82},\
                    #                                     121, {ACTIVITY_SELECTED_GRID.button[1] + 27 + 82 + 29})"
                    # )
                    continue
            elif CLICK_COUNT < button_list_length:
                if self.appear(EVENT_NOTIFY_PAGE, offset=(5,5)):
                    all_words = self.recognize_activity_page(self.device.image,page_area,orc_api)
                    # all_words = None
                    if not all_words:
                        if event_grid.buttons[CLICK_COUNT].button[3] > 585:
                            CLICK_COUNT = button_list_length
                            too_low_drag = True
                            logger.info("click too low")
                            continue
                        self.device.click(event_grid.buttons[CLICK_COUNT],control_check=False)
                        self.device.sleep(0.3)
                        logger.info(f"Clicking event_grid count: {CLICK_COUNT}")
                        CLICK_COUNT += 1
                        continue
                    else:
                        go_count = self.recognize_activiy_status(all_words)
                        if go_count >= 2:
                            logger.warning("七天小任务当前没有可领取项")
                            return "no_get"
                        return True
            NOCLICK_TIMER.start()
            if NOCLICK_TIMER.reached():
                NOCLICK_COUNT += 1
                NOCLICK_TIMER.reset()
                if NOCLICK_COUNT >= 5:
                    logger.info("GOTO_SEVEND_TASK No click TIMER REACHED")
                    break
        return False

    def ocr_api_init(self):
        if self.config.Smallevent_OcrModel == "baidu":
            if self.config.DropRecord_BaiduAPIKey != "null" and self.config.DropRecord_BaiduAPISecret != "null":
                ORC_API = BaiduOcr(self.config)
                return ORC_API
            else:
                logger.warning("未配置Baidu API Key或Secret Key")
                return False
        elif self.config.Smallevent_OcrModel == "volc":
            if self.config.DropRecord_VolcAPIKey != "null" and self.config.DropRecord_VolcAPISecret != "null":
                ORC_API = VolcOcr(self.config)
                return ORC_API
            else:
                logger.warning("未配置Volc API Key或Secret Key")
                return False
        else:
            logger.warning("未配置OcrModel")
            return False
            
    def run(self):
        # # LogRes(self.config).SevenDayStatus += 11
        # # logger.hr(LogRes(self.config).SevenDayStatus)
        # # logger.hr(self.config.cross_get('Dashboard.SevenDayStatus.Value'))
        # if self.config.Smallevent_SevenDayTask == True:
        #     task_icon = f"SEVEND_TASK_{self.SEVEND_DATE}"
        #     task_get1 = f"SEVEND_TASK_GET1_{self.SEVEND_DATE}"
        #     task_get2 = f"SEVEND_TASK_GET2_{self.SEVEND_DATE}"
        #     task_finish = f"SEVEND_TASK_FINISH_{self.SEVEND_DATE}"
        #     # task_unget1 = f"SEVEND_TASK_UNGET1_{self.SEVEND_DATE}"
        #     # task_unget2 = f"SEVEND_TASK_UNGET2_{self.SEVEND_DATE}"   
        #     self.SevenDayTask(
        #         SEVEND_TASK_ICON_MAIN=globals()[task_icon],
        #         SEVEND_TASK_GET1=globals()[task_get1],
        #         SEVEND_TASK_GET2=globals()[task_get2],
        #         SEVEND_TASK_FINISH=globals()[task_finish],
        #         # SEVEND_TASK_UNGET1=globals()[task_unget1],
        #         # SEVEND_TASK_UNGET2=globals()[task_unget2]
        #     )
        # else:LogRes(self.config).SevenDayStatus = 0
        if datetime.now() < datetime(2025, 8, 1, 1, 0, 0):#设置活动结束时间
            ORC_API = self.ocr_api_init()
            if ORC_API:
                page_area = (281, 79, 1254, 560)
                # page_area =(0,0,1280,720)
                goPage_result = self.goto_sevenD_page(page_area, ORC_API)
                if goPage_result == "no_get":
                    pass
                elif goPage_result is True:
                    self.get_reward(page_area, ORC_API)
                    if self.config.Smallevent_UpdateInfoImmediately == True:
                        self.device.sleep(1)
                        self.device.screenshot()
                        update_words = self.recognize_activity_page(self.device.image,page_area ,ORC_API)
                        if update_words:
                            self.recognize_activiy_status(update_words)
                else:
                    logger.warning("未成功进入七天小任务页面")
            else:
                logger.warning("Ocr API 初始化失败")
        else:
            logger.info('7day task expired')

        self.config.task_delay(server_update=True)
if __name__ == "__main__":
    self = SmallEvent('zTTT')
    # from adbutils import AdbClient
    # self.adb=AdbClient(host="127.0.0.1", port=16448)
    self.device.screenshot()
    page_area = (281, 79, 1254, 560)
    ORC_API = BaiduOcr(self.config)
    if self.goto_sevenD_page(page_area,ORC_API):
        self.get_reward(page_area,ORC_API)
        if self.config.Smallevent_SevenDayTask == True:
            self.device.sleep(1)
            self.device.screenshot()
            update_words = self.recognize_activity_page(self.device.image,page_area,ORC_API)
            if update_words:
                self.recognize_activiy_status(update_words)
        pass
    else:
        logger.warning("未成功进入七天小任务页面")
        pass
