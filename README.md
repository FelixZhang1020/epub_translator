# EPUB Translator - 双语翻译工具

将英文 EPUB 翻译成中英双语 EPUB，每个英文段落后附带中文翻译。

## 功能特点

- **两种翻译模式**
  - 基于作者背景翻译：根据作者背景和自定义提示词进行全新翻译
  - 优化已有翻译：基于已有中文翻译，优化使其更符合现代语言习惯

- **多 LLM 支持**
  - OpenAI (GPT-4o, GPT-4o-mini)
  - Claude (Anthropic)
  - Google Gemini
  - 通义千问 (Qwen)

- **断点续传**
  - 支持暂停/恢复翻译
  - 翻译进度实时保存

- **双语预览**
  - 实时预览翻译结果
  - 支持手动编辑翻译

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- npm 或 yarn

### 安装运行

```bash
# 克隆项目
git clone <repo-url>
cd epub_translate

# 一键启动
chmod +x start.sh
./start.sh
```

或分别启动：

```bash
# 启动后端
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# 启动前端（新终端）
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

### 配置 LLM

1. 打开设置页面
2. 选择 LLM 提供商（OpenAI/Claude/Gemini/Qwen）
3. 输入 API 密钥
4. 测试连接

## 使用流程

1. **上传 EPUB** - 上传英文 EPUB 文件
2. **配置翻译** - 选择翻译模式，填写作者背景（可选）
3. **开始翻译** - 点击开始，查看实时进度
4. **预览编辑** - 预览双语结果，手动修改翻译
5. **导出 EPUB** - 导出双语 EPUB 文件

## 项目结构

```
epub_translate/
├── backend/           # Python FastAPI 后端
│   ├── app/
│   │   ├── api/       # API 路由
│   │   ├── core/      # 核心逻辑
│   │   │   ├── epub/  # EPUB 解析/生成
│   │   │   ├── llm/   # LLM 适配器
│   │   │   └── translation/  # 翻译编排
│   │   └── models/    # 数据模型
│   └── requirements.txt
│
├── frontend/          # React + TypeScript 前端
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── stores/
│   └── package.json
│
├── start.sh           # 一键启动脚本
└── README.md
```

## 技术栈

**后端**
- FastAPI + Python 3.11
- SQLAlchemy + SQLite
- ebooklib + BeautifulSoup

**前端**
- React 18 + TypeScript
- Vite + Tailwind CSS
- Zustand + TanStack Query

## License

MIT
