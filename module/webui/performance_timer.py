import time
import functools
from typing import Optional, Callable
from contextlib import contextmanager

from module.logger import logger


class PerformanceTimer:
    """性能计时器，用于测量函数执行时间"""
    
    @staticmethod
    def timer(name: Optional[str] = None, log_level: str = "info", threshold_ms: float = 0):
        """
        函数计时装饰器
        
        Args:
            name: 自定义名称，默认使用函数名
            log_level: 日志级别 (debug, info, warning, error)
            threshold_ms: 只记录超过阈值的执行时间(毫秒)，0表示记录所有
        """
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.perf_counter()
                    duration_ms = (end_time - start_time) * 1000
                    
                    if duration_ms >= threshold_ms:
                        func_name = name or f"{func.__module__}.{func.__qualname__}"
                        log_msg = f"⏱️ [{func_name}] 执行耗时: {duration_ms:.2f}ms"
                        
                        # 根据耗时选择日志级别
                        if duration_ms > 1000:  # 超过1秒
                            logger.warning(f"🐌 {log_msg} (性能警告)")
                        elif duration_ms > 100:  # 超过100ms
                            logger.info(f"⚠️ {log_msg}")
                        else:
                            getattr(logger, log_level)(log_msg)
            
            return wrapper
        return decorator
    
    @staticmethod
    @contextmanager
    def measure(name: str, log_level: str = "info", threshold_ms: float = 0):
        """
        上下文管理器计时
        
        使用示例:
        with PerformanceTimer.measure("数据库查询"):
            # 执行代码
            pass
        """
        start_time = time.perf_counter()
        try:
            yield
        finally:
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000
            
            if duration_ms >= threshold_ms:
                log_msg = f"⏱️ [{name}] 执行耗时: {duration_ms:.2f}ms"
                
                if duration_ms > 1000:  # 超过1秒
                    logger.warning(f"🐌 {log_msg} (性能警告)")
                elif duration_ms > 100:  # 超过100ms
                    logger.info(f"⚠️ {log_msg}")
                else:
                    getattr(logger, log_level)(log_msg)


# 便捷的装饰器别名
timer = PerformanceTimer.timer
measure = PerformanceTimer.measure

# 预定义的常用装饰器
def critical_timer(name: Optional[str] = None):
    """关键路径计时器 - 记录所有执行时间"""
    return timer(name=name, log_level="info", threshold_ms=0)

def slow_timer(name: Optional[str] = None):
    """慢操作计时器 - 只记录超过100ms的操作"""
    return timer(name=name, log_level="info", threshold_ms=100)

def debug_timer(name: Optional[str] = None):
    """调试计时器 - 只记录超过10ms的操作"""
    return timer(name=name, log_level="debug", threshold_ms=10) 