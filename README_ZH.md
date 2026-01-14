<h1 align="center">📖 ePub Translator</h1>

<div align="center">
  <a href="https://github.com/FelixZhang1020/epub_translator/stargazers"><img src="https://img.shields.io/github/stars/FelixZhang1020/epub_translator?style=flat-square" alt="GitHub Stars"></a>
  <a href="https://github.com/FelixZhang1020/epub_translator/actions"><img src="https://img.shields.io/badge/CI-status-grey?style=flat-square" alt="CI Status"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square" alt="License: MIT"></a>
  <a><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a><img src="https://img.shields.io/badge/Node.js-18+-339933?style=flat-square&logo=nodedotjs&logoColor=white" alt="Node.js 18+"></a>
</div>

<div align="center">

**[English](README.md) · [License](LICENSE) · [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md) · [Security](SECURITY.md)**

</div>

---

基于大模型的英文 ePub 翻译工具，尽可能保留排版与语境。为规避版权风险，导出仅支持 PDF/HTML 纯文本（不再提供 ePub）。

## 项目背景

在长期的学习和专业阅读过程中，我反复遇到一个现实问题：真正构成某些领域基础结构的书，却往往缺乏可以长期依赖的中文版本。

例如，The Anxiety of Influence（Harold Bloom，1973 年）提出了“影响的焦虑”这一核心理论，深刻塑造了英语世界对文学传统、原创性与经典形成机制的理解，至今仍是文学研究和写作理论中被高度引用的著作。但在中文世界，这本书长期面临的现实是：理论术语高度抽象，不同译介中概念处理差异较大，缺乏一种可以稳定对照原文、反复精读的阅读方式，使得它常常只停留在“被提及”，而难以真正被理解和消化。

又如，The Presentation of Self in Everyday Life（Erving Goffman，1956 年）以“舞台”“角色”“情境”等隐喻重新定义了社会互动的理解方式，对社会学、人类学、传播学乃至当代文化研究产生了跨学科影响。然而在实际使用中，这类作品的中文阅读痛点在于：译本语言风格差异较大，关键概念在不同章节甚至不同版本中缺乏一致性，对需要系统学习和引用的读者而言，阅读和回溯成本始终很高。

再如，Church Dogmatics（Karl Barth，1932–1967 年陆续出版），通常被视为二十世纪最具影响力的系统性思想著作之一，在思想深度、结构规模和历史地位上，常被认为可与加尔文《基督教要义》相媲美。但这样一部奠基性作品，对许多中文读者而言，真正的障碍并不在于内容本身，而在于：体量巨大、翻译难度极高，现有中文资源零散且不便于整体对照阅读，使得持续、完整的学习几乎难以实现。

这些书在各自领域中都不是“冷门书”，而是被反复引用、反复依赖的思想源头。对真正需要它们的人来说，问题并不在于是否愿意阅读原文，而在于：是否有一种现实可行的方式，能在尊重版权的前提下，支持长期、稳定、可回溯的对照阅读。

正是基于这样的个人阅读体验，我开始自己动手做这款 ePub 翻译工具。在 GitHub 上寻找解决方案时，我很少看到工具真正围绕原文—译文对照、精读和长期学习来设计，于是借助 Claude Code 从零实现了一套流程，希望它能服务于像我一样需要高质量专业资料，却长期受限于语言与译本条件的读者。

出于对版权的尊重，也为了尽量降低风险，所有译文仅限在工具内进行原文—译文对照查看，或导出为 PDF/HTML 的纯文本形式，不支持直接生成或传播 ePub 文件。

## 关于提示词工程

本工具内置了一套经过实践验证的通用翻译指引、流程约束，以及成体系的提示词工程与参数配置，这些能力本身已经可以显著优于“随手写提示词直接翻译”的效果，并为整本书的翻译提供稳定的质量下限。

在此基础上，翻译效果还会受到两个因素的共同影响：
一是所使用大语言模型的能力水平，它决定了语言理解、长距离一致性和复杂句式处理的上限；
二是针对具体书籍的提示词设计，它直接影响术语选择、风格控制和整体可读性。

因此，本项目并非只是一个空壳框架，而是一套具备明确能力基线的翻译系统。同时，它也刻意为进阶用户保留了空间：当提示词能够针对某一本书进行细化和定制时，翻译质量仍然可以在既有基础上进一步提升。

## 概览

ePub Translator 是一个全栈应用，自动完成电子书的分析、翻译、校对与双语导出，可按章节跟踪状态，并支持多家大模型。

## 功能亮点

- **多模型支持**：OpenAI、Anthropic Claude、Google Gemini、阿里通义千问、DeepSeek
- **四步流程**：分析 → 翻译 → 校对 → 导出，按章节管理进度
- **风格提取**：自动识别语气、术语、写作风格
- **参考对齐**：段落与已有译文匹配，保证一致性
- **提示词管理**：系统/用户提示词支持变量与模板复用
- **纯文本导出**：仅支持 PDF/HTML（含原文与译文），避免版权风险
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
6. **导出**：生成双语 PDF/HTML 纯文本（不支持 ePub）并下载
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
| `UPLOAD_DIR` | 临时上传目录 | `data/temp/uploads` |
| `OUTPUT_DIR` | 临时输出目录 | `data/temp/outputs` |
| `MAX_UPLOAD_SIZE_MB` | 最大上传文件大小（MB） | `100` |
| `API_AUTH_TOKEN` | API 认证令牌（可选） | - |
| `REQUIRE_AUTH_ALL` | 对所有端点启用认证 | `false` |
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
| `/api/v1/export` | PDF/HTML 纯文本导出 |
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
