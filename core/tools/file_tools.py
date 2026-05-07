"""文件操作工具"""
import os
import aiofiles
from pathlib import Path
from typing import Optional, List
from loguru import logger

from .base import ToolResult


async def read_file_tool(
    file_path: str,
    encoding: str = "utf-8",
    limit: Optional[int] = None,
    offset: int = 0,
) -> ToolResult:
    """
    读取文件工具
    
    Args:
        file_path: 文件路径
        encoding: 文件编码
        limit: 读取行数限制
        offset: 起始行偏移
    """
    import time
    start_time = time.time()
    
    try:
        if not os.path.exists(file_path):
            return ToolResult(
                success=False,
                error=f"文件不存在: {file_path}",
                execution_time=time.time() - start_time,
            )
        
        async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
            content = await f.read()
        
        lines = content.split('\n')
        
        if offset > 0:
            lines = lines[offset:]
        if limit:
            lines = lines[:limit]
        
        return ToolResult(
            success=True,
            result={
                "file_path": file_path,
                "content": '\n'.join(lines),
                "total_lines": len(content.split('\n')),
                "read_lines": len(lines),
                "offset": offset,
                "limit": limit,
            },
            execution_time=time.time() - start_time,
        )
        
    except Exception as e:
        logger.error(f"文件读取失败: {e}")
        return ToolResult(
            success=False,
            error=str(e),
            execution_time=time.time() - start_time,
        )


async def write_file_tool(
    file_path: str,
    content: str,
    encoding: str = "utf-8",
    create_dirs: bool = True,
) -> ToolResult:
    """
    写入文件工具
    
    Args:
        file_path: 文件路径
        content: 文件内容
        encoding: 文件编码
        create_dirs: 是否创建目录
    """
    import time
    start_time = time.time()
    
    try:
        # 创建目录
        if create_dirs:
            dir_path = os.path.dirname(file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
        
        async with aiofiles.open(file_path, 'w', encoding=encoding) as f:
            await f.write(content)
        
        return ToolResult(
            success=True,
            result={
                "file_path": file_path,
                "bytes_written": len(content.encode(encoding)),
                "lines_written": len(content.split('\n')),
            },
            execution_time=time.time() - start_time,
        )
        
    except Exception as e:
        logger.error(f"文件写入失败: {e}")
        return ToolResult(
            success=False,
            error=str(e),
            execution_time=time.time() - start_time,
        )


async def list_files_tool(
    directory: str,
    pattern: str = "*",
    recursive: bool = False,
    max_depth: int = 3,
) -> ToolResult:
    """
    列出文件工具
    
    Args:
        directory: 目录路径
        pattern: 文件匹配模式
        recursive: 是否递归
        max_depth: 最大递归深度
    """
    import time
    start_time = time.time()
    
    try:
        if not os.path.exists(directory):
            return ToolResult(
                success=False,
                error=f"目录不存在: {directory}",
                execution_time=time.time() - start_time,
            )
        
        if not os.path.isdir(directory):
            return ToolResult(
                success=False,
                error=f"不是有效目录: {directory}",
                execution_time=time.time() - start_time,
            )
        
        from pathlib import Path
        
        files = []
        path = Path(directory)
        
        if recursive:
            for p in path.rglob(pattern):
                if p.is_file():
                    depth = len(p.relative_to(path).parts) - 1
                    if depth < max_depth:
                        files.append({
                            "path": str(p),
                            "name": p.name,
                            "size": p.stat().st_size,
                            "extension": p.suffix,
                        })
        else:
            for p in path.glob(pattern):
                if p.is_file():
                    files.append({
                        "path": str(p),
                        "name": p.name,
                        "size": p.stat().st_size,
                        "extension": p.suffix,
                    })
        
        return ToolResult(
            success=True,
            result={
                "directory": directory,
                "files": files,
                "count": len(files),
                "pattern": pattern,
                "recursive": recursive,
            },
            execution_time=time.time() - start_time,
        )
        
    except Exception as e:
        logger.error(f"文件列表获取失败: {e}")
        return ToolResult(
            success=False,
            error=str(e),
            execution_time=time.time() - start_time,
        )
