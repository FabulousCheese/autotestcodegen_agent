"""缺陷分析 Agent"""
from typing import Any, Dict, List, Optional
from pydantic import Field
from datetime import datetime
import json
from loguru import logger

from core.agent.base_agent import AgentConfig, AgentType, AgentStatus
from core.agent.react_agent import ReActAgent, ThoughtStep, ActionType


class DefectAnalyzerAgent(ReActAgent):
    """
    缺陷分析 Agent
    
    功能:
    - 分析测试失败日志
    - 识别错误类型
    - 定位根因
    - 生成修复建议
    """
    
    def __init__(self, config: AgentConfig, llm=None, rag_memory=None):
        super().__init__(config, llm)
        self.rag_memory = rag_memory
        
        # 注册工具
        self._register_tools()
    
    def _register_tools(self):
        """注册 Agent 工具"""
        from core.tools.code_tools import analyze_logs_tool
        
        async def analyze_defects(**kwargs):
            result = await analyze_logs_tool(**kwargs)
            return result.to_dict()
        
        self.add_tool("analyze_defects", analyze_defects)
        
        async def search_knowledge_base(query: str):
            if self.rag_memory:
                results = self.rag_memory.search(query, n_results=5)
                return results
            return []
        
        self.add_tool("search_knowledge_base", search_knowledge_base)
        
        async def generate_fix_suggestion(error_type: str, context: str):
            """生成修复建议"""
            suggestions = {
                "KeyError": [
                    "使用 dict.get() 方法提供默认值",
                    "在访问前检查键是否存在",
                    "使用 collections.defaultdict",
                ],
                "TypeError": [
                    "检查参数类型是否匹配",
                    "添加类型转换逻辑",
                    "使用 isinstance() 进行类型检查",
                ],
                "ValueError": [
                    "添加输入验证",
                    "使用 try-except 捕获异常",
                    "提供有意义的错误信息",
                ],
                "ImportError": [
                    "检查依赖是否安装: pip install <package>",
                    "检查 Python 版本兼容性",
                    "确认包名是否正确",
                ],
            }
            
            return {
                "error_type": error_type,
                "suggestions": suggestions.get(error_type, [
                    "需要进一步分析错误上下文",
                    "建议查看相关文档",
                    "考虑向社区寻求帮助",
                ]),
                "context_required": True,
            }
        
        self.add_tool("generate_fix_suggestion", generate_fix_suggestion)
    
    async def process(self, input_data: Any) -> Dict[str, Any]:
        """处理缺陷分析请求"""
        if isinstance(input_data, dict):
            logs = input_data.get("logs", "")
            test_results = input_data.get("test_results", {})
        else:
            logs = str(input_data)
            test_results = {}
        
        logger.info(f"[DefectAnalyzer] 开始分析缺陷")
        
        self.status = AgentStatus.RUNNING
        self.thought_history = []
        
        try:
            # 1. 解析错误信息
            parse_step = ThoughtStep(
                step_number=1,
                thought="解析测试结果和日志信息",
                action="parse_errors",
                action_input={"logs": logs[:500], "test_results": test_results},
                action_type=ActionType.THINK,
            )
            self.thought_history.append(parse_step)
            
            # 2. 搜索知识库
            kb_step = ThoughtStep(
                step_number=2,
                thought="搜索历史缺陷解决方案",
                action="search_knowledge_base",
                action_input={"query": logs[:500]},
                action_type=ActionType.TOOL_CALL,
            )
            
            similar_cases = []
            try:
                if "search_knowledge_base" in self.tools:
                    similar_cases = await self.tools["search_knowledge_base"](logs[:500])
                    kb_step.observation = f"找到 {len(similar_cases)} 个相似案例"
                    kb_step.result = similar_cases
            except Exception as e:
                kb_step.observation = f"知识库搜索失败: {e}"
            
            self.thought_history.append(kb_step)
            
            # 3. 分析缺陷
            analyze_step = ThoughtStep(
                step_number=3,
                thought="执行深度缺陷分析",
                action="analyze_defects",
                action_input={"logs": logs},
                action_type=ActionType.TOOL_CALL,
            )
            
            try:
                result = await self.tools["analyze_defects"](logs=logs)
                analyze_step.result = result
                
                if result.get("success"):
                    error_summary = result.get("result", {}).get("error_summary", {})
                    analyze_step.observation = f"发现 {len(error_summary)} 种错误类型"
                    analyze_step.action_type = ActionType.SUCCESS
                else:
                    analyze_step.error = result.get("error")
                    analyze_step.action_type = ActionType.FAIL
                    
            except Exception as e:
                analyze_step.error = str(e)
                analyze_step.action_type = ActionType.FAIL
            
            self.thought_history.append(analyze_step)
            
            # 4. 生成修复建议
            suggestions = []
            if result.get("success"):
                root_cause = result.get("result", {}).get("root_cause_analysis", {})
                primary_issue = root_cause.get("primary_issue", "Other")
                
                suggest_step = ThoughtStep(
                    step_number=4,
                    thought=f"基于主要问题 '{primary_issue}' 生成修复建议",
                    action="generate_fix_suggestion",
                    action_input={"error_type": primary_issue, "context": logs[:300]},
                    action_type=ActionType.TOOL_CALL,
                )
                
                try:
                    fix_result = await self.tools["generate_fix_suggestion"](
                        error_type=primary_issue,
                        context=logs[:300],
                    )
                    suggestions = fix_result.get("suggestions", [])
                    suggest_step.result = fix_result
                    suggest_step.observation = f"生成 {len(suggestions)} 条修复建议"
                except Exception as e:
                    suggest_step.observation = f"建议生成失败: {e}"
                
                self.thought_history.append(suggest_step)
                
                # 保存到知识库
                if self.rag_memory:
                    try:
                        self.rag_memory.add_document(
                            logs,
                            {
                                "type": "defect_case",
                                "error_type": primary_issue,
                                "suggestions": json.dumps(suggestions),
                                "created_at": datetime.now().isoformat(),
                            }
                        )
                    except Exception as e:
                        logger.warning(f"保存到知识库失败: {e}")
            
            # 返回结果
            self.status = AgentStatus.COMPLETED
            
            return {
                "success": True,
                "result": {
                    "error_summary": result.get("result", {}).get("error_summary", {}),
                    "root_cause": result.get("result", {}).get("root_cause_analysis", {}),
                    "fix_suggestions": suggestions,
                    "similar_cases": [
                        {"content": c.get("content", "")[:200], "metadata": c.get("metadata", {})}
                        for c in similar_cases[:3]
                    ],
                },
                "steps": [s.to_dict() for s in self.thought_history],
            }
            
        except Exception as e:
            logger.error(f"[DefectAnalyzer] 处理失败: {e}")
            self.status = AgentStatus.FAILED
            return {
                "success": False,
                "error": str(e),
                "steps": [s.to_dict() for s in self.thought_history],
            }
    
    async def plan(self, task: str) -> List[str]:
        """制定缺陷分析计划"""
        return [
            "解析错误信息",
            "搜索历史案例",
            "分析根因",
            "生成修复建议",
        ]


def create_defect_analyzer_agent(llm=None, rag_memory=None) -> DefectAnalyzerAgent:
    """创建缺陷分析 Agent"""
    config = AgentConfig(
        name="DefectAnalyzer",
        agent_type=AgentType.DEFECT_ANALYZER,
        description="专业的缺陷分析专家",
        max_steps=5,
        timeout=120,
        tools=["analyze_defects", "search_knowledge_base", "generate_fix_suggestion"],
        retry_on_failure=True,
        max_retries=2,
    )
    
    return DefectAnalyzerAgent(config, llm, rag_memory)
