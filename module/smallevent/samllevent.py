from module.ui.ui import UI
from module.ui.page import page_main
from module.smallevent.assets import * 
from module.handler.assets import POPUP_CONFIRM
from module.combat.assets import GET_ITEMS_1
from module.logger import logger
from module.base.timer import Timer
from module.log_res.log_res import LogRes

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
                
            
    def run(self):
        # LogRes(self.config).SevenDayStatus += 11
        # logger.hr(LogRes(self.config).SevenDayStatus)
        # logger.hr(self.config.cross_get('Dashboard.SevenDayStatus.Value'))
        if self.config.Smallevent_SevenDayTask == True:
            task_icon = f"SEVEND_TASK_{self.SEVEND_DATE}"
            task_get1 = f"SEVEND_TASK_GET1_{self.SEVEND_DATE}"
            task_get2 = f"SEVEND_TASK_GET2_{self.SEVEND_DATE}"
            task_finish = f"SEVEND_TASK_FINISH_{self.SEVEND_DATE}"
            # task_unget1 = f"SEVEND_TASK_UNGET1_{self.SEVEND_DATE}"
            # task_unget2 = f"SEVEND_TASK_UNGET2_{self.SEVEND_DATE}"   
            self.SevenDayTask(
                SEVEND_TASK_ICON_MAIN=globals()[task_icon],
                SEVEND_TASK_GET1=globals()[task_get1],
                SEVEND_TASK_GET2=globals()[task_get2],
                SEVEND_TASK_FINISH=globals()[task_finish],
                # SEVEND_TASK_UNGET1=globals()[task_unget1],
                # SEVEND_TASK_UNGET2=globals()[task_unget2]
            )
        else:LogRes(self.config).SevenDayStatus = 0
        self.config.task_delay(server_update=True)
