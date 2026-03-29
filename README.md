# Fanbook

`Fanbook` 是一个面向本地单用户场景的 `EPUB` 翻译工具。它把英文 `EPUB` 解析成可恢复的翻译任务，调用大模型完成翻译，并基于同一份结果导出：

- 中文版 `EPUB`
- 中英双语 `EPUB`
- 一致性报告 `JSON / Markdown`

它提供两种使用方式：

- `Web UI`：上传、查看进度、恢复任务、下载结果
- `CLI`：交互菜单和命令式调用

## 适合什么场景

- 你想把一本英文 `EPUB` 翻译成中文，而不是只翻一小段文本
- 你希望翻译过程可以中断后继续，而不是失败后从头开始
- 你希望导出双语版本，方便校对或对照阅读
- 你希望保留原始 `EPUB` 结构，而不是简单导出成纯文本

## 功能亮点

- 只接受 `EPUB` 输入，围绕电子书翻译链路做了专门实现
- 上传后自动解析章节、段落和原始文档位置，导出时按原结构写回
- 按 token 预算把段落分块翻译，兼顾上下文、吞吐量和模型限制
- 翻译结果实时落盘，支持 checkpoint 和恢复
- 同时生成中文导出、双语导出和一致性报告
- 前端可选择后端提供的翻译配置档，适合多模型或多 endpoint 切换
- 内置 `openai` 和 `mock` provider；`openai` 支持自定义 `base_url`

## 当前边界

- 当前正式输入格式只有 `.epub`
- 当前目标语言固定为中文
- 内置 provider 只有 `openai` 和 `mock`
- 正式导出要求整本书全部翻译完成后才能生成
- 这是本地单用户应用，不是面向多租户部署的平台

## 快速开始

### 1. 克隆并安装依赖

```bash
git clone https://github.com/Tjy5/FanBook.git
cd FanBook
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. 配置模型

把 `.env.example` 复制成 `.env` 后，至少填写这些字段：

```bash
FANBOOK_TRANSLATION_PROVIDER=openai
FANBOOK_TRANSLATION_MODEL=gpt-5.4
FANBOOK_TRANSLATION_API_KEY=sk-xxxxx
FANBOOK_TRANSLATION_RUNTIME_PROFILE=generic_safe
```

常用说明：

- `FANBOOK_TRANSLATION_PROVIDER`：当前正式支持 `openai` 和 `mock`
- `FANBOOK_TRANSLATION_MODEL`：模型名
- `FANBOOK_TRANSLATION_API_KEY`：接口密钥
- `FANBOOK_TRANSLATION_BASE_URL`：可选，自定义兼容 endpoint
- `FANBOOK_TRANSLATION_RUNTIME_PROFILE`：运行时策略预设

内置运行时预设：

- `generic_safe`
- `generic_large_context`
- `generic_low_latency`
- `generic_reasoning`
- `generic_rate_limited`
- `novel_consistency`

如果你不想手动固定运行时预设，可以把 `FANBOOK_TRANSLATION_RUNTIME_PROFILE` 留空，让系统按 endpoint 能力和模型特征自动选档。更完整的配置项请看 [.env.example](./.env.example)。

### 3. 启动服务

```bash
uvicorn main:app --reload
```

默认打开：

- Web 页面：`http://localhost:8000/`
- API：`http://localhost:8000/api/*`

## Web 使用流程

1. 打开首页并上传一本英文 `EPUB`
2. 系统创建书籍记录并解析章节
3. 选择翻译配置档，启动翻译任务
4. 页面会轮询刷新任务进度和章节状态
5. 如果任务中断，可以直接恢复
6. 翻译完成后下载：
   - 中文 `EPUB`
   - 中英双语 `EPUB`
   - 一致性报告

## CLI 用法

### 交互模式

```bash
python -m backend.cli
```

交互菜单支持：

- 选择书籍
- 启动翻译
- 查看进度
- 恢复任务
- 导出结果

### 命令模式

```bash
python -m backend.cli translate path/to/book.epub --runtime-root temp/.fanbook-cli
python -m backend.cli status 1 --runtime-root temp/.fanbook-cli
python -m backend.cli resume 1 --runtime-root temp/.fanbook-cli
python -m backend.cli export 1 --kind all --runtime-root temp/.fanbook-cli
```

说明：

- `translate`：导入一本本地 `EPUB` 并启动翻译
- `status`：查看书籍、任务、章节和产物状态
- `resume`：恢复未完成任务
- `export`：导出 `zh`、`bilingual` 或 `consistency_report`

## API 概览

核心接口如下：

```text
GET  /api/health
GET  /api/providers
POST /api/books
GET  /api/books/{book_id}
GET  /api/books/{book_id}/resume
POST /api/books/{book_id}/translate
POST /api/books/{book_id}/resume
GET  /api/books/{book_id}/exports/zh
GET  /api/books/{book_id}/exports/bilingual
GET  /api/books/{book_id}/reports/consistency
GET  /api/books/{book_id}/reports/consistency.md
```

`POST /api/books` 使用 `base64` 上传 `EPUB` 内容；前端已经封装了这一步。如果你要从外部系统调用，建议先查看 [backend/api/app.py](./backend/api/app.py) 里的请求模型和返回结构。

## 它是怎么工作的

### 1. EPUB 解析

系统会读取 `container.xml`、`OPF spine` 和章节文档，把正文拆成带定位信息的段落。每个段落除了文本内容，还会保留：

- 所在文档路径
- 所在 block 路径
- 内联文本片段位置
- 写回时需要的结构信息

这使得导出阶段可以把译文写回原始 `EPUB` 结构，而不是粗暴重排整本书。

### 2. 分块翻译

系统不会简单按“一个段落一次请求”处理，而是：

- 按 token 预算分块
- 尽量保持同章节上下文
- 为 chunk 注入前后文、glossary 和近期翻译记忆
- 在过长或失败时做回退拆分

### 3. 持久化与恢复

翻译过程中的状态会写入 `SQLite + 文件系统`：

- 书籍、章节、段落
- 任务状态和进度
- chunk checkpoint
- 导出产物
- 一致性报告

因此任务中断后可以恢复，而不需要从头开始。

### 4. 导出

导出阶段使用同一份翻译结果生成：

- 中文版 `EPUB`
- 中英双语 `EPUB`

同时生成一致性报告，方便检查专名或术语是否前后统一。

## 项目结构

```text
FanBook/
├── backend/      # FastAPI、翻译编排、持久化、导出
├── frontend/     # 单页前端
├── tests/        # 单元测试和集成测试
├── .env.example  # 配置示例
├── main.py       # 应用入口
└── requirements.txt
```

## 运行测试

```bash
python -m pytest tests/unit tests/integration -q
```

## 运行时数据

默认运行时目录是 `temp/.fanbook-runtime`。这里会存放：

- 数据库
- 上传的原始书籍
- checkpoint
- 导出结果
- 一致性报告

如需改位置，可以设置：

```bash
FANBOOK_RUNTIME_ROOT=/path/to/runtime
```

## 适合贡献者了解的事实

- 当前主链路围绕 `EPUB` 设计，不是通用多格式导入器
- 当前前端采用轮询刷新，不是实时推送
- `openai` provider 是当前真实翻译主路径，`mock` 主要用于测试
- 如果你要扩模型接入，优先从 `backend/core/providers/` 和 `backend/config/env_provider.py` 开始

## License

仓库当前未声明许可证。在复用代码或分发修改版之前，建议先补充明确的 `LICENSE` 文件。
