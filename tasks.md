# 项目任务状态 (Project Tasks Status)

## ✅ 已完成任务 (Completed Tasks)

### 基础设施 (Infrastructure)

- [x] **环境配置** (`core/config.py`)
  - [x] 操作系统检测 (macOS/Windows)。
  - [x] 硬件加速检测 (MPS/CUDA/CPU)。
  - [x] HuggingFace 镜像源配置 (`HF_ENDPOINT`)。
  - [x] 使用 `pathlib` 进行路径管理。

### 数据摄取 (Data Ingestion)

- [x] **文档处理器** (`core/ingestion.py`)
  - [x] 通过 `python-docx` 读取 `.docx` 文件。
  - [x] 文本清洗与标准化。
  - [x] 支持**滑动窗口 (Sliding Window)** 的段落处理。
  - [x] 表格行提取。
  - [x] 保留切片元数据（原始索引、来源类型）。

### 检索引擎 (Search Engine)

- [x] **语义检索引擎** (`core/search_engine.py`)
  - [x] 实现单例模式 (Singleton pattern)。
  - [x] 健壮的模型下载机制（完整性检查、多线程下载）。
  - [x] Embedding 模型 (`bge-m3`) 加载与设备分配。
  - [x] Reranker 模型 (`bge-reranker-large`) 加载与设备分配。
  - [x] `load_document` 实现（向量化）。
  - [x] `search` 实现（双阶段：检索 + 重排序）。

### API 与集成 (API & Integration)

- [x] **API 接口** (`api_interface.py`)
  - [x] `init_engine` 包装器。
  - [x] `process_file_for_search` 包装器。
  - [x] `search_query` 包装器。
- [x] **审计与预览扩展** (超出原计划)
  - [x] 用于合同审查功能的 `audit_and_prepare_contract`。
  - [x] 生成带有 ID 注入的 HTML 预览，用于 UI 交互。

## ⏳ 待完成/规划中 (Pending / Future Tasks)

### 功能扩展 (v1.x - v2.0)

- [ ] **LLM 集成 (v2.0)** (`core/llm_bridge.py`)
  - [ ] 本地 Ollama 服务管理（保活/启动）。
  - [ ] 用于 RAG（检索增强生成）的系统提示词注入。
  - [ ] 聊天接口 API。

### 优化与工程化

- [ ] **打包 (Packaging)**
  - [ ] 创建 `PyInstaller` spec 文件。
  - [ ] 处理 `sentence-transformers` 和 `torch` 的隐式导入 (hidden imports)。
- [ ] **性能调优 (Performance Tuning)**
  - [ ] 根据实际准确率反馈优化滑动窗口参数。
  - [ ] 如果在 8GB Mac 上内存占用过高，研究量化 (int8) 方案。
- [ ] **测试 (Testing)**
  - [ ] 扩展 `search_engine.py` 边缘情况（空文档、特殊字符）的单元测试覆盖率。
  - [ ] 自动化端到端回归测试。

### UI 集成 (前端依赖)

- [ ] 根据特定 Qt/前端数据格式要求完善 `api_interface.py` (进行中)。
