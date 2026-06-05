# 前端布局优化与内容丰富化实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 重构翻译页面布局为多栏 CSS Grid，使侧边栏轻量化；重定义空状态展示为快速开始指南与最近书籍列表；修复配置文案截断与侧边栏按钮变形重叠的视觉 Bug。

**架构：**
1. 调整 HTML 结构，将“导出”和“活动日志”移至主工作台区域。
2. 配置 CSS Grid 使得工作台按 Hero(1/1) -> Summary|Exports(2/3) -> Chapters|Logs(3/3) 比例排布，并在小屏下自适应为单列。
3. 动态编写 JS 在未载入书籍时向空状态渲染快捷加载列表与快速引导指南，并自动隐藏导出和日志面板。

**技术栈：** HTML5, Vanilla CSS, Vanilla JS, Node.js Test Harness (assert)

---

### 任务 1：HTML 结构迁移

**文件：**
- 修改：[index.html](file:///d:/1something/fanbook/frontend/index.html)

- [x] **步骤 1：调整 HTML 结构**
  将“导出”和“活动日志”对应的 `section` 面板从 `<aside class="translate-tools">` 移至 `<div class="translate-content">` 中。
  为导出面板添加类 `.exports-panel`，将日志面板类修改为 `.log-workspace-panel`。

- [x] **步骤 2：运行测试验证元素位置迁移后功能正常**
  运行：`node frontend/tests/frontend-rendering.test.mjs`
  预期：PASS (因为 ID 保持不变，JS 绑定的 DOM 引用依然可以正确查询并渲染)

- [x] **步骤 3：Commit**
  ```bash
  git add frontend/index.html
  git commit -m "style: move exports and log panels to main workspace container"
  ```

---

### 任务 2：CSS Grid 布局与自适应媒体查询配置

**文件：**
- 修改：[styles.css](file:///d:/1something/fanbook/frontend/src/styles.css)

- [x] **步骤 1：添加 CSS Grid 和自适应样式**
  在 `frontend/src/styles.css` 中，重定义 `.translate-content` 布局参数为 Grid 且设定 `grid-template-areas`，定义各个子 Panel 的 `grid-area` 定位；增加 `.log-workspace-panel` 样式（自适应高度与最大高度滚动限制）；并为宽屏配置 `.translate-grid`，以及小屏下的 `@media (max-width: 1200px)` 自适应媒体查询。

- [x] **步骤 2：运行单元测试验证代码正确性**
  运行：`node frontend/tests/frontend-rendering.test.mjs`
  预期：PASS

- [x] **步骤 3：Commit**
  ```bash
  git add frontend/src/styles.css
  git commit -m "style: implement CSS Grid multi-column layout for workbench"
  ```

---

### 任务 3：配置详情展示、侧边栏按钮对齐与按钮微动效优化

**文件：**
- 修改：[styles.css](file:///d:/1something/fanbook/frontend/src/styles.css)
- 修改：[index.html](file:///d:/1something/fanbook/frontend/index.html)

- [x] **步骤 1：修复配置参数折行截断与按钮换行问题**
  1. 移除 `.profile-summary` 的 `-webkit-line-clamp` 和 `overflow: hidden` 属性。
  2. 修改 `.translation-form` 的布局与按钮文字：将“取消当前任务”修改为“取消任务”。
  3. 为在线阅读的空状态按钮 `#reader-empty-action` 添加过渡动效。

- [x] **步骤 2：验证测试**
  运行：`node frontend/tests/frontend-rendering.test.mjs`
  预期：PASS

- [x] **步骤 3：Commit**
  ```bash
  git add frontend/src/styles.css frontend/index.html
  git commit -m "style: fix profile summary truncation and sidebar button text"
  ```

---

### 任务 4：动态空状态引导与最近书籍加载列表

**文件：**
- 修改：[translate.js](file:///d:/1something/fanbook/frontend/src/pages/translate.js)
- 修改：[app.js](file:///d:/1something/fanbook/frontend/src/app.js)
- 修改：[frontend-rendering.test.mjs](file:///d:/1something/fanbook/frontend/tests/frontend-rendering.test.mjs)

- [x] **步骤 1：编写失败的渲染测试**
  在 `frontend/tests/frontend-rendering.test.mjs` 中添加针对未选书状态下渲染空状态仪表盘的断言。检查空状态时是否正确显示“开始翻译你的第一本书”标题、最近处理的 3 本书籍的加载链接，以及隐藏导出和日志面板。

- [x] **步骤 2：运行测试验证失败**
  运行：`node frontend/tests/frontend-rendering.test.mjs`
  预期：FAIL，报错 "AssertionError: Expected ... to match /开始翻译你的第一本书/"

- [x] **步骤 3：实现动态空状态引导与面板可见性控制**
  1. 在 `frontend/src/pages/translate.js` 中重写 `renderTranslate` 函数，检测 `book` 是否为空：
     - 若为空：将 `translateEmptyState` 的 innerHTML 填充为包含“开始翻译你的第一本书”标题、3 步指南、以及从 `state.books` 中过滤出前 3 本书籍的快捷加载按钮。
     - 在有书和无书状态下，控制面板显示与隐藏。
  2. 在 `frontend/src/events.js` 中，添加对空状态中最近书籍加载按钮 `data-load-recent-book-id` 点击事件的委托，调用 `actions.loadBook(bookId)` 载入书籍。

- [x] **步骤 4：运行测试验证通过**
  运行：`node frontend/tests/frontend-rendering.test.mjs`
  预期：PASS

- [x] **步骤 5：Commit**
  ```bash
  git add frontend/src/pages/translate.js frontend/tests/frontend-rendering.test.mjs
  git commit -m "feat: implement dynamic empty state dashboard with recent books quickload"
  ```
