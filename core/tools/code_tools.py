"""代码相关工具"""
import subprocess
import time
import tempfile
import os
import json
import re
from typing import Any, Dict, List, Optional
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
            
            passed_count = _parse_passed_count(result.stdout)
            failed_count = _parse_failed_count(result.stdout)
            passed_tests = _parse_test_names(result.stdout, passed=True)
            failed_tests = _parse_test_names(result.stdout, passed=False)
            
            return ToolResult(
                success=result.returncode == 0,
                result={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.returncode,
                    "passed": passed_count,
                    "failed": failed_count,
                    "passed_tests": passed_tests,
                    "failed_tests": failed_tests,
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


def _parse_test_names(output: str, passed: bool = True) -> List[str]:
    """解析通过的测试名称列表"""
    test_names = []
    # pytest -v 输出格式: test_file.py::test_name[params] PASSED
    # 支持参数化测试: test_divide_normal[6-3-2.0] PASSED
    status = "PASSED" if passed else "FAILED"
    
    for line in output.split('\n'):
        line = line.strip()
        if status in line:
            # 提取测试名称，支持参数化测试格式: test_xxx 或 test_xxx[params]
            match = re.search(r'::((?:test_\w+)(?:\[[^\]]+\])?)\s+' + status, line)
            if match:
                test_names.append(match.group(1))
    
    return test_names


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


def fix_floating_point_assertions(tests_code: str) -> str:
    """
    修复测试代码中的浮点数断言问题
    
    将不健壮的浮点数断言转换为使用 math.isclose() 的健壮断言：
    1. 将 `assert x == float_value` 转换为 `assert math.isclose(x, float_value)`
    2. 将 `assert x == float('nan')` 转换为 `assert math.isnan(x)`
    3. 将 `assert x == float('inf')` 转换为 `assert math.isinf(x)`
    
    Args:
        tests_code: 测试代码字符串
        
    Returns:
        修复后的测试代码
    """
    import math
    
    # 确保导入 math 模块
    if 'import math' not in tests_code and 'from math import' not in tests_code:
        # 在第一个 import 语句后添加，或在文件开头添加
        if 'import pytest' in tests_code:
            tests_code = tests_code.replace('import pytest', 'import math\nimport pytest', 1)
        elif 'import unittest' in tests_code:
            tests_code = tests_code.replace('import unittest', 'import math\nimport unittest', 1)
        else:
            tests_code = 'import math\n\n' + tests_code
    
    # 使用简单的字符串查找和替换方法处理特殊浮点值
    lines = tests_code.split('\n')
    result_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # 跳过已经使用 math 函数检查的行
        if 'math.isnan' in stripped or 'math.isinf' in stripped or 'math.isclose' in stripped:
            result_lines.append(line)
            continue
        
        # 处理 NaN 断言: assert ... == float('nan') 或 float("nan")
        if "== float('nan')" in stripped or '== float("nan")' in stripped:
            # 提取等号左边的表达式
            if '==' in stripped:
                parts = stripped.split('==')
                left_expr = parts[0].replace('assert', '').strip()
                line = f'    assert math.isnan({left_expr})'
        
        # 处理 Infinity 断言: assert ... == float('inf') 或 float("inf")
        elif "== float('inf')" in stripped or '== float("inf")' in stripped:
            if '==' in stripped:
                parts = stripped.split('==')
                left_expr = parts[0].replace('assert', '').strip()
                line = f'    assert math.isinf({left_expr})'
        
        # 处理浮点数精确比较: assert expr == number_with_decimal_or_scientific
        elif '==' in stripped and stripped.startswith('assert'):
            try:
                # 提取等号两边的部分
                parts = stripped.split('==')
                if len(parts) == 2:
                    left_expr = parts[0].replace('assert', '').strip()
                    right_value = parts[1].strip()
                    
                    # 检查右边是否是数值（包含小数点或科学计数法）
                    if re.match(r'^-?\d+\.\d+([eE][+-]?\d+)?$', right_value) or \
                       re.match(r'^-?\d+[eE][+-]?\d+$', right_value):
                        line = f'    assert math.isclose({left_expr}, {right_value}, rel_tol=1e-9, abs_tol=1e-12)'
            except:
                pass
        
        result_lines.append(line)
    
    return '\n'.join(result_lines)
