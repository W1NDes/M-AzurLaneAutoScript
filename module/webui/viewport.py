import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Optional

import cv2
import numpy as np
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from module.logger import logger
from module.webui.process_manager import ProcessManager
from module.webui.setting import State

# Shared thread pool for screenshot operations
_screenshot_executor: Optional[ThreadPoolExecutor] = None


def get_auth_token() -> Optional[str]:
    """Get the authentication token from deploy config."""
    return State.deploy_config.Password


def get_screenshot_executor() -> ThreadPoolExecutor:
    global _screenshot_executor
    if _screenshot_executor is None:
        _screenshot_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='ViewportScreenshot')
    return _screenshot_executor


class DeviceConnection:
    """
    Device connection for viewport streaming.
    Reuses main script's Device class for fast screenshot methods.
    """

    def __init__(self, instance_name: str):
        self.instance_name = instance_name
        self._device = None
        self._connected = False
        self._ref_count = 0
        self._lock = threading.Lock()
        self._resolution: tuple = (1280, 720)
        self._error_count = 0
        self._max_errors = 30
        self._screenshot_method = 'unknown'
        self._control_method = 'unknown'

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> tuple:
        """
        Connect to device.
        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        try:
            # Remove fake PIL module before importing Device
            from module.webui.fake_pil_module import remove_fake_pil_module
            remove_fake_pil_module()

            # Import here to avoid circular imports
            from module.config.config import AzurLaneConfig
            from adbutils import AdbClient

            # Load config for this instance
            config = AzurLaneConfig(config_name=self.instance_name, task=None)

            # Check if device is available before creating Device object
            # This prevents auto-starting the emulator
            serial = config.Emulator_Serial
            if serial and serial != 'auto':
                try:
                    adb_client = AdbClient('127.0.0.1', 5037)

                    # First check if already in device list
                    connected_devices = [d.serial for d in adb_client.device_list()]
                    if serial not in connected_devices:
                        # Not in list, try to connect (this won't start the emulator)
                        # For IP:port style serials like 127.0.0.1:5555
                        if ':' in serial:
                            msg = adb_client.connect(serial)
                            logger.info(f'[Viewport] ADB connect {serial}: {msg}')
                            # Check result
                            if 'connected' in msg:
                                # Successfully connected
                                pass
                            elif '(10061)' in msg or 'refused' in msg.lower():
                                # Connection refused - emulator not running
                                logger.info(f'[Viewport] Emulator {serial} is not running (connection refused)')
                                return False, 'emulator_not_running'
                            elif 'cannot connect' in msg or 'failed' in msg.lower():
                                logger.info(f'[Viewport] Cannot connect to {serial}: {msg}')
                                return False, 'connection_failed'
                        else:
                            # For emulator-* style or physical devices, just check if in list
                            logger.info(f'[Viewport] Device {serial} not found in connected devices: {connected_devices}')
                            return False, 'device_not_found'
                except Exception as e:
                    logger.info(f'[Viewport] Failed to check device availability: {e}')
                    return False, 'adb_error'

            # Now safe to create Device object
            from module.device.device import Device
            from module.exception import EmulatorNotRunningError, RequestHumanTakeover

            # Create device with the config
            try:
                self._device = Device(config=config)
            except (EmulatorNotRunningError, RequestHumanTakeover) as e:
                logger.info(f'[Viewport] Emulator not running for {self.instance_name}: {e}')
                return False, 'emulator_not_running'

            # Verify connection
            try:
                # Try to get a screenshot to verify device is working
                self._device.screenshot()
                self._connected = True
                self._error_count = 0

                # Get actual resolution from screenshot
                if self._device.image is not None:
                    h, w = self._device.image.shape[:2]
                    self._resolution = (w, h)

                # Log the methods being used
                self._screenshot_method = config.Emulator_ScreenshotMethod
                self._control_method = config.Emulator_ControlMethod
                logger.info(
                    f'[Viewport] Connected {self.instance_name}: '
                    f'screenshot={self._screenshot_method}, control={self._control_method}, '
                    f'resolution={self._resolution}'
                )
                return True, None
            except Exception as e:
                logger.info(f'[Viewport] Device {self.instance_name} not ready: {e}')
                self._device = None
                return False, 'screenshot_failed'

        except Exception as e:
            logger.warning(f'[Viewport] Failed to connect {self.instance_name}: {e}')
            self._connected = False
            return False, 'unknown_error'

    def screenshot(self) -> Optional[np.ndarray]:
        """Get screenshot as numpy array (BGR format)."""
        if not self._connected or self._device is None:
            return None
        try:
            # Call underlying screenshot method directly to bypass stuck_record_check
            # and _screenshot_interval delays
            method_name = f'screenshot_{self._screenshot_method}'
            if hasattr(self._device, method_name):
                method = getattr(self._device, method_name)
                self._device.image = method()
            else:
                # Fallback to normal screenshot
                self._device.screenshot()

            if self._device.image is not None:
                self._error_count = 0
                return self._device.image
            else:
                self._error_count += 1
        except Exception as e:
            if self._error_count == 0:
                logger.info(f'[Viewport] Screenshot error for {self.instance_name}: {e}')
            self._error_count += 1

        if self._error_count >= self._max_errors:
            logger.warning(f'[Viewport] Too many errors, disconnecting {self.instance_name}')
            self._connected = False
        return None

    def screenshot_encode(self, quality: int = 30, scale: float = 1.0, skip_unchanged: bool = False) -> Optional[bytes]:
        """Get screenshot as JPEG bytes.

        Args:
            quality: JPEG quality (1-100)
            scale: Resolution scale (0.25-1.0), e.g. 0.5 = half resolution
            skip_unchanged: If True, skip encoding when frame content is unchanged

        Returns:
            bytes: Encoded frame data, or None if screenshot failed or frame unchanged.
        """
        import time
        t0 = time.perf_counter()

        img = self.screenshot()
        t1 = time.perf_counter()

        if img is None:
            return None
        try:
            # Update resolution if changed
            h, w = img.shape[:2]
            if (w, h) != self._resolution:
                self._resolution = (w, h)
                logger.info(f'[Viewport] Updated resolution: {self._resolution}')

            # Resize if scale < 1.0
            if scale < 1.0:
                new_w = int(w * scale)
                new_h = int(h * scale)
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

            # Frame-skip detection: only check when idle (skip_unchanged=True)
            if skip_unchanged:
                if hasattr(self, '_last_frame') and self._last_frame is not None:
                    if self._last_frame.shape == img.shape:
                        diff = cv2.absdiff(img, self._last_frame)
                        if np.mean(diff) < 1.0:
                            # Frame unchanged, skip
                            return None
            self._last_frame = img

            # Convert BGR to RGB for correct colors in browser
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            t2 = time.perf_counter()

            # Encode to JPEG
            _, encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])
            t3 = time.perf_counter()

            result = encoded.tobytes()
            t4 = time.perf_counter()

            # Log timing every 100 frames
            if not hasattr(self, '_frame_count'):
                self._frame_count = 0
                self._total_times = [0, 0, 0, 0]
            self._frame_count += 1
            self._total_times[0] += t1 - t0  # screenshot
            self._total_times[1] += t2 - t1  # resize + diff
            self._total_times[2] += t3 - t2  # imencode
            self._total_times[3] += t4 - t3  # tobytes

            if self._frame_count >= 100:
                avg = [t / self._frame_count * 1000 for t in self._total_times]
                total = sum(avg)
                out_h, out_w = img.shape[:2]
                logger.info(
                    f'[Viewport] Timing (avg ms): screenshot={avg[0]:.1f}, '
                    f'resize={avg[1]:.1f}, imencode={avg[2]:.1f}, tobytes={avg[3]:.1f}, '
                    f'total={total:.1f}, size={len(result)//1024}KB, res={out_w}x{out_h}'
                )
                self._frame_count = 0
                self._total_times = [0, 0, 0, 0]

            return result
        except Exception as e:
            if self._error_count == 0:
                logger.info(f'[Viewport] Encode error: {e}')
            return None

    def touch(self, x: int, y: int):
        """Send touch/click event."""
        if not self._connected or self._device is None:
            return
        try:
            # Call underlying click method directly based on control method
            method_name = f'click_{self._control_method}'
            if hasattr(self._device, method_name):
                method = getattr(self._device, method_name)
                method(x, y)
            else:
                # Fallback to adb click
                self._device.click_adb(x, y)
            # logger.info(f'[Viewport] Touch ({x}, {y})')
        except Exception as e:
            logger.debug(f'[Viewport] Touch error: {e}')

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300):
        """Send swipe event."""
        if not self._connected or self._device is None:
            return
        try:
            # Call underlying swipe method directly based on control method
            method_name = f'swipe_{self._control_method}'
            if hasattr(self._device, method_name):
                method = getattr(self._device, method_name)
                # minitouch/maatouch/nemu_ipc don't take duration, only adb does
                if self._control_method in ('minitouch', 'MaaTouch', 'nemu_ipc', 'scrcpy'):
                    method((x1, y1), (x2, y2))
                else:
                    method((x1, y1), (x2, y2), duration / 1000.0)
            else:
                # Fallback to adb swipe
                self._device.swipe_adb((x1, y1), (x2, y2), duration / 1000.0)
            logger.info(f'[Viewport] Swipe ({x1}, {y1}) -> ({x2}, {y2})')
        except Exception as e:
            logger.debug(f'[Viewport] Swipe error: {e}')

    @property
    def supports_raw_touch(self) -> bool:
        """Whether the control method supports raw touch_down/move/up primitives."""
        return self._control_method in ('minitouch', 'MaaTouch', 'nemu_ipc', 'scrcpy')

    def _minitouch_send_no_delay(self):
        """Send minitouch commands without the DEFAULT_DELAY sleep.

        The normal builder.send() calls minitouch_send() which sleeps 50ms+ after
        each send. For real-time touch streaming this delay is unacceptable as it
        causes the game to register a 'down' as a press/click before the 'move' arrives.
        """
        builder = self._device.minitouch_builder
        content = builder.to_minitouch()
        byte_content = content.encode('utf-8')
        self._device._minitouch_client.sendall(byte_content)
        self._device._minitouch_client.recv(0)
        builder.clear()

    def swipe_start(self, x_down: int, y_down: int, x_move: int, y_move: int):
        """Atomically send touch down + first move (starts a swipe without click gap)."""
        if not self._connected or self._device is None:
            return
        try:
            if self._control_method in ('minitouch', 'MaaTouch'):
                builder = self._device.minitouch_builder
                builder.down(x_down, y_down).commit()
                builder.move(x_move, y_move).commit()
                self._minitouch_send_no_delay()
            elif self._control_method == 'nemu_ipc':
                self._device.nemu_ipc.down(x_down, y_down)
                self._device.nemu_ipc.down(x_move, y_move)
            elif self._control_method == 'scrcpy':
                from module.device.method.scrcpy import const
                self._device.scrcpy_ensure_running()
                self._device._scrcpy_control.touch(x_down, y_down, const.ACTION_DOWN)
                self._device._scrcpy_control.touch(x_move, y_move, const.ACTION_MOVE)
        except Exception as e:
            logger.debug(f'[Viewport] Swipe start error: {e}')

    def touch_move(self, x: int, y: int):
        """Send touch move event (finger drag)."""
        if not self._connected or self._device is None:
            return
        try:
            if self._control_method in ('minitouch', 'MaaTouch'):
                builder = self._device.minitouch_builder
                builder.move(x, y).commit()
                self._minitouch_send_no_delay()
            elif self._control_method == 'nemu_ipc':
                # nemu_ipc uses down() for move as well
                self._device.nemu_ipc.down(x, y)
            elif self._control_method == 'scrcpy':
                from module.device.method.scrcpy import const
                self._device._scrcpy_control.touch(x, y, const.ACTION_MOVE)
        except Exception as e:
            logger.debug(f'[Viewport] Touch move error: {e}')

    def touch_up(self):
        """Send touch up event (finger release)."""
        if not self._connected or self._device is None:
            return
        try:
            if self._control_method in ('minitouch', 'MaaTouch'):
                builder = self._device.minitouch_builder
                builder.up().commit()
                self._minitouch_send_no_delay()
            elif self._control_method == 'nemu_ipc':
                self._device.nemu_ipc.up()
            elif self._control_method == 'scrcpy':
                from module.device.method.scrcpy import const
                # scrcpy needs coordinates for up, use (0,0) as placeholder
                self._device._scrcpy_control.touch(0, 0, const.ACTION_UP)
        except Exception as e:
            logger.debug(f'[Viewport] Touch up error: {e}')

    def disconnect(self):
        self._connected = False
        if self._device is not None:
            try:
                # Release any resources
                pass
            except Exception:
                pass
        self._device = None
        logger.info(f'[Viewport] Disconnected {self.instance_name}')

    def acquire(self):
        with self._lock:
            self._ref_count += 1

    def release(self) -> bool:
        """Returns True if ref count reaches zero (should disconnect)."""
        with self._lock:
            self._ref_count -= 1
            if self._ref_count <= 0:
                self._ref_count = 0
                return True
            return False

    @property
    def resolution(self) -> tuple:
        return self._resolution

    @property
    def screenshot_method(self) -> str:
        return self._screenshot_method

    @property
    def control_method(self) -> str:
        return self._control_method


class ViewportManager:
    """Singleton managing per-instance DeviceConnections."""
    _instance: Optional['ViewportManager'] = None
    _lock = threading.Lock()

    def __init__(self):
        self.connections: Dict[str, DeviceConnection] = {}
        self.client_counts: Dict[str, int] = {}  # Track client count per instance

    @classmethod
    def get_instance(cls) -> 'ViewportManager':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = ViewportManager()
        return cls._instance

    def add_client(self, instance_name: str):
        """Increment client count for an instance."""
        with self._lock:
            self.client_counts[instance_name] = self.client_counts.get(instance_name, 0) + 1
            logger.info(f'[Viewport] Client connected to {instance_name}, total: {self.client_counts[instance_name]}')

    def remove_client(self, instance_name: str):
        """Decrement client count for an instance."""
        with self._lock:
            if instance_name in self.client_counts:
                self.client_counts[instance_name] = max(0, self.client_counts[instance_name] - 1)
                logger.info(f'[Viewport] Client disconnected from {instance_name}, total: {self.client_counts[instance_name]}')

    def get_client_count(self, instance_name: str) -> int:
        """Get the number of connected clients for an instance."""
        return self.client_counts.get(instance_name, 0)

    def instance_exists(self, instance_name: str) -> bool:
        """Check if instance config exists."""
        config_path = Path(f'./config/{instance_name}.json')
        return config_path.exists()

    def get_connection(self, instance_name: str) -> tuple:
        """
        Get or create a device connection.
        Returns:
            tuple: (DeviceConnection or None, error_code: str or None)
        """
        if instance_name in self.connections:
            conn = self.connections[instance_name]
            if conn.connected:
                return conn, None

        if not self.instance_exists(instance_name):
            logger.warning(f'[Viewport] Config not found for {instance_name}')
            return None, 'config_not_found'

        conn = DeviceConnection(instance_name)
        success, error = conn.connect()
        if success:
            self.connections[instance_name] = conn
            return conn, None
        return None, error

    def release_connection(self, instance_name: str):
        conn = self.connections.get(instance_name)
        if conn is None:
            return
        if conn.release():
            conn.disconnect()
            if instance_name in self.connections:
                del self.connections[instance_name]

    @staticmethod
    def is_script_running(instance_name: str) -> bool:
        try:
            mgr = ProcessManager.get_manager(instance_name)
            return mgr.alive
        except Exception:
            return False

    def shutdown(self):
        for name in list(self.connections.keys()):
            self.connections[name].disconnect()
        self.connections.clear()


_HTML_PATH = Path(__file__).parent / 'viewport.html'
_CONFIG_DIR = Path('./config')


def get_valid_instances() -> list:
    """
    Get list of valid instance names from config directory.
    Valid instances are .json files that:
    - Have size > 30KB
    - Are not named template.json
    """
    instances = []
    if not _CONFIG_DIR.exists():
        return instances

    for json_file in _CONFIG_DIR.glob('*.json'):
        # Skip template.json
        if json_file.name == 'template.json':
            continue
        # Check file size > 30KB (30 * 1024 = 30720 bytes)
        if json_file.stat().st_size > 30 * 1024:
            # Instance name is filename without extension
            instances.append(json_file.stem)

    return sorted(instances)


def generate_homepage_html(instances: list) -> str:
    """Generate homepage HTML with instance selection."""
    instance_items = ''
    for name in instances:
        instance_items += f'''
            <a href="?instance={name}" class="instance-card">
                <div class="instance-icon">📱</div>
                <div class="instance-name">{name}</div>
            </a>
        '''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Viewport - Select Instance</title>
    <style>
        :root {{
            --bg-gradient-start: #1a1a2e;
            --bg-gradient-end: #16213e;
            --text-primary: #fff;
            --text-secondary: #888;
            --card-bg: rgba(255, 255, 255, 0.1);
            --card-bg-hover: rgba(255, 255, 255, 0.2);
            --card-border: rgba(255, 255, 255, 0.1);
            --card-border-hover: rgba(255, 255, 255, 0.3);
            --btn-bg: rgba(255, 255, 255, 0.1);
            --btn-bg-hover: rgba(255, 255, 255, 0.2);
        }}
        [data-theme="light"] {{
            --bg-gradient-start: #f0f2f5;
            --bg-gradient-end: #e0e5ec;
            --text-primary: #333;
            --text-secondary: #666;
            --card-bg: rgba(255, 255, 255, 0.8);
            --card-bg-hover: rgba(255, 255, 255, 1);
            --card-border: rgba(0, 0, 0, 0.1);
            --card-border-hover: rgba(0, 0, 0, 0.2);
            --btn-bg: rgba(0, 0, 0, 0.05);
            --btn-bg-hover: rgba(0, 0, 0, 0.1);
        }}
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, var(--bg-gradient-start) 0%, var(--bg-gradient-end) 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 40px 20px;
            color: var(--text-primary);
            transition: background 0.3s, color 0.3s;
        }}
        .header {{
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 10px;
        }}
        h1 {{
            font-size: 2rem;
            color: var(--text-primary);
        }}
        .btn-theme {{
            background: var(--btn-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 18px;
            cursor: pointer;
            transition: all 0.2s;
            color: var(--text-primary);
        }}
        .btn-theme:hover {{
            background: var(--btn-bg-hover);
            border-color: var(--card-border-hover);
        }}
        .subtitle {{
            color: var(--text-secondary);
            margin-bottom: 40px;
        }}
        .instances-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 20px;
            max-width: 800px;
            width: 100%;
        }}
        .instance-card {{
            background: var(--card-bg);
            border-radius: 12px;
            padding: 30px 20px;
            text-align: center;
            text-decoration: none;
            color: var(--text-primary);
            transition: all 0.3s ease;
            border: 1px solid var(--card-border);
        }}
        .instance-card:hover {{
            background: var(--card-bg-hover);
            transform: translateY(-5px);
            border-color: var(--card-border-hover);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
        }}
        .instance-icon {{
            font-size: 3rem;
            margin-bottom: 15px;
        }}
        .instance-name {{
            font-size: 1.1rem;
            font-weight: 500;
        }}
        .no-instances {{
            color: var(--text-secondary);
            text-align: center;
            padding: 40px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Viewport</h1>
        <button class="btn-theme" id="themeToggle" title="Toggle light/dark mode">🌙</button>
    </div>
    <p class="subtitle">Select an instance to view</p>
    <div class="instances-grid">
        {instance_items if instances else '<div class="no-instances">No instances found</div>'}
    </div>
    <script>
        const themeToggle = document.getElementById('themeToggle');

        function getStoredTheme() {{
            return localStorage.getItem('viewport_theme') || 'dark';
        }}

        function setTheme(theme) {{
            if (theme === 'light') {{
                document.documentElement.setAttribute('data-theme', 'light');
                themeToggle.textContent = '☀️';
                themeToggle.title = 'Switch to dark mode';
            }} else {{
                document.documentElement.removeAttribute('data-theme');
                themeToggle.textContent = '🌙';
                themeToggle.title = 'Switch to light mode';
            }}
            localStorage.setItem('viewport_theme', theme);
        }}

        setTheme(getStoredTheme());

        themeToggle.addEventListener('click', () => {{
            const currentTheme = getStoredTheme();
            setTheme(currentTheme === 'dark' ? 'light' : 'dark');
        }});
    </script>
</body>
</html>'''


async def homepage(request):
    """
    Return viewport page or instance selection homepage.
    - No instance param: show homepage with instance list
    - Invalid instance: show error
    - Valid instance: show viewport page
    """
    instance = request.query_params.get('instance', '')

    if not instance:
        # No instance specified, show homepage with instance list
        instances = get_valid_instances()
        return HTMLResponse(generate_homepage_html(instances))

    # Check if instance exists
    instances = get_valid_instances()
    if instance not in instances:
        return HTMLResponse('instance not exist', status_code=404)

    # Valid instance, return viewport page
    with open(_HTML_PATH, 'r', encoding='utf-8') as f:
        html = f.read()
    return HTMLResponse(html)


# Error code to user-friendly message mapping
ERROR_MESSAGES = {
    'emulator_not_running': 'Emulator is not running. Please start the emulator first.',
    'device_not_found': 'Device not found. Please check if the emulator is running.',
    'connection_failed': 'Failed to connect to device. Please check the serial configuration.',
    'adb_error': 'ADB connection error. Please check if ADB server is running.',
    'config_not_found': 'Instance configuration not found.',
    'screenshot_failed': 'Failed to take screenshot. The game may not be running.',
    'unknown_error': 'An unknown error occurred.',
}


async def websocket_endpoint(websocket: WebSocket):
    instance_name = websocket.path_params.get('instance_name', '')
    if not instance_name:
        await websocket.close(code=4000, reason='Missing instance name')
        return

    # Verify authentication via URL query parameter
    auth_token = get_auth_token()
    if auth_token:
        # Get token from query string
        token = websocket.query_params.get('token', '')
        if token != auth_token:
            logger.warning(f'[Viewport] Unauthorized access attempt for {instance_name}')
            await websocket.close(code=4001, reason='Unauthorized')
            return

    await websocket.accept()
    manager = ViewportManager.get_instance()
    executor = get_screenshot_executor()

    conn, error_code = manager.get_connection(instance_name)
    if conn is None:
        error_msg = ERROR_MESSAGES.get(error_code, f'Cannot connect to device: {error_code}')
        await websocket.send_json({
            'type': 'error',
            'code': error_code,
            'message': error_msg
        })
        await websocket.close()
        return

    conn.acquire()
    manager.add_client(instance_name)  # Track client connection

    try:
        quality = 30
        scale = 0.5  # Resolution scale (1.0 = 720p, 0.5 = 360p, etc.) - default 360p for better performance
        target_fps = 30  # Default 30 FPS for smooth streaming
        is_paused = False  # Pause state for visibility-based streaming

        # Stats tracking
        stats_frame_count = 0
        stats_total_latency = 0.0
        stats_total_bytes = 0
        stats_start_time = time.monotonic()
        current_latency_ms = 0.0
        current_bandwidth_kbps = 0.0

        logger.info(
            f'[Viewport] Stream started for {instance_name}, '
            f'method={conn.screenshot_method}, resolution={conn.resolution}'
        )
        await websocket.send_json({
            'type': 'status',
            'connected': True,
            'script_running': manager.is_script_running(instance_name),
            'resolution': list(conn.resolution),
            'fps': target_fps,
            'screenshot_method': conn.screenshot_method,
            'control_method': conn.control_method,
            'client_count': manager.get_client_count(instance_name),
            'supports_raw_touch': conn.supports_raw_touch
        })

        last_status_time = time.monotonic()
        last_interaction_time = time.monotonic()  # Track last touch/swipe for idle frame-skip
        loop = asyncio.get_event_loop()

        while True:
            frame_start = time.monotonic()

            # Non-blocking check for incoming messages
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.005)
                data = json.loads(msg)
                action = data.get('action', '')

                if action == 'tap':
                    if not manager.is_script_running(instance_name):
                        loop.run_in_executor(executor, conn.touch, int(data['x']), int(data['y']))
                    last_interaction_time = time.monotonic()
                elif action == 'swipe':
                    if not manager.is_script_running(instance_name):
                        loop.run_in_executor(
                            executor, conn.swipe,
                            int(data['x1']), int(data['y1']),
                            int(data['x2']), int(data['y2']),
                            int(data.get('duration', 300))
                        )
                    last_interaction_time = time.monotonic()
                elif action == 'swipe_start':
                    if not manager.is_script_running(instance_name):
                        loop.run_in_executor(
                            executor, conn.swipe_start,
                            int(data['x1']), int(data['y1']),
                            int(data['x2']), int(data['y2'])
                        )
                    last_interaction_time = time.monotonic()
                elif action == 'touch_move':
                    if not manager.is_script_running(instance_name):
                        loop.run_in_executor(executor, conn.touch_move, int(data['x']), int(data['y']))
                    last_interaction_time = time.monotonic()
                elif action == 'touch_up':
                    if not manager.is_script_running(instance_name):
                        loop.run_in_executor(executor, conn.touch_up)
                    last_interaction_time = time.monotonic()
                elif action == 'set_quality':
                    quality = max(10, min(99, int(data['quality'])))
                elif action == 'set_fps':
                    target_fps = max(1, min(60, int(data['fps'])))
                elif action == 'set_scale':
                    scale = max(0.25, min(1.0, float(data['scale'])))
                elif action == 'resume_idle':
                    last_interaction_time = time.monotonic()
                    is_paused = False
                elif action == 'pause':
                    is_paused = data.get('paused', False)
                    logger.info(f'[Viewport] Stream {"paused" if is_paused else "resumed"} for {instance_name}')
                elif action == 'reconnect':
                    if conn.connected:
                        conn.release()
                        conn.disconnect()
                        if instance_name in manager.connections:
                            del manager.connections[instance_name]
                    new_conn, _ = manager.get_connection(instance_name)
                    if new_conn:
                        conn = new_conn
                        conn.acquire()
                        await websocket.send_json({
                            'type': 'status',
                            'connected': True,
                            'script_running': manager.is_script_running(instance_name),
                            'resolution': list(conn.resolution),
                            'fps': target_fps,
                            'screenshot_method': conn.screenshot_method,
                            'control_method': conn.control_method,
                            'client_count': manager.get_client_count(instance_name),
                            'supports_raw_touch': conn.supports_raw_touch
                        })
                    else:
                        await websocket.send_json({'type': 'error', 'message': 'Reconnect failed'})
            except asyncio.TimeoutError:
                pass
            except json.JSONDecodeError:
                pass

            # Handle disconnection
            if not conn.connected:
                logger.info(f'[Viewport] Connection lost for {instance_name}, reconnecting...')
                conn.release()
                conn.disconnect()
                if instance_name in manager.connections:
                    del manager.connections[instance_name]

                new_conn, _ = manager.get_connection(instance_name)
                if new_conn:
                    conn = new_conn
                    conn.acquire()
                    await websocket.send_json({
                        'type': 'status',
                        'connected': True,
                        'script_running': manager.is_script_running(instance_name),
                        'resolution': list(conn.resolution),
                        'fps': target_fps,
                        'screenshot_method': conn.screenshot_method,
                        'control_method': conn.control_method,
                        'client_count': manager.get_client_count(instance_name),
                        'supports_raw_touch': conn.supports_raw_touch
                    })
                else:
                    await websocket.send_json({'type': 'error', 'message': 'Device disconnected'})
                    await asyncio.sleep(2)
                continue

            # Skip frame capture if paused (page not visible)
            if is_paused:
                # Still need to check for WebSocket messages/disconnection
                try:
                    msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                    data = json.loads(msg)
                    action = data.get('action', '')
                    if action == 'pause':
                        is_paused = data.get('paused', False)
                        logger.info(f'[Viewport] Stream {"paused" if is_paused else "resumed"} for {instance_name}')
                    elif action == 'resume_idle':
                        last_interaction_time = time.monotonic()
                        is_paused = False
                except asyncio.TimeoutError:
                    pass
                except json.JSONDecodeError:
                    pass
                continue

            # Capture and send frame
            t_cap_start = time.monotonic()
            idle_seconds = t_cap_start - last_interaction_time
            skip_unchanged = idle_seconds >= 5.0
            is_idle = idle_seconds >= 300.0

            # When idle for 300s, skip capturing entirely (save CPU)
            if is_idle:
                jpeg_data = None
            else:
                jpeg_data = await loop.run_in_executor(
                    executor, lambda: conn.screenshot_encode(quality, scale, skip_unchanged)
                )
            t_cap_end = time.monotonic()

            if jpeg_data:
                t_send_start = time.monotonic()
                await websocket.send_bytes(jpeg_data)
                t_send_end = time.monotonic()

                # Update stats
                frame_latency = (t_cap_end - t_cap_start) * 1000  # ms
                stats_frame_count += 1
                stats_total_latency += frame_latency
                stats_total_bytes += len(jpeg_data)

                # Track WebSocket timing
                if not hasattr(websocket, '_ws_frame_count'):
                    websocket._ws_frame_count = 0
                    websocket._ws_cap_time = 0
                    websocket._ws_send_time = 0
                websocket._ws_frame_count += 1
                websocket._ws_cap_time += t_cap_end - t_cap_start
                websocket._ws_send_time += t_send_end - t_send_start

                if websocket._ws_frame_count >= 100:
                    avg_cap = websocket._ws_cap_time / websocket._ws_frame_count * 1000
                    avg_send = websocket._ws_send_time / websocket._ws_frame_count * 1000
                    # logger.info(
                    #     f'[Viewport] WS Timing (avg ms): capture={avg_cap:.1f}, send={avg_send:.1f}'
                    # )
                    websocket._ws_frame_count = 0
                    websocket._ws_cap_time = 0
                    websocket._ws_send_time = 0

            # Calculate stats every second (outside if jpeg_data so stats update during skips)
            stats_elapsed = time.monotonic() - stats_start_time
            if stats_elapsed >= 1.0:
                current_latency_ms = stats_total_latency / max(1, stats_frame_count)
                current_bandwidth_kbps = (stats_total_bytes * 8) / stats_elapsed / 1000  # kbps
                # Reset stats
                stats_frame_count = 0
                stats_total_latency = 0.0
                stats_total_bytes = 0
                stats_start_time = time.monotonic()

            # Periodic status update
            now = time.monotonic()
            if now - last_status_time >= 1.0:  # Update every second for stats
                last_status_time = now
                await websocket.send_json({
                    'type': 'status',
                    'connected': conn.connected,
                    'script_running': manager.is_script_running(instance_name),
                    'resolution': list(conn.resolution),
                    'fps': target_fps,
                    'screenshot_method': conn.screenshot_method,
                    'control_method': conn.control_method,
                    'latency_ms': round(current_latency_ms, 1),
                    'bandwidth_kbps': round(current_bandwidth_kbps, 0),
                    'client_count': manager.get_client_count(instance_name),
                    'idle': is_idle
                })

            # Frame rate limiting
            elapsed = time.monotonic() - frame_start
            sleep_time = (1.0 / target_fps) - elapsed
            if sleep_time > 0.001:
                await asyncio.sleep(sleep_time)

    except WebSocketDisconnect:
        logger.info(f'[Viewport] WebSocket disconnected for {instance_name}')
    except Exception as e:
        logger.warning(f'[Viewport] WebSocket error for {instance_name}: {e}')
    finally:
        manager.remove_client(instance_name)  # Track client disconnection
        manager.release_connection(instance_name)
        logger.info(f'[Viewport] Stream ended for {instance_name}, clients remaining: {manager.get_client_count(instance_name)}')


routes = [
    Route('/', homepage),
    WebSocketRoute('/ws/{instance_name}', websocket_endpoint),
]

viewport_app = Starlette(routes=routes)


# Emulator start status tracking
_emulator_start_status: Dict[str, str] = {}  # instance_name -> status ('starting', 'success', 'failed')


async def start_emulator_endpoint(request):
    """Start emulator for the given instance."""
    from starlette.responses import JSONResponse

    instance_name = request.path_params.get('instance_name', '')
    if not instance_name:
        return JSONResponse({'error': 'Missing instance name'}, status_code=400)

    # Check if instance config exists
    config_path = Path(f'./config/{instance_name}.json')
    if not config_path.exists():
        return JSONResponse({'error': 'Instance not found'}, status_code=404)

    # Check if already starting
    if _emulator_start_status.get(instance_name) == 'starting':
        return JSONResponse({'status': 'starting', 'message': 'Emulator is already starting'})

    # Start emulator in background
    _emulator_start_status[instance_name] = 'starting'

    def start_emulator_task():
        try:
            from module.config.config import AzurLaneConfig
            from module.device.platform.emulator_windows import EmulatorManager, Emulator
            import subprocess

            # Load config
            config = AzurLaneConfig(config_name=instance_name, task=None)

            # Find emulator instance
            emulator_manager = EmulatorManager()
            serial = config.Emulator_Serial

            # Find matching emulator
            emulator_instance = None
            for emulator in emulator_manager.all_emulator_instances:
                if emulator.serial == serial:
                    emulator_instance = emulator
                    break

            if emulator_instance is None:
                logger.warning(f'[Viewport] No emulator found for serial {serial}')
                _emulator_start_status[instance_name] = 'failed'
                return

            logger.info(f'[Viewport] Starting emulator for {instance_name}: {emulator_instance}')

            # Build start command based on emulator type
            exe = emulator_instance.emulator.path
            cmd = None

            if emulator_instance == Emulator.MuMuPlayer:
                cmd = f'"{exe}"'
            elif emulator_instance == Emulator.MuMuPlayerX:
                cmd = f'"{exe}" -m {emulator_instance.name}'
            elif emulator_instance == Emulator.MuMuPlayer12:
                if emulator_instance.MuMuPlayer12_id is not None:
                    # Use MuMuManager.exe api to launch, which creates independent window
                    manager_exe = Emulator.single_to_console(exe)
                    cmd = f'"{manager_exe}" api -v {emulator_instance.MuMuPlayer12_id} launch_player'
            elif emulator_instance == Emulator.LDPlayerFamily:
                console = Emulator.single_to_console(exe)
                cmd = f'"{console}" launch --index {emulator_instance.LDPlayer_id}'
            elif emulator_instance == Emulator.NoxPlayerFamily:
                cmd = f'"{exe}" -clone:{emulator_instance.name}'
            elif emulator_instance == Emulator.BlueStacks5:
                cmd = f'"{exe}" --instance {emulator_instance.name}'
            elif emulator_instance == Emulator.BlueStacks4:
                cmd = f'"{exe}" -vmname {emulator_instance.name}'
            elif emulator_instance == Emulator.MEmuPlayer:
                cmd = f'"{exe}" {emulator_instance.name}'

            if cmd is None:
                logger.warning(f'[Viewport] Unknown emulator type for {instance_name}')
                _emulator_start_status[instance_name] = 'failed'
                return

            logger.info(f'[Viewport] Executing: {cmd}')
            # Use close_fds and start_new_session to ensure emulator runs independently
            # This prevents emulator from being killed when ALAS closes
            # Same method as platform_windows.py execute()
            cmd = cmd.replace(r"\\", "/").replace("\\", "/").replace('"', '"')
            subprocess.Popen(cmd, close_fds=True, start_new_session=True)

            # Wait for emulator to be ready (check ADB connection)
            from adbutils import AdbClient
            import time

            adb_client = AdbClient('127.0.0.1', 5037)
            for i in range(60):  # Wait up to 60 seconds
                time.sleep(1)
                try:
                    # Try to connect
                    if ':' in serial:
                        msg = adb_client.connect(serial)
                        if 'connected' in msg:
                            logger.info(f'[Viewport] Emulator ready for {instance_name}')
                            _emulator_start_status[instance_name] = 'success'
                            return
                    else:
                        devices = [d.serial for d in adb_client.device_list()]
                        if serial in devices:
                            logger.info(f'[Viewport] Emulator ready for {instance_name}')
                            _emulator_start_status[instance_name] = 'success'
                            return
                except Exception:
                    pass

            logger.warning(f'[Viewport] Emulator start timeout for {instance_name}')
            _emulator_start_status[instance_name] = 'failed'

        except Exception as e:
            logger.warning(f'[Viewport] Failed to start emulator for {instance_name}: {e}')
            _emulator_start_status[instance_name] = 'failed'

    # Run in independent thread (not in executor pool to avoid shutdown issues)
    import threading
    thread = threading.Thread(target=start_emulator_task, daemon=False)
    thread.start()

    return JSONResponse({'status': 'starting', 'message': 'Emulator start initiated'})


async def start_emulator_status(request):
    """Get emulator start status."""
    from starlette.responses import JSONResponse

    instance_name = request.path_params.get('instance_name', '')
    status = _emulator_start_status.get(instance_name, 'unknown')
    return JSONResponse({'status': status})


# Add emulator start routes
from starlette.routing import Route as StarletteRoute
viewport_app.routes.append(StarletteRoute('/start/{instance_name}', start_emulator_endpoint, methods=['POST']))
viewport_app.routes.append(StarletteRoute('/start/{instance_name}/status', start_emulator_status, methods=['GET']))


def run_viewport_server(port: int = 22999, host: str = '0.0.0.0', ssl_keyfile: str = None, ssl_certfile: str = None):
    import uvicorn

    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    ssl_info = f', SSL={bool(ssl_keyfile and ssl_certfile)}' if ssl_keyfile or ssl_certfile else ''
    logger.info(f'[Viewport] Starting viewport server on {host}:{port}{ssl_info}')
    try:
        config = uvicorn.Config(
            viewport_app, host=host, port=port, log_level='warning', loop='asyncio',
            ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile
        )
        server = uvicorn.Server(config)
        loop.run_until_complete(server.serve())
    except Exception as e:
        logger.warning(f'[Viewport] Server error: {e}')


_viewport_thread: Optional[threading.Thread] = None


def start_viewport_server(port: int = 22999, ssl_keyfile: str = None, ssl_certfile: str = None):
    global _viewport_thread
    if _viewport_thread is not None and _viewport_thread.is_alive():
        logger.info('[Viewport] Server already running')
        return

    def delayed_start():
        time.sleep(2)  # Wait for main server to initialize
        run_viewport_server(port, ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile)

    _viewport_thread = threading.Thread(
        target=delayed_start,
        daemon=True,
        name='ViewportServer'
    )
    _viewport_thread.start()
    logger.info(f'[Viewport] Server thread started on port {port}')


def stop_viewport_server():
    global _viewport_thread, _screenshot_executor
    manager = ViewportManager.get_instance()
    manager.shutdown()
    if _screenshot_executor is not None:
        _screenshot_executor.shutdown(wait=False)
        _screenshot_executor = None
    _viewport_thread = None
    logger.info('[Viewport] Server stopped')
