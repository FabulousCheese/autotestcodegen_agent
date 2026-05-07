"""多 Agent 调度器"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid
from loguru import logger

from .base_agent import AgentType, AgentStatus, AgentContext
from .react_agent import ReActAgent, ThoughtStep


class WorkflowStatus(str, Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStep(BaseModel):
    """工作流步骤"""
    step_id: str
    agent_name: str
    agent_type: AgentType
    input_data: Any
    output_data: Any = None
    status: AgentStatus = AgentStatus.IDLE
    thought_history: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class Workflow(BaseModel):
    """工作流定义"""
    workflow_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    status: WorkflowStatus = WorkflowStatus.PENDING
    steps: List[WorkflowStep] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    current_step: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class AgentScheduler:
    """
    多 Agent 调度器
    
    负责:
    1. 管理多个 Agent 的生命周期
    2. 调度 Agent 执行任务
    3. 处理 Agent 间的消息传递
    4. 维护工作流状态
    """
    
    def __init__(self):
        self.agents: Dict[str, ReActAgent] = {}
        self.workflows: Dict[str, Workflow] = {}
        self.contexts: Dict[str, AgentContext] = {}
    
    def register_agent(self, agent: ReActAgent):
        """注册 Agent"""
        self.agents[agent.config.name] = agent
        logger.info(f"注册 Agent: {agent.config.name}")
    
    def create_workflow(self, name: str, description: str = "") -> Workflow:
        """创建工作流"""
        workflow = Workflow(name=name, description=description)
        self.workflows[workflow.workflow_id] = workflow
        logger.info(f"创建工作流: {workflow.workflow_id} - {name}")
        return workflow
    
    def add_workflow_step(self, workflow_id: str, agent_name: str, 
                          agent_type: AgentType, input_data: Any) -> WorkflowStep:
        """添加工作流步骤"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"工作流不存在: {workflow_id}")
        
        step = WorkflowStep(
            step_id=str(uuid.uuid4()),
            agent_name=agent_name,
            agent_type=agent_type,
            input_data=input_data,
        )
        workflow.steps.append(step)
        logger.info(f"添加工作流步骤: {step.step_id} - {agent_name}")
        return step
    
    async def execute_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """执行工作流"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return {"success": False, "error": f"工作流不存在: {workflow_id}"}
        
        workflow.status = WorkflowStatus.RUNNING
        workflow.updated_at = datetime.now()
        
        logger.info(f"开始执行工作流: {workflow_id}")
        
        try:
            for i, step in enumerate(workflow.steps):
                workflow.current_step = i
                step.started_at = datetime.now()
                step.status = AgentStatus.RUNNING
                
                agent = self.agents.get(step.agent_name)
                if not agent:
                    step.status = AgentStatus.FAILED
                    step.error = f"Agent 不存在: {step.agent_name}"
                    continue
                
                # 准备输入数据 (可能需要从前置步骤获取)
                input_data = step.input_data
                if isinstance(input_data, str) and input_data.startswith("$"):
                    # 从上下文引用
                    ref_key = input_data[1:]
                    input_data = workflow.context.get(ref_key)
                
                # 执行 Agent
                result = await agent.process(input_data)
                
                step.output_data = result.get("result")
                step.thought_history = result.get("steps", [])
                step.completed_at = datetime.now()
                
                if result.get("success"):
                    step.status = AgentStatus.COMPLETED
                    workflow.context[f"step_{i}_result"] = step.output_data
                else:
                    step.status = AgentStatus.FAILED
                    step.error = result.get("error")
                    
                    # 检查是否支持回退
                    if hasattr(agent.config, 'allow_rollback') and agent.config.allow_rollback:
                        # 回退到上一个成功步骤
                        logger.warning(f"步骤失败，尝试回退: {step.agent_name}")
                        await self._rollback_workflow(workflow, i)
                    else:
                        raise Exception(f"步骤执行失败: {step.error}")
                
                workflow.updated_at = datetime.now()
            
            workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = datetime.now()
            
            return {
                "success": True,
                "workflow_id": workflow_id,
                "result": workflow.context,
                "steps": [s.dict() for s in workflow.steps],
            }
            
        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            workflow.status = WorkflowStatus.FAILED
            workflow.updated_at = datetime.now()
            return {
                "success": False,
                "workflow_id": workflow_id,
                "error": str(e),
            }
    
    async def _rollback_workflow(self, workflow: Workflow, failed_step: int):
        """回退工作流"""
        for i in range(failed_step - 1, -1, -1):
            step = workflow.steps[i]
            if step.status == AgentStatus.COMPLETED:
                # 重新执行该步骤
                logger.info(f"回退到步骤 {i}: {step.agent_name}")
                step.status = AgentStatus.IDLE
                step.started_at = None
                step.completed_at = None
                step.output_data = None
                step.error = None
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Workflow]:
        """获取工作流状态"""
        return self.workflows.get(workflow_id)
    
    def cancel_workflow(self, workflow_id: str) -> bool:
        """取消工作流"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return False
        
        if workflow.status in [WorkflowStatus.PENDING, WorkflowStatus.RUNNING]:
            workflow.status = WorkflowStatus.CANCELLED
            workflow.updated_at = datetime.now()
            return True
        
        return False
    
    def get_available_agents(self) -> List[str]:
        """获取所有已注册的 Agent"""
        return list(self.agents.keys())
    
    async def execute_single_agent(self, agent_name: str, input_data: Any) -> Dict[str, Any]:
        """执行单个 Agent"""
        agent = self.agents.get(agent_name)
        if not agent:
            return {"success": False, "error": f"Agent 不存在: {agent_name}"}
        
        return await agent.process(input_data)
