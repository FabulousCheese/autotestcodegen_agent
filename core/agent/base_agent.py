"""Agent 基类定义"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
import uuid


class AgentType(str, Enum):
    """Agent 类型枚举"""
    TEST_GENERATOR = "test_generator"
    TEST_EXECUTOR = "test_executor"
    DEFECT_ANALYZER = "defect_analyzer"
    REPORT_GENERATOR = "report_generator"
    COORDINATOR = "coordinator"


class AgentStatus(str, Enum):
    """Agent 状态"""
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentConfig(BaseModel):
    """Agent 配置"""
    name: str
    agent_type: AgentType
    description: str = ""
    max_steps: int = 10
    timeout: int = 300
    tools: List[str] = Field(default_factory=list)
    retry_on_failure: bool = True
    max_retries: int = 3


class AgentMessage(BaseModel):
    """Agent 消息"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: str
    receiver: str
    content: Any
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseAgent(ABC):
    """Agent 基类"""
    
    def __init__(self, config: AgentConfig, llm=None):
        self.config = config
        self.llm = llm
        self.status = AgentStatus.IDLE
        self.memory: List[AgentMessage] = []
        self.tools: Dict[str, callable] = {}
    
    @abstractmethod
    async def process(self, input_data: Any) -> Any:
        """处理输入，返回结果"""
        pass
    
    @abstractmethod
    async def plan(self, task: str) -> List[str]:
        """制定执行计划"""
        pass
    
    def add_tool(self, name: str, func: callable):
        """注册工具"""
        self.tools[name] = func
    
    def get_memory(self) -> List[AgentMessage]:
        """获取记忆"""
        return self.memory
    
    def add_to_memory(self, message: AgentMessage):
        """添加到记忆"""
        self.memory.append(message)
    
    def clear_memory(self):
        """清空记忆"""
        self.memory = []


class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0


class AgentContext(BaseModel):
    """Agent 执行上下文"""
    task_id: str
    current_agent: str
    state: Dict[str, Any] = Field(default_factory=dict)
    history: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
