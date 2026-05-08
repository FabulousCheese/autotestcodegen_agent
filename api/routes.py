"""API 路由定义"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum
import uuid
import os
import re

# API 路由
router = APIRouter(prefix="/api/v1", tags=["Agent 测试助手"])

# 全局调度器 (会在 main.py 中初始化)
_scheduler = None


def set_scheduler(scheduler):
    """设置全局调度器"""
    global _scheduler
    _scheduler = scheduler


# ============ 请求/响应模型 ============

class GenerateTestsRequest(BaseModel):
    """生成测试用例请求"""
    code: str = Field(..., description="源代码或函数定义")
    language: str = Field(default="python", description="编程语言")
    framework: str = Field(default="pytest", description="测试框架")
    test_cases: int = Field(default=5, description="生成测试用例数量")
    save_to_kb: bool = Field(default=True, description="是否保存到知识库")


class ExecuteTestsRequest(BaseModel):
    """执行测试请求"""
    tests: str = Field(..., description="测试代码")
    language: str = Field(default="python", description="编程语言")
    timeout: int = Field(default=60, description="超时时间(秒)")


class AnalyzeDefectsRequest(BaseModel):
    """缺陷分析请求"""
    logs: str = Field(..., description="日志内容或测试输出")
    test_results: Optional[Dict[str, Any]] = Field(default=None, description="测试结果")
    save_to_kb: bool = Field(default=True, description="是否保存到知识库")


class GenerateReportRequest(BaseModel):
    """生成报告请求"""
    test_results: Dict[str, Any] = Field(..., description="测试结果")
    test_cases: Optional[str] = Field(default=None, description="测试代码")
    code: Optional[str] = Field(default=None, description="源代码")
    format: str = Field(default="markdown", description="报告格式: markdown/html")


class WorkflowCreateRequest(BaseModel):
    """创建工作流请求"""
    name: str = Field(..., description="工作流名称")
    description: str = Field(default="", description="工作流描述")
    steps: List[Dict[str, Any]] = Field(default_factory=list, description="工作流步骤")


# ============ API 端点 ============

@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }


@router.post("/generate-tests-simple")
async def generate_tests_simple(request: GenerateTestsRequest):
    """简化版生成测试用例 - 只返回关键信息"""
    if not _scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")
    
    agent_name = "TestGenerator"
    if agent_name not in _scheduler.agents:
        raise HTTPException(status_code=404, detail=f"Agent 不存在: {agent_name}")
    
    result = await _scheduler.execute_single_agent(
        agent_name,
        {
            "code": request.code,
            "language": request.language,
            "framework": request.framework,
            "test_cases": request.test_cases,
        }
    )
    
    # 自动保存测试文件
    file_path = None
    tests_code = None
    if result.get("success") and result.get("result", {}).get("tests"):
        tests_code = result["result"]["tests"]
        func_match = re.search(r'def\s+(\w+)\s*\(', request.code)
        func_name = func_match.group(1) if func_match else "test"
        
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "generated_tests")
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(output_dir, f"test_{func_name}_{timestamp}.py")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(tests_code)
    
    # 简化返回
    return {
        "success": result.get("success", False),
        "tests": tests_code,
        "file_path": file_path,
        "test_count": result.get("result", {}).get("test_count", 0),
    }


@router.post("/generate-tests")
async def generate_tests(request: GenerateTestsRequest):
    """生成测试用例"""
    if not _scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")
    
    # 获取测试生成 Agent
    agent_name = "TestGenerator"
    if agent_name not in _scheduler.agents:
        raise HTTPException(status_code=404, detail=f"Agent 不存在: {agent_name}")
    
    result = await _scheduler.execute_single_agent(
        agent_name,
        {
            "code": request.code,
            "language": request.language,
            "framework": request.framework,
            "test_cases": request.test_cases,
        }
    )
    
    # 自动保存测试文件到项目目录
    file_path = None
    if result.get("success") and result.get("result", {}).get("tests"):
        tests_code = result["result"]["tests"]
        # 从代码中提取函数名
        func_match = re.search(r'def\s+(\w+)\s*\(', request.code)
        func_name = func_match.group(1) if func_match else "test"
        
        # 创建输出目录
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "generated_tests")
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(output_dir, f"test_{func_name}_{timestamp}.py")
        
        # 保存文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(tests_code)
        
        result["result"]["file_path"] = file_path
    
    return {
        "success": result.get("success", False),
        "data": result.get("result"),
        "error": result.get("error"),
        "steps": result.get("steps", []),
    }


@router.post("/execute-tests")
async def execute_tests(request: ExecuteTestsRequest):
    """执行测试"""
    if not _scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")
    
    agent_name = "TestExecutor"
    if agent_name not in _scheduler.agents:
        raise HTTPException(status_code=404, detail=f"Agent 不存在: {agent_name}")
    
    result = await _scheduler.execute_single_agent(
        agent_name,
        {
            "tests": request.tests,
            "language": request.language,
            "timeout": request.timeout,
        }
    )
    
    return {
        "success": result.get("success", False),
        "data": result.get("result"),
        "error": result.get("error"),
        "steps": result.get("steps", []),
    }


@router.post("/analyze-defects")
async def analyze_defects(request: AnalyzeDefectsRequest):
    """缺陷分析"""
    if not _scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")
    
    agent_name = "DefectAnalyzer"
    if agent_name not in _scheduler.agents:
        raise HTTPException(status_code=404, detail=f"Agent 不存在: {agent_name}")
    
    result = await _scheduler.execute_single_agent(
        agent_name,
        {
            "logs": request.logs,
            "test_results": request.test_results,
        }
    )
    
    return {
        "success": result.get("success", False),
        "data": result.get("result"),
        "error": result.get("error"),
        "steps": result.get("steps", []),
    }


@router.post("/generate-report")
async def generate_report(request: GenerateReportRequest):
    """生成报告"""
    if not _scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")
    
    agent_name = "ReportGenerator"
    if agent_name not in _scheduler.agents:
        raise HTTPException(status_code=404, detail=f"Agent 不存在: {agent_name}")
    
    result = await _scheduler.execute_single_agent(
        agent_name,
        {
            "test_results": request.test_results,
            "test_cases": request.test_cases,
            "code": request.code,
            "format": request.format,
        }
    )
    
    return {
        "success": result.get("success", False),
        "data": result.get("result"),
        "error": result.get("error"),
        "steps": result.get("steps", []),
    }


@router.post("/workflow/create")
async def create_workflow(request: WorkflowCreateRequest):
    """创建工作流"""
    if not _scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")
    
    workflow = _scheduler.create_workflow(request.name, request.description)
    
    # 添加步骤
    from core.agent.base_agent import AgentType
    for step in request.steps:
        _scheduler.add_workflow_step(
            workflow.workflow_id,
            step.get("agent_name"),
            AgentType(step.get("agent_type", "test_generator")),
            step.get("input_data"),
        )
    
    return {
        "workflow_id": workflow.workflow_id,
        "name": workflow.name,
        "status": workflow.status.value,
        "steps_count": len(workflow.steps),
    }


@router.post("/workflow/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, background_tasks: BackgroundTasks):
    """执行工作流"""
    if not _scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")
    
    workflow = _scheduler.get_workflow_status(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")
    
    # 后台执行
    async def run_workflow():
        await _scheduler.execute_workflow(workflow_id)
    
    background_tasks.add_task(run_workflow)
    
    return {
        "workflow_id": workflow_id,
        "status": "running",
        "message": "工作流已在后台启动",
    }


@router.get("/workflow/{workflow_id}")
async def get_workflow_status(workflow_id: str):
    """获取工作流状态"""
    if not _scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")
    
    workflow = _scheduler.get_workflow_status(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")
    
    return {
        "workflow_id": workflow.workflow_id,
        "name": workflow.name,
        "description": workflow.description,
        "status": workflow.status.value,
        "current_step": workflow.current_step,
        "total_steps": len(workflow.steps),
        "steps": [
            {
                "step_id": s.step_id,
                "agent_name": s.agent_name,
                "status": s.status.value,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "error": s.error,
                "thought_history": s.thought_history,
            }
            for s in workflow.steps
        ],
        "context": workflow.context,
        "created_at": workflow.created_at.isoformat(),
        "updated_at": workflow.updated_at.isoformat(),
    }


@router.delete("/workflow/{workflow_id}")
async def cancel_workflow(workflow_id: str):
    """取消工作流"""
    if not _scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")
    
    success = _scheduler.cancel_workflow(workflow_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="无法取消工作流")
    
    return {"message": "工作流已取消", "workflow_id": workflow_id}


@router.get("/agents")
async def list_agents():
    """列出所有 Agent"""
    if not _scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")
    
    return {
        "agents": _scheduler.get_available_agents(),
        "count": len(_scheduler.agents),
    }


# ============ 端到端测试流程 ============

@router.post("/test-flow")
async def run_test_flow(request: GenerateTestsRequest):
    """
    端到端测试流程
    
    完整流程:
    1. 生成测试用例
    2. 执行测试
    3. 分析缺陷 (如果测试失败)
    4. 生成报告
    """
    if not _scheduler:
        raise HTTPException(status_code=500, detail="调度器未初始化")
    
    flow_id = str(uuid.uuid4())
    results = {
        "flow_id": flow_id,
        "steps": {},
    }
    
    # 1. 生成测试用例
    generator = _scheduler.agents.get("TestGenerator")
    if not generator:
        raise HTTPException(status_code=500, detail="TestGenerator Agent 未找到")
    
    gen_result = await generator.process({
        "code": request.code,
        "language": request.language,
        "framework": request.framework,
        "test_cases": request.test_cases,
    })
    
    results["steps"]["test_generation"] = {
        "success": gen_result.get("success", False),
        "data": gen_result.get("result"),
        "steps": gen_result.get("steps", []),
    }
    
    if not gen_result.get("success") or not gen_result.get("result"):
        results["status"] = "failed"
        results["error"] = "测试用例生成失败"
        return results
    
    tests = gen_result.get("result", {}).get("tests", "")
    
    # 保存测试代码到文件
    func_match = re.search(r'def\s+(\w+)\s*\(', request.code)
    func_name = func_match.group(1) if func_match else "test"
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "generated_tests")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(output_dir, f"test_{func_name}_{timestamp}.py")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(tests)
    gen_result["result"]["file_path"] = file_path
    
    # 2. 执行测试
    executor = _scheduler.agents.get("TestExecutor")
    if executor:
        exec_result = await executor.process({
            "tests": tests,
            "language": request.language,
            "timeout": 60,
        })
        
        results["steps"]["test_execution"] = {
            "success": exec_result.get("success", False),
            "data": exec_result.get("result"),
            "steps": exec_result.get("steps", []),
        }
    
    # 3. 缺陷分析 (如果执行失败)
    if results["steps"].get("test_execution", {}).get("success") == False:
        logs = results["steps"]["test_execution"].get("data", {}).get("stderr", "")
        
        analyzer = _scheduler.agents.get("DefectAnalyzer")
        if analyzer:
            analysis_result = await analyzer.process({
                "logs": logs,
                "test_results": results["steps"]["test_execution"].get("data"),
            })
            
            results["steps"]["defect_analysis"] = {
                "success": analysis_result.get("success", False),
                "data": analysis_result.get("result"),
                "steps": analysis_result.get("steps", []),
            }
    
    # 4. 生成报告
    report_gen = _scheduler.agents.get("ReportGenerator")
    if report_gen:
        report_result = await report_gen.process({
            "test_results": results["steps"].get("test_execution", {}).get("data", {}),
            "test_cases": tests,
            "code": request.code,
            "format": "html",
        })
        
        results["steps"]["report_generation"] = {
            "success": report_result.get("success", False),
            "data": report_result.get("result"),
            "steps": report_result.get("steps", []),
        }
    
    results["status"] = "completed"
    return results
