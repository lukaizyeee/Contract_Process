# 项目结构与功能指南 (Project Structure & Function Guide)

本文档旨在记录当前项目的目录结构、各模块的核心职责以及功能实现的边界。
**主要目的**：作为开发指南，帮助开发者快速定位功能代码，明确模块职责，防止逻辑耦合和重复实现（如：避免在底层工具类中重复加载重量级 AI 模型）。

---

## 1. 目录结构概览 (Directory Structure)

```text
code/
├── web_server.py                 # Web 服务入口 (FastAPI)
├── api_interface.py              # 业务逻辑编排层 (API Controller)
├── core/                         # 核心功能模块 (Core Domain)
│   ├── config.py                 # 全局配置与硬件检测
│   ├── ingestion.py              # 文档解析与切片 (DocProcessor)
│   ├── search_engine.py          # 语义搜索引擎 (SemanticSearchEngine)
│   ├── word_processor.py         # 文档审计与修订引擎 (WordProcessor, TrackChangesHelper)
│   └── preview_generator.py      # HTML 预览生成器 (DocxPreviewGenerator)
├── templates/                    # 前端页面模板
│   └── index.html                # Web 界面 (HTML/JS/CSS)
├── tests/                        # 单元测试目录
│   └── test_core.py
├── requirements.txt              # Python 依赖清单
└── *.md                          # 项目规划与需求文档 (Master, Implementation, Tasks 等)
```

---

## 2. 核心模块功能说明 (Module Responsibilities)

为确保“高内聚、低耦合”，请严格遵循以下各模块的职责边界：

### 2.1 应用入口与网关
*   **`web_server.py`**
    *   **职责**：HTTP 请求处理、路由分发、并发控制。
    *   **功能**：
        *   初始化 FastAPI 应用和 Uvicorn 服务器。
        *   配置 `ThreadPoolExecutor` 处理耗时的审计任务，防止阻塞主线程。
        *   管理每次请求的独立临时文件夹 (`UUID`)，确保多用户并发安全。
        *   提供 `/api/audit` (审计), `/api/download` (下载), `/api/status` (状态) 接口。
    *   **禁忌**：不包含任何文档解析或 AI 业务逻辑。

### 2.2 业务逻辑编排
*   **`api_interface.py`**
    *   **职责**：系统的大脑（Controller），负责串联 `core/` 目录下的各个工具模块。
    *   **功能**：
        *   维护全局单例：AI 检索引擎 (`_engine_instance`)、文档切片器 (`_processor`)。
        *   核心函数 `audit_and_prepare_contract` 编排了整个审计生命周期：
            1.  调用 `WordProcessor` 进行审计并生成带修订标记的 `.docx`。
            2.  调用 `DocxPreviewGenerator` 将修订后的文档转为 HTML。
            3.  向 HTML 中注入高亮跳转所需的 `id` 锚点。
    *   **架构原则**：所有重量级的 AI 模型加载必须在这里通过 `init_engine` 单例模式完成，**禁止**在其他地方重复实例化模型。

### 2.3 核心处理引擎 (`core/`)

这是系统的底层工具箱，各司其职：

*   **`core/config.py`**
    *   **职责**：环境感知与配置中心。
    *   **功能**：检测当前操作系统 (Mac/Windows)、硬件加速环境 (MPS/CUDA/CPU)，并配置模型下载路径。

*   **`core/search_engine.py`**
    *   **职责**：基于 AI 模型的语义向量化与检索。
    *   **功能**：
        *   加载 `bge-m3` (Embedding) 和 `bge-reranker-large` (Reranker) 模型。
        *   `load_document(chunks)`: 接收文本块并将其向量化存入内存。
        *   `search(query)`: 执行“双阶段检索”（粗排 + 精排），返回最相关的文本块。
    *   **注意**：这是一个极其消耗内存/显存的类，必须作为单例使用。

*   **`core/ingestion.py` (DocProcessor)**
    *   **职责**：文档解构。
    *   **功能**：使用 `python-docx` 读取 `.docx`，将段落和表格清洗并切分为固定大小的、带重叠的文本块 (`Chunk`)，供搜索引擎向量化使用。

*   **`core/word_processor.py` (WordProcessor & TrackChangesHelper)**
    *   **职责**：规则匹配、AI 判定调用与文档物理修改。
    *   **功能**：
        *   **审计规则**：包含正则匹配（如全局识别电话/邮箱）和特定条款识别（如争议解决、违约金）。
        *   **底层修改 (`TrackChangesHelper`)**：直接操作 OpenXML，在文档中注入 `<w:ins>` (插入), `<w:del>` (删除) 和批注标记，实现纯 Python 的“修订模式”。
    *   **架构交互**：当需要进行语义审计时（如 RAG 检索付款条款），**应接收来自 `api_interface.py` 的已初始化的 `search_engine` 实例或检索结果**，切勿在此文件内重新 `SemanticSearchEngine()`。

*   **`core/preview_generator.py` (DocxPreviewGenerator)**
    *   **职责**：前端渲染引擎。
    *   **功能**：解析 `.docx` 的 XML 结构，将其转换为带有 CSS 样式的 HTML 字符串。特别是将 `<w:ins>` 和 `<w:del>` 标签映射为 HTML 的绿色下划线和红色删除线，实现高保真的 Web 预览。

---

## 3. 功能数据流向 (Data Flow)

理解一个完整的“上传并审计”请求的数据流向，有助于防止逻辑错乱：

1.  **用户** 在 `index.html` 上传 `test.docx`。
2.  `web_server.py` 接收文件，放入独立的临时目录 `/tmp/uuid/test.docx`。
3.  `web_server.py` 调用 `api_interface.audit_and_prepare_contract`。
4.  `api_interface.py`：
    *   (未来若需语义) 调用 `DocProcessor` 切片，并让全局 `SemanticSearchEngine` 进行 `load_document`。
    *   调用 `WordProcessor.audit_and_fix`。
5.  `WordProcessor`：
    *   执行正则审计 (`_check_global_compliance`)。
    *   (未来) 向全局 `SemanticSearchEngine` 发起 Query，获取相关段落，执行判定。
    *   调用 `TrackChangesHelper` 修改 XML。
    *   保存为 `/tmp/uuid/test_revised.docx`，并返回卡片数据 (`audit_results`)。
6.  `api_interface.py` 调用 `DocxPreviewGenerator` 解析 `test_revised.docx`，生成 HTML。
7.  `api_interface.py` 在 HTML 中注入跳转锚点，打包返回。
8.  `web_server.py` 将 JSON (HTML + 卡片数据 + 下载链接) 返回给前端。
9.  `index.html` 渲染视图。

---

## 4. 开发防坑指南 (Anti-Patterns)

*   ❌ **重复加载模型**：不要在 `word_processor.py` 等底层类中 `import SemanticSearchEngine` 并实例化。AI 模型必须在服务启动时于全局（或通过依赖注入）加载。
*   ❌ **硬编码文件路径**：不要使用 `./output.docx` 或固定的临时文件名。必须使用传入的、由 `web_server.py` 提供的 `UUID` 隔离路径，否则并发请求会互相覆盖文件。
*   ❌ **跨越边界**：`WordProcessor` 只负责“找问题”和“改文件”；如何把改好的文件显示给用户，是 `DocxPreviewGenerator` 和前端的责任，不要在 `WordProcessor` 里拼装 HTML。
