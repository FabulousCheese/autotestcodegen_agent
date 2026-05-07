"""
Agent 测试助手 - 主入口文件

智能测试助手: 多 Agent 协作的自动化测试系统
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
from loguru import logger

# 导入配置
from core.agent.base import settings

# 导入 Agent 相关
from core.agent.scheduler import AgentScheduler
from core.memory.rag import SimpleMemory  # 禁用 RAG，直接用简单内存

# 导入 Agent 工厂
from agents import (
    create_test_generator_agent,
    create_test_executor_agent,
    create_defect_analyzer_agent,
    create_report_generator_agent,
)

# 导入 API 路由
from api.routes import router, set_scheduler

# ============ LLM 初始化 ============

llm = None


def init_llm():
    """初始化 DeepSeek LLM"""
    global llm
    
    api_key = settings.deepseek_api_key
    
    if not api_key:
        logger.warning("未设置 DEEPSEEK_API_KEY，LLM 功能不可用")
        return None
    
    try:
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(
            model=settings.deepseek_model,
            api_key=api_key,
            base_url=settings.deepseek_base_url,
            temperature=0.1,
        )
        logger.info(f"LLM 初始化成功: {settings.deepseek_model}")
        return llm
    except Exception as e:
        logger.error(f"LLM 初始化失败: {e}")
        return None


# ============ 日志配置 ============

logger.add(
    "logs/agent_test_assistant_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
)


# ============ 应用初始化 ============

app = FastAPI(
    title=settings.app_name,
    description="智能测试助手 - 基于多 Agent 协作 + DeepSeek LLM",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)


# ============ 初始化 Agent 系统 ============

def init_agents() -> AgentScheduler:
    """初始化 Agent 系统"""
    global llm
    
    logger.info("=" * 50)
    logger.info("开始初始化 Agent 系统...")
    logger.info("=" * 50)
    
    # 初始化 LLM
    llm = init_llm()
    
    # 使用简单内存（禁用 RAG）
    rag_memory = SimpleMemory()
    logger.info("使用简单内存（RAG 已禁用）")
    
    # 创建调度器
    scheduler = AgentScheduler()
    
    # 创建并注册各个 Agent（传入 LLM）
    agents = [
        create_test_generator_agent(llm=llm, rag_memory=rag_memory),
        create_test_executor_agent(llm=llm),
        create_defect_analyzer_agent(llm=llm, rag_memory=rag_memory),
        create_report_generator_agent(llm=llm),
    ]
    
    for agent in agents:
        scheduler.register_agent(agent)
        logger.info(f"注册 Agent: {agent.config.name}")
    
    logger.info(f"Agent 系统初始化完成，共 {len(agents)} 个 Agent")
    
    return scheduler


# 初始化调度器
scheduler = init_agents()
set_scheduler(scheduler)


# ============ 前端页面 ============

@app.get("/", response_class=HTMLResponse)
async def index():
    """主页"""
    llm_status = "✅ DeepSeek 已连接" if llm else "❌ 未连接 LLM"
    
    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent 测试助手</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .header h1 {{
            color: #333;
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header p {{
            color: #666;
            font-size: 1.1em;
        }}
        .llm-status {{
            display: inline-block;
            background: {'#d4edda' if llm else '#f8d7da'};
            color: {'#155724' if llm else '#721c24'};
            padding: 8px 20px;
            border-radius: 20px;
            margin-top: 15px;
            font-weight: 500;
        }}
        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }}
        .card {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }}
        .card:hover {{
            transform: translateY(-5px);
        }}
        .card h3 {{
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.3em;
        }}
        .card p {{
            color: #666;
            line-height: 1.6;
        }}
        .badge {{
            display: inline-block;
            background: #e8e8e8;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            color: #666;
            margin-top: 15px;
        }}
        .btn {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 25px;
            border-radius: 25px;
            text-decoration: none;
            margin-top: 15px;
            font-weight: 500;
            transition: all 0.3s ease;
        }}
        .btn:hover {{
            transform: scale(1.05);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }}
        .links {{
            display: flex;
            gap: 15px;
            margin-top: 20px;
            flex-wrap: wrap;
            justify-content: center;
        }}
        .link {{
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }}
        .link:hover {{
            text-decoration: underline;
        }}
        .demo-code {{
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 20px;
            border-radius: 10px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.9em;
            overflow-x: auto;
            margin-top: 15px;
        }}
        .demo-code .comment {{
            color: #6a9955;
        }}
        .demo-code .string {{
            color: #ce9178;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Agent 测试助手</h1>
            <p>基于多 Agent 协作 + DeepSeek LLM 的智能自动化测试系统</p>
            <div class="llm-status">{llm_status}</div>
            <div class="links">
                <a href="/docs" class="link">API 文档</a>
                <a href="/redoc" class="link">ReDoc 文档</a>
            </div>
        </div>
        
        <div class="cards">
            <div class="card">
                <h3>测试用例生成</h3>
                <p>使用 DeepSeek LLM 智能分析代码，生成完整可运行的 pytest 测试用例</p>
                <span class="badge">TestGenerator Agent</span>
            </div>
            
            <div class="card">
                <h3>测试执行</h3>
                <p>自动运行测试，收集执行结果和覆盖率数据</p>
                <span class="badge">TestExecutor Agent</span>
            </div>
            
            <div class="card">
                <h3>缺陷分析</h3>
                <p>智能分析日志和错误，定位根因并给出修复建议</p>
                <span class="badge">DefectAnalyzer Agent</span>
            </div>
            
            <div class="card">
                <h3>报告生成</h3>
                <p>生成 Markdown/HTML 格式的精美测试报告</p>
                <span class="badge">ReportGenerator Agent</span>
            </div>
        </div>
        
        <div class="card" style="margin-top: 20px;">
            <h3>快速测试</h3>
            <p>在终端执行以下命令测试：</p>
            <div class="demo-code">
<span class="comment"># 生成测试用例</span>
curl -X POST http://localhost:8001/api/v1/generate-tests \\
  -H "Content-Type: application/json" \\
  -d '<span class="string">'{{"code": "def add(a, b): return a + b", "language": "python"}}'</span>'
            </div>
        </div>
    </div>
</body>
</html>
"""


# ============ 启动应用 ============

if __name__ == "__main__":
    # 确保目录存在
    os.makedirs("logs", exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    os.makedirs("generated_tests", exist_ok=True)
    
    logger.info(f"启动 {settings.app_name}")
    logger.info(f"调试模式: {settings.debug}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.debug,
        log_level="info",
    )
