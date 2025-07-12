import random
from module.base.button import Button, ButtonGrid
from module.ocr.ocr import Ocr
from module.logger import logger
from module.ui.scroll import Scroll
from module.ship_ir.assets import *
from module.ship_ir.utils import convert_filter_to_params
from module.ship_ir.handbook import Handbook

HANDBOOK_SCROLL = Scroll(HANDBOOK_SCROLL_AREA, color=(244, 208, 66))
SHIP_NAME_BUTTON = ButtonGrid(origin=(200, 448), delta=(164 + 1 / 3, 226), button_shape=(135,21), grid_shape=(6, 2), name='SHIP_NAME')

CHECK_FILTER1 = ["全部","全阵营","彩色","无限制"]
CHECK_FILTER2 = ["","白鹰","精锐","无限制"]
CHECK_FILTER3 = ["","重樱","全部","无限制"]
CHECK_FILTER4 = ["","白鹰","金色","无限制"]
CHECK_FILTER5 = ["","皇家","全部","无限制"]
CHECK_FILTER_LIST = [CHECK_FILTER1, CHECK_FILTER2, CHECK_FILTER3, CHECK_FILTER4, CHECK_FILTER5]

class ShipIr(Handbook):

    def name_ocr(self,name_area):
        """
        识别角色名
        """
        self.device.screenshot()
        def has_chinese(text):# 检查结果是否包含中文
            return any('\u4e00' <= char <= '\u9fff' for char in text)
        
        def filter_text(text):
            keep_chars = set('()（）·IuVXUN')# 要保留的特殊字符
            exclude_chars = {'丶', '一'}# 需要排除的中文字符
            return ''.join(char for char in text if ('\u4e00' <= char <= '\u9fff' and char not in exclude_chars) or char in keep_chars)
            
        ocr_result =  Ocr(name_area, lang= 'cnocr',threshold=150).ocr(self.device.image,_pre_process=True)
        if not has_chinese(ocr_result):# 如果结果不包含中文，则大概率是未获取角色，使用更高的threshold重新识别
            ocr_result = ''.join(['UN',Ocr(name_area, lang='cnocr', letter=(95, 95, 95),threshold=128).ocr(self.device.image, _pre_process=True)])
        filtered_result = filter_text(ocr_result)
        if not has_chinese(filtered_result):
            filtered_result = ''
        return filtered_result
    
    def ship_ir_by_namebar(self,recognized_names,namebar_list):
        """
        通过边框位置识别角色名
        """
        for name_bar in namebar_list:
            if self.appear(name_bar,offset=(30,70),similarity=0.75):
                logger.info(name_bar.button[1])
                name = Button(area=(name_bar.button[0]+1, name_bar.button[1]-30, name_bar.button[2]-1, name_bar.button[3]-19), color=(),button=(0, 1, 0, 2))
                # name = area_offset(nameBar.area, (0,-20))
                ship_name = self.name_ocr(name)
                
                if ship_name and ship_name not in recognized_names:
                    recognized_names.append(ship_name) 
                    logger.info (f'识别为：{ship_name}')
        return recognized_names
    
    def ship_ir_by_area(self,recognized_names):
        """
        在滑动至底部时采用该方法
        """
        for button in SHIP_NAME_BUTTON.buttons:
            ship_name = self.name_ocr(button)
            if ship_name and ship_name not in recognized_names:
                recognized_names.append(ship_name)
                logger.info(f'识别为：{ship_name}')
        return recognized_names
    
    def summon_namebar_list(self,rarity):
        # 'all', 'common', 'rare', 'elite', 'super_rare', 'ultra'
        namebars = {
            1: {'G': NAMEBAR1_G, 'P': NAMEBAR1_P, 'U': NAMEBAR1_U},
            2: {'G': NAMEBAR2_G, 'P': NAMEBAR2_P, 'U': NAMEBAR2_U},
            3: {'G': NAMEBAR3_G, 'P': NAMEBAR3_P, 'U': NAMEBAR3_U},
            4: {'G': NAMEBAR4_G, 'P': NAMEBAR4_P, 'U': NAMEBAR4_U},
            5: {'G': NAMEBAR5_G, 'P': NAMEBAR5_P, 'U': NAMEBAR5_U},
            6: {'G': NAMEBAR6_G, 'P': NAMEBAR6_P, 'U': NAMEBAR6_U},
        }
        if rarity == 'all':
            return [namebars[i][s] for i in range(1, 7) for s in ['G', 'P', 'U']]
        elif any(rarity == i for i in ['common', 'rare']):
            return [namebars[i][s] for i in range(1, 7) for s in ['G', 'P']]
        elif rarity == 'elite':
            return [namebars[i]['P'] for i in range(1, 7)]
        elif rarity == 'super_rare':
            return [namebars[i]['G'] for i in range(1, 7)]
        elif rarity == 'ultra':
            return [namebars[i]['U'] for i in range(1, 7)]
        else:
            return [namebars[i][s] for i in range(1, 7) for s in ['G', 'P']]
        
    def ship_ir(self,recognized_names,rarity,skip_first_screenshot=True):
        # while len(recognized_names) < 36:
        # HANDBOOK_SCROLL.set_top(main=self)
        namebar_list = self.summon_namebar_list(rarity)
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            if HANDBOOK_SCROLL.cal_position(main=self) >= 0.96 or abs(HANDBOOK_SCROLL.length-HANDBOOK_SCROLL.total) <= 0.05:
                # HANDBOOK_SCROLL.drag_page(page=0.7, random_range=(0.0, 0.0), main=self,control_check=False)
                for _ in range(5):
                    self.handbook_swipe(random.randint(400,900))
                logger.info('Handbook reach bottom, stop')
                recognized_names = self.ship_ir_by_namebar(recognized_names,namebar_list)
                recognized_names = self.ship_ir_by_area(recognized_names)
                break
            else:
                recognized_names = self.ship_ir_by_namebar(recognized_names,namebar_list)
                HANDBOOK_SCROLL.drag_page(page=0.07, random_range=(0.0, 0.0), main=self,control_check=False)
                # self.handbook_swipe(random.randint(400,900))
                continue
        return recognized_names


    def run(self):
        #更新过滤器显示
        for i, check_filter in enumerate(CHECK_FILTER_LIST):
            if check_filter[0] == '':
                self.config.cross_set(keys=f"ShipIr.ShipIr.check_filter_show_{i+1}", value="PASS")
                continue
            check_filter_str = ",".join(check_filter)
            self.config.cross_set(keys=f"ShipIr.ShipIr.check_filter_show_{i+1}", value=check_filter_str)
        #进入图鉴页面
        while 1:
            if not self.pageCheck():
                continue
            else:
                break
        # 识别舰船
        for i, check_filter in enumerate(CHECK_FILTER_LIST):
            if check_filter[0] == '':
                continue
            params = convert_filter_to_params(check_filter)
            self.dock_filter_set(**params)
            recognized_names=self.ship_ir([],params['rarity'])
            logger.info(f"过滤器{i+1}识别到{len(recognized_names)}个角色: {recognized_names}")
            recognized_names_str = ",".join(recognized_names)
            
            check_filter[3] = "未获取"
            params = convert_filter_to_params(check_filter)
            self.dock_filter_set(**params)
            recognized_names_unget=self.ship_ir([],params['rarity'])
            logger.info(f"过滤器{i+1}识别到未获取{len(recognized_names_unget)}个角色: {recognized_names_unget}")
            recognized_names_unget_str = ",".join(recognized_names_unget)

            self.config.cross_set(keys=f"ShipIr.ShipIr.check_filter_result_{i+1}", value=f"全部：{recognized_names_str}\n未获取：{recognized_names_unget_str}")
        
        self.config.task_delay(server_update=True)

if __name__ == '__main__':
    self = ShipIr('alas')
    CHECK_FILTER1 = ["前排先锋","白鹰","金色","无限制"]
    params = convert_filter_to_params(CHECK_FILTER1)
    print(self.summon_namebar_list(params['rarity']))
    CHECK_FILTER2 = ["轻巡","白鹰","精锐","无限制"]
    CHECK_FILTER3 = ["轻巡","重樱","全部","无限制"]
    CHECK_FILTER4 = ["战列","白鹰","金色","无限制"]
    CHECK_FILTER5 = ["航母","皇家","全部","无限制"]
    CHECK_FILTER_LIST = [CHECK_FILTER1, CHECK_FILTER2, CHECK_FILTER3, CHECK_FILTER4, CHECK_FILTER5]
    while 1:
        if not self.pageCheck():
            continue
    for check_filter in CHECK_FILTER_LIST:
        params = convert_filter_to_params(check_filter)
        self.dock_filter_set(**params)
        recognized_names=self.ship_ir([],params['rarity'])
        logger.info(f"识别到{len(recognized_names)}个角色: {recognized_names}")

        check_filter[3] = "未获取"
        params = convert_filter_to_params(check_filter)
        self.dock_filter_set(**params)
        recognized_names=self.ship_ir([],params['rarity'])
        logger.info(f"识别到{len(recognized_names)}个角色: {recognized_names}")
        break

