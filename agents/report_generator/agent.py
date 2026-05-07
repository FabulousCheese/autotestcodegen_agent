"""报告生成 Agent"""
from typing import Any, Dict, List, Optional
from pydantic import Field
from datetime import datetime
import json
from loguru import logger

from core.agent.base_agent import AgentConfig, AgentType, AgentStatus
from core.agent.react_agent import ReActAgent, ThoughtStep, ActionType


class ReportGeneratorAgent(ReActAgent):
    """
    报告生成 Agent
    
    功能:
    - 汇总测试结果
    - 生成测试报告
    - 支持多种格式 (Markdown, HTML)
    - 可视化展示
    """
    
    def __init__(self, config: AgentConfig, llm=None):
        super().__init__(config, llm)
        
        # 注册工具
        self._register_tools()
    
    def _register_tools(self):
        """注册 Agent 工具"""
        from core.tools.code_tools import calculate_coverage_tool
        from core.tools.file_tools import write_file_tool
        
        async def generate_markdown_report(data: Dict) -> Dict:
            """生成 Markdown 报告"""
            report = _generate_markdown(data)
            return {"success": True, "report": report}
        
        self.add_tool("generate_markdown_report", generate_markdown_report)
        
        async def generate_html_report(data: Dict) -> Dict:
            """生成 HTML 报告"""
            report = _generate_html(data)
            return {"success": True, "report": report}
        
        self.add_tool("generate_html_report", generate_html_report)
        
        async def calculate_coverage(data: Dict) -> Dict:
            result = await calculate_coverage_tool(
                code=data.get("code", ""),
                tests=data.get("tests", ""),
            )
            return result.to_dict()
        
        self.add_tool("calculate_coverage", calculate_coverage)
        
        async def save_report(content: str, file_path: str) -> Dict:
            result = await write_file_tool(
                file_path=file_path,
                content=content,
            )
            return result.to_dict()
        
        self.add_tool("save_report", save_report)
    
    async def process(self, input_data: Any) -> Dict[str, Any]:
        """处理报告生成请求"""
        if isinstance(input_data, dict):
            test_results = input_data.get("test_results", {})
            test_cases = input_data.get("test_cases", "")
            code = input_data.get("code", "")
            format_type = input_data.get("format", "markdown")
        else:
            test_results = {}
            test_cases = ""
            code = ""
            format_type = "markdown"
        
        logger.info(f"[ReportGenerator] 开始生成 {format_type} 报告")
        
        self.status = AgentStatus.RUNNING
        self.thought_history = []
        
        try:
            # 1. 准备报告数据
            prep_step = ThoughtStep(
                step_number=1,
                thought="整理测试数据，准备报告生成",
                action="prepare_data",
                action_input={"test_results": test_results},
                action_type=ActionType.THINK,
            )
            
            report_data = {
                "summary": _prepare_summary(test_results),
                "test_results": test_results,
                "test_cases": test_cases,
                "code": code,
                "generated_at": datetime.now().isoformat(),
            }
            prep_step.result = report_data
            self.thought_history.append(prep_step)
            
            # 2. 计算覆盖率
            coverage_step = ThoughtStep(
                step_number=2,
                thought="计算测试覆盖率",
                action="calculate_coverage",
                action_input={"code": code, "tests": test_cases},
                action_type=ActionType.TOOL_CALL,
            )
            
            try:
                if code and test_cases:
                    coverage_result = await self.tools["calculate_coverage"](
                        {"code": code, "tests": test_cases}
                    )
                    if coverage_result.get("success"):
                        report_data["coverage"] = coverage_result.get("result")
                        coverage_step.observation = f"覆盖率: {coverage_result.get('result', {}).get('estimated_coverage', 'N/A')}"
                        coverage_step.result = coverage_result
            except Exception as e:
                coverage_step.observation = f"覆盖率计算失败: {e}"
            
            self.thought_history.append(coverage_step)
            
            # 3. 生成报告
            report_step = ThoughtStep(
                step_number=3,
                thought=f"生成 {format_type.upper()} 格式报告",
                action=f"generate_{format_type}_report",
                action_input={"data": report_data},
                action_type=ActionType.TOOL_CALL,
            )
            
            tool_name = f"generate_{format_type}_report"
            if tool_name in self.tools:
                try:
                    report_result = await self.tools[tool_name](report_data)
                    if report_result.get("success"):
                        report_content = report_result.get("report")
                        report_step.observation = f"报告生成成功，长度: {len(report_content)} 字符"
                        report_step.result = {"report": report_content}
                    else:
                        report_step.error = report_result.get("error")
                except Exception as e:
                    report_step.error = str(e)
            else:
                report_step.error = f"不支持的报告格式: {format_type}"
            
            self.thought_history.append(report_step)
            
            # 4. 保存报告
            save_step = ThoughtStep(
                step_number=4,
                thought="保存报告文件",
                action="save_report",
                action_input={
                    "content": report_content,
                    "file_path": f"./reports/test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
                },
                action_type=ActionType.TOOL_CALL,
            )
            
            try:
                save_result = await self.tools["save_report"](
                    content=report_content,
                    file_path=f"./reports/test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
                )
                if save_result.get("success"):
                    save_step.observation = f"报告已保存: {save_result.get('result', {}).get('file_path', 'unknown')}"
                else:
                    save_step.observation = "报告保存失败，但内容已生成"
            except Exception as e:
                save_step.observation = f"保存失败: {e}"
            
            self.thought_history.append(save_step)
            
            # 返回结果
            self.status = AgentStatus.COMPLETED
            
            return {
                "success": True,
                "result": {
                    "report": report_content,
                    "format": format_type,
                    "summary": report_data["summary"],
                    "coverage": report_data.get("coverage", {}),
                },
                "steps": [s.to_dict() for s in self.thought_history],
            }
            
        except Exception as e:
            logger.error(f"[ReportGenerator] 处理失败: {e}")
            self.status = AgentStatus.FAILED
            return {
                "success": False,
                "error": str(e),
                "steps": [s.to_dict() for s in self.thought_history],
            }
    
    async def plan(self, task: str) -> List[str]:
        """制定报告生成计划"""
        return [
            "整理测试数据",
            "计算覆盖率",
            "生成报告内容",
            "保存报告文件",
        ]


def _prepare_summary(test_results: Dict) -> Dict:
    """准备报告摘要"""
    if not test_results:
        return {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "pass_rate": "0%",
        }
    
    passed = test_results.get("passed", 0)
    failed = test_results.get("failed", 0)
    total = passed + failed
    
    return {
        "total_tests": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": f"{(passed / total * 100) if total > 0 else 0:.1f}%",
    }


def _generate_markdown(data: Dict) -> str:
    """生成 Markdown 报告"""
    summary = data.get("summary", {})
    test_results = data.get("test_results", {})
    coverage = data.get("coverage", {})
    generated_at = data.get("generated_at", datetime.now().isoformat())
    
    md = f"""# 测试报告

## 基本信息

- **生成时间**: {generated_at}
- **测试状态**: {"通过" if summary.get("failed", 1) == 0 else "存在失败"}

## 测试摘要

| 指标 | 数值 |
|------|------|
| 总测试数 | {summary.get("total_tests", 0)} |
| 通过 | {summary.get("passed", 0)} |
| 失败 | {summary.get("failed", 0)} |
| 通过率 | {summary.get("pass_rate", "0%")} |

"""
    
    if coverage:
        md += f"""## 覆盖率分析

- **估算覆盖率**: {coverage.get("estimated_coverage", "N/A")}
- **代码行数**: {coverage.get("code_lines", 0)}
- **测试行数**: {coverage.get("test_lines", 0)}
- **建议**: 
"""
        for rec in coverage.get("recommendations", []):
            md += f"  - {rec}\n"
    
    if test_results.get("errors"):
        md += f"""
## 错误详情

"""
        for error in test_results.get("errors", [])[:10]:
            md += f"""### 错误 {error.get("line_number", "?")}: {error.get("type", "error")}

```
{error.get("content", "")}
```

"""
    
    md += """
## 建议

"""
    if summary.get("failed", 0) > 0:
        md += """1. 检查失败的测试用例
2. 分析错误日志
3. 根据建议修复代码
4. 重新执行测试验证
"""
    else:
        md += """1. 测试全部通过，保持代码质量
2. 建议增加边界值测试
3. 定期运行回归测试
"""
    
    return md


def _generate_html(data: Dict) -> str:
    """生成 HTML 报告"""
    summary = data.get("summary", {})
    coverage = data.get("coverage", {})
    generated_at = data.get("generated_at", datetime.now().isoformat())
    
    pass_rate = float(summary.get("pass_rate", "0%").replace("%", ""))
    pass_color = "green" if pass_rate >= 80 else "orange" if pass_rate >= 60 else "red"
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>测试报告</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat {{
            text-align: center;
            padding: 20px;
            border-radius: 8px;
            background: #f8f9fa;
        }}
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }}
        .stat-label {{
            color: #666;
            margin-top: 5px;
        }}
        .pass-rate {{
            color: {pass_color};
        }}
        .chart {{
            height: 20px;
            background: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
            margin: 20px 0;
        }}
        .chart-fill {{
            height: 100%;
            background: linear-gradient(90deg, #28a745, #28b94a);
            border-radius: 10px;
            width: {pass_rate}%;
            transition: width 0.5s ease;
        }}
        .error-list {{
            list-style: none;
            padding: 0;
        }}
        .error-item {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 4px;
        }}
        .code {{
            background: #f4f4f4;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>测试报告</h1>
        <p>生成时间: {generated_at}</p>
    </div>
    
    <div class="stats">
        <div class="stat">
            <div class="stat-value">{summary.get("total_tests", 0)}</div>
            <div class="stat-label">总测试数</div>
        </div>
        <div class="stat">
            <div class="stat-value" style="color: #28a745">{summary.get("passed", 0)}</div>
            <div class="stat-label">通过</div>
        </div>
        <div class="stat">
            <div class="stat-value" style="color: #dc3545">{summary.get("failed", 0)}</div>
            <div class="stat-label">失败</div>
        </div>
        <div class="stat">
            <div class="stat-value pass-rate">{summary.get("pass_rate", "0%")}</div>
            <div class="stat-label">通过率</div>
        </div>
    </div>
    
    <div class="chart">
        <div class="chart-fill"></div>
    </div>
"""
    
    if coverage:
        html += f"""
    <div class="card">
        <h2>覆盖率分析</h2>
        <p><strong>估算覆盖率:</strong> {coverage.get("estimated_coverage", "N/A")}</p>
        <p><strong>代码行数:</strong> {coverage.get("code_lines", 0)}</p>
        <p><strong>测试行数:</strong> {coverage.get("test_lines", 0)}</p>
        <h3>建议</h3>
        <ul>
"""
        for rec in coverage.get("recommendations", []):
            html += f"            <li>{rec}</li>\n"
        html += "        </ul>\n    </div>\n"
    
    html += """
    <div class="card">
        <h2>Agent 执行流程</h2>
        <p>此报告由多 Agent 系统自动生成，包括:</p>
        <ul>
            <li>测试用例生成 Agent</li>
            <li>测试执行 Agent</li>
            <li>缺陷分析 Agent</li>
            <li>报告生成 Agent</li>
        </ul>
    </div>
</body>
</html>
"""
    
    return html


def create_report_generator_agent(llm=None) -> ReportGeneratorAgent:
    """创建报告生成 Agent"""
    config = AgentConfig(
        name="ReportGenerator",
        agent_type=AgentType.REPORT_GENERATOR,
        description="专业的测试报告生成专家",
        max_steps=5,
        timeout=60,
        tools=["generate_markdown_report", "generate_html_report", "calculate_coverage", "save_report"],
        retry_on_failure=False,
        max_retries=1,
    )
    
    return ReportGeneratorAgent(config, llm)
