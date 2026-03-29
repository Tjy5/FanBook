# Fanbook - 英文书翻译成中文

## 这是什么？

一个网页工具，把英文 EPUB 电子书翻译成中文。翻译完能导出两个版本：
- **纯中文版**：只有中文译文
- **双语对照版**：原文和译文一起显示（原文是半透明的）

## 怎么用？

### 1. 启动
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

浏览器打开：http://localhost:8000/

### CLI 模式

也可以直接在命令行里跑。现在最适合新手的是直接进入菜单：

```bash
python -m backend.cli
```

启动后会看到：

```text
1. 翻译一本书
2. 查看进度
3. 恢复翻译
4. 导出结果
5. 退出
```

如果是在正常终端里直接运行，现在也支持：

- `↑ / ↓` 选择菜单项
- `Enter` 确认
- 在书籍选择和导出类型选择里也可以直接用方向键操作
- `Esc` 或 `q` 返回上一级（仅交互菜单）

如果你更喜欢命令式用法，也可以直接这样执行：

```bash
python -m backend.cli translate path/to/book.epub --runtime-root temp/.fanbook-cli
python -m backend.cli status 1 --runtime-root temp/.fanbook-cli
python -m backend.cli export 1 --kind all --runtime-root temp/.fanbook-cli
python -m backend.cli resume 1 --runtime-root temp/.fanbook-cli
```

- `translate`：从本地 `EPUB` 创建书籍、启动翻译，并默认阻塞到完成
- `status`：查看书籍、任务、章节和导出产物状态
- `export`：构建或获取 `zh`、`bilingual`、`consistency_report` 路径
- `resume`：恢复未完成的翻译任务
- `--no-wait` 当前仅作为兼容参数保留；CLI 仍会等待任务完成，避免进程退出后丢失翻译任务

### 工作区约定

- `backend/`、`frontend/`、`tests/`、`docs/` 是主要源码和文档目录
- `samples/` 用来放需要长期保留的本地样本书
- `temp/` 只放运行时、测试和 benchmark 产物；应用未运行时可以按需清理
- `reference-projects/` 保留为只读参考材料，不参与当前应用运行

### 远程参考排除约定

- 做 AI 远程参考、远程索引或上传上下文时，默认只纳入当前项目运行所需的源码
- 默认排除：`.env`、`.venv/`、`temp/`、`samples/`、整个 `docs/`、`pytest` 缓存/运行目录、整个 `reference-projects/`，以及根目录的 `PROJECT.md`、`AGENTS.md`

### 2. 配置翻译 API

复制 `.env.example` 改名为 `.env`，填上你的 API key：
```bash
FANBOOK_TRANSLATION_PROVIDER=openai
FANBOOK_TRANSLATION_MODEL=gpt-5.4
FANBOOK_TRANSLATION_RUNTIME_PROFILE=generic_safe
FANBOOK_TRANSLATION_API_KEY=sk-xxxxx
```

`runtime_profile` 用来决定运行时策略，`model` 只负责模型路由。默认建议先用 `generic_safe`，确认 endpoint 稳定后再切到更激进的档位。

注意：

- 显式设置 `runtime_profile` 会优先于自动探测、target override 和 model family fallback。
- 也就是说，只要你在 `.env` 或 profile 里写死了 `*_RUNTIME_PROFILE`，系统就不会再按 endpoint / model 能力自动改成别的 `generic_*` 档位。
- 如果你希望“同一套配置随着不同模型 / endpoint 自动选档”，应该留空 `*_RUNTIME_PROFILE`，只提供 `model`、`base_url` 和能力探测开关。

当前内置的通用档位：

- `generic_safe`：未知模型或首次接入，保守 chunk 和并发，稳定优先
- `generic_large_context`：已知大上下文模型，允许更大的输入预算
- `generic_low_latency`：低延迟优先，适合快速失败和快速回退
- `generic_reasoning`：thinking / reasoning 模型，保留更多上下文余量并降低并发
- `generic_rate_limited`：RPM 严格受限的 endpoint，偏向低并发和限速控制

如果你想在网页里切换多套翻译配置，可以在 `.env` 里定义多个 profile：
```bash
FANBOOK_TRANSLATION_PROFILES=fast,cheap
FANBOOK_TRANSLATION_DEFAULT_PROFILE=fast

FANBOOK_TRANSLATION_PROFILE_FAST_PROVIDER=openai
FANBOOK_TRANSLATION_PROFILE_FAST_MODEL=gpt-5.4
FANBOOK_TRANSLATION_PROFILE_FAST_RUNTIME_PROFILE=generic_large_context
FANBOOK_TRANSLATION_PROFILE_FAST_API_MODE=responses
FANBOOK_TRANSLATION_PROFILE_FAST_API_KEY=sk-fast-xxxxx
FANBOOK_TRANSLATION_PROFILE_FAST_MAX_REQUESTS_PER_MINUTE=60
FANBOOK_TRANSLATION_PROFILE_FAST_MAX_CONCURRENCY=24

FANBOOK_TRANSLATION_PROFILE_CHEAP_PROVIDER=openai
FANBOOK_TRANSLATION_PROFILE_CHEAP_MODEL=deepseek-chat
FANBOOK_TRANSLATION_PROFILE_CHEAP_RUNTIME_PROFILE=generic_rate_limited
FANBOOK_TRANSLATION_PROFILE_CHEAP_API_MODE=chat_completions
FANBOOK_TRANSLATION_PROFILE_CHEAP_API_KEY=sk-cheap-xxxxx
FANBOOK_TRANSLATION_PROFILE_CHEAP_MAX_REQUESTS_PER_MINUTE=30
FANBOOK_TRANSLATION_PROFILE_CHEAP_MAX_CONCURRENCY=10
```

启动后，页面里的“翻译配置档”下拉框会列出这些 profile，开始翻译和恢复任务时都可以选用其中一套。

如果 endpoint 已知能力，也可以补充运行时元信息，帮助系统选档或记录 benchmark：

```bash
FANBOOK_TRANSLATION_DETECTED_CONTEXT_WINDOW=128000
FANBOOK_TRANSLATION_STRUCTURED_OUTPUT_STRENGTH=high
FANBOOK_TRANSLATION_REASONING_MODE=off
```

这些字段是运行时信号，不会替代 `model` 本身。

如果你没有手工补这些字段，系统现在会优先尝试对兼容 endpoint 发一次低成本的 `GET /models` 探测，并在运行时目录和当前进程内缓存结果；能识别到常见扩展 metadata 时会自动补 `api_mode`、`detected_context_window`、`structured_output_strength`、`reasoning_mode`，如果 `/models` 只返回标准 `id` 列表，则会再尝试用一小层本地已知模型目录补 `detected_context_window`。当 `/models` 仍不足以确认关键能力时，还会补一轮极小流量的真实 probe 请求去验证 `api_mode`、structured output 和 reasoning 支持，并把高可信结论缓存起来。

这个自动探测只在没有显式锁定 `runtime_profile` 时参与最终选档；如果你已经写死 `*_RUNTIME_PROFILE`，探测结果仍会记录下来，但不会改写当前预设。

如果你想关掉或收紧这一步，可以配置：

```bash
FANBOOK_TRANSLATION_ENDPOINT_CAPABILITY_DETECTION_ENABLED=true
FANBOOK_TRANSLATION_ENDPOINT_CAPABILITY_DETECTION_TIMEOUT_SECONDS=5
FANBOOK_TRANSLATION_ENDPOINT_CAPABILITY_DETECTION_TTL_SECONDS=1800
```

运行结束后，checkpoint 和 benchmark 的 `runtime_settings` 里会带上 `runtime_setting_sources`，用于标记每个关键 runtime 值来自 `provider_config`、`request_override`、`runtime_profile:*`、推断链路还是归一化约束。高可信探测自动解析出的 `runtime_profile` 还会按 `model@base_url` 写入运行时 override store，后续运行可以直接复用。

如果你已经跑过本地 benchmark，并且想把报告整理成“是否值得加 curated override”的建议，可以使用：

```powershell
python -m backend.benchmark.cli suggest-overrides `
  --report-glob "temp/benchmark_results/*.json" `
  --output-dir temp\benchmark_override_suggestions `
  --suggestion-name current-run
```

这个工具会优先读取 benchmark JSON；如果只给 Markdown，它会优先复用同名 JSON，或者退回解析 Markdown。旧报告如果缺少 target 信息，可以额外补 `--base-url https://your-endpoint/v1`。当前版本 benchmark 报告现在也会额外记录：

- `provider_base_url`
- `override_target_key`
- `models_endpoint`
- `endpoint_capability_strategy`
- `endpoint_capability_confidence`
- `deep_probe_status`
- `requested_provider_options`
- `requested_provider_option_sources`

这样后续可以更稳定地按 `model@base_url` 聚合证据，而不是只看模型名。

如果你现在更关心“通用 benchmark 基线”，而不是某个模型的专项报告，可以使用：

```powershell
python -m backend.benchmark.cli summarize-baselines `
  temp\benchmark_results `
  --output-dir temp\benchmark_baselines `
  --summary-name baseline-by-runtime-profile-and-capability-tier
```

这个汇总会按两层来组织现有报告：

- `runtime_profile`
- `capability_tier`

其中 `capability_tier` 是从这些通用能力信号本地归一出来的分组键：

- `api_mode`
- `reasoning_mode`
- `structured_output_strength`
- `detected_context_window`
- `max_requests_per_minute`

因此扩样时可以先看“哪个 `runtime_profile / capability_tier` 组合缺 target 覆盖”，而不是先盯着 `gpt-5.4` 之类的单模型报告。

### 3. 使用流程
1. 上传 EPUB 文件
2. 点"开始翻译"
3. 等翻译完成（可以中途关闭，下次继续）
4. 下载中文版或双语版

## 它是怎么工作的？

### 第一步：拆书

上传 EPUB 后，系统会：
1. 解压 EPUB（其实就是个 ZIP 文件）
2. 找到所有章节文件（按顺序）
3. 从每个章节里提取段落

**关键点**：每个段落不只保存文字，还记录它在原文件里的**精确位置**。

比如这段 HTML：
```html
<p>This is <em>important</em> text.</p>
```

系统会记录：
- 第 1 块文字 "This is " 在 `<p>` 标签里
- 第 2 块文字 "important" 在 `<em>` 标签里
- 第 3 块文字 " text." 在 `<em>` 标签后面

为什么要这么麻烦？因为翻译完要**原样写回去**，不能破坏原来的格式。

### 第二步：分组翻译

不是一句一句翻译，而是**把多个段落打包一起翻**。

为什么？
- 一次翻多段，AI 能看到上下文，翻得更连贯
- 减少 API 调用次数，省钱省时间

怎么分组？
- 按 token 数量控制，不超过模型限制
- 同一章节的段落尽量放一起
- 太长的段落会自动拆分

### 第三步：调用 AI 翻译

发给 OpenAI（或其他兼容 API）：
```
请翻译这 5 个段落：
1. Hello world
2. How are you
3. ...

参考信息：
- 前面翻译过的内容：...
- 专有名词对照表：Judge Stone = 斯通法官
```

AI 返回：
```
1. 你好世界
2. 你好吗
3. ...
```

### 第四步：保存结果

每翻译完一组段落，立即存到数据库。所以：
- 中途关闭没关系，已翻译的不会丢
- 下次打开继续翻译剩下的

### 第五步：导出 EPUB

**中文版**：
1. 打开原始 EPUB 文件
2. 根据之前记录的位置，把原文替换成译文
3. 打包成新的 EPUB

**双语版**：
1. 替换译文之前，先复制一份原文
2. 把复制的原文设置成半透明
3. 原文和译文都保留，一上一下显示

## 核心技术点

### 为什么能精确替换文字？

因为保存了每个段落的"地址"：
```python
{
  "path": "/html[1]/body[1]/p[3]",  # 第 3 个 <p> 标签
  "slot": "text"  # 标签里的文字（不是标签后面的）
}
```

导出时按这个地址找到原文位置，直接替换。

### 为什么要分块翻译？

假设一本书有 4520 个段落：
- 逐句翻译：调用 4520 次 API，慢且贵
- 分块翻译：调用 300-500 次，快且便宜

而且分块翻译时，AI 能看到前后文，翻译质量更好。

### 怎么保证不翻译坏？

1. **验证原文没变**：翻译前算个哈希值，导出时再算一次，不一致就跳过
2. **失败自动重试**：翻译失败会自动拆小块重试
3. **跳过特殊内容**：代码块、脚本、样式表不翻译

## 项目结构

```
fanbook/
├── backend/
│   ├── api/              # 网页接口
│   ├── core/
│   │   ├── epub/         # 拆书和导出
│   │   ├── providers/    # 对接翻译 API
│   │   └── translation/  # 翻译调度
│   ├── storage/          # 数据库
│   └── services/         # 业务逻辑
├── frontend/             # 网页界面
├── samples/              # 长期保留的本地样本书
├── temp/                 # 可再生成的运行时和 benchmark 产物
├── reference-projects/   # 只读参考项目
└── tests/                # 测试
```

## 常见问题

**Q: 支持哪些翻译 API？**
A: 目前支持 OpenAI 和兼容 OpenAI 格式的 API（如 DeepSeek、通义千问等）

**Q: 翻译到一半断网了怎么办？**
A: 没关系，重新打开继续翻译，已完成的不会重复翻

**Q: 能翻译 PDF 吗？**
A: 目前只支持 EPUB

**Q: 双语版是什么样的？**
A: 原文和译文都显示，原文是半透明的灰色，译文是正常黑色

**Q: 会破坏原书的格式吗？**
A: 不会，系统会精确定位每个文字的位置，原样写回

## 技术细节

- **后端**：Python + FastAPI
- **数据库**：SQLite
- **前端**：原生 JavaScript
- **EPUB 处理**：xml.etree.ElementTree + zipfile
- **并发控制**：ThreadPoolExecutor + `runtime_profile` / 显式覆盖

## 运行测试

```bash
python -m pytest tests/unit tests/integration -q
```

## 参考文档

- [PROJECT.md](./PROJECT.md) - 详细技术文档
- [docs/translation-speed-optimization-plan.md](./docs/translation-speed-optimization-plan.md) - `gpt-5.4 + right.codes/codex` 历史专项 benchmark 记录，已收口，默认不作为当前执行清单
- [docs/generic-model-optimization-plan.md](./docs/generic-model-optimization-plan.md) - 通用 runtime / benchmark baseline 维护态状态文档，只有出现新的 reopen 条件时才继续推进
