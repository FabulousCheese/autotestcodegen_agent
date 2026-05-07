"""
Agent 测试助手 - 使用示例

这个文件展示了如何使用 Agent 测试助手系统。
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import (
    create_test_generator_agent,
    create_test_executor_agent,
    create_defect_analyzer_agent,
    create_report_generator_agent,
)
from core.agent.scheduler import AgentScheduler
from core.memory.rag import SimpleMemory


async def demo_basic():
    """基础使用示例"""
    print("=" * 60)
    print("基础使用示例")
    print("=" * 60)
    
    # 创建 Agent
    generator = create_test_generator_agent(llm=None, rag_memory=SimpleMemory())
    executor = create_test_executor_agent(llm=None)
    analyzer = create_defect_analyzer_agent(llm=None, rag_memory=SimpleMemory())
    reporter = create_report_generator_agent(llm=None)
    
    # 示例代码
    sample_code = '''
def calculate_fibonacci(n: int) -> int:
    """计算斐波那契数列"""
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        return calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2)


def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
'''
    
    # 1. 生成测试用例
    print("\n[1] 生成测试用例...")
    result = await generator.process({
        "code": sample_code,
        "language": "python",
        "framework": "pytest",
        "test_cases": 4,
    })
    
    if result["success"]:
        tests = result["result"]["tests"]
        print(f"✓ 生成成功，共 {result['result']['test_count']} 个测试用例")
        print("\n生成的测试代码预览:")
        print(tests[:500] + "..." if len(tests) > 500 else tests)
    else:
        print(f"✗ 生成失败: {result.get('error')}")
        return
    
    # 显示思考过程
    print("\n思考过程:")
    for step in result["steps"]:
        print(f"  步骤 {step['step_number']}: {step['thought'][:50]}...")
    
    # 2. 执行测试
    print("\n[2] 执行测试...")
    exec_result = await executor.process({
        "tests": tests,
        "language": "python",
        "timeout": 30,
    })
    
    if exec_result["success"]:
        print("✓ 测试执行成功")
    else:
        print(f"✗ 测试执行失败: {exec_result.get('error')}")
        stderr = exec_result["result"].get("stderr", "") if exec_result.get("result") else ""
        if stderr:
            print(f"\n错误输出:\n{stderr[:500]}")
    
    # 3. 分析缺陷
    print("\n[3] 分析缺陷...")
    logs = """
2024-01-01 10:00:00 ERROR KeyError: 'invalid_key' in calculate_fibonacci
2024-01-01 10:00:01 WARNING TypeError: unsupported operand type(s) for +: 'NoneType' and 'int'
2024-01-01 10:00:02 ERROR ValueError: invalid literal for int() with base 10: 'abc'
"""
    analysis = await analyzer.process({"logs": logs})
    
    if analysis["success"]:
        print("✓ 缺陷分析完成")
        data = analysis["result"]
        print(f"  发现 {data['error_summary']} 个错误类型")
        print(f"  主要问题: {data['root_cause']['primary_issue']}")
        print("  修复建议:")
        for i, suggestion in enumerate(data["fix_suggestions"], 1):
            print(f"    {i}. {suggestion}")
    else:
        print(f"✗ 分析失败: {analysis.get('error')}")
    
    # 4. 生成报告
    print("\n[4] 生成报告...")
    report_result = await reporter.process({
        "test_results": exec_result.get("result", {}),
        "test_cases": tests,
        "code": sample_code,
        "format": "markdown",
    })
    
    if report_result["success"]:
        print("✓ 报告生成成功")
        print("\n报告预览:")
        print(report_result["result"]["report"][:500] + "...")
    else:
        print(f"✗ 报告生成失败: {report_result.get('error')}")


async def demo_workflow():
    """工作流示例"""
    print("\n" + "=" * 60)
    print("工作流示例")
    print("=" * 60)
    
    # 创建调度器
    scheduler = AgentScheduler()
    
    # 注册 Agent
    scheduler.register_agent(create_test_generator_agent(llm=None, rag_memory=SimpleMemory()))
    scheduler.register_agent(create_test_executor_agent(llm=None))
    scheduler.register_agent(create_report_generator_agent(llm=None))
    
    # 创建工作流
    workflow = scheduler.create_workflow(
        name="自动化测试工作流",
        description="完整的测试生成-执行-报告流程"
    )
    
    # 添加步骤
    from core.agent.base_agent import AgentType
    
    sample_code = '''
def add(a: int, b: int) -> int:
    return a + b

def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Division by zero")
    return a / b
'''
    
    scheduler.add_workflow_step(
        workflow.workflow_id,
        "TestGenerator",
        AgentType.TEST_GENERATOR,
        {"code": sample_code, "test_cases": 3}
    )
    
    scheduler.add_workflow_step(
        workflow.workflow_id,
        "TestExecutor",
        AgentType.TEST_EXECUTOR,
        "$step_0_result"  # 引用前一步结果
    )
    
    scheduler.add_workflow_step(
        workflow.workflow_id,
        "ReportGenerator",
        AgentType.REPORT_GENERATOR,
        "$step_1_result"
    )
    
    print(f"创建工作流: {workflow.workflow_id}")
    print(f"步骤数量: {len(workflow.steps)}")
    
    # 执行工作流
    print("\n开始执行工作流...")
    result = await scheduler.execute_workflow(workflow.workflow_id)
    
    if result["success"]:
        print("✓ 工作流执行成功")
        print(f"  步骤数: {len(result['steps'])}")
    else:
        print(f"✗ 工作流执行失败: {result.get('error')}")


async def demo_visualization():
    """可视化示例"""
    print("\n" + "=" * 60)
    print("思考过程可视化示例")
    print("=" * 60)
    
    generator = create_test_generator_agent(llm=None, rag_memory=SimpleMemory())
    
    result = await generator.process({
        "code": "def hello(): return 'Hello, World!'",
        "test_cases": 2,
    })
    
    print("\n思考过程可视化:")
    print("-" * 40)
    
    for step in result.get("steps", []):
        step_num = step["step_number"]
        thought = step["thought"]
        action = step["action"]
        action_type = step.get("action_type", "unknown")
        observation = step.get("observation", "")
        error = step.get("error")
        
        # 颜色
        colors = {
            "think": "\033[94m",     # 蓝色
            "tool_call": "\033[92m",  # 绿色
            "observe": "\033[93m",    # 黄色
            "fail": "\033[91m",       # 红色
            "success": "\033[92m",    # 绿色
        }
        reset = "\033[0m"
        
        color = colors.get(action_type, "\033[0m")
        
        print(f"\n{color}[步骤 {step_num}]{reset}")
        print(f"  思考: {thought[:60]}...")
        print(f"  动作: {action}")
        
        if observation:
            print(f"  观察: {observation}")
        
        if error:
            print(f"  {colors['fail']}错误: {error}{reset}")


async def main():
    """主函数"""
    print("\n🚀 Agent 测试助手 - 演示程序")
    print("=" * 60)
    
    try:
        await demo_basic()
        await demo_workflow()
        await demo_visualization()
        
        print("\n" + "=" * 60)
        print("演示完成!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
