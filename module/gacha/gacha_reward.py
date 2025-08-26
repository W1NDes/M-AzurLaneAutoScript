from module.base.timer import Timer
from module.campaign.campaign_status import OCR_COIN
from module.combat.assets import GET_SHIP
from module.exception import ScriptError
from module.gacha.assets import *
from module.gacha.ui import GachaUI
from module.handler.assets import POPUP_CONFIRM, STORY_SKIP
from module.logger import logger
from module.ocr.ocr import Digit, Ocr
from module.retire.retirement import Retirement
from module.log_res.log_res import LogRes
from module.base.utils import crop, extract_letters
import numpy
from module.ocr.api_ocr import BaiduOcr
from datetime import datetime
RECORD_GACHA_OPTION = ('RewardRecord', 'gacha')
RECORD_GACHA_SINCE = (0,)
OCR_BUILD_CUBE_COUNT = Digit(BUILD_CUBE_COUNT, letter=(255, 247, 247), threshold=64)
OCR_BUILD_TICKET_COUNT = Digit(BUILD_TICKET_COUNT, letter=(255, 247, 247), threshold=64)
OCR_BUILD_SUBMIT_COUNT = Digit(BUILD_SUBMIT_COUNT, letter=(255, 247, 247), threshold=64)
OCR_BUILD_SUBMIT_WW_COUNT = Digit(BUILD_SUBMIT_WW_COUNT, letter=(255, 247, 247), threshold=64)


class RewardGacha(GachaUI, Retirement):
    build_coin_count = 0
    build_cube_count = 0
    build_ticket_count = 0

    def gacha_prep(self, target, skip_first_screenshot=True):
        """
        Initiate preparation to submit build orders.

        Args:
            target (int): Number of build orders to submit
            skip_first_screenshot (bool):

        Returns:
            bool: True if prep complete otherwise False.

        Pages:
            in: page_build (any)
            out: submit pop up

        Except:
            May exit if unable to process prep
        """
        # Nothing to prep if 'target' = 0
        if not target:
            return False

        # Ensure correct page to be able to prep in
        if not self.appear(BUILD_SUBMIT_ORDERS) \
                and not self.appear(BUILD_SUBMIT_WW_ORDERS):
            return False

        # Use 'appear' to update actual position of assets
        # for ui_ensure_index
        confirm_timer = Timer(1, count=2).start()
        ocr_submit = None
        index_offset = (60, 20)
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            if self.appear_then_click(BUILD_SUBMIT_ORDERS, interval=3):
                ocr_submit = OCR_BUILD_SUBMIT_COUNT
                confirm_timer.reset()
                continue

            if self.appear_then_click(BUILD_SUBMIT_WW_ORDERS, interval=3):
                ocr_submit = OCR_BUILD_SUBMIT_WW_COUNT
                confirm_timer.reset()
                continue
            # Continue gacha even if UR exchange point is full
            if self.handle_popup_confirm('GACHA_PREP'):
                confirm_timer.reset()
                continue

            # End
            if self.appear(BUILD_PLUS, offset=index_offset) \
                    and self.appear(BUILD_MINUS, offset=index_offset):
                if confirm_timer.reached():
                    break

        # Check for exception, exited prematurely
        # Apply appropriate submission count
        if ocr_submit is None:
            raise ScriptError('Failed to identify ocr asset required, '
                              'cannot continue prep work')
        area = ocr_submit.buttons[0]
        ocr_submit.buttons = [(BUILD_MINUS.button[2] + 3, area[1], BUILD_PLUS.button[0] - 3, area[3])]
        self.ui_ensure_index(target, letter=ocr_submit, prev_button=BUILD_MINUS,
                             next_button=BUILD_PLUS, skip_first_screenshot=True)

        return True

    def gacha_calculate(self, target_count, gold_cost, cube_cost):
        """
        Calculate number able to actually submit.

        Args:
            target_count (int): Number of build orders like to submit
            gold_cost (int): Gold coin cost
            cube_cost (int): Cube cost

        Returns:
            int: Actual number able to submit based on current resources
        """
        while 1:
            # Calculate cost of resources based on 'target_count'
            gold_total = gold_cost * target_count
            cube_total = cube_cost * target_count

            # Reached 0, cannot execute gacha roll
            if not target_count:
                logger.warning('Insufficient gold and/or cubes to gacha roll')
                break

            # Insufficient resources, reduce by 1 and re-calculate
            if gold_total > self.build_coin_count or cube_total > self.build_cube_count:
                target_count -= 1
                continue

            break

        # Modify resources, return current 'target_count'
        logger.info(f'Able to submit up to {target_count} build orders')
        self.build_coin_count -= gold_total
        self.build_cube_count -= cube_total
        LogRes(self.config).Cube = self.build_cube_count
        self.config.update()
        return target_count

    def gacha_goto_pool(self, target_pool):
        """
        Transition to appropriate build pool page.

        Args:
            target_pool (str): Name of pool, default to
            'light' path if outside of acceptable range

        Returns:
            str: Current pool location based on availability

        Pages:
            in: page_build (gacha pool selection)
            out: page_build (gacha pool allowed)

        Except:
            May exit if 'wishing_well' but not
            complete configuration
        """
        # Switch view to 'light' pool
        self.gacha_bottom_navbar_ensure(right=3, is_build=True)

        # Transition to 'target_pool' if needed, update
        # 'target_pool' appropriately
        if target_pool == 'wishing_well':
            if self._gacha_side_navbar.get_total(main=self) != 5:
                logger.warning('\'wishing_well\' is not available, '
                               'default to \'light\' pool')
                target_pool = 'light'
            else:
                self.gacha_side_navbar_ensure(upper=2)
                if self.appear(BUILD_WW_CHECK):
                    raise ScriptError('\'wishing_well\' must be configured '
                                      'manually by user, cannot continue '
                                      'gacha_goto_pool')
        elif target_pool == 'event':
            gacha_bottom_navbar = self._gacha_bottom_navbar(is_build=True)
            if gacha_bottom_navbar.get_total(main=self) == 3:
                logger.warning('\'event\' is not available, default '
                               'to \'light\' pool')
                target_pool = 'light'
            else:
                self.gacha_bottom_navbar_ensure(left=1, is_build=True)
        elif target_pool in ['heavy', 'special']:
            if target_pool == 'heavy':
                self.gacha_bottom_navbar_ensure(right=2, is_build=True)
            else:
                self.gacha_bottom_navbar_ensure(right=1, is_build=True)

        return target_pool

    def gacha_flush_queue(self, skip_first_screenshot=True):
        """
        Flush build order queue to ensure empty before submission.

        Args:
            skip_first_screenshot (bool):

        Pages:
            in: page_build (any)
            out: page_build (gacha pool selection)

        Except:
            May exit if unable to flush queue entirely,
            dock likely full
        """
        # Go to Gacha/Orders page
        self.gacha_side_navbar_ensure(bottom=3)

        # Transition appropriate screens
        # and end up in Gacha/Build page
        confirm_timer = Timer(1, count=2).start()
        confirm_mode = True  # Drill, Lock Ship
        # Clear button offset, or will click at the PLUS button of gems or HOME button
        STORY_SKIP.clear_offset()
        queue_clean = True
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            if self.appear(BUILD_QUEUE_EMPTY, offset=(20, 20)) and queue_clean:
                self.gacha_side_navbar_ensure(upper=1)
                break
            else:
                queue_clean = False

            if self.appear_then_click(BUILD_FINISH_ORDERS, interval=3):
                confirm_timer.reset()
                continue

            if self.handle_retirement():
                confirm_timer.reset()
                continue

            if self.handle_popup_confirm('FINISH_ORDERS'):
                if confirm_mode:
                    self.device.sleep((0.5, 0.8))
                    self.device.click(BUILD_FINISH_ORDERS)  # Skip animation, safe area
                    confirm_mode = False
                confirm_timer.reset()
                continue
            if self.config.DropRecord_NewShipRecord != "save":
                if self.appear(GET_SHIP, interval=1):
                    self.device.click(STORY_SKIP)  # Fast forward for multiple orders
                    confirm_timer.reset()
                    continue
            else:   
                if self.handle_get_ship(ocr_type=self.config.DropRecord_NewShipOcrMethod):
                    # self.device.click(STORY_SKIP)
                    confirm_timer.reset()
                    continue

            if self.appear(BUILD_FINISH_RESULTS, offset=(20, 150), interval=3):
                self.device.click(BUILD_FINISH_ORDERS)  # Safe area
                confirm_timer.reset()
                continue

            # End, goes back to pool page if clicked with queue empty
            if self.appear(BUILD_SUBMIT_ORDERS) or self.appear(BUILD_SUBMIT_WW_ORDERS):
                if confirm_timer.reached():
                    break

        # Wishing pool no longer shows coins, go back to normal pools
        if self.appear(BUILD_SUBMIT_WW_ORDERS):
            logger.info('In wishing pool, go back to normal pools')
            self.gacha_side_navbar_ensure(upper=1)

    def gacha_submit(self, skip_first_screenshot=True):
        """
        Pages:
            in: POPUP_CONFIRM
            out: BUILD_FINISH_ORDERS
        """
        logger.info('Submit gacha')
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            if self.appear(POPUP_CONFIRM, offset=(20, 80), interval=3):
                # Alter asset name for click
                POPUP_CONFIRM.name = POPUP_CONFIRM.name + '_' + 'GACHA_ORDER'
                self.device.click(POPUP_CONFIRM)
                POPUP_CONFIRM.name = POPUP_CONFIRM.name[:-len('GACHA_ORDER') - 1]
                continue

            # End
            if self.appear(BUILD_FINISH_ORDERS):
                break

    def gacha_run(self):
        """
        Run gacha operations to submit build orders.

        Returns:
            bool: True if run successful otherwise False

        Pages:
            in: any
            out: page_build
        """
        # Go to Gacha
        self.ui_goto_gacha()

        # Flush queue of any pre-existing
        # builds to ensure starting fresh
        # Upon exit, expected to be in
        # main Build page
        self.gacha_flush_queue()

        # OCR Gold and Cubes
        self.build_coin_count = OCR_COIN.ocr(self.device.image)
        self.build_cube_count = OCR_BUILD_CUBE_COUNT.ocr(self.device.image)

        # Transition to appropriate target construction pool
        # Returns appropriate costs for gacha as well
        actual_pool = self.gacha_goto_pool(self.config.Gacha_Pool)

        # Determine appropriate cost based on gacha_goto_pool
        gold_cost = 600
        cube_cost = 1
        if actual_pool in ['heavy', 'special', 'event', 'wishing_well']:
            gold_cost = 1500
            cube_cost = 2

        # OCR build tickets, decide use cubes/coins or not
        # buy = [rolls_using_tickets, rolls_using_cubes]
        buy = [self.config.Gacha_Amount, 0]
        if actual_pool == "event" and self.config.Gacha_UseTicket:
            if self.appear(BUILD_TICKET_CHECK, offset=(30, 30)):
                self.build_ticket_count = OCR_BUILD_TICKET_COUNT.ocr(self.device.image)
            else:
                logger.info('Build ticket not detected, use cubes and coins')
        if self.config.Gacha_Amount > self.build_ticket_count:
            buy[0] = self.build_ticket_count
            # Calculate rolls allowed based on configurations and resources
            buy[1] = self.gacha_calculate(self.config.Gacha_Amount - self.build_ticket_count, gold_cost, cube_cost)

        # Submit 'buy_count' and execute if capable
        # Cannot use handle_popup_confirm, this window
        # lacks POPUP_CANCEL
        result = False
        for buy_count in buy:
            if self.gacha_prep(buy_count):
                self.gacha_submit()

                # If configured to use drill after build
                if self.config.Gacha_UseDrill:
                    self.gacha_flush_queue()
                # Return True if any submit successed
                result = True

        return result

    def run(self):
        """
        Handle gacha operations if configured to do so.

        Pages:
            in: Any page
            out: page_build
        """
        self.gacha_run()
        self.config.task_delay(server_update=True)

    
    def recognize_ship_name(self, image, area, OCR_API, model="general_basic"):
        """
        Use Baidu OCR API to recognize ship name
        
        Args:
            image: Original image
            area: Crop area (x1, y1, x2, y2)
            model: Recognition model, can be "general_basic" or "accurate_basic"
        Returns:
            str: Recognized ship name, returns "Unknown" if recognition fails
        """

        # from PIL import Image
        
        # Show original crop area
        original_crop = crop(image, area)
        # Image.fromarray(original_crop).show(title="Original Crop")
        
        # Show preprocessed image
        image = extract_letters(original_crop, letter=(247, 251, 247), threshold=128)
        image = image.astype(numpy.uint8)
        # Image.fromarray(image).show(title="Preprocessed Image")
        
        result = OCR_API.request_baidu_ocr(image,area,model)
        if result:
            if 'words_result' in result and len(result['words_result']) > 0:
                ship_name = result['words_result'][0]['words']
                return ship_name
            else:
                logger.info(result)
                logger.warning('Failed to recognize ship name')
                return "Unknown"
        else:
            logger.warning('Failed to call Baidu OCR API')
            return "Unknown"

    def handle_get_ship(self, drop=None, skip_first_screenshot=True,ocr_type="LOCAL"):
        """
        Args:
            drop (DropImage):
        Returns:
            bool:
        """
        if not self.appear(GET_SHIP, interval=5):
            return False

        if 'save' in self.config.DropRecord_NewShipRecord:
            confirm_timer = Timer(3)
        else:
            confirm_timer = Timer(1)
        confirm_timer.start()
        OCR_API = BaiduOcr(self.config)
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            # End
            if confirm_timer.reached():
                break
            from module.combat.assets import NEW_SHIP
            if self.appear(NEW_SHIP):
                logger.info('Get a new SHIP')
                # Use OCR to recognize ship name
                ship_name_area = (360, 552, 550, 582)  # Ship name area
                if ocr_type == "LOCAL":
                    ship_name = Ocr(ship_name_area, lang="cnocr", letter=(247, 251, 247), threshold=128).ocr(self.device.image)#ocr_LOCAL
                elif ocr_type == "API_BASIC":
                    ship_name = self.recognize_ship_name(self.device.image, ship_name_area,OCR_API,model="general_basic")#ocr_API_basic
                elif ocr_type == "API_ACCURATE":
                    ship_name = self.recognize_ship_name(self.device.image, ship_name_area,OCR_API,model="accurate_basic")#ocr_API_accurate
                logger.info(f'New ship name: {ship_name}')

                current_date = datetime.now()
                date_prefix = f"{current_date.month}_{current_date.day}_"
                ship_name_with_date = date_prefix + ship_name
                
                if drop:
                    drop.handle_add(self)
                with self.stat.new(
                    genre=self.config.config_name,
                    method=self.config.DropRecord_NewShipRecord,
                    info=ship_name_with_date
                ) as drop2:
                    drop2.handle_add(self, before=1.0)
                self.config.GET_SHIP_TRIGGERED = True
                break
        self.device.click(GET_SHIP)
        return True

if __name__ == "__main__":
    from module.base.utils import load_image
    import os
    self = RewardGacha('alas', task='RewardGacha')
    folder_path = r"C:\Users\W1NDe\Documents\GitHub\M-AzurLaneAutoScript\screenshots\zTTT"
    ship_name_area = (360, 552, 550, 582)  # Ship name area
    ocr_api = BaiduOcr(self.config,api_key="",secret_key="")
    # Traverse all images in the folder
    for filename in os.listdir(folder_path):
        if filename.endswith(('.png', '.jpg', '.jpeg')):
            image_path = os.path.join(folder_path, filename)
            logger.info(f'Processing image: {filename}')
            
            try:
                image = load_image(image_path)
                # Use local OCR recognition
                # ship_name = Ocr(ship_name_area, lang="cnocr", letter=(247, 251, 247), threshold=128).ocr(image)
                # logger.info(f'Local OCR result: {ship_name}')
                
                # Use Baidu OCR API recognition
                api_result = self.recognize_ship_name(image, ship_name_area,ocr_api)
                logger.info(f'API OCR result: {api_result}')
                
                # Save results to file
                # with open(os.path.join(folder_path, 'ocr_results.txt'), 'a', encoding='utf-8') as f:
                #     f.write(f'{filename}: Local={ship_name}, API={api_result}\n')
                    
            except Exception as e:
                logger.error(f'Error processing {filename}: {str(e)}')
                continue