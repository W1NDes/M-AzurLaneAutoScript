from module.base.button import ButtonGrid
from module.base.decorator import cached_property
from module.base.timer import Timer
from module.os_handler.assets import *
from module.logger import logger
from module.ui.navbar import Navbar
from module.ui.ui import UI


class OSShopUI(UI):
    def os_shop_load_ensure(self, skip_first_screenshot=True):
        """
        Switching between sidebar clicks for some
        takes a bit of processing before fully loading
        like guild logistics

        Args:
            skip_first_screenshot (bool):

        Returns:
            bool: Whether expected assets loaded completely
        """
        ensure_timeout = Timer(3, count=6).start()
        while True:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.device.screenshot()

            # End
            if self.appear(PORT_SUPPLY_CHECK):
                return True

            # Exception
            if ensure_timeout.reached():
                logger.warning('Wait for loaded assets is incomplete, ensure not guaranteed')
                return False

    @cached_property
    def _os_shop_side_navbar(self):
        """
        limited_sidebar 4 options
            NY
            Liverpool
            Gibraltar
            St. Petersburg
        """
        os_shop_side_navbar = ButtonGrid(
            origin=(44, 266), delta=(0, 87),
            button_shape=(231, 46), grid_shape=(1, 4),
            name='OS_SHOP_SIDE_NAVBAR')

        return Navbar(grids=os_shop_side_navbar,
                      active_color=(43, 94, 248), active_threshold=221,
                      inactive_color=(12, 58, 86), inactive_threshold=221)

    def os_shop_side_navbar_ensure(self, upper=None, bottom=None):
        """
        Ensure able to transition to page and
        page has loaded to completion

        Args:
            upper (int):
            limited|regular
                1     NY
                2     Liverpool
                3     Gibraltar
                4     St. Petersburg
            bottom (int):
            limited|regular
                4     NY
                3     Liverpool
                2     Gibraltar
                1     St. Petersburg

        Returns:
            bool: if side_navbar set ensured

        Pages:
            in: PORT_SUPPLY_CHECK
            out: PORT_SUPPLY_CHECK
        """
        if self._os_shop_side_navbar.set(self, upper=upper, bottom=bottom) \
                and self.os_shop_load_ensure():
            return True
        return False
