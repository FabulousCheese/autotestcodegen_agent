"""测试执行 Agent"""
from typing import Any, Dict, List, Optional
from pydantic import Field
from datetime import datetime
import json
from loguru import logger

from core.agent.base_agent import AgentConfig, AgentType, AgentStatus
from core.agent.react_agent import ReActAgent, ThoughtStep, ActionType


class TestExecutorAgent(ReActAgent):
    """
    测试执行 Agent
    
    功能:
    - 准备测试环境
    - 执行测试用例
    - 收集测试结果
    - 处理测试输出
    """
    
    def __init__(self, config: AgentConfig, llm=None):
        super().__init__(config, llm)
        
        # 注册工具
        self._register_tools()
    
    def _register_tools(self):
        """注册 Agent 工具"""
        from core.tools.code_tools import execute_tests_tool, analyze_logs_tool
        
        async def execute_tests(**kwargs):
            result = await execute_tests_tool(**kwargs)
            return result.to_dict()
        
        self.add_tool("execute_tests", execute_tests)
        
        async def analyze_test_logs(logs: str):
            result = await analyze_logs_tool(logs)
            return result.to_dict()
        
        self.add_tool("analyze_test_logs", analyze_test_logs)
        
        async def prepare_environment():
            """准备测试环境"""
            # 这里可以添加环境准备逻辑
            return {
                "success": True,
                "message": "测试环境准备完成",
                "checks": {
                    "python": True,
                    "pytest": True,
                    "dependencies": True,
                }
            }
        
        self.add_tool("prepare_environment", prepare_environment)
    
    async def process(self, input_data: Any) -> Dict[str, Any]:
        """处理测试执行请求"""
        if isinstance(input_data, dict):
            tests = input_data.get("tests", "")
            language = input_data.get("language", "python")
            timeout = input_data.get("timeout", 60)
        else:
            tests = str(input_data)
            language = "python"
            timeout = 60
        
        logger.info(f"[TestExecutor] 开始执行测试")
        
        self.status = AgentStatus.RUNNING
        self.thought_history = []
        
        try:
            # 1. 准备环境
            prep_step = ThoughtStep(
                step_number=1,
                thought="准备测试执行环境",
                action="prepare_environment",
                action_input={},
                action_type=ActionType.TOOL_CALL,
            )
            
            try:
                prep_result = await self.tools["prepare_environment"]()
                prep_step.observation = "环境准备完成"
                prep_step.result = prep_result
            except Exception as e:
                prep_step.observation = f"环境准备失败: {e}，继续执行"
            
            self.thought_history.append(prep_step)
            
            # 2. 执行测试
            exec_step = ThoughtStep(
                step_number=2,
                thought=f"执行测试用例，超时设置: {timeout}s",
                action="execute_tests",
                action_input={
                    "tests": tests,
                    "language": language,
                    "timeout": timeout,
                },
                action_type=ActionType.TOOL_CALL,
            )
            
            try:
                result = await self.tools["execute_tests"](
                    tests=tests,
                    language=language,
                    timeout=timeout,
                )
                
                exec_step.result = result
                
                if result.get("success"):
                    exec_step.observation = f"测试执行成功: {result.get('result', {}).get('passed', 0)} 通过"
                    exec_step.action_type = ActionType.SUCCESS
                else:
                    exec_step.observation = f"测试执行失败: {result.get('result', {}).get('failed', 0)} 失败"
                    exec_step.action_type = ActionType.FAIL
                    
            except Exception as e:
                exec_step.error = str(e)
                exec_step.action_type = ActionType.FAIL
            
            self.thought_history.append(exec_step)
            
            # 3. 分析测试日志
            if result.get("result", {}).get("stderr"):
                analyze_step = ThoughtStep(
                    step_number=3,
                    thought="分析测试日志，提取错误信息",
                    action="analyze_test_logs",
                    action_input={"logs": result.get("result", {}).get("stderr", "")},
                    action_type=ActionType.TOOL_CALL,
                )
                
                try:
                    logs_result = await self.tools["analyze_test_logs"](
                        result.get("result", {}).get("stderr", "")
                    )
                    analyze_step.result = logs_result
                    analyze_step.observation = f"发现 {logs_result.get('result', {}).get('total_errors', 0)} 个错误"
                except Exception as e:
                    analyze_step.observation = f"日志分析失败: {e}"
                
                self.thought_history.append(analyze_step)
            
            # 返回结果
            self.status = AgentStatus.COMPLETED
            
            return {
                "success": result.get("success", False),
                "result": result.get("result"),
                "steps": [s.to_dict() for s in self.thought_history],
            }
            
        except Exception as e:
            logger.error(f"[TestExecutor] 处理失败: {e}")
            self.status = AgentStatus.FAILED
            return {
                "success": False,
                "error": str(e),
                "steps": [s.to_dict() for s in self.thought_history],
            }
    
    async def plan(self, task: str) -> List[str]:
        """制定测试执行计划"""
        return [
            "准备测试环境",
            "执行测试用例",
            "收集测试结果",
            "分析测试日志",
        ]


def create_test_executor_agent(llm=None) -> TestExecutorAgent:
    """创建测试执行 Agent"""
    config = AgentConfig(
        name="TestExecutor",
        agent_type=AgentType.TEST_EXECUTOR,
        description="专业的测试执行专家",
        max_steps=4,
        timeout=180,
        tools=["execute_tests", "analyze_test_logs", "prepare_environment"],
        retry_on_failure=True,
        max_retries=2,
    )
    
    return TestExecutorAgent(config, llm)
