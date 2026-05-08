# Agent 测试助手 - 智能自动代码测试系统

基于多 Agent 协作 + DeepSeek LLM 的智能测试用例生成与执行系统。

## 功能特性

- **智能测试生成**：使用 DeepSeek LLM 自动生成完整的 pytest 测试用例
- **多 Agent 协作**：TestGenerator → TestExecutor → DefectAnalyzer → ReportGenerator
- **自动缺陷分析**：分析测试失败原因，定位根因并提供修复建议
- **多种报告格式**：支持 Markdown 和 HTML 报告输出

## 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI + Uvicorn |
| LLM 集成 | LangChain + DeepSeek API |
| 向量数据库 | ChromaDB (可选) |
| 数据验证 | Pydantic |
| 测试框架 | pytest |
| 日志 | Loguru |

## 项目结构

```
automatic_code_gen/
├── main.py                    # 主入口文件 (FastAPI 应用)
├── requirements.txt           # 依赖配置
├── .env.example               # 环境变量示例
│
├── core/                      # 核心模块
│   ├── agent/                  # Agent 核心
│   │   ├── base.py           # 配置管理 (Settings)
│   │   ├── base_agent.py     # Agent 基类定义
│   │   ├── react_agent.py    # ReAct Agent 实现
│   │   └── scheduler.py      # 多 Agent 调度器
│   │
│   ├── memory/                # 记忆模块
│   │   └── rag.py            # RAG/SimpleMemory 实现
│   │
│   └── tools/                 # 工具模块
│       ├── base.py           # 工具基类
│       ├── code_tools.py     # 代码相关工具
│       └── file_tools.py     # 文件操作工具
│
├── agents/                    # 业务 Agent
│   ├── test_generator/       # 测试用例生成 Agent
│   ├── test_executor/        # 测试执行 Agent
│   ├── defect_analyzer/      # 缺陷分析 Agent
│   └── report_generator/      # 报告生成 Agent
│
├── api/                       # API 路由
│   └── routes.py             # FastAPI 路由定义
│
├── generated_tests/           # 生成的测试文件
├── reports/                   # 生成的报告
├── logs/                      # 日志文件
└── data/                      # 数据存储 (ChromaDB)
```

## 架构设计

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FastAPI 应用 (main.py)                        │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                          API Routes (routes.py)                     │ │
│  │   /generate-tests  /execute-tests  /analyze-defects  /test-flow    │ │
│  └───────────────────────────────┬─────────────────────────────────────┘ │
└──────────────────────────────────┼──────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────┐
│                     AgentScheduler (调度器)                              │
│  ┌──────────────┬──────────────┬───────────────┬──────────────────────┐ │
│  │TestGenerator │ TestExecutor │DefectAnalyzer│  ReportGenerator     │ │
│  │   Agent      │    Agent     │    Agent     │      Agent           │ │
│  └──────┬───────┴───────┬──────┴───────┬──────┴──────────┬───────────┘ │
│         │               │              │                  │              │
│         └───────────────┴──────────────┴──────────────────┘              │
│                                   │                                      │
│                     ┌─────────────▼─────────────┐                       │
│                     │     ReAct Agent 引擎       │                       │
│                     │  (Thought-Action-Obs循环)  │                       │
│                     └─────────────┬─────────────┘                       │
└──────────────────────────────────┼──────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────┐
│                              工具层                                      │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────┐  │
│  │   code_tools.py     │  │   file_tools.py     │  │   memory/       │  │
│  │  • generate_tests   │  │  • read_file        │  │  • RAGMemory    │  │
│  │  • execute_tests    │  │  • write_file       │  │  • SimpleMemory │  │
│  │  • analyze_logs     │  │  • list_files       │  │                 │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
               ┌───────────────────┼───────────────────┐
               │                   │                   │
       ┌───────▼───────┐   ┌───────▼───────┐   ┌──────▼───────┐
       │  DeepSeek API │   │   ChromaDB    │   │    pytest    │
       │   (LLM)       │   │  (向量存储)   │   │   (测试)     │
       └───────────────┘   └───────────────┘   └──────────────┘
```

### Agent 协作流程

```
用户请求
    │
    ▼
┌─────────────────┐
│ TestGenerator   │  ← 生成完整测试代码 (DeepSeek LLM)
│   Agent         │
└────────┬────────┘
         │ 生成的测试代码
         ▼
┌─────────────────┐
│  TestExecutor   │  ← 执行 pytest，获取结果和日志
│    Agent        │
└────────┬────────┘
         │ 测试结果
         ▼
┌─────────────────┐
│ DefectAnalyzer  │  ← 分析失败的测试，定位根因
│    Agent        │
└────────┬────────┘
         │ 缺陷分析
         ▼
┌─────────────────┐
│ ReportGenerator │  ← 生成 Markdown/HTML 报告
│    Agent        │
└────────┬────────┘
         │
         ▼
     最终报告
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
DEEPSEEK_API_KEY=你的API密钥
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 3. 启动服务

```bash
python main.py --port 8001
```

### 4. 测试 API

```bash
# 生成测试用例
curl -X POST http://localhost:8001/api/v1/generate-tests \
  -H "Content-Type: application/json" \
  -d '{"code": "def add(a, b): return a + b", "language": "python"}'

# 端到端测试流程
curl -X POST http://localhost:8001/api/v1/test-flow \
  -H "Content-Type: application/json" \
  -d '{"code": "def add(a, b): return a + b", "language": "python"}'
```

## API 文档

启动服务后访问：http://localhost:8001/docs

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/health` | GET | 健康检查 |
| `/api/v1/generate-tests` | POST | 生成测试用例 |
| `/api/v1/generate-tests-simple` | POST | 简化版生成测试 |
| `/api/v1/execute-tests` | POST | 执行测试 |
| `/api/v1/analyze-defects` | POST | 缺陷分析 |
| `/api/v1/generate-report` | POST | 生成报告 |
| `/api/v1/test-flow` | POST | 端到端测试流程 |
| `/api/v1/agents` | GET | 列出所有 Agent |

## Agent 详解

### TestGenerator Agent
- **职责**：分析源代码，使用 DeepSeek LLM 生成完整可运行的测试用例
- **核心工具**：`generate_tests`
- **输出**：pytest 测试代码文件

### TestExecutor Agent
- **职责**：执行生成的测试用例，收集执行结果和日志
- **核心工具**：`execute_tests`, `analyze_test_logs`
- **输出**：测试执行结果、覆盖率报告

### DefectAnalyzer Agent
- **职责**：分析测试失败原因，定位缺陷根因，提供修复建议
- **核心工具**：`analyze_defects`, `search_knowledge_base`
- **输出**：错误类型、根因分析、修复建议

### ReportGenerator Agent
- **职责**：生成测试报告
- **核心工具**：`generate_markdown_report`, `generate_html_report`
- **输出**：Markdown/HTML 格式报告

## 核心文件说明

| 文件 | 作用 | 重点关注 |
|------|------|---------|
| `main.py` | 应用入口，LLM 初始化 | LLM 配置、Agent 初始化逻辑 |
| `core/agent/react_agent.py` | ReAct 推理引擎 | 思考-行动-观察循环实现 |
| `core/agent/scheduler.py` | 多 Agent 调度 | 工作流编排 |
| `agents/test_generator/agent.py` | 测试生成核心 | **最重要** - 生成完整测试代码 |
| `core/tools/code_tools.py` | 测试生成工具 | execute_tests、analyze_logs |
| `api/routes.py` | API 端点定义 | 扩展新接口的位置 |

## License

MIT License
