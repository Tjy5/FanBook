# Fanbook

`Fanbook` 是一个面向私有团队部署的 EPUB 翻译系统。它把英文 EPUB 解析成可恢复的翻译任务，使用结构化 AI Provider 完成翻译，并基于同一份结果导出：

- 中文版 EPUB
- 中英双语 EPUB
- 一致性报告 JSON / Markdown

当前后端位于 `backend/`，使用 Java 21 和 Spring Boot 构建；前端位于 `frontend/`，使用 Vite + React + TypeScript 构建。

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
- 提供本地账号登录、服务端 Cookie Session、CSRF 保护、角色权限、Actuator 健康检查、OpenAPI 文档和 Docker Compose 私有部署配置。

## 当前边界

- 当前正式输入格式只有 `.epub`。
- 当前目标语言固定为中文。
- 当前目标是单团队共享 workspace 的私有部署，不是公开 SaaS。
- 内置本地账号体系，角色为 `ADMIN`、`MEMBER`、`VIEWER`。
- MySQL 存关系型数据、文本段落、任务状态和导出元数据；本地文件系统存上传 EPUB 和导出 artifact。
- S3/MinIO、OIDC/JWT Resource Server、公开注册、计费和公网防滥用不在当前范围。
- 真实模型接入通过 OpenAI-compatible Provider 配置，默认测试路径使用 mock Provider。

## 快速开始

### 环境要求

- Java 21
- Maven 3.9+
- Node.js 22+ / npm 11+（用于 Vite 前端开发、测试和构建）
- Docker 与 Docker Compose（用于 MySQL、Redis、RabbitMQ 和后端服务编排）

本仓库在自动化测试中使用 H2 MySQL compatibility mode。生产近似本地运行可使用 Docker Compose；快速开发调试也提供 `local` profile。

### 启动本地服务

Docker Compose 后端包含 MySQL、Redis、RabbitMQ 和 Spring Boot 服务。私有部署需要先准备 `.env`，不要使用默认弱密码：

```bash
cd backend
cp .env.example .env
# 编辑 .env，至少填写数据库、RabbitMQ 和首个管理员密码
```

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
cd frontend
npm install
FANBOOK_BACKEND_URL=http://localhost:8080 npm run dev
```

Windows PowerShell 可用：

```powershell
cd frontend
npm install
$env:FANBOOK_BACKEND_URL='http://localhost:8080'; npm run dev
```

前端会通过 Vite dev server 代理 `/api` 到后端。加载一本书后，前端主页可以按章节阅读原文、译文或双语内容，并为段落创建笔记。`frontend/dev-server.mjs` 仍保留给轻量静态代理测试，但推荐开发入口是 Vite。

只想预览前端界面时，可以使用内置 mock API，不需要启动 Java 后端。开两个终端：

```bash
cd frontend
npm run mock-api
```

```bash
cd frontend
npm run dev
```

mock API 的固定登录账号仅用于本地界面预览：

```text
用户名：1
密码：1
```

默认地址：

- 前端：`http://localhost:5173`
- API：`http://localhost:8080`
- Health：`http://localhost:8080/actuator/health`
- OpenAPI：`http://localhost:8080/v3/api-docs`（`prod` profile 默认关闭）
- Swagger UI：`http://localhost:8080/swagger-ui/index.html`（`prod` profile 默认关闭）

### 本地测试

```bash
cd backend
mvn test
```

```bash
cd frontend
npm test
npm run typecheck
npm run build
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

私有部署必须显式管理这些 secret，不要提交到 Git：

```bash
FANBOOK_MYSQL_ROOT_PASSWORD=<random-root-password>
FANBOOK_DATASOURCE_USERNAME=fanbook
FANBOOK_DATASOURCE_PASSWORD=<random-db-password>
FANBOOK_RABBITMQ_USERNAME=fanbook
FANBOOK_RABBITMQ_PASSWORD=<random-rabbitmq-password>
FANBOOK_BOOTSTRAP_ADMIN_USERNAME=admin
FANBOOK_BOOTSTRAP_ADMIN_PASSWORD=<initial-admin-password>
FANBOOK_BOOTSTRAP_ADMIN_EMAIL=admin@example.test
FANBOOK_SESSION_TIMEOUT=30m
FANBOOK_STORAGE_ROOT=/app/runtime/storage
```

首次启动时，如果数据库中还没有 `ADMIN` 用户，后端会用 `FANBOOK_BOOTSTRAP_ADMIN_USERNAME` 和 `FANBOOK_BOOTSTRAP_ADMIN_PASSWORD` 创建首个管理员。日志只会打印用户名，不会打印密码。创建成功后应尽快修改初始密码，并从部署环境中移除或轮换 bootstrap 密码。

上传/解析限制可通过环境变量调整：

```bash
FANBOOK_EPUB_MAX_ENTRIES=1000
FANBOOK_EPUB_MAX_EXPANDED_SIZE=100MB
FANBOOK_EPUB_MAX_ENTRY_SIZE=25MB
```

翻译 chunk 规划使用配置值：

```bash
fanbook.translation.chunk-target-characters=6000
fanbook.translation.max-segments-per-chunk=40
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
GET  /api/auth/csrf
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
GET  /api/admin/users
POST /api/admin/users
PATCH /api/admin/users/{userId}/roles
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
POST /api/books/{bookId}/exports/zh
GET  /api/books/{bookId}/exports/zh
POST /api/books/{bookId}/exports/bilingual
GET  /api/books/{bookId}/exports/bilingual
POST /api/books/{bookId}/reports/consistency
GET  /api/books/{bookId}/reports/consistency
POST /api/books/{bookId}/reports/consistency.md
GET  /api/books/{bookId}/reports/consistency.md
GET  /actuator/health
GET  /v3/api-docs
```

`POST /api/books` 使用 `multipart/form-data` 上传 EPUB 文件，字段名为 `file`，可选参数 `sourceLanguage` 默认为 `en`。

除 `GET /api/auth/csrf`、`POST /api/auth/login` 和健康检查外，API 需要已登录 Session。浏览器或前端客户端应先读取 `/api/auth/csrf`，并在 `POST`、`PATCH`、`PUT`、`DELETE`、上传、导出生成、任务 mutation 和 admin 操作中携带返回的 `X-CSRF-TOKEN` header。

导出接口采用生成/下载分离语义：`POST` 生成或刷新 artifact，`GET` 只下载已经存在且状态为 `READY` 的 artifact。`VIEWER` 只能读取和下载 ready artifact，不能触发上传、翻译、笔记 mutation 或导出生成。

## 它是怎么工作的

### 1. EPUB 解析

系统读取 `container.xml`、OPF spine 和章节文档，把正文拆成带定位信息的段落。每个段落会保留章节、顺序、类型和原文内容，供翻译任务和导出阶段使用。

### 2. 分块翻译

系统按段落创建 chunk，把待翻译段落交给 AI Provider。mock Provider 用于测试和演示，OpenAI-compatible Provider 通过 `/responses` 接口请求结构化输出。

### 3. 持久化与恢复

翻译状态写入 MySQL，本地文件 storage 保存原始 EPUB、导出 EPUB 和一致性报告。任务中断后可以恢复，不需要从头开始。

## 私有部署运维

### 安全边界

- `backend/docker-compose.yml` 默认只暴露后端 HTTP 端口，不暴露 MySQL、Redis 和 RabbitMQ 管理端口。
- `SPRING_PROFILES_ACTIVE=prod` 时，OpenAPI/Swagger 默认关闭，Actuator 只暴露 health，且不显示健康详情。
- 反向代理、TLS 终止、完整 metrics dashboard 和定时备份任务由部署环境决定，本仓库不绑定具体方案。

### 备份和恢复

Fanbook 的一致性单元是 **MySQL 数据库 + `FANBOOK_STORAGE_ROOT` 本地文件存储根目录**。只备份其中一个会导致书籍、导出 artifact 或元数据不一致。

推荐备份步骤：

```bash
cd backend
docker compose stop backend
docker compose exec mysql mysqldump -u root -p fanbook > fanbook.sql
docker run --rm -v fanbook-storage:/data -v "$PWD":/backup alpine tar czf /backup/fanbook-storage.tgz -C /data .
docker compose start backend
```

推荐恢复步骤：

```bash
cd backend
docker compose stop backend
docker compose exec -T mysql mysql -u root -p fanbook < fanbook.sql
docker run --rm -v fanbook-storage:/data -v "$PWD":/backup alpine sh -c "rm -rf /data/* && tar xzf /backup/fanbook-storage.tgz -C /data"
docker compose start backend
```

### 常见故障处理

- 健康检查：`GET /actuator/health`。生产 profile 不返回内部细节。
- 卡住的翻译任务：优先查看后端日志、RabbitMQ 队列堆积、`translation_jobs` 和 `translation_chunks` 状态，再使用 resume 接口恢复失败任务。
- 存储清理：删除书籍或 artifact 前，应确认 MySQL 元数据和本地 storage object key 一致；不要手动只删磁盘文件。
- bootstrap admin：如果已有 `ADMIN` 用户，环境变量不会再次创建管理员。

### 4. 导出

导出阶段基于同一份翻译结果生成中文版 EPUB、中英双语 EPUB，以及 JSON / Markdown 一致性报告。

## 项目结构

```text
FanBook/
├── backend/       # Spring Boot 后端、数据库迁移、测试和 Docker Compose
├── frontend/      # Vite + React + TypeScript 前端、测试和构建配置
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
