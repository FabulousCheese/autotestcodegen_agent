"""
GitHub API 客户端

用于 PR 评论、状态检查等功能
"""
import os
import aiohttp
import asyncio
from typing import List, Optional, Dict, Any
from loguru import logger


class GitHubClient:
    """GitHub API 客户端"""
    
    def __init__(self, token: str = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.api_base = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    
    async def _request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Dict[str, Any]:
        """发送 HTTP 请求"""
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                headers=self.headers,
                **kwargs
            ) as response:
                if response.status >= 400:
                    text = await response.text()
                    logger.error(f"GitHub API Error: {response.status} - {text}")
                    raise Exception(f"API Error: {response.status}")
                return await response.json()
    
    async def get_pr(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """获取 PR 信息"""
        url = f"{self.api_base}/repos/{owner}/{repo}/pulls/{pr_number}"
        return await self._request("GET", url)
    
    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """获取 PR 变更的文件列表"""
        url = f"{self.api_base}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        return await self._request("GET", url)
    
    async def get_file_content(self, owner: str, repo: str, path: str, ref: str = "HEAD") -> Optional[str]:
        """获取文件内容"""
        url = f"{self.api_base}/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": ref}
        try:
            data = await self._request("GET", url, params=params)
            import base64
            if "content" in data:
                return base64.b64decode(data["content"]).decode("utf-8")
        except Exception as e:
            logger.error(f"获取文件 {path} 失败: {e}")
        return None
    
    async def create_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str
    ) -> Dict[str, Any]:
        """在 PR 下创建评论"""
        url = f"{self.api_base}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        data = {"body": body}
        return await self._request("POST", url, json=data)
    
    async def update_comment(
        self,
        owner: str,
        repo: str,
        comment_id: int,
        body: str
    ) -> Dict[str, Any]:
        """更新评论"""
        url = f"{self.api_base}/repos/{owner}/{repo}/issues/comments/{comment_id}"
        data = {"body": body}
        return await self._request("PATCH", url, json=data)
    
    async def get_comments(
        self,
        owner: str,
        repo: str,
        pr_number: int
    ) -> List[Dict[str, Any]]:
        """获取 PR 的所有评论"""
        url = f"{self.api_base}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        return await self._request("GET", url)
    
    async def find_ai_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        marker: str = "🤖 **AI Test"
    ) -> Optional[Dict[str, Any]]:
        """查找已有的 AI 测试评论"""
        comments = await self.get_comments(owner, repo, pr_number)
        for comment in comments:
            if marker in comment.get("body", ""):
                return comment
        return None
    
    async def create_or_update_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        marker: str = "🤖 **AI Test"
    ) -> Dict[str, Any]:
        """创建或更新评论（如果已存在则更新）"""
        existing = await self.find_ai_comment(owner, repo, pr_number, marker)
        if existing:
            return await self.update_comment(owner, repo, existing["id"], body)
        else:
            return await self.create_comment(owner, repo, pr_number, body)
    
    async def create_status(
        self,
        owner: str,
        repo: str,
        sha: str,
        state: str,
        target_url: str = None,
        description: str = None,
        context: str = "ai-test"
    ) -> Dict[str, Any]:
        """创建 commit status"""
        url = f"{self.api_base}/repos/{owner}/{repo}/statuses/{sha}"
        data = {
            "state": state,  # pending, success, error, failure
            "context": context,
        }
        if target_url:
            data["target_url"] = target_url
        if description:
            data["description"] = description
        return await self._request("POST", url, json=data)


# ============ 工具函数 ============

def parse_repo_name(full_name: str) -> tuple:
    """解析仓库名称，返回 (owner, repo)"""
    parts = full_name.split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid repo name: {full_name}")
    return parts[0], parts[1]


def format_test_report(
    tests_generated: int,
    passed: int,
    failed: int,
    coverage: float = None,
    execution_time: float = None
) -> str:
    """格式化测试报告为 Markdown"""
    total = passed + failed
    success_rate = (passed / total * 100) if total > 0 else 0
    status_emoji = "✅" if failed == 0 else "⚠️"
    
    coverage_str = f"\n| Coverage | {coverage:.1f}% |" if coverage else ""
    
    time_str = f"\n| Execution Time | {execution_time:.2f}s |" if execution_time else ""
    
    return f"""🤖 **AI Test Results**

| Metric | Value |
|--------|-------|
| Tests Generated | {tests_generated} |
| Passed | ✅ {passed} |
| Failed | ❌ {failed} |
| Success Rate | {status_emoji} {success_rate:.1f}% |{coverage_str}{time_str}

---
*Generated by AI Test System* 🤖"""
