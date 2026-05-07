"""ReAct (Reasoning + Acting) Agent 实现"""
from typing import Any, Dict, List, Optional, Callable
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import json
import time
from loguru import logger

from .base_agent import AgentConfig, AgentStatus, ToolResult, BaseAgent


class ActionType(str, Enum):
    """动作类型"""
    THINK = "think"
    TOOL_CALL = "tool_call"
    RESPOND = "respond"
    OBSERVE = "observe"
    PLAN = "plan"
    REASON = "reason"
    FAIL = "fail"
    SUCCESS = "success"
    RETRY = "retry"


class ThoughtStep(BaseModel):
    """思考步骤"""
    step_number: int
    thought: str
    action: str
    action_input: Dict[str, Any] = Field(default_factory=dict)
    observation: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    action_type: ActionType = ActionType.THINK
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "action_type": self.action_type.value,
        }


class ReActAgent(BaseAgent):
    """
    ReAct Agent 实现
    
    基于 Thought-Action-Observation 模式:
    1. Thought: 分析当前情况，制定下一步行动
    2. Action: 执行工具或生成响应
    3. Observation: 观察结果，更新状态
    """
    
    def __init__(self, config: AgentConfig, llm=None):
        super().__init__(config, llm)
        self.thought_history: List[ThoughtStep] = []
        self.max_steps = config.max_steps
        self.retry_count = 0
        
    async def process(self, input_data: Any) -> Dict[str, Any]:
        """执行 ReAct 循环"""
        self.status = AgentStatus.RUNNING
        self.thought_history = []
        self.retry_count = 0
        
        logger.info(f"[{self.config.name}] 开始处理任务")
        
        try:
            result = await self._react_loop(input_data)
            self.status = AgentStatus.COMPLETED
            return {
                "success": True,
                "result": result,
                "steps": [s.to_dict() for s in self.thought_history],
            }
        except Exception as e:
            logger.error(f"[{self.config.name}] 执行失败: {str(e)}")
            self.status = AgentStatus.FAILED
            return {
                "success": False,
                "error": str(e),
                "steps": [s.to_dict() for s in self.thought_history],
            }
    
    async def _react_loop(self, input_data: Any) -> Any:
        """ReAct 主循环"""
        state = {"input": input_data, "context": {}}
        
        for step in range(self.max_steps):
            step_number = step + 1
            
            # 1. Thought - 分析情况
            thought = await self._think(step_number, state)
            
            # 2. Action - 决定行动
            action_result = await self._act(step_number, thought, state)
            
            # 3. Observation - 观察结果
            if action_result.success:
                state = await self._observe(step_number, action_result, state)
                
                # 检查是否完成
                if action_result.is_final:
                    return action_result.result
            
            # 检查是否需要重试
            if action_result.needs_retry and self.retry_count < self.config.max_retries:
                self.retry_count += 1
                logger.warning(f"[{self.config.name}] 重试次数: {self.retry_count}")
        
        raise Exception(f"超过最大步骤数 {self.max_steps}")
    
    async def _think(self, step_number: int, state: Dict[str, Any]) -> str:
        """思考阶段 - 分析当前情况"""
        thought_prompt = f"""你是一个专业的{self.config.description}。
        
当前任务: {state.get('input', {})}
当前状态: {json.dumps(state.get('context', {}), ensure_ascii=False, indent=2)}

请分析当前情况，决定下一步行动。考虑:
1. 已经完成了什么
2. 当前面临什么问题
3. 下一步应该做什么

请用简洁的语言描述你的思考过程。"""
        
        # 如果有 LLM，使用 LLM 生成思考
        if self.llm:
            try:
                response = await self.llm.agenerate([thought_prompt])
                thought = response.generations[0][0].text
            except Exception as e:
                logger.warning(f"LLM 调用失败: {e}, 使用默认思考")
                thought = f"分析当前任务，准备执行下一步操作"
        else:
            thought = f"分析任务，制定执行计划"
        
        # 记录思考步骤
        thought_step = ThoughtStep(
            step_number=step_number,
            thought=thought,
            action="thinking",
            action_input={"state": state},
            action_type=ActionType.THINK,
        )
        self.thought_history.append(thought_step)
        
        return thought
    
    async def _act(self, step_number: int, thought: str, state: Dict[str, Any]) -> ToolResult:
        """行动阶段 - 执行工具或生成响应"""
        # 解析需要的动作
        action = self._parse_action(thought, state)
        
        thought_step = ThoughtStep(
            step_number=step_number,
            thought=thought,
            action=action.get("name", "unknown"),
            action_input=action.get("input", {}),
            action_type=ActionType.TOOL_CALL,
        )
        
        start_time = time.time()
        
        try:
            # 执行工具
            if action["name"] in self.tools:
                result = await self.tools[action["name"]](**action.get("input", {}))
                execution_time = time.time() - start_time
                
                thought_step.result = result
                thought_step.observation = f"工具执行成功，耗时 {execution_time:.2f}s"
                
                return ToolResult(
                    success=True,
                    result=result,
                    execution_time=execution_time,
                    is_final=action.get("is_final", False),
                    needs_retry=False,
                )
            else:
                # 没有可用工具，返回思考结果作为最终响应
                thought_step.observation = "无可用工具，使用 LLM 直接生成响应"
                thought_step.action_type = ActionType.RESPOND
                
                if self.llm:
                    response = await self.llm.agenerate([f"基于以下思考生成响应: {thought}"])
                    return ToolResult(
                        success=True,
                        result=response.generations[0][0].text,
                        execution_time=time.time() - start_time,
                        is_final=True,
                    )
                else:
                    return ToolResult(
                        success=True,
                        result=thought,
                        execution_time=time.time() - start_time,
                        is_final=True,
                    )
                        
        except Exception as e:
            execution_time = time.time() - start_time
            thought_step.error = str(e)
            thought_step.action_type = ActionType.FAIL
            
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
                needs_retry=self.config.retry_on_failure,
            )
        finally:
            self.thought_history.append(thought_step)
    
    async def _observe(self, step_number: int, action_result: ToolResult, 
                       state: Dict[str, Any]) -> Dict[str, Any]:
        """观察阶段 - 更新状态"""
        observation = f"观察结果: {action_result.result if action_result.success else action_result.error}"
        
        thought_step = ThoughtStep(
            step_number=step_number,
            thought=observation,
            action="observe",
            action_input={"state": state},
            observation=observation,
            result=action_result.result,
            action_type=ActionType.OBSERVE,
        )
        self.thought_history.append(thought_step)
        
        # 更新状态
        state["context"]["last_result"] = action_result.result
        state["context"]["last_error"] = action_result.error
        
        return state
    
    def _parse_action(self, thought: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """解析思考结果，确定动作"""
        # 检查是否有预定义的工具
        if self.tools:
            available_tools = list(self.tools.keys())
            
            # 简单规则匹配
            if "测试用例" in thought or "生成" in thought:
                if "generate_tests" in available_tools:
                    return {"name": "generate_tests", "input": {"task": state.get("input")}}
            
            if "执行" in thought or "运行" in thought:
                if "execute_tests" in available_tools:
                    return {"name": "execute_tests", "input": {"tests": state.get("context", {}).get("last_result")}}
            
            if "分析" in thought or "缺陷" in thought:
                if "analyze_defects" in available_tools:
                    return {"name": "analyze_defects", "input": {"logs": state.get("context", {}).get("last_result")}}
        
        return {"name": "respond", "input": {"thought": thought}, "is_final": True}
    
    async def plan(self, task: str) -> List[str]:
        """制定执行计划"""
        plan_prompt = f"""为以下任务制定执行计划:

任务: {task}

可用步骤:
1. 分析需求/代码
2. 生成测试用例
3. 执行测试
4. 分析结果
5. 生成报告

请列出具体的执行步骤，以 JSON 数组格式返回。"""
        
        if self.llm:
            try:
                response = await self.llm.agenerate([plan_prompt])
                import re
                # 提取 JSON 数组
                match = re.search(r'\[.*\]', response.generations[0][0].text, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
            except Exception as e:
                logger.warning(f"计划生成失败: {e}")
        
        # 默认计划
        return ["分析输入", "执行核心逻辑", "返回结果"]
    
    def get_thought_history(self) -> List[Dict[str, Any]]:
        """获取思考历史"""
        return [s.to_dict() for s in self.thought_history]
