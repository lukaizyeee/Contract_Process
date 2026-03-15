# Master Plan: Local Legal Contract Semantic Search Backend (Web Version)

## 1. Project Vision (项目愿景)

本项目的核心目标是构建一个**本地化、高精度、跨语言**的英文法律合同中文语义检索与审计系统（v1.0）。
系统采用 **B/S (Browser/Server)** 架构，部署在局域网高性能服务器（如 Mac Mini）上，用户通过浏览器即可访问。旨在通过中文意图精准定位英文条款，并提供智能化的合规审计建议，大幅提高法律专业人士的审查效率。

## 2. Core Value Proposition (核心价值)

* **Privacy First (隐私优先)**: 零数据外流，所有计算（文档解析、AI 推理）完全在本地局域网服务器完成，确保法律文档的安全。
* **Zero Client Installation (零安装)**: 采用 Web 架构，客户端无需安装任何软件或环境，只要有浏览器即可使用，兼容 Windows/Mac/Mobile。
* **High Performance Sharing (资源共享)**: 集中利用服务器的 GPU/MPS 加速能力，支持多用户并发审计，降低用户端硬件门槛。
* **Cross-Lingual (跨语言)**: 原生支持中文查询搜英文文档，无需中间翻译层，避免语义损耗。

## 3. Technical Constraints & Requirements (关键约束)

* **Architecture**: Browser/Server (B/S).
* **Server Platform**: macOS (Apple Silicon/Metal) priority; Linux/Windows compatible.
* **Concurrency**: 支持小规模（~5-10人）并发使用，需处理好文件隔离与线程阻塞问题。
* **Hardware**: 服务器需具备足够的 RAM (16GB+) 和加速卡 (MPS/CUDA) 以运行 Embedding 模型。
* **Input Format**: Word Documents (`.docx`).

## 4. Architecture Overview (架构概览)

系统由以下核心模块组成：

1. **Web Server Layer (Web 服务层)**
    * `web_server.py`: 基于 `FastAPI` + `Uvicorn` 的高性能异步 Web 服务器。
    * 负责静态资源托管 (`index.html`)、API 路由分发、请求上下文管理。
    * **并发控制**: 使用 `ThreadPoolExecutor` 将 CPU 密集型任务卸载到线程池。

2. **Core Processing Layer (核心处理层)**
    * `core/ingestion.py`: `.docx` 解析与切片。
    * `core/word_processor.py`: 基于 XML 注入的文档审计与修订引擎（去 Word 依赖）。
    * `core/preview_generator.py`: 生成带修订痕迹的高保真 HTML 预览。

3. **Retrieval Engine Layer (检索引擎层)**
    * `core/search_engine.py`: 核心双层检索逻辑 (`bge-m3` + `bge-reranker-large`)。

## 5. Future Roadmap (未来规划)

* **v1.0 (Current)**: Web 化架构重构完成。支持文件上传、在线预览、智能审计、修订下载。支持局域网并发访问。
* **v1.x**: 增加用户鉴权 (Login)、审计历史记录 (History)、多文档对比。
* **v2.0**: 引入本地 LLM (Ollama) 进行增强问答与条款生成 (RAG)，实现“针对本合同的 AI 助手”。
