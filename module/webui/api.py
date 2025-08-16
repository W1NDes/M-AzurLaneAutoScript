"""
基于 Starlette 的 Alas 实例控制 API
不需要额外的依赖，使用项目已有的 Starlette 框架
"""

import json
from datetime import datetime
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

from module.webui.process_manager import ProcessManager
from module.config.utils import alas_instance
from module.submodule.utils import get_config_mod
from module.logger import logger
from module.webui.updater import updater


class LocalOnlyMiddleware(BaseHTTPMiddleware):
    """只允许本地请求的中间件"""
    
    ALLOWED_IPS = {
        "127.0.0.1",      # IPv4 localhost
        "::1",            # IPv6 localhost
        "localhost"       # hostname localhost
    }
    
    async def dispatch(self, request: Request, call_next):
        # 获取客户端IP
        client_ip = request.client.host if request.client else None
        
        # 检查是否为本地请求
        if not self._is_local_request(client_ip, request):
            logger.warning(f"API访问被拒绝: 来自 {client_ip} 的非本地请求")
            return JSONResponse(
                {
                    "success": False,
                    "message": "访问被拒绝：API仅允许本地访问"
                },
                status_code=403
            )
        
        # 记录本地访问
        logger.info(f"API本地访问: {client_ip} -> {request.method} {request.url.path}")
        
        response = await call_next(request)
        return response
    
    def _is_local_request(self, client_ip: str, request: Request) -> bool:
        """检查是否为本地请求"""
        if not client_ip:
            return False
        
        # 直接IP检查
        if client_ip in self.ALLOWED_IPS:
            return True
        
        # 检查是否为127.x.x.x网段
        if client_ip.startswith("127."):
            return True
        
        # 检查IPv6本地地址
        if client_ip.startswith("::1") or client_ip == "::":
            return True
        
        # 检查HTTP headers中的Host
        host = request.headers.get("host", "").split(":")[0]
        if host in self.ALLOWED_IPS or host.startswith("127."):
            return True
        
        # 检查X-Forwarded-For头（可能通过代理）
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # 取第一个IP（原始客户端IP）
            original_ip = forwarded_for.split(",")[0].strip()
            if original_ip in self.ALLOWED_IPS or original_ip.startswith("127."):
                return True
        
        return False


def create_response(success: bool, message: str, data: dict = None):
    """创建统一的响应格式"""
    response_data = {
        "success": success,
        "message": message
    }
    if data:
        response_data["data"] = data
    return JSONResponse(response_data)

async def list_instances(request: Request):
    """列出所有实例"""

    try:
        instances = alas_instance()
        instance_list = []
        
        for instance_name in instances:
            manager = ProcessManager.get_manager(instance_name)
            state_map = {
                1: "运行中",
                2: "已停止", 
                3: "异常停止",
                4: "更新中"
            }
            
            instance_list.append({
                "name": instance_name,
                "alive": manager.alive,
                "state": manager.state,
                "state_description": state_map.get(manager.state, "未知状态")
            })
        
        return create_response(True, "获取实例列表成功", {"instances": instance_list})
    
    except Exception as e:
        logger.error(f"List instances error: {e}")
        return create_response(False, f"获取实例列表失败: {str(e)}")

async def get_instance_status(request: Request):
    """获取指定实例状态"""

    try:
        instance_name = request.path_params.get("instance")

        if instance_name not in alas_instance():
            return create_response(False, f"实例 '{instance_name}' 不存在")
        
        manager = ProcessManager.get_manager(instance_name)
        state_map = {
            1: "运行中",
            2: "已停止", 
            3: "异常停止",
            4: "更新中"
        }
        
        status_data = {
            "name": instance_name,
            "alive": manager.alive,
            "state": manager.state,
            "state_description": state_map.get(manager.state, "未知状态")
        }
        
        return create_response(True, "获取状态成功", status_data)
    
    except Exception as e:
        logger.error(f"Get status error: {e}")
        return create_response(False, f"获取状态失败: {str(e)}")

async def start_instance(request: Request):
    """启动实例"""
    try:
        instance_name = request.path_params.get("instance")

        if instance_name not in alas_instance():
            return create_response(False, f"实例 '{instance_name}' 不存在")
        
        manager = ProcessManager.get_manager(instance_name)
        if manager.alive:
            return create_response(True, f"实例 '{instance_name}' 已在运行")
        
        logger.info(f"API: Starting instance {instance_name}")
        manager.start(None, updater.event)
        
        logger.info(f"API: Started instance {instance_name}")
        return create_response(True, f"实例 '{instance_name}' 启动成功")
    
    except Exception as e:
        logger.error(f"Start instance error: {e}")
        return create_response(False, f"启动实例失败: {str(e)}")

async def stop_instance(request: Request):
    """停止实例"""
    try:
        instance_name = request.path_params.get("instance")
        
        if instance_name not in alas_instance():
            return create_response(False, f"实例 '{instance_name}' 不存在")
        
        manager = ProcessManager.get_manager(instance_name)
        if not manager.alive:
            return create_response(True, f"实例 '{instance_name}' 没有在运行")
        
        manager.stop()
        
        logger.info(f"API: Stopped instance {instance_name}")
        return create_response(True, f"实例 '{instance_name}' 停止成功")
    
    except Exception as e:
        logger.error(f"Stop instance error: {e}")
        return create_response(False, f"停止实例失败: {str(e)}")

async def batch_start_instances(request: Request):
    """批量启动实例"""
    try:
        body = await request.body()
        if not body:
            return create_response(False, "请求体为空")
        
        try:
            data = json.loads(body)
            instances = data.get("instances", [])
        except:
            return create_response(False, "请求格式错误")
        
        if not instances:
            return create_response(False, "未指定要启动的实例")
        
        all_instances = alas_instance()
        results = []
        success_count = 0
        
        for instance_name in instances:
            if instance_name not in all_instances:
                results.append({"name": instance_name, "success": False, "message": "实例不存在"})
                continue
            
            manager = ProcessManager.get_manager(instance_name)
            if manager.alive:
                results.append({"name": instance_name, "success": True, "message": "已在运行"})
                continue
            
            try:
                manager.start(None, updater.event)
                results.append({"name": instance_name, "success": True, "message": "启动成功"})
                success_count += 1
                logger.info(f"API: Batch started instance {instance_name}")
            except Exception as e:
                results.append({"name": instance_name, "success": False, "message": str(e)})
        
        return create_response(True, f"批量启动完成: {success_count}/{len(instances)} 成功", {"results": results})
    
    except Exception as e:
        logger.error(f"Batch start instances error: {e}")
        return create_response(False, f"批量启动失败: {str(e)}")

async def batch_stop_instances(request: Request):
    """批量停止实例"""
    try:
        body = await request.body()
        if not body:
            return create_response(False, "请求体为空")
        
        try:
            data = json.loads(body)
            instances = data.get("instances", [])
        except:
            return create_response(False, "请求格式错误")
        
        if not instances:
            return create_response(False, "未指定要停止的实例")
        
        all_instances = alas_instance()
        results = []
        success_count = 0
        
        for instance_name in instances:
            if instance_name not in all_instances:
                results.append({"name": instance_name, "success": False, "message": "实例不存在"})
                continue
            
            manager = ProcessManager.get_manager(instance_name)
            if not manager.alive:
                results.append({"name": instance_name, "success": True, "message": "未在运行"})
                success_count += 1
                continue
            
            try:
                manager.stop()
                results.append({"name": instance_name, "success": True, "message": "停止成功"})
                success_count += 1
                logger.info(f"API: Batch stopped instance {instance_name}")
            except Exception as e:
                results.append({"name": instance_name, "success": False, "message": str(e)})
        
        return create_response(True, f"批量停止完成: {success_count}/{len(instances)} 成功", {"results": results})
    
    except Exception as e:
        logger.error(f"Batch stop instances error: {e}")
        return create_response(False, f"批量停止失败: {str(e)}")

async def batch_instance_status(request: Request):
    """批量获取实例状态"""
    state_map = {
        1: "运行中",
        2: "已停止", 
        3: "异常停止",
        4: "更新中"
    }
    try:
        body = await request.body()
        if not body:
            return create_response(False, "请求体为空")
        try:
            data = json.loads(body)
            instances = data.get("instances", [])
        except:
            return create_response(False, "请求格式错误")
        
        if not instances:
            return create_response(False, "未指定要获取状态的实例")
        
        all_instances = alas_instance()
        results = []
        
        for instance_name in instances:
            if instance_name not in all_instances:
                status_data = {
                "name": instance_name,
                "state_description": "实例不存在"
                }
            else:
                manager = ProcessManager.get_manager(instance_name)
                status_data = {
                    "name": instance_name,
                    "state_description": state_map.get(manager.state, "未知状态")
                }
                results.append(status_data)
            
        return create_response(True, "获取状态成功", {"results": results})
    
    except Exception as e:
        logger.error(f"Batch get status error: {e}")
        return create_response(False, f"批量获取状态失败: {str(e)}")

# 定义路由
api_routes = [
    Route("/api/instances", list_instances, methods=["GET"]),
    Route("/api/instances/{instance}/status", get_instance_status, methods=["GET"]),
    Route("/api/instances/{instance}/start", start_instance, methods=["POST"]),
    Route("/api/instances/{instance}/stop", stop_instance, methods=["POST"]),
    Route("/api/instances/batch-start", batch_start_instances, methods=["POST"]),
    Route("/api/instances/batch-stop", batch_stop_instances, methods=["POST"]),
    Route("/api/instances/batch-status", batch_instance_status, methods=["POST"]),
]

# 创建API应用，添加本地访问限制中间件
api_app = Starlette(
    routes=api_routes,
    middleware=[
        Middleware(LocalOnlyMiddleware)
    ]
) 