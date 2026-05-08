"""报告生成 Agent"""
from typing import Any, Dict, List, Optional
from pydantic import Field
from datetime import datetime
import json
import re
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
    
    # 确保 passed 和 failed 是数字类型
    passed_raw = test_results.get("passed", 0)
    failed_raw = test_results.get("failed", 0)
    
    # 处理传入的是列表（passed_tests）而非数字的情况
    if isinstance(passed_raw, list):
        passed = len(passed_raw)
    elif isinstance(passed_raw, (int, float)):
        passed = int(passed_raw)
    else:
        passed = 0
    
    if isinstance(failed_raw, list):
        failed = len(failed_raw)
    elif isinstance(failed_raw, (int, float)):
        failed = int(failed_raw)
    else:
        failed = 0
    
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


def _extract_test_cases(test_code: str) -> List[Dict]:
    """从测试代码中提取测试用例列表"""
    import re
    
    test_cases = []
    
    # 先找出所有参数化测试及其参数数量
    parametrize_tests = {}  # {test_name: param_count}
    
    # 匹配参数化装饰器（支持多种格式）
    # 格式: @pytest.mark.parametrize("a, b", [...]) 或 @pytest.mark.parametrize("a, b", [\n...])
    param_pattern = r'@pytest\.mark\.parametrize\("([^"]+)"\)[\s]*,\s*\[([\s\S]*?)\n\s*\]'
    for match in re.finditer(param_pattern, test_code):
        param_names = match.group(1)
        params_content = match.group(2)
        # 找到这个装饰器后面的函数定义
        decorator_end = match.end()
        next_func = re.search(r'def\s+(test_\w+)\s*\(', test_code[decorator_end:])
        if next_func:
            test_name = next_func.group(1)
            # 计算参数组数量（通过元组数量）
            param_count = params_content.count('(')
            if param_count == 0:
                # 检查是否有逗号分隔的简单列表
                items = [p.strip() for p in params_content.split(',') if p.strip()]
                param_count = len(items)
            parametrize_tests[test_name] = param_count
    
    # 匹配所有测试函数
    func_pattern = r'def (test_\w+)\(([^)]*)\):'
    matches = list(re.finditer(func_pattern, test_code))
    
    for i, match in enumerate(matches):
        name = match.group(1)
        # 找到这个函数的结束位置（下一个函数或类开始之前）
        if i + 1 < len(matches):
            func_end = matches[i + 1].start()
        else:
            func_end = len(test_code)
        
        # 提取函数体（从函数定义到下一个函数之前）
        func_start = match.start()
        body = test_code[func_start:func_end]
        
        # 提取 docstring 描述
        docstring_match = re.search(r'"""(.+?)"""', body, re.DOTALL)
        docstring = docstring_match.group(1).strip() if docstring_match else ""
        
        # 识别测试类型
        test_type = _identify_test_type(name, body, docstring)
        
        # 判断是否为参数化测试
        is_parametrized = name in parametrize_tests
        param_count = parametrize_tests.get(name, 1)
        
        # 为参数化测试的每个参数生成单独的条目
        if is_parametrized and param_count > 1:
            for idx in range(param_count):
                display_name = f"{name}[{idx}]"
                test_cases.append({
                    "name": name,
                    "display_name": display_name,
                    "docstring": docstring,
                    "test_type": test_type,
                    "is_parametrized": is_parametrized,
                    "param_index": idx,
                    "body": body.strip()[:200] + "..." if len(body.strip()) > 200 else body.strip()
                })
        else:
            # 非参数化测试只生成一个条目
            test_cases.append({
                "name": name,
                "display_name": name,
                "docstring": docstring,
                "test_type": test_type,
                "is_parametrized": False,
                "param_index": None,
                "body": body.strip()[:200] + "..." if len(body.strip()) > 200 else body.strip()
            })
    
    return test_cases


def _identify_test_type(name: str, body: str, docstring: str) -> str:
    """识别测试类型
    
    优先级：
    1. 从 docstring 中提取 [测试类型: xxx] 标记（最准确，由 AI 生成时直接标注）
    2. 使用启发式规则推断
    """
    
    # 1. 优先从 docstring 中提取 AI 标注的类型
    if docstring:
        type_match = re.search(r'\[测试类型:\s*([^\]]+)\]', docstring)
        if type_match:
            return type_match.group(1).strip()
    
    combined = (name + " " + body + " " + docstring).lower()
    
    # 2. 启发式规则推断
    # 异常测试
    if 'pytest.raises' in body or 'assert_raises' in body:
        return "异常测试"
    
    # 参数化测试
    if '@pytest.mark.parametrize' in body:
        return "参数化测试"
    
    # 精度测试
    if any(kw in combined for kw in ['precision', 'accuracy', 'decimal', 'float', 'round']):
        return "精度测试"
    
    # 边界值测试
    boundary_keywords = ['zero', 'boundary', 'edge', 'min', 'max', 'large', 'small', 
                        'empty', 'one', 'negative_one', 'very_small', 'very_large',
                        'limit', 'overflow', 'underflow', 'extreme']
    if any(kw in combined for kw in boundary_keywords):
        return "边界测试"
    
    # 类型测试
    if 'type' in combined or 'isinstance' in body:
        return "类型测试"
    
    # 正常情况测试
    return "正常测试"


# 测试类型对应的颜色
TEST_TYPE_COLORS = {
    "正常测试": "#667eea",      # 蓝色
    "边界测试": "#f59e0b",      # 橙色
    "异常测试": "#dc3545",      # 红色
    "精度测试": "#10b981",      # 绿色
    "类型测试": "#8b5cf6",      # 紫色
    "参数化测试": "#06b6d4",    # 青色
}


def _generate_html(data: Dict) -> str:
    """生成增强版 HTML 报告"""
    summary = data.get("summary", {})
    test_results = data.get("test_results", {})
    test_cases = data.get("test_cases", "")
    code = data.get("code", "")
    coverage = data.get("coverage", {})
    generated_at = data.get("generated_at", datetime.now().isoformat())
    
    # 解析测试用例结果（直接从 pytest 输出）
    passed_tests = test_results.get("passed_tests", [])
    failed_tests = test_results.get("failed_tests", [])
    
    # 计算通过率 - 确保 passed 和 failed 是数字
    passed_raw = summary.get("passed", 0)
    failed_raw = summary.get("failed", 0)
    
    if isinstance(passed_raw, list):
        passed = len(passed_raw)
    elif isinstance(passed_raw, (int, float)):
        passed = int(passed_raw)
    else:
        passed = len(passed_tests)
    
    if isinstance(failed_raw, list):
        failed = len(failed_raw)
    elif isinstance(failed_raw, (int, float)):
        failed = int(failed_raw)
    else:
        failed = len(failed_tests)
    
    total = passed + failed
    pass_rate = (passed / total * 100) if total > 0 else 0
    pass_color = "green" if pass_rate >= 80 else "orange" if pass_rate >= 60 else "red"
    
    # 测试用例总数
    total_test_cases = len(passed_tests) + len(failed_tests)
    
    # 代码高亮函数
    def escape_html(text):
        return (text.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace('"', "&quot;"))
    
    # 生成测试用例表格行 - 直接使用 pytest 输出的测试名称
    test_rows = ""
    type_color_map = {
        "正常测试": "#667eea",
        "边界测试": "#f59e0b",
        "异常测试": "#dc3545",
        "精度测试": "#10b981",
        "类型测试": "#8b5cf6",
        "参数化测试": "#06b6d4",
    }
    
    # 合并所有测试用例（通过+失败），按名称排序
    all_tests = [(name, True) for name in passed_tests] + [(name, False) for name in failed_tests]
    all_tests.sort(key=lambda x: x[0])
    
    for test_name, is_passed in all_tests:
        is_failed = not is_passed
        status = "通过" if is_passed else "失败"
        status_class = "passed" if is_passed else "failed"
        status_icon = "✓" if is_passed else "✗"
        
        # 推断测试类型
        test_type = _identify_test_type(test_name, "", "")
        type_color = type_color_map.get(test_type, "#667eea")
        
        test_rows += f"""
        <tr class="{status_class}">
            <td><span class="icon">{status_icon}</span></td>
            <td><code>{escape_html(test_name)}</code></td>
            <td><span class="badge {status_class}">{status}</span></td>
            <td><span class="type-tag" style="background: {type_color}20; color: {type_color}; border: 1px solid {type_color};">{test_type}</span></td>
            <td>-</td>
        </tr>"""
    
    if not test_rows:
        # 如果没有结果数据，使用测试代码解析
        test_case_list = _extract_test_cases(test_cases) if test_cases else []
        for tc in test_case_list[:10]:
            display_name = tc.get("display_name", tc["name"])
            test_type = tc.get("test_type", "正常测试")
            type_color = type_color_map.get(test_type, "#667eea")
            test_rows += f"""
        <tr class="pending">
            <td><span class="icon">○</span></td>
            <td><code>{escape_html(display_name)}</code></td>
            <td><span class="badge pending">未运行</span></td>
            <td><span class="type-tag" style="background: {type_color}20; color: {type_color}; border: 1px solid {type_color};">{test_type}</span></td>
            <td>-</td>
        </tr>"""
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智能测试报告</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
            min-height: 100vh;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 25px;
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
        }}
        .header h1 {{ margin: 0 0 10px 0; font-size: 2em; }}
        .header p {{ margin: 5px 0; opacity: 0.9; }}
        .card {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 25px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin-bottom: 25px;
        }}
        .stat {{
            text-align: center;
            padding: 25px 20px;
            border-radius: 12px;
            background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
            border: 1px solid #e9ecef;
            transition: transform 0.2s;
        }}
        .stat:hover {{ transform: translateY(-3px); box-shadow: 0 6px 20px rgba(0,0,0,0.1); }}
        .stat-value {{
            font-size: 2.5em;
            font-weight: bold;
            color: #333;
        }}
        .stat-label {{
            color: #666;
            margin-top: 8px;
            font-size: 0.95em;
        }}
        .stat.total .stat-value {{ color: #667eea; }}
        .stat.passed .stat-value {{ color: #28a745; }}
        .stat.failed .stat-value {{ color: #dc3545; }}
        .stat.rate .stat-value {{ color: {pass_color}; }}
        
        .chart-container {{
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        }}
        .chart {{
            height: 30px;
            background: #e9ecef;
            border-radius: 15px;
            overflow: hidden;
            display: flex;
        }}
        .chart-pass {{ background: linear-gradient(90deg, #28a745, #34ce57); height: 100%; }}
        .chart-fail {{ background: linear-gradient(90deg, #dc3545, #e74a3b); height: 100%; }}
        .chart-legend {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 15px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .legend-color {{
            width: 20px;
            height: 12px;
            border-radius: 3px;
        }}
        .legend-color.pass {{ background: #28a745; }}
        .legend-color.fail {{ background: #dc3545; }}
        
        h2 {{
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        
        /* 测试用例表格 */
        .test-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        .test-table th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 12px;
            text-align: left;
            font-weight: 500;
        }}
        .test-table th:first-child {{ border-radius: 8px 0 0 0; }}
        .test-table th:last-child {{ border-radius: 0 8px 0 0; }}
        .test-table td {{
            padding: 12px;
            border-bottom: 1px solid #e9ecef;
        }}
        .test-table tr:hover {{ background: #f8f9fa; }}
        .test-table tr.passed {{ background: #d4edda; }}
        .test-table tr.failed {{ background: #f8d7da; }}
        .test-table tr.pending {{ background: #fff3cd; }}
        
        .icon {{ font-size: 1.2em; font-weight: bold; }}
        tr.passed .icon {{ color: #28a745; }}
        tr.failed .icon {{ color: #dc3545; }}
        tr.pending .icon {{ color: #ffc107; }}
        
        .badge {{
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
        }}
        .badge.passed {{ background: #d4edda; color: #155724; }}
        .badge.failed {{ background: #f8d7da; color: #721c24; }}
        .badge.pending {{ background: #fff3cd; color: #856404; }}
        
        /* 类型标签 */
        .type-tag {{
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 500;
            display: inline-block;
        }}
        
        /* 测试类型图例 */
        .type-legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 15px;
        }}
        .type-legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 0.85em;
            color: #666;
        }}
        .type-legend-color {{
            width: 12px;
            height: 12px;
            border-radius: 3px;
        }}
        
        /* 代码块 */
        .code-block {{
            background: #1e1e1e;
            border-radius: 10px;
            padding: 20px;
            margin: 15px 0;
            overflow-x: auto;
        }}
        .code-block pre {{
            margin: 0;
            color: #d4d4d4;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 0.9em;
            line-height: 1.6;
        }}
        .code-title {{
            color: #888;
            font-size: 0.85em;
            margin-bottom: 10px;
        }}
        
        /* 覆盖率 */
        .coverage-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        .coverage-item {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .coverage-value {{
            font-size: 1.8em;
            font-weight: bold;
            color: #667eea;
        }}
        .coverage-label {{
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        
        /* 错误详情 */
        .error-item {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px 20px;
            margin-bottom: 15px;
            border-radius: 0 8px 8px 0;
        }}
        .error-item h4 {{ margin: 0 0 10px 0; color: #856404; }}
        .error-item pre {{
            background: #fff;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0 0 0;
            font-size: 0.85em;
            overflow-x: auto;
        }}
        
        /* Agent 流程 */
        .agent-flow {{
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 15px;
            margin: 20px 0;
        }}
        .agent-step {{
            background: linear-gradient(135deg, #667eea20, #764ba220);
            padding: 15px 25px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid #667eea30;
        }}
        .agent-step .num {{
            background: #667eea;
            color: white;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .agent-step .name {{ font-weight: 500; color: #333; }}
        
        /* 代码和测试对比 */
        .code-test-container {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        @media (max-width: 900px) {{
            .code-test-container {{ grid-template-columns: 1fr; }}
        }}
        
        .test-summary {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 10px;
        }}
        .test-summary span {{
            background: #e9ecef;
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 0.85em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>智能测试报告</h1>
        <p>生成时间: {generated_at}</p>
        <p>基于 DeepSeek LLM + 多 Agent 协作系统</p>
    </div>
    
    <div class="stats">
        <div class="stat total">
            <div class="stat-value">{total}</div>
            <div class="stat-label">总测试数</div>
        </div>
        <div class="stat passed">
            <div class="stat-value">{passed}</div>
            <div class="stat-label">通过</div>
        </div>
        <div class="stat failed">
            <div class="stat-value">{failed}</div>
            <div class="stat-label">失败</div>
        </div>
        <div class="stat rate">
            <div class="stat-value">{pass_rate:.1f}%</div>
            <div class="stat-label">通过率</div>
        </div>
    </div>
    
    <div class="card">
        <h2>测试进度</h2>
        <div class="chart-container">
            <div class="chart">
                <div class="chart-pass" style="width: {pass_rate}%;"></div>
                <div class="chart-fail" style="width: {100-pass_rate}%;"></div>
            </div>
            <div class="chart-legend">
                <div class="legend-item">
                    <div class="legend-color pass"></div>
                    <span>通过 ({passed})</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color fail"></div>
                    <span>失败 ({failed})</span>
                </div>
            </div>
        </div>
    </div>
    
    <!-- 代码与测试对比 -->
    <div class="card">
        <h2>代码与测试用例</h2>
        <div class="code-test-container">
            <div>
                <div class="code-title">原始代码</div>
                <div class="code-block">
                    <pre>{escape_html(code) if code else "# 无源代码"}</pre>
                </div>
            </div>
            <div>
                <div class="code-title">测试代码 (共 {total_test_cases} 个用例)</div>
                <div class="code-block" style="max-height: 300px; overflow-y: auto;">
                    <pre>{escape_html(test_cases[:2000] + "..." if len(test_cases) > 2000 else test_cases) if test_cases else "# 无测试代码"}</pre>
                </div>
            </div>
        </div>
    </div>
    
    <!-- 测试用例列表 -->
    <div class="card">
        <h2>测试用例详情</h2>
        <p style="color: #666; margin-bottom: 15px;">
            共 {total_test_cases} 个测试用例
            <span style="color: #28a745;">{passed or 0} 通过</span> / 
            <span style="color: #dc3545;">{failed or 0} 失败</span>
        </p>
        <div class="type-legend">
            <div class="type-legend-item"><div class="type-legend-color" style="background: #667eea;"></div> 正常测试</div>
            <div class="type-legend-item"><div class="type-legend-color" style="background: #f59e0b;"></div> 边界测试</div>
            <div class="type-legend-item"><div class="type-legend-color" style="background: #dc3545;"></div> 异常测试</div>
            <div class="type-legend-item"><div class="type-legend-color" style="background: #10b981;"></div> 精度测试</div>
            <div class="type-legend-item"><div class="type-legend-color" style="background: #8b5cf6;"></div> 类型测试</div>
            <div class="type-legend-item"><div class="type-legend-color" style="background: #06b6d4;"></div> 参数化测试</div>
        </div>
        <table class="test-table" style="margin-top: 15px;">
            <thead>
                <tr>
                    <th style="width: 60px;">状态</th>
                    <th>用例名称</th>
                    <th style="width: 100px;">结果</th>
                    <th style="width: 110px;">类型</th>
                    <th>描述</th>
                </tr>
            </thead>
            <tbody>
                {test_rows if test_rows else '<tr><td colspan="5" style="text-align: center; color: #666;">运行测试后查看详情</td></tr>'}
            </tbody>
        </table>
    </div>
"""
    
    # 错误详情
    errors = test_results.get("errors", [])
    if errors:
        html += """
    <div class="card">
        <h2>错误详情</h2>
"""
        for error in errors[:5]:
            html += f"""
        <div class="error-item">
            <h4>{error.get("name", "错误")}: {error.get("message", "未知错误")}</h4>
            <pre>{escape_html(error.get("traceback", ""))}</pre>
        </div>
"""
        html += "    </div>\n"
    
    # 覆盖率
    if coverage:
        html += f"""
    <div class="card">
        <h2>覆盖率分析</h2>
        <div class="coverage-grid">
            <div class="coverage-item">
                <div class="coverage-value">{coverage.get("estimated_coverage", "N/A")}</div>
                <div class="coverage-label">估算覆盖率</div>
            </div>
            <div class="coverage-item">
                <div class="coverage-value">{coverage.get("code_lines", 0)}</div>
                <div class="coverage-label">代码行数</div>
            </div>
            <div class="coverage-item">
                <div class="coverage-value">{coverage.get("test_lines", 0)}</div>
                <div class="coverage-label">测试行数</div>
            </div>
        </div>
"""
        recommendations = coverage.get("recommendations", [])
        if recommendations:
            html += """
        <h3 style="margin-top: 20px;">改进建议</h3>
        <ul>
"""
            for rec in recommendations:
                html += f"            <li>{rec}</li>\n"
            html += "        </ul>\n"
        html += "    </div>\n"
    
    # Agent 流程
    html += """
    <div class="card">
        <h2>执行流程</h2>
        <div class="agent-flow">
            <div class="agent-step">
                <div class="num">1</div>
                <div class="name">TestGenerator</div>
                <div style="color: #666; font-size: 0.85em;">生成测试用例</div>
            </div>
            <div class="agent-step">
                <div class="num">2</div>
                <div class="name">TestExecutor</div>
                <div style="color: #666; font-size: 0.85em;">执行测试</div>
            </div>
            <div class="agent-step">
                <div class="num">3</div>
                <div class="name">DefectAnalyzer</div>
                <div style="color: #666; font-size: 0.85em;">分析缺陷</div>
            </div>
            <div class="agent-step">
                <div class="num">4</div>
                <div class="name">ReportGenerator</div>
                <div style="color: #666; font-size: 0.85em;">生成报告</div>
            </div>
        </div>
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
