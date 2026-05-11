"""
GitHub Webhook 处理模块

接收 GitHub PR 事件，自动触发测试并评论结果
"""
from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import hmac
import hashlib
import asyncio
import aiohttp
from loguru import logger

router = APIRouter(prefix="/api/v1/github", tags=["GitHub Integration"])


# ============ 配置 ============

GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")


# ============ 请求/响应模型 ============

class GitHubWebhookPayload(BaseModel):
    """GitHub Webhook 负载"""
    action: str
    number: int
    pull_request: Optional[Dict[str, Any]] = None
    repository: Optional[Dict[str, Any]] = None


class PRCommentRequest(BaseModel):
    """PR 评论请求"""
    pr_number: int
    body: str
    repo_owner: str
    repo_name: str


# ============ Webhook 验证 ============

def verify_github_signature(payload: bytes, signature: str, secret: str) -> bool:
    """验证 GitHub Webhook 签名"""
    if not secret:
        logger.warning("GitHub Webhook secret 未配置，跳过验证")
        return True
    
    mac = hmac.new(
        key=secret.encode(),
        msg=payload,
        digestmod=hashlib.sha256
    )
    expected_signature = f"sha256={mac.hexdigest()}"
    
    return hmac.compare_digest(expected_signature, signature)


# ============ API 端点 ============

@router.post("/webhook")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(None),
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_delivery: Optional[str] = Header(None),
):
    """
    GitHub Webhook 主入口
    
    事件类型:
    - pull_request: PR 创建/更新
    - push: 代码推送
    - check_run: CI 检查
    """
    # 获取原始 payload
    payload = await request.body()
    
    # 验证签名
    if not verify_github_signature(payload, x_hub_signature_256 or "", GITHUB_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    import json
    data = json.loads(payload)
    
    logger.info(f"收到 GitHub Webhook: {x_github_event}, Delivery: {x_github_delivery}")
    
    # 处理不同事件
    if x_github_event == "pull_request":
        return await handle_pull_request(data)
    elif x_github_event == "push":
        return await handle_push(data)
    elif x_github_event == "check_run":
        return await handle_check_run(data)
    else:
        return {"status": "ignored", "event": x_github_event}


async def handle_pull_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """处理 PR 事件"""
    action = data.get("action")
    pr = data.get("pull_request", {})
    
    pr_number = pr.get("number")
    pr_title = pr.get("title")
    pr_url = pr.get("html_url")
    repo = data.get("repository", {})
    repo_name = repo.get("full_name")
    
    logger.info(f"PR #{pr_number}: {pr_title} - Action: {action}")
    
    # 只处理 PR 打开和更新的情况
    if action in ["opened", "synchronize", "reopened"]:
        # 异步触发测试
        asyncio.create_task(run_pr_tests(
            pr_number=pr_number,
            pr_title=pr_title,
            pr_url=pr_url,
            repo_name=repo_name,
            action=action
        ))
        
        return {
            "status": "accepted",
            "message": f"开始为 PR #{pr_number} 生成测试",
            "pr_number": pr_number,
            "action": action
        }
    
    return {"status": "ignored", "action": action}


async def handle_push(data: Dict[str, Any]) -> Dict[str, Any]:
    """处理 push 事件"""
    ref = data.get("ref")
    commits = data.get("commits", [])
    
    logger.info(f"Push to {ref}, {len(commits)} commits")
    
    return {"status": "ok", "ref": ref, "commits": len(commits)}


async def handle_check_run(data: Dict[str, Any]) -> Dict[str, Any]:
    """处理 CI 检查事件"""
    check_run = data.get("check_run", {})
    conclusion = check_run.get("conclusion")
    
    logger.info(f"Check run completed: {conclusion}")
    
    return {"status": "ok", "conclusion": conclusion}


# ============ 核心逻辑 ============

async def run_pr_tests(
    pr_number: int,
    pr_title: str,
    pr_url: str,
    repo_name: str,
    action: str
):
    """异步执行 PR 测试"""
    try:
        # 1. 获取 PR 变更的文件
        changed_files = await get_pr_changed_files(repo_name, pr_number)
        
        # 2. 过滤 Python 文件
        python_files = [f for f in changed_files if f.endswith(".py")]
        
        if not python_files:
            await post_pr_comment(
                repo_name=repo_name,
                pr_number=pr_number,
                body="🤖 **AI Test**: 未检测到 Python 文件变更，跳过测试生成。"
            )
            return
        
        # 3. 获取文件内容
        file_contents = []
        for file_path in python_files[:10]:  # 限制最多 10 个文件
            content = await get_file_content(repo_name, file_path)
            if content:
                file_contents.append({
                    "path": file_path,
                    "content": content
                })
        
        # 4. 调用测试生成 API
        test_results = await trigger_test_generation(file_contents)
        
        # 5. 执行测试
        execution_results = await execute_tests(test_results.get("tests", ""))
        
        # 6. 生成报告并评论
        report = generate_report(test_results, execution_results)
        
        await post_pr_comment(
            repo_name=repo_name,
            pr_number=pr_number,
            body=report
        )
        
        logger.info(f"PR #{pr_number} 测试完成")
        
    except Exception as e:
        logger.error(f"PR #{pr_number} 测试失败: {e}")
        await post_pr_comment(
            repo_name=repo_name,
            pr_number=pr_number,
            body=f"🤖 **AI Test Error**: 测试执行失败\n\nError: {str(e)}"
        )


# ============ GitHub API 调用 ============

async def get_pr_changed_files(repo_name: str, pr_number: int) -> List[str]:
    """获取 PR 变更的文件列表"""
    # TODO: 实现 GitHub API 调用
    # 使用 github3.py 或 PyGithub 库
    return []


async def get_file_content(repo_name: str, file_path: str, ref: str = "HEAD") -> Optional[str]:
    """获取文件内容"""
    # TODO: 实现 GitHub API 调用
    return None


async def post_pr_comment(repo_name: str, pr_number: int, body: str):
    """在 PR 下发表评论"""
    # TODO: 实现 GitHub API 调用
    logger.info(f"发表 PR 评论 #{pr_number}: {body[:100]}...")


async def trigger_test_generation(files: List[Dict[str, str]]) -> Dict[str, Any]:
    """触发测试生成"""
    # TODO: 调用内部测试生成服务
    return {"tests": "", "status": "success"}


async def execute_tests(tests_code: str) -> Dict[str, Any]:
    """执行测试"""
    # TODO: 调用测试执行服务
    return {"passed": 0, "failed": 0, "total": 0}


def generate_report(test_results: Dict, execution_results: Dict) -> str:
    """生成 PR 评论内容"""
    passed = execution_results.get("passed", 0)
    failed = execution_results.get("failed", 0)
    total = execution_results.get("total", 0)
    
    success_rate = (passed / total * 100) if total > 0 else 0
    
    status_emoji = "✅" if failed == 0 else "⚠️"
    
    return f"""🤖 **AI Test Results**

| Metric | Value |
|--------|-------|
| Tests Generated | {total} |
| Passed | ✅ {passed} |
| Failed | ❌ {failed} |
| Success Rate | {status_emoji} {success_rate:.1f}% |

---
*Generated by AI Test System*
"""


# ============ 手动触发接口 ============

class ManualTriggerRequest(BaseModel):
    """手动触发测试请求"""
    repo_name: str = Field(..., description="仓库名称，格式: owner/repo")
    pr_number: int = Field(..., description="PR 编号")
    github_token: str = Field(..., description="GitHub Token")


@router.post("/trigger")
async def manual_trigger(request: ManualTriggerRequest):
    """手动触发 PR 测试"""
    repo_name = request.repo_name
    pr_number = request.pr_number
    
    try:
        asyncio.create_task(run_pr_tests(
            pr_number=pr_number,
            pr_title="Manual Trigger",
            pr_url=f"https://github.com/{repo_name}/pull/{pr_number}",
            repo_name=repo_name,
            action="manual"
        ))
        
        return {
            "status": "accepted",
            "message": f"开始为 {repo_name}/pull/{pr_number} 生成测试"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
