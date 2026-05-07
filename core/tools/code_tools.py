"""代码相关工具"""
import subprocess
import time
import tempfile
import os
import json
import re
from typing import Any, Dict, Optional
from loguru import logger

from .base import ToolResult


async def generate_tests_tool(
    code: str,
    language: str = "python",
    framework: str = "pytest",
    test_cases: int = 5,
) -> ToolResult:
    """
    生成测试用例工具
    
    Args:
        code: 源代码或函数定义
        language: 编程语言
        framework: 测试框架 (pytest/unittest)
        test_cases: 生成的测试用例数量
    """
    start_time = time.time()
    
    try:
        # 简单解析函数签名
        if language == "python":
            tests = _generate_python_tests(code, framework, test_cases)
        elif language == "javascript":
            tests = _generate_javascript_tests(code, framework, test_cases)
        else:
            return ToolResult(
                success=False,
                error=f"不支持的语言: {language}",
                execution_time=time.time() - start_time,
            )
        
        return ToolResult(
            success=True,
            result={
                "tests": tests,
                "framework": framework,
                "language": language,
                "test_count": len(tests.split("def test_")) - 1 if "def test_" in tests else 0,
            },
            execution_time=time.time() - start_time,
        )
        
    except Exception as e:
        logger.error(f"测试生成失败: {e}")
        return ToolResult(
            success=False,
            error=str(e),
            execution_time=time.time() - start_time,
        )


def _generate_python_tests(code: str, framework: str, count: int) -> str:
    """生成 Python 测试用例"""
    # 提取函数名
    func_match = re.search(r'def\s+(\w+)\s*\(', code)
    func_name = func_match.group(1) if func_match else "function"
    
    # 提取参数类型提示
    param_match = re.findall(r'(\w+):\s*(\w+)', code)
    params = {name: ptype for name, ptype in param_match}
    
    if framework == "pytest":
        tests = f'''"""自动生成的测试用例"""
import pytest


# 被测试函数: {func_name}
# 参数: {params}

class Test{func_name.title()}:
    """{func_name} 测试类"""
'''
        for i in range(count):
            case_type = ["正常情况", "边界值", "异常情况", "特殊值"][i % 4]
            if i == 0:
                tests += f'''
    def test_{func_name}_normal_{i+1}(self):
        """测试 {func_name} - {case_type}"""
        # TODO: 根据函数逻辑填充测试
        pass
'''
            elif i == 1:
                tests += f'''
    def test_{func_name}_boundary_{i+1}(self):
        """测试 {func_name} - 边界值测试"""
        # TODO: 边界值测试
        pass
'''
            elif i == 2:
                tests += f'''
    def test_{func_name}_exception_{i+1}(self):
        """测试 {func_name} - 异常情况"""
        with pytest.raises(Exception):
            # TODO: 触发异常的测试
            pass
'''
            else:
                tests += f'''
    def test_{func_name}_edge_{i+1}(self):
        """测试 {func_name} - 特殊值测试"""
        # TODO: 特殊值测试
        pass
'''
    else:  # unittest
        tests = f'''"""自动生成的测试用例"""
import unittest


class Test{func_name.title()}(unittest.TestCase):
    """{func_name} 测试类"""
'''
        for i in range(count):
            tests += f'''
    def test_{func_name}_{i+1}(self):
        """测试 {func_name} - 用例 {i+1}"""
        # TODO: 根据函数逻辑填充测试
        self.assertTrue(True)
'''
    
    tests += "\n\nif __name__ == '__main__':\n    unittest.main()\n"
    
    return tests


def _generate_javascript_tests(code: str, framework: str, count: int) -> str:
    """生成 JavaScript 测试用例"""
    func_match = re.search(r'function\s+(\w+)\s*\(', code)
    func_name = func_match.group(1) if func_match else "function"
    
    if framework == "jest":
        tests = f'''// 自动生成的测试用例

describe('{func_name}', () => {{
'''
        for i in range(count):
            tests += f'''
  test('测试 {func_name} - 用例 {i+1}', () => {{
    // TODO: 根据函数逻辑填充测试
    expect(true).toBe(true);
  }});
'''
        tests += "});\n"
    else:
        tests = f'''// 自动生成的测试用例

const assert = require('assert');

describe('{func_name}', () => {{
'''
        for i in range(count):
            tests += f'''
  it('测试 {func_name} - 用例 {i+1}', () => {{
    // TODO: 根据函数逻辑填充测试
  }});
'''
        tests += "});\n"
    
    return tests


async def execute_tests_tool(
    tests: str,
    language: str = "python",
    timeout: int = 60,
) -> ToolResult:
    """
    执行测试工具
    
    Args:
        tests: 测试代码
        language: 编程语言
        timeout: 超时时间(秒)
    """
    start_time = time.time()
    
    try:
        # 写入临时文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix=f'_test.{"py" if language == "python" else "js"}',
            delete=False
        ) as f:
            f.write(tests)
            temp_file = f.name
        
        try:
            if language == "python":
                result = subprocess.run(
                    ['pytest', '-v', '--tb=short', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            elif language == "javascript":
                result = subprocess.run(
                    ['npm', 'test', '--', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"不支持的语言: {language}",
                    execution_time=time.time() - start_time,
                )
            
            return ToolResult(
                success=result.returncode == 0,
                result={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.returncode,
                    "passed": _parse_passed_count(result.stdout),
                    "failed": _parse_failed_count(result.stdout),
                },
                execution_time=time.time() - start_time,
            )
            
        finally:
            os.unlink(temp_file)
            
    except subprocess.TimeoutExpired:
        return ToolResult(
            success=False,
            error=f"测试执行超时 ({timeout}s)",
            execution_time=time.time() - start_time,
        )
    except Exception as e:
        logger.error(f"测试执行失败: {e}")
        return ToolResult(
            success=False,
            error=str(e),
            execution_time=time.time() - start_time,
        )


def _parse_passed_count(output: str) -> int:
    """解析通过的测试数量"""
    match = re.search(r'(\d+) passed', output)
    return int(match.group(1)) if match else 0


def _parse_failed_count(output: str) -> int:
    """解析失败的测试数量"""
    match = re.search(r'(\d+) failed', output)
    return int(match.group(1)) if match else 0


async def analyze_logs_tool(
    logs: str,
    error_pattern: str = r'ERROR|FATAL|Exception',
) -> ToolResult:
    """
    日志分析工具
    
    Args:
        logs: 日志内容
        error_pattern: 错误匹配模式
    """
    start_time = time.time()
    
    try:
        errors = []
        warnings = []
        lines = logs.split('\n')
        
        for i, line in enumerate(lines):
            if re.search(error_pattern, line, re.IGNORECASE):
                errors.append({
                    "line_number": i + 1,
                    "content": line.strip(),
                    "type": "error",
                })
            elif 'WARNING' in line.upper():
                warnings.append({
                    "line_number": i + 1,
                    "content": line.strip(),
                    "type": "warning",
                })
        
        # 简单分析错误类型
        error_summary = {}
        for error in errors:
            error_type = _extract_error_type(error['content'])
            error_summary[error_type] = error_summary.get(error_type, 0) + 1
        
        # 生成根因分析
        root_cause = _analyze_root_cause(errors)
        
        return ToolResult(
            success=True,
            result={
                "total_errors": len(errors),
                "total_warnings": len(warnings),
                "errors": errors[:20],  # 限制返回数量
                "warnings": warnings[:20],
                "error_summary": error_summary,
                "root_cause_analysis": root_cause,
            },
            execution_time=time.time() - start_time,
        )
        
    except Exception as e:
        logger.error(f"日志分析失败: {e}")
        return ToolResult(
            success=False,
            error=str(e),
            execution_time=time.time() - start_time,
        )


def _extract_error_type(error_msg: str) -> str:
    """提取错误类型"""
    if 'KeyError' in error_msg:
        return 'KeyError - 键不存在'
    elif 'TypeError' in error_msg:
        return 'TypeError - 类型错误'
    elif 'ValueError' in error_msg:
        return 'ValueError - 值错误'
    elif 'ImportError' in error_msg or 'ModuleNotFoundError' in error_msg:
        return 'ImportError - 导入错误'
    elif 'Timeout' in error_msg:
        return 'Timeout - 超时'
    elif 'ConnectionError' in error_msg:
        return 'ConnectionError - 连接错误'
    elif 'PermissionError' in error_msg:
        return 'PermissionError - 权限错误'
    else:
        return 'Other - 其他错误'


def _analyze_root_cause(errors: list) -> Dict[str, Any]:
    """分析根因"""
    if not errors:
        return {"status": "no_errors", "message": "未发现明显错误"}
    
    error_types = [e.get('type', 'unknown') for e in errors]
    
    most_common = max(set(error_types), key=error_types.count)
    
    return {
        "primary_issue": most_common,
        "confidence": error_types.count(most_common) / len(error_types),
        "recommendations": _generate_recommendations(most_common),
    }


def _generate_recommendations(error_type: str) -> list:
    """生成修复建议"""
    recommendations = {
        "KeyError": [
            "检查字典访问前是否存在该键",
            "使用 dict.get() 方法提供默认值",
            "使用 dict.setdefault() 初始化键",
        ],
        "TypeError": [
            "检查变量类型是否匹配预期",
            "添加类型检查和转换",
            "确保操作符两边类型一致",
        ],
        "ValueError": [
            "验证输入值是否符合有效范围",
            "添加输入校验逻辑",
            "提供更详细的错误信息",
        ],
        "ImportError": [
            "检查依赖是否正确安装",
            "确认模块路径是否正确",
            "检查 Python 版本兼容性",
        ],
    }
    
    return recommendations.get(error_type, ["需要进一步分析具体错误"])


async def calculate_coverage_tool(
    code: str,
    tests: str,
) -> ToolResult:
    """
    计算测试覆盖率
    
    Args:
        code: 源代码
        tests: 测试代码
    """
    start_time = time.time()
    
    try:
        # 简单统计代码行数和测试覆盖的函数
        code_lines = len(code.split('\n'))
        test_lines = len(tests.split('\n'))
        
        # 提取函数定义
        func_pattern = r'def\s+(\w+)\s*\('
        code_funcs = re.findall(func_pattern, code)
        test_func_pattern = r'test_\w+|def\s+test_\w+'
        test_funcs = re.findall(test_func_pattern, tests)
        
        # 估算覆盖率
        estimated_coverage = min(100, len(test_funcs) * 10 + 20)
        
        return ToolResult(
            success=True,
            result={
                "code_lines": code_lines,
                "test_lines": test_lines,
                "functions_in_code": code_funcs,
                "test_functions": len(test_funcs),
                "estimated_coverage": f"{estimated_coverage}%",
                "recommendations": _generate_coverage_recommendations(estimated_coverage),
            },
            execution_time=time.time() - start_time,
        )
        
    except Exception as e:
        logger.error(f"覆盖率计算失败: {e}")
        return ToolResult(
            success=False,
            error=str(e),
            execution_time=time.time() - start_time,
        )


def _generate_coverage_recommendations(coverage: int) -> list:
    """生成覆盖率建议"""
    if coverage >= 80:
        return ["覆盖率良好", "建议关注边界条件测试"]
    elif coverage >= 60:
        return ["覆盖率一般", "建议增加异常情况测试", "增加边界值测试"]
    else:
        return ["覆盖率不足", "建议大幅增加测试用例", "优先覆盖核心函数"]
