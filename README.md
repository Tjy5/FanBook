# Fanbook

`Fanbook` 是一个面向本地单用户场景的 EPUB 翻译后端。它把英文 EPUB 解析成可恢复的翻译任务，使用结构化 AI Provider 完成翻译，并基于同一份结果导出：

- 中文版 EPUB
- 中英双语 EPUB
- 一致性报告 JSON / Markdown

当前后端位于 `backend/`，使用 Java 21 和 Spring Boot 构建。

## 适合什么场景

- 你想把一本英文 EPUB 翻译成中文，而不是只翻一小段文本。
- 你希望翻译过程可以中断后继续，而不是失败后从头开始。
- 你希望导出双语版本，方便校对或对照阅读。
- 你希望保留原始 EPUB 结构，而不是简单导出成纯文本。

## 功能亮点

- 只接受 EPUB 输入，围绕电子书翻译链路做了专门实现。
- 上传后解析章节、段落和原始文档位置，导出时按原结构写回。
- 按段落分块创建翻译任务，后台异步执行。
- 支持 Redis 书籍级任务锁、任务取消、失败恢复和断点续跑。
- 支持 mock Provider 和 OpenAI-compatible Provider。
- 支持中文 EPUB、双语 EPUB、JSON / Markdown 一致性报告导出。
- 提供在线阅读器，可按章节查看原文、译文或双语内容，并为段落创建笔记与导出 Markdown。
- 提供 Actuator 健康检查、OpenAPI 文档和 Docker Compose 本地运行配置。

## 当前边界

- 当前正式输入格式只有 `.epub`。
- 当前目标语言固定为中文。
- 第一阶段是本地单用户工具，不包含多用户登录、复杂权限或 MinIO profile。
- 真实模型接入通过 OpenAI-compatible Provider 配置，默认测试路径使用 mock Provider。

## 快速开始

### 环境要求

- Java 21
- Maven 3.9+
- Node.js 18+（用于本地前端静态服务和 API 代理）
- Docker 与 Docker Compose（用于 MySQL、Redis、RabbitMQ 和后端服务编排）

本仓库在自动化测试中使用 H2 MySQL compatibility mode。生产近似本地运行可使用 Docker Compose；快速开发调试也提供 `local` profile。

### 启动本地服务

Docker Compose 后端包含 MySQL、Redis、RabbitMQ 和 Spring Boot 服务：

```bash
cd backend
docker compose up --build
```

本地直启后端：

```bash
cd backend
mvn spring-boot:run -Dspring-boot.run.profiles=local
```

前端：

```bash
node frontend/dev-server.mjs --port=5173 --backend=http://localhost:8080
```

加载一本书后，前端主页可以按章节阅读原文、译文或双语内容，并为段落创建笔记。

默认地址：

- 前端：`http://localhost:5173`
- API：`http://localhost:8080`
- Health：`http://localhost:8080/actuator/health`
- OpenAPI：`http://localhost:8080/v3/api-docs`
- Swagger UI：`http://localhost:8080/swagger-ui/index.html`

### 本地测试

```bash
cd backend
mvn test
```

## 配置

`backend/src/main/resources/application.yml` 提供本地默认值。常用环境变量如下：

```bash
FANBOOK_DATASOURCE_URL=jdbc:mysql://localhost:3306/fanbook?serverTimezone=UTC
FANBOOK_DATASOURCE_USERNAME=fanbook
FANBOOK_DATASOURCE_PASSWORD=fanbook
FANBOOK_REDIS_HOST=localhost
FANBOOK_REDIS_PORT=6379
FANBOOK_RABBITMQ_HOST=localhost
FANBOOK_RABBITMQ_PORT=5672
FANBOOK_RABBITMQ_USERNAME=fanbook
FANBOOK_RABBITMQ_PASSWORD=fanbook
FANBOOK_STORAGE_ROOT=./runtime/storage
FANBOOK_AI_PROVIDER=mock
FANBOOK_AI_BASE_URL=https://api.openai.com/v1
FANBOOK_AI_API_KEY=
FANBOOK_AI_MODEL=mock-translator
```

如需启用 OpenAI-compatible Provider：

```bash
FANBOOK_AI_PROVIDER=openai-compatible
FANBOOK_AI_BASE_URL=https://api.openai.com/v1
FANBOOK_AI_API_KEY=sk-xxxxx
FANBOOK_AI_MODEL=<model-name>
```

## API 概览

核心接口如下：

```text
POST /api/books
POST /api/books/{bookId}/translation-jobs
GET  /api/translation-jobs/{jobId}
POST /api/books/{bookId}/translation-jobs/resume
POST /api/translation-jobs/{jobId}/cancel
GET  /api/books/{bookId}/reader/info
GET  /api/books/{bookId}/chapters
GET  /api/books/{bookId}/chapters/{chapterId}/segments?mode=bilingual
POST /api/segments/{segmentId}/notes
GET  /api/segments/{segmentId}/notes
PUT  /api/notes/{noteId}
DELETE /api/notes/{noteId}
GET  /api/books/{bookId}/notes/export
GET  /api/books/{bookId}/exports/zh
GET  /api/books/{bookId}/exports/bilingual
GET  /api/books/{bookId}/reports/consistency
GET  /api/books/{bookId}/reports/consistency.md
GET  /actuator/health
GET  /v3/api-docs
```

`POST /api/books` 使用 `multipart/form-data` 上传 EPUB 文件，字段名为 `file`，可选参数 `sourceLanguage` 默认为 `en`。

## 它是怎么工作的

### 1. EPUB 解析

系统读取 `container.xml`、OPF spine 和章节文档，把正文拆成带定位信息的段落。每个段落会保留章节、顺序、类型和原文内容，供翻译任务和导出阶段使用。

### 2. 分块翻译

系统按段落创建 chunk，把待翻译段落交给 AI Provider。mock Provider 用于测试和演示，OpenAI-compatible Provider 通过 `/responses` 接口请求结构化输出。

### 3. 持久化与恢复

翻译状态写入 MySQL，本地文件 storage 保存原始 EPUB、导出 EPUB 和一致性报告。任务中断后可以恢复，不需要从头开始。

### 4. 导出

导出阶段基于同一份翻译结果生成中文版 EPUB、中英双语 EPUB，以及 JSON / Markdown 一致性报告。

## 项目结构

```text
FanBook/
├── backend/       # Spring Boot 后端、数据库迁移、测试和 Docker Compose
├── frontend/      # 前端静态资源
├── docs/          # 设计规格和执行计划（本地忽略）
├── samples/       # 样例文件（本地忽略）
└── README.md
```

## 运行时数据

默认运行时目录是 `backend/runtime/storage`（通过 `FANBOOK_STORAGE_ROOT` 可改）。这里会存放：

- 上传的原始 EPUB
- 导出的中文 EPUB
- 导出的双语 EPUB
- 一致性报告

## 适合贡献者了解的事实

- 当前主链路围绕 EPUB 设计，不是通用多格式导入器。
- Java 后端包结构按 `book`、`translation`、`ai`、`export`、`storage`、`common` 划分。
- 自动化测试使用 H2 的 MySQL 兼容模式；生产近似本地运行可通过 Docker Compose 编排 MySQL、Redis 和后端服务。
- 扩展模型接入时，优先从 `backend/src/main/java/com/fanbook/ai/` 开始。

## License

仓库当前未声明许可证。在复用代码或分发修改版之前，建议先补充明确的 `LICENSE` 文件。
