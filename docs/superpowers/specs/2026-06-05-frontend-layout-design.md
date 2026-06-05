# 2026-06-05 前端界面布局优化与内容丰富化设计规格

本项目通过重构翻译工作台页面布局、优化未载入书籍时的空状态以及打磨细节 Bug，提升整体视觉体验与用户交互连贯性。

## 设计方案详情

### 1. 布局重构与页面的多栏自适应调整
*   **侧边栏减负**：将“导出”面板和“活动日志”面板从左侧 sticky 栏移至右侧工作台。
*   **Grid 网格参数定义**：
    *   `.translate-content` 布局参数：
        ```css
        .translate-content {
          display: grid;
          grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr);
          grid-template-rows: auto auto auto;
          gap: 1.5rem;
          grid-template-areas:
            "hero hero"
            "summary exports"
            "chapters log";
        }
        ```
    *   **区域定义**：
        *   行 1：`.book-hero` (横跨整行，`grid-area: hero`)
        *   行 2：左侧 `.summary-panel` (`grid-area: summary`)，右侧 `.exports-panel` (`grid-area: exports`)
        *   行 3：左侧 `.chapters-panel` (`grid-area: chapters`)，右侧 `.log-workspace-panel` (`grid-area: log`)
    *   **日志面板尺寸限制**：`.log-workspace-panel` 最大高度固定为 `400px`，超出自动显示纵向滚动条 (`overflow-y: auto`)。
*   **响应式断点**：
    *   当视口宽度小于 `1200px` 时，`.translate-content` 重置为单列流式排布：
        ```css
        @media (max-width: 1200px) {
          .translate-content {
            grid-template-columns: 1fr;
            grid-template-rows: auto;
            grid-template-areas:
              "hero"
              "summary"
              "exports"
              "chapters"
              "log";
          }
        }
        ```

### 2. 翻译工作台空状态设计 (Focused Empty State)
当未加载书籍（`state.currentBookDetail` 为空）时，右侧工作台不再显示冗长的书籍库管理，而是专注于“快速开始翻译流程”的引导：
*   **欢迎标题**：“开始翻译你的第一本书”
*   **上传引导**：突出显示左侧的上传区域，并在空状态中央放置一个醒目的“上传/选择 EPUB 书籍”快速引导块。
*   **3 步快速指南**：
    1. 上传 EPUB 电子书文件。
    2. 选择目标翻译配置档（配置提供者与模型）。
    3. 点击左侧的“开始翻译”按钮启动任务。
*   **最近上传快速加载链接**：如果 `state.books` 中存在书籍，显示“最近上传的书籍（最多 3 本）”的极简列表，点击可以一键加载并打开对应的书籍详情。
*   **显示/隐藏控制**：在空状态时，`.exports-panel` 和 `.log-workspace-panel` **不显示**。只有在成功加载书籍后，网格和各个面板才渲染并展示。

### 3. DOM 元素迁移与 ID 保持
*   **结构迁移**：
    *   将包含 `#export-list` 的“导出”面板与下载按钮移入新建的 `.exports-panel` 容器。
    *   将包含 `#message-log` 的“活动日志”面板移入新建的 `.log-workspace-panel` 容器。
*   **ID 与选择器保持**：
    *   保留原有元素 ID：`#export-list`、`#message-log`、`#download-zh`、`#download-bilingual`、`#download-consistency`。
    *   保持 `dom.js` 中选择器的有效性，不需要重写 API 数据绑定逻辑，确保平滑迁移。

### 4. 细节打磨与 Bug 修复
*   **配置参数完整展示**：移去 `.profile-summary` 的 `-webkit-line-clamp: 2` 和 `overflow: hidden;`，使其高度根据内容自适应，确保并发上限、RPM、状态等所有参数全文本展示。
*   **侧边栏按钮防折行**：
    *   对“恢复任务”与“取消当前任务”的容器使用 Flex 弹性拉伸与间距对齐。
    *   在 HTML 模板中将“取消当前任务”文字缩短为“取消任务”，避免侧边栏窄屏宽度（280px-340px）下折行导致与“恢复任务”重叠。
*   **主页在线阅读空状态**：优化在线阅读页面空状态的按钮样式，加入流畅的悬停过渡微动效。

## 验证与测试计划

### 1. 自动化测试设计
*   **布局与渲染测试**：编写前端测试验证当加载书籍与不加载书籍时，DOM 元素（`.exports-panel`、`.log-workspace-panel`、`.page-empty-state`）的 `display` 状态或 `classList` 的正确切换。
*   **DOM 选择器测试**：确保在 DOM 元素迁移后，`dom.js` 返回的各个节点引用有效。
*   **按钮事件绑定测试**：模拟点击“下载/导出”和“日志加载”，确保事件绑定在位置迁移后仍能被正确捕获和处理。

### 2. 手动验证步骤
1.  **侧边栏高度测试**：确保限制在小高度视口时，由于“导出”与“日志”移走，左侧工具栏能够完美完整显示，无需滚动条。
2.  **网格布局对齐**：载入书籍，查看 Grid 的 `2fr 1fr` 栏宽比例、`1.5rem` 间距、以及各个面板对齐。
3.  **响应式断点**：收缩窗口至 1200px 以下、768px 以下，验证是否自适应为单列。
4.  **配置档展示**：切换不同的翻译配置，验证描述文案完整显示无省略号。
