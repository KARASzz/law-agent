"""
工具基类和注册机制

提供统一的工具接口和简单的注册机制
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import inspect


class ToolType(Enum):
    """工具类型枚举"""
    REGULATION = "regulation"
    CASE = "case"
    CITATION = "citation"
    DOCUMENT = "document"
    RAG = "rag"
    CUSTOM = "custom"


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __bool__(self):
        return self.success


class BaseTool(ABC):
    """
    工具基类
    
    所有工具必须继承此类并实现execute方法
    """
    
    name: str = ""  # 工具名称
    description: str = ""  # 工具描述
    tool_type: ToolType = ToolType.CUSTOM  # 工具类型
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        执行工具
        
        Args:
            **kwargs: 工具参数
            
        Returns:
            ToolResult: 执行结果
        """
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """
        获取工具的JSON Schema
        
        用于LLM理解工具的输入输出
        """
        sig = inspect.signature(self.execute)
        params = {}
        
        for name, param in sig.parameters.items():
            if name == "kwargs":
                continue
            
            param_info = {
                "type": "string",  # 默认类型
                "description": param.name,
            }
            
            # 处理默认值
            if param.default != inspect.Parameter.empty:
                param_info["default"] = param.default
            
            params[name] = param_info
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": params,
                "required": [
                    name for name, p in sig.parameters.items()
                    if p.default == inspect.Parameter.empty and name != "kwargs"
                ],
            },
        }


class ToolRegistry:
    """
    工具注册表
    
    使用简单的装饰器模式注册工具
    支持按名称调用工具
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._functions: Dict[str, Callable] = {}
    
    def register_tool(self, tool: BaseTool):
        """
        注册工具实例
        
        Args:
            tool: 工具实例
        """
        self._tools[tool.name] = tool
    
    def register_function(self, name: str, func: Callable):
        """
        注册函数
        
        Args:
            name: 函数名称
            func: 函数
        """
        self._functions[name] = func
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(name)
    
    def get_function(self, name: str) -> Optional[Callable]:
        """获取函数"""
        return self._functions.get(name)
    
    async def run_tool(self, name: str, **kwargs) -> ToolResult:
        """
        运行工具
        
        Args:
            name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            ToolResult: 执行结果
        """
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool '{name}' not found",
            )
        
        try:
            return await tool.execute(**kwargs)
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )
    
    async def run_function(self, name: str, **kwargs) -> Any:
        """
        运行函数
        
        Args:
            name: 函数名称
            **kwargs: 函数参数
            
        Returns:
            函数返回值
        """
        func = self._functions.get(name)
        if not func:
            raise ValueError(f"Function '{name}' not found")
        
        return await func(**kwargs)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有工具"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "type": tool.tool_type.value,
            }
            for tool in self._tools.values()
        ]
    
    def list_functions(self) -> List[str]:
        """列出所有函数"""
        return list(self._functions.keys())


# ===== 装饰器便捷函数 =====

def create_registry() -> ToolRegistry:
    """创建新的工具注册表"""
    return ToolRegistry()


# 全局注册表实例
_global_registry: Optional[ToolRegistry] = None


def get_global_registry() -> ToolRegistry:
    """获取全局注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def tool(name: str = None):
    """
    工具装饰器
    
    用法：
    ```python
    registry = ToolRegistry()
    
    @registry.tool("my_tool")
    async def my_tool(param1: str, param2: int = 10):
        return {"result": f"{param1} - {param2}"}
    ```
    """
    def decorator(func: Callable):
        func._is_tool = True
        func._tool_name = name or func.__name__
        
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        wrapper._tool_func = func
        wrapper._tool_name = name or func.__name__
        
        return wrapper
    
    return decorator
