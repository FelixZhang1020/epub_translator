# ePub Translator

<div align="center">
  <a href="https://github.com/FelixZhang1020/epub_translator/stargazers"><img src="https://img.shields.io/github/stars/FelixZhang1020/epub_translator?style=flat-square" alt="GitHub Stars"></a>
  <a href="https://github.com/FelixZhang1020/epub_translator/actions"><img src="https://img.shields.io/badge/CI-status-grey?style=flat-square" alt="CI Status"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square" alt="License: MIT"></a>
  <a><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a><img src="https://img.shields.io/badge/Node.js-18+-339933?style=flat-square&logo=nodedotjs&logoColor=white" alt="Node.js 18+"></a>
</div>

<br>

<div align="center">
  <table>
    <tr>
      <td align="center">
        <a href="#-english"><img src="https://img.shields.io/badge/English-0969da?style=for-the-badge&logo=readme&logoColor=white" alt="English"></a>
      </td>
      <td align="center">
        <a href="#-中文"><img src="https://img.shields.io/badge/中文-0969da?style=for-the-badge&logo=readme&logoColor=white" alt="中文"></a>
      </td>
    </tr>
  </table>
</div>

<div align="center">

**[License](LICENSE) · [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md) · [Security](SECURITY.md)**

</div>

---

# 🇬🇧 English

LLM-powered pipeline that translates English ePub books into Chinese while keeping layout, tone, and context intact.

## Overview

ePub Translator is a full-stack app that analyzes, translates, and proofreads ePub books, then exports bilingual output. It supports multiple LLM providers and reference matching to keep terminology consistent across chapters.

## Highlights

- **Multi-LLM**: OpenAI, Anthropic Claude, Google Gemini, Alibaba Qwen, DeepSeek
- **Guided pipeline**: Analysis → Translation → Proofreading → Export with chapter-level state
- **Style extraction**: Automatically captures tone, terminology, and writing style
- **Reference matching**: Aligns paragraphs with existing translations for consistency
- **Prompt control**: System/user prompts with variables, reusable templates
- **Bilingual export**: Generates ePub with original + translated text
- **Web UI**: Preview chapters, edit translations, and rerun steps as needed

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Uvicorn |
| Frontend | React + Vite + TypeScript, Zustand, Ant Design |
| Storage | SQLite by default (override via `DATABASE_URL`) |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm or pnpm

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # add API keys or tweak ports as needed
```

### Frontend Setup
```bash
cd frontend
npm install
cp .env.example .env  # adjust API host/port if changed
```

### Run
```bash
# Option A: manual
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev

# Option B: from repo root (auto installs on first run)
./start.sh
```

Open http://localhost:5173 and API docs at http://localhost:8000/docs.

## Usage Workflow

1. Upload an English ePub to create a project
2. Set LLM provider and API key (via UI or backend `.env`)
3. Run **Analysis** to extract tone, style, and terminology
4. Run **Translation**; reference matching keeps phrasing consistent
5. Use **Proofreading** to refine outputs or edit paragraphs manually
6. **Export** a bilingual ePub and download from the UI
7. Manage prompts/reference files under `backend/prompts/` or in the UI

## Configuration

<details>
<summary><b>Backend Environment Variables</b> (<code>backend/.env</code>)</summary>

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable debug mode | `true` |
| `HOST` | Backend host | `0.0.0.0` |
| `PORT` | Backend port | `8000` |
| `FRONTEND_PORT` | Port used for CORS allowlist | `5173` |
| `DATABASE_URL` | Database URL (SQLite by default) | `sqlite+aiosqlite:///./epub_translator.db` |
| `UPLOAD_DIR` | Directory for uploaded epubs | `./uploads` |
| `OUTPUT_DIR` | Directory for generated exports | `./outputs` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic (Claude) API key | - |
| `GEMINI_API_KEY` | Google Gemini API key | - |
| `DASHSCOPE_API_KEY` | Alibaba Qwen API key | - |
| `DEEPSEEK_API_KEY` | DeepSeek API key | - |
| `OPENROUTER_API_KEY` | OpenRouter multi-provider key | - |
| `DEFAULT_CHUNK_SIZE` | Characters per translation chunk | `500` |
| `MAX_RETRIES` | Retry count for LLM calls | `3` |
| `RETRY_DELAY` | Seconds between retries | `1.0` |
| `CORS_ORIGINS` | Allowed origins list | `["http://localhost:5173"]` |

</details>

<details>
<summary><b>Frontend Environment Variables</b> (<code>frontend/.env</code>)</summary>

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_PORT` | Frontend dev server port | `5173` |
| `VITE_API_HOST` | Backend host | `localhost` |
| `VITE_API_PORT` | Backend port | `8000` |

</details>

## Project Structure

```
epub_translator/
├── backend/
│   ├── app/
│   │   ├── api/v1/routes/    # REST endpoints
│   │   ├── core/             # Pipeline + services
│   │   │   ├── analysis/     # Book analysis
│   │   │   ├── epub/         # ePub parsing/export
│   │   │   ├── llm/          # Provider adapters
│   │   │   ├── matching/     # Reference alignment
│   │   │   ├── proofreading/ # Proofreading routines
│   │   │   ├── prompts/      # Prompt loading/variables
│   │   │   └── translation/  # Translation pipeline
│   │   └── models/database/  # SQLAlchemy models
│   ├── prompts/              # Prompt templates
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/       # UI components
│       ├── pages/            # Views
│       ├── services/api/     # API client
│       ├── stores/           # Zustand state
│       └── i18n/             # EN/ZH copy
├── scripts/                  # Utility scripts
├── start.sh                  # One-shot setup + dev servers
└── tests/                    # Test fixtures
```

## API Overview

| Endpoint | Description |
|----------|-------------|
| `/api/v1/upload` | ePub upload and project creation |
| `/api/v1/analysis` | Book content analysis |
| `/api/v1/translation` | Translation workflow |
| `/api/v1/proofreading` | Proofreading suggestions |
| `/api/v1/export` | ePub export |
| `/api/v1/prompts` | Prompt template management |
| `/api/v1/llm-settings` | LLM configuration |
| `/api/v1/workflow` | Workflow state management |
| `/api/v1/reference` | Reference ePub matching |
| `/api/v1/preview` | Chapter content preview |

## Prompt Variables

Templates support `{{variable}}` substitution:

| Namespace | Variables |
|-----------|-----------|
| `project.*` | `title`, `author`, `source_language`, `target_language` |
| `content.*` | `source_text`, `paragraph_index`, `chapter_index` |
| `pipeline.*` | `existing_translation`, `reference_translation` |
| `derived.*` | `writing_style`, `tone`, `terminology_table` |
| `user.*` | Custom user-defined variables |

## License

MIT

---

# 🇨🇳 中文

基于大模型的英文 ePub 翻译工具，尽可能保留排版与语境。

## 概览

ePub Translator 是一个全栈应用，自动完成电子书的分析、翻译、校对与双语导出，可按章节跟踪状态，并支持多家大模型。

## 功能亮点

- **多模型支持**：OpenAI、Anthropic Claude、Google Gemini、阿里通义千问、DeepSeek
- **四步流程**：分析 → 翻译 → 校对 → 导出，按章节管理进度
- **风格提取**：自动识别语气、术语、写作风格
- **参考对齐**：段落与已有译文匹配，保证一致性
- **提示词管理**：系统/用户提示词支持变量与模板复用
- **双语导出**：生成包含原文与译文的 ePub
- **友好界面**：章节预览、人工微调、可重复运行各步骤

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11+、FastAPI、SQLAlchemy、Uvicorn |
| 前端 | React + Vite + TypeScript、Zustand、Ant Design |
| 存储 | 默认 SQLite，可通过 `DATABASE_URL` 替换 |

## 快速开始

### 前置依赖
- Python 3.11+
- Node.js 18+
- npm 或 pnpm

### 后端配置
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # 填入 API Key 或端口配置
```

### 前端配置
```bash
cd frontend
npm install
cp .env.example .env  # 如有端口变动请同步修改
```

### 运行
```bash
# 方案 A：分别启动
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev

# 方案 B：在仓库根目录一键启动（首次会自动安装依赖）
./start.sh
```

访问 http://localhost:5173 ，API 文档在 http://localhost:8000/docs 。

## 使用流程

1. 上传英文 ePub，创建项目
2. 在 UI 或 `.env` 中配置模型提供商与 API Key
3. **分析**：抽取语气、风格与术语表
4. **翻译**：按段落翻译，并结合参考译文保持一致性
5. **校对**：审阅与手工修改译文
6. **导出**：生成双语 ePub 并下载
7. 在 `backend/prompts/` 或界面中管理提示词与参考资源

## 配置项

<details>
<summary><b>后端环境变量</b>（<code>backend/.env</code>）</summary>

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEBUG` | 调试模式 | `true` |
| `HOST` | 后端监听地址 | `0.0.0.0` |
| `PORT` | 后端端口 | `8000` |
| `FRONTEND_PORT` | 用于生成 CORS 白名单的前端端口 | `5173` |
| `DATABASE_URL` | 数据库连接串（默认 SQLite） | `sqlite+aiosqlite:///./epub_translator.db` |
| `UPLOAD_DIR` | 上传 ePub 的存储目录 | `./uploads` |
| `OUTPUT_DIR` | 导出文件目录 | `./outputs` |
| `OPENAI_API_KEY` | OpenAI 密钥 | - |
| `ANTHROPIC_API_KEY` | Anthropic（Claude）密钥 | - |
| `GEMINI_API_KEY` | Google Gemini 密钥 | - |
| `DASHSCOPE_API_KEY` | 通义千问密钥 | - |
| `DEEPSEEK_API_KEY` | DeepSeek 密钥 | - |
| `OPENROUTER_API_KEY` | OpenRouter 多模型密钥 | - |
| `DEFAULT_CHUNK_SIZE` | 每次翻译的字符数 | `500` |
| `MAX_RETRIES` | 调用失败重试次数 | `3` |
| `RETRY_DELAY` | 重试间隔（秒） | `1.0` |
| `CORS_ORIGINS` | 允许的跨域来源 | `["http://localhost:5173"]` |

</details>

<details>
<summary><b>前端环境变量</b>（<code>frontend/.env</code>）</summary>

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VITE_PORT` | 前端开发端口 | `5173` |
| `VITE_API_HOST` | 后端 Host | `localhost` |
| `VITE_API_PORT` | 后端端口 | `8000` |

</details>

## 目录结构

```
epub_translator/
├── backend/
│   ├── app/
│   │   ├── api/v1/routes/    # REST 接口
│   │   ├── core/             # 核心流程与服务
│   │   │   ├── analysis/     # 内容分析
│   │   │   ├── epub/         # 解析与导出
│   │   │   ├── llm/          # 模型适配器
│   │   │   ├── matching/     # 参考匹配
│   │   │   ├── proofreading/ # 校对模块
│   │   │   ├── prompts/      # 提示词管理
│   │   │   └── translation/  # 翻译流水线
│   │   └── models/database/  # 数据模型
│   ├── prompts/              # 提示词模板
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/       # 组件
│       ├── pages/            # 页面
│       ├── services/api/     # API 客户端
│       ├── stores/           # 状态管理
│       └── i18n/             # 国际化
├── scripts/                  # 脚本工具
├── start.sh                  # 一键安装与启动脚本
└── tests/                    # 测试资源
```

## API 概览

| 端点 | 描述 |
|------|------|
| `/api/v1/upload` | 上传 ePub 并创建项目 |
| `/api/v1/analysis` | 书籍内容分析 |
| `/api/v1/translation` | 翻译流程 |
| `/api/v1/proofreading` | 校对建议 |
| `/api/v1/export` | ePub 导出 |
| `/api/v1/prompts` | 提示词管理 |
| `/api/v1/llm-settings` | 模型配置 |
| `/api/v1/workflow` | 流程状态管理 |
| `/api/v1/reference` | 参考译文匹配 |
| `/api/v1/preview` | 章节预览 |

## 提示词变量

模板支持 `{{variable}}` 占位符：

| 命名空间 | 变量 |
|----------|------|
| `project.*` | `title`、`author`、`source_language`、`target_language` |
| `content.*` | `source_text`、`paragraph_index`、`chapter_index` |
| `pipeline.*` | `existing_translation`、`reference_translation` |
| `derived.*` | `writing_style`、`tone`、`terminology_table` |
| `user.*` | 用户自定义变量 |

## 许可证

MIT
