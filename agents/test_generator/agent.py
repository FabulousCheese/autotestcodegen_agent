"""测试用例生成 Agent"""
from typing import Any, Dict, List, Optional
from pydantic import Field
from datetime import datetime
import json
import re
from loguru import logger

from core.agent.base_agent import AgentConfig, AgentType, AgentStatus
from core.agent.react_agent import ReActAgent, ThoughtStep, ActionType


# 测试生成提示词模板
TEST_GENERATION_PROMPT = """你是一个专业的测试工程师。请为以下代码生成完整的 pytest 测试用例。

要求：
1. 测试用例要完整可运行，不要有 TODO 或 pass
2. 包含正常情况、边界值、异常情况的测试
3. 每个测试用例要有明确的断言
4. 使用 pytest 框架
5. 只输出测试代码，不要解释
6. 每个测试函数的 docstring 第一行必须标注测试类型，格式为：[测试类型: xxx]

重要：浮点数断言规则
- 禁止使用 == 精确比较浮点数结果！
- 必须导入 math 模块并使用以下方法：
  * 对于浮点数比较：使用 math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12)
  * 对于 NaN 检查：使用 math.isnan(value) 而非 value == float('nan')
  * 对于无穷大检查：使用 math.isinf(value) 而非 value == float('inf')
- 例如：assert math.isclose(divide(1, 3), 0.333333333, rel_tol=1e-9)

测试类型定义：
- [测试类型: 正常测试] - 测试函数的常规、预期行为
- [测试类型: 边界测试] - 测试边界值、极端情况
- [测试类型: 异常测试] - 测试异常输入、错误处理
- [测试类型: 精度测试] - 测试数值精度、浮点计算
- [测试类型: 类型测试] - 测试类型转换、类型边界
- [测试类型: 参数化测试] - 使用 @pytest.mark.parametrize 的参数化测试

示例格式：
```python
import math

def test_divide_positive_numbers():
    """[测试类型: 正常测试] 测试两个正数相除
    """
    assert math.isclose(divide(1, 3), 0.333333333, rel_tol=1e-9)

def test_divide_with_nan():
    """[测试类型: 边界测试] 测试 NaN 结果
    """
    result = divide(float('inf'), float('inf'))
    assert math.isnan(result), f"期望 NaN，实际得到 {result}"
```

代码：
{code}

生成的测试用例："""


class TestGeneratorAgent(ReActAgent):
    """
    测试用例生成 Agent
    
    功能:
    - 使用 LLM 分析源代码
    - 生成完整可运行的测试用例
    - 保存到知识库
    """
    
    def __init__(self, config: AgentConfig, llm=None, rag_memory=None):
        super().__init__(config, llm)
        self.rag_memory = rag_memory
        
        # 注册工具
        self._register_tools()
    
    def _register_tools(self):
        """注册 Agent 工具"""
        from core.tools.code_tools import generate_tests_tool
        
        # 规则引擎生成（备用）
        async def generate_tests_rule(**kwargs):
            result = await generate_tests_tool(**kwargs)
            return result.to_dict()
        
        # LLM 生成（主用）
        async def generate_tests_llm(code: str, language: str = "python", 
                                      framework: str = "pytest", test_cases: int = 5):
            """使用 LLM 生成测试用例"""
            if not self.llm:
                return {"success": False, "error": "LLM 未初始化"}
            
            try:
                prompt = TEST_GENERATION_PROMPT.format(code=code)
                
                # 调用 LLM
                from langchain_core.messages import HumanMessage
                
                response = await self.llm.agenerate([[HumanMessage(content=prompt)]])
                
                # 提取响应内容
                generation = response.generations[0][0]
                if hasattr(generation, 'message') and hasattr(generation.message, 'content'):
                    tests_code = generation.message.content.strip()
                else:
                    tests_code = generation.text.strip()
                
                # 清理代码（移除可能的 markdown 代码块）
                if tests_code.startswith("```"):
                    tests_code = re.sub(r'^```\w*\n?', '', tests_code)
                    tests_code = re.sub(r'\n?```$', '', tests_code)
                
                # 后处理：修复浮点数断言问题
                from core.tools.code_tools import fix_floating_point_assertions
                tests_code = fix_floating_point_assertions(tests_code)
                
                # 统计测试数量
                test_count = len(re.findall(r'def test_\w+\(', tests_code))
                
                return {
                    "success": True,
                    "result": {
                        "tests": tests_code,
                        "framework": framework,
                        "language": language,
                        "test_count": test_count,
                    }
                }
            except Exception as e:
                logger.error(f"LLM 生成失败: {e}")
                return {"success": False, "error": str(e)}
        
        self.add_tool("generate_tests", generate_tests_llm)
        self.add_tool("generate_tests_rule", generate_tests_rule)
        
        async def search_knowledge_base(query: str):
            if self.rag_memory:
                results = self.rag_memory.search(query, n_results=3)
                return results
            return []
        
        self.add_tool("search_knowledge_base", search_knowledge_base)
        
        async def save_to_knowledge_base(content: str, metadata: Dict):
            if self.rag_memory:
                self.rag_memory.add_document(content, metadata)
                return {"success": True, "message": "已保存"}
            return {"success": False, "message": "知识库未初始化"}
        
        self.add_tool("save_to_knowledge_base", save_to_knowledge_base)
    
    async def process(self, input_data: Any) -> Dict[str, Any]:
        """处理测试生成请求"""
        if isinstance(input_data, dict):
            code = input_data.get("code", "")
            language = input_data.get("language", "python")
            framework = input_data.get("framework", "pytest")
            test_cases = input_data.get("test_cases", 5)
        else:
            code = str(input_data)
            language = "python"
            framework = "pytest"
            test_cases = 5
        
        logger.info(f"[TestGenerator] 开始生成测试用例，语言: {language}")
        
        self.status = AgentStatus.RUNNING
        self.thought_history = []
        
        # 判断使用 LLM 还是规则引擎
        use_llm = self.llm is not None
        
        try:
            # 1. 思考阶段
            thought_step = ThoughtStep(
                step_number=1,
                thought=f"分析代码结构，准备生成测试用例" + ("（使用 DeepSeek LLM）" if use_llm else "（使用规则引擎）"),
                action="analyze_code",
                action_input={"code": code[:200] + "..." if len(code) > 200 else code},
                action_type=ActionType.THINK,
            )
            self.thought_history.append(thought_step)
            
            # 2. 生成测试用例
            generate_step = ThoughtStep(
                step_number=2,
                thought=f"调用 {'LLM' if use_llm else '规则引擎'} 生成测试用例",
                action="generate_tests",
                action_input={
                    "code": code,
                    "language": language,
                    "framework": framework,
                    "test_cases": test_cases,
                },
                action_type=ActionType.TOOL_CALL,
            )
            
            try:
                if use_llm:
                    result = await self.tools["generate_tests"](
                        code=code,
                        language=language,
                        framework=framework,
                        test_cases=test_cases,
                    )
                else:
                    # 降级到规则引擎
                    result = await self.tools["generate_tests_rule"](
                        code=code,
                        language=language,
                        framework=framework,
                        test_cases=test_cases,
                    )
                
                if result.get("success"):
                    test_count = result.get("result", {}).get("test_count", 0)
                    generate_step.observation = f"成功生成 {test_count} 个测试用例"
                    generate_step.result = result.get("result")
                else:
                    generate_step.error = result.get("error")
                    generate_step.action_type = ActionType.FAIL
                    
            except Exception as e:
                generate_step.error = str(e)
                generate_step.action_type = ActionType.FAIL
                result = {"success": False, "error": str(e)}
            
            self.thought_history.append(generate_step)
            
            # 3. 保存到知识库
            if result.get("success"):
                save_step = ThoughtStep(
                    step_number=3,
                    thought="保存测试用例到知识库",
                    action="save_to_knowledge_base",
                    action_input={},
                    action_type=ActionType.TOOL_CALL,
                )
                
                try:
                    if "save_to_knowledge_base" in self.tools:
                        await self.tools["save_to_knowledge_base"](
                            result.get("result", {}).get("tests", ""),
                            {
                                "type": "test_case",
                                "language": language,
                                "framework": framework,
                                "created_at": datetime.now().isoformat(),
                            }
                        )
                        save_step.observation = "已保存到知识库"
                except Exception as e:
                    save_step.observation = f"保存失败: {e}"
                
                self.thought_history.append(save_step)
            
            # 返回结果
            self.status = AgentStatus.COMPLETED
            
            return {
                "success": result.get("success", False),
                "result": result.get("result"),
                "error": result.get("error"),
                "steps": [s.to_dict() for s in self.thought_history],
            }
            
        except Exception as e:
            logger.error(f"[TestGenerator] 处理失败: {e}")
            self.status = AgentStatus.FAILED
            return {
                "success": False,
                "error": str(e),
                "steps": [s.to_dict() for s in self.thought_history],
            }
    
    async def plan(self, task: str) -> List[str]:
        """制定测试生成计划"""
        return [
            "分析代码结构",
            "生成测试用例",
            "保存到知识库",
        ]


# Agent 配置工厂
def create_test_generator_agent(llm=None, rag_memory=None) -> TestGeneratorAgent:
    """创建测试生成 Agent"""
    config = AgentConfig(
        name="TestGenerator",
        agent_type=AgentType.TEST_GENERATOR,
        description="专业的测试用例生成专家",
        max_steps=4,
        timeout=120,
        tools=["generate_tests", "generate_tests_rule", "save_to_knowledge_base"],
        retry_on_failure=True,
        max_retries=2,
    )
    
    return TestGeneratorAgent(config, llm, rag_memory)
