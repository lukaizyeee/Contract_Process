# 项目任务状态 (Project Tasks Status)

## ✅ 已完成任务 (Completed Tasks)

### 架构重构 (Architecture Refactoring)

- [x] **Web 化迁移** (从 Qt 桌面端迁移至 B/S 架构)
  - [x] 创建 `web_server.py` (FastAPI + Uvicorn)。
  - [x] 实现前端页面 `templates/index.html` (复刻原 UI 交互)。
  - [x] 移除旧的 `main_ui_qt.py` 及相关依赖。
- [x] **并发与部署支持**
  - [x] 引入 `ThreadPoolExecutor` 处理 CPU 密集型审计任务。
  - [x] 实现基于 `UUID` 的请求级文件隔离机制。
  - [x] 编写 `web_deployment_plan.md` 部署指南。

### 核心功能 (Core Features)

- [x] **文档处理器** (`core/ingestion.py`, `core/word_processor.py`)
  - [x] `.docx` 解析与 XML 注入修订（去 Word 依赖）。
  - [x] 敏感信息、条款缺失等规则审计。
- [x] **预览生成** (`core/preview_generator.py`)
  - [x] 自研 XML -> HTML 解析器，支持红线修订渲染。
- [x] **检索引擎** (`core/search_engine.py`)
  - [x] 双阶段检索 (`bge-m3` + `bge-reranker-large`)。
  - [x] 自动模型下载与设备适配 (MPS/CUDA)。

### 接口与交互 (API & UI)

- [x] **API 接口** (`api_interface.py`)
  - [x] 适配 Web 层的异步调用与路径管理。
- [x] **前端交互**
  - [x] 文件上传与 Loading 状态。
  - [x] 审计结果卡片展示。
  - [x] 点击卡片跳转高亮。
  - [x] 修订版文档下载。

## ⏳ 待完成/规划中 (Pending / Future Tasks)

### 功能扩展 (v1.x - v2.0)

- [ ] **LLM 集成 (v2.0)** (`core/llm_bridge.py`)
  - [ ] 本地 Ollama 服务管理（保活/启动）。
  - [ ] 用于 RAG（检索增强生成）的系统提示词注入。
  - [ ] 聊天接口 API。
- [ ] **多用户增强**
  - [ ] 简单的用户登录/鉴权机制。
  - [ ] 审计历史记录持久化（SQLite/Redis）。

### 优化与工程化

- [ ] **打包 (Packaging)**
  - [ ] 探索 `PyInstaller` 打包 Web Server 为单文件可执行程序，方便非技术人员部署。
- [ ] **性能调优**
  - [ ] 针对大文件 (>100页) 的解析与推理性能优化。
  - [ ] 前端大 HTML 渲染性能优化（虚拟滚动）。
- [ ] **测试 (Testing)**
  - [ ] 针对并发请求的压力测试。
  - [ ] API 接口的单元测试。
