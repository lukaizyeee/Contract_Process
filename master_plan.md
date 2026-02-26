# Master Plan: Local Legal Contract Semantic Search Backend

## 1. Project Vision (项目愿景)

本项目的核心目标是构建一个**本地化、高精度、跨语言**的英文法律合同中文语义检索系统（v1.0）。
用户可以通过输入**中文**意图，精准定位合同中的**英文**条款，从而提高法律专业人士的审查效率。

## 2. Core Value Proposition (核心价值)

* **Privacy First (隐私优先)**: 零数据外流，所有计算完全在本地设备完成，确保法律文档的安全。
* **High Precision (极致精度)**: 优先保证检索准确性，采用 "Embedding + Reranker" 双阶段检索架构，允许使用较高的计算资源（内存/显存）。
* **Cross-Lingual (跨语言)**: 原生支持中文查询搜英文文档，无需中间翻译层，避免语义损耗。
* **No Database Overhead (轻量级架构)**: 针对单篇文档检索场景，采用 In-Memory (NumPy) 计算，不依赖重量级向量数据库 (ChromaDB/Milvus)。

## 3. Technical Constraints & Requirements (关键约束)

* **Platform**:
  * **Development**: macOS & Windows.
  * **Target**: macOS (Apple Silicon/Metal) priority; Windows (Nvidia GPU/CUDA) compatible.
  * **Path Handling**: Strict usage of `pathlib` for cross-platform compatibility.
* **Hardware**:
  * Supports MPS (Mac) and CUDA (Windows) acceleration.
  * CPU fallback for compatibility.
* **Input Format**: Word Documents (`.docx`).

## 4. Architecture Overview (架构概览)

系统由以下四个核心模块组成：

1. **Infrastructure Layer (基础设施层)**
    * `core/config.py`: 负责跨平台环境检测、硬件加速适配、路径管理及模型下载配置。

2. **Data Ingestion Layer (数据摄取层)**
    * `core/ingestion.py`: 负责解析 `.docx` 文档，提取段落与表格，进行清洗、索引映射及滑动窗口切片 (Sliding Window Chunking)。

3. **Retrieval Engine Layer (检索引擎层)**
    * `core/search_engine.py`: 核心双层检索逻辑。
        * **Stage 1**: 语义粗排 (Bi-Encoder `bge-m3`) -> Top-N.
        * **Stage 2**: 语义精排 (Cross-Encoder `bge-reranker-large`) -> Top-K.

4. **Interface Layer (接口层)**
    * `api_interface.py`: 向前端 (Qt/Web) 暴露统一调用接口，管理引擎生命周期及业务流程（含审计与预览生成）。

## 5. Future Roadmap (未来规划)

* **v1.0 (Current)**: 基础语义检索、文档解析、本地模型推理、审计预览基础功能。
* **v1.x**: 性能优化、打包发布 (PyInstaller)。
* **v2.0**: 引入本地 LLM (Ollama) 进行增强问答与条款生成 (RAG)。
