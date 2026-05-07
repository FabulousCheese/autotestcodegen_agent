"""工具基类定义"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class Tool(BaseModel, ABC):
    """工具基类"""
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    @abstractmethod
    async def execute(self, **kwargs) -> "ToolResult":
        """执行工具"""
        pass
    
    def to_langchain_tool(self):
        """转换为 LangChain 工具格式"""
        from langchain.tools import Tool as LangChainTool
        
        async def async_execute(**kwargs):
            result = await self.execute(**kwargs)
            return result.to_dict()
        
        return LangChainTool(
            name=self.name,
            description=self.description,
            func=lambda **kw: async_execute(**kw),
        )


class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }
