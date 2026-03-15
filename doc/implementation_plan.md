# 实施计划：Web 版法律合同智能审计系统

## 1. 技术栈 (Tech Stack)

| 组件 | 选型 | 说明 |
| :--- | :--- | :--- |
| **Web 框架** | `FastAPI` | 高性能、异步、易于部署 |
| **应用服务器** | `Uvicorn` | ASGI 服务器，生产级标准 |
| **前端技术** | HTML5 / JS (Vanilla) | 轻量级、零构建、易于嵌入 |
| **文档解析** | `python-docx` | 核心 `.docx` 解析与修改 |
| **AI 模型** | `BAAI/bge-m3` | Embedding (语义召回) |
| **AI 模型** | `BAAI/bge-reranker-large` | Reranker (精准重排) |
| **并发控制** | `ThreadPoolExecutor` | 处理 CPU 密集型任务 |
| **文件管理** | `pathlib` + `tempfile` | 跨平台路径与临时文件隔离 |

## 2. 详细模块设计 (Detailed Module Design)

### 2.1 Web 服务层 (`web_server.py`)

* **职责**: 系统的统一入口，处理 HTTP 请求。
* **API 接口**:
  * `GET /`: 返回前端单页应用 (`templates/index.html`)。
  * `POST /api/audit`:
    * 接收 `UploadFile`。
    * 创建独立的 `UUID` 临时目录。
    * 将任务提交给 `ThreadPoolExecutor`。
    * 返回审计结果 JSON（含预览 HTML 和下载链接）。
  * `GET /api/download/{request_id}/{filename}`:
    * 安全校验路径。
    * 返回 `FileResponse` 供用户下载。
* **中间件**: 配置 CORS 以允许灵活的网络访问。

### 2.2 核心业务层 (`api_interface.py`)

* **职责**: 编排文档处理流程，连接 Core 模块与 Web 层。
* **关键重构**:
  * `audit_and_prepare_contract(file_path)`:
    * 修改了文件输出路径逻辑，不再依赖原文件目录，而是自动识别输入文件所在的临时目录。
    * 确保在多线程环境下，每个任务操作的是自己沙箱内的文件。

### 2.3 前端交互层 (`templates/index.html`)

* **设计风格**: 复刻原 Qt 版本的 macOS 风格，简洁专业。
* **关键交互**:
  * **异步上传**: 使用 `fetch` API 上传文件，显示全屏 Loading 遮罩。
  * **HTML 渲染**: 接收后端返回的 `preview_html`，直接渲染高保真文档。
  * **卡片联动**: 点击右侧审计卡片，左侧文档视图自动平滑滚动 (`scrollIntoView`) 并高亮显示。
  * **动态下载**: 审计成功后，动态显示下载按钮。

### 2.4 核心处理模块 (`core/`)

* **`core/word_processor.py`**:
  * 全平台统一使用 **XML 注入** 技术实现“修订模式”。
  * 移除了所有 Windows COM / AppleScript 依赖，实现纯 Python 运行。
* **`core/preview_generator.py`**:
  * 自研 XML -> HTML 解析器，支持 `<ins>`/`<del>` 标签渲染，完美还原修订痕迹。

## 3. 开发规范 (Development Guidelines)

1. **并发安全**:
    * 严禁使用全局变量存储请求相关的状态。
    * 文件操作必须在 `request_id` 隔离的目录下进行。
2. **资源管理**:
    * `web_server.py` 需配置全局临时目录清理策略（目前为请求级清理或保留供下载，需注意磁盘占用）。
    * AI 模型在 `startup` 事件中预加载。
3. **错误处理**:
    * API 层需捕获所有异常并返回标准的 HTTP 500 错误及详细信息，便于前端展示。

## 4. 部署策略

1. **服务器**: 推荐 Mac Mini (M1/M2) 或高性能 Linux 服务器。
2. **网络**: 确保服务器 IP 固定，或在局域网内通过 Hostname 访问。
3. **运行**: 使用 `python web_server.py` 直接启动，或配合 `Process Monitor` (如 Supervisor) 守护进程。
