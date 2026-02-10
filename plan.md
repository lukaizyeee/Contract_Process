# backend_implementation_plan.md

## 1. 项目概述 (Project Overview)

本项目旨在构建一个**本地化、高精度、跨语言**的英文法律合同语义检索后端的1.0版本基础功能。

* **核心目标**：针对**单篇** Word (.docx) 合同文档，实现“输入*中文*意图，精准定位*英文*条款”的功能。
* **关键约束**：
* **零数据外流**：所有计算在本地完成。
* **极致准确性**：优先保证检索精度，允许 GB 级别的内存/显存占用（使用Embedding和Reranker模型）。
* **无数据库模式**：针对单篇文档使用 **In-Memory (NumPy)** 检索，不依赖 ChromaDB/Milvus。
* **跨平台兼容**：开发设备是windows，但是产品必须同时支持 Windows (Nvidia GPU/CUDA) 和 macOS (Apple Silicon/Metal)。整个项目中所有路径要用pathlib写，不能直接用字符串拼接，防止跨平台路径问题。
* **测试方法**：借助Github Actions，在Windows和macOS虚拟机上分别运行测试。

---

## 2. 技术栈选型 (Tech Stack)

| 组件 | 选型 | 说明 |
| --- | --- | --- |
| **语言** | Python 3.11 |  |
| **文档解析** | `python-docx` | 用于解析 .docx 段落与表格 |
| **Embedding model** | `BAAI/bge-m3` | 支持多语言、长文本，高精度 |
| **Reranker model** | `BAAI/bge-reranker-large` | 重排序模型，用于在检索后进行二次精排，提升准确率 |
| **LLM**| 待定 | 待定，目前的1.0版本基础检索功能暂时不需要加载llm |
| **向量计算** | `numpy` | 使用矩阵运算进行暴力全量匹配 (Brute-force) |
| **模型推理框架** | `sentence-transformers` | 加载 Embedding 和 Reranker 模型 |
| **LLM 客户端** | `ollama` (Python lib) | 用于与本地 Sidecar 运行的 Ollama 服务通信 |
| **打包工具** | `PyInstaller` | 后续打包需求 |

---

## 3. 模块化架构设计 (Modular Architecture)

后端代码需划分为以下 4 个核心模块：

### 模块 A: 跨平台环境配置 (`config.py`)

负责处理路径差异和硬件加速设备检测。

* **功能要求**：
1. 检测操作系统 (`platform.system()`)。
2. 检测硬件加速设备：
* macOS: 检测 `mps` (Metal Performance Shaders)。
* Windows: 检测 `cuda`。
* Fallback: `cpu`。


3. 定义模型存储路径：优先使用项目目录下的 `./models`，而非用户主目录。


### 模块 B: 文档解析与切片 (`ingestion.py`)

负责将 .docx 文件转换为可检索的语义块 (Chunks)。

* **功能要求**：

1. 读取 Word 文档的段落 (`paragraphs`) 和表格 (`tables`)。

2. **清洗**：去除空行、页眉页脚干扰字符。

3. **索引映射**：必须保留每个 Chunk 在原文档中的索引位置 (Index)，以便前端高亮跳转。

4. **切片策略**：对于相对短的段落保留完整段落作为基础单位。对于超过一定字符数（如 400 字符）的长段落，增加“滑动窗口切片”：
做法：将长段落拆分为 3-5 个句子组成的重叠块。
重叠（Overlap）：每个小块与前一个块保留 1-2 句的重叠，防止某些关键语义刚好被从中间切断。



### 模块 C: 语义检索引擎 (`search_engine.py`)

核心模块，实现“检索 + 重排序”的双层漏斗逻辑。

* **类设计**：`class SemanticSearchEngine`
* **初始化**：
* 加载 `BAAI/bge-m3` 到指定 Device。
* 加载 `BAAI/bge-reranker-large` 到指定 Device。


* **方法 1: `load_document(chunks)**`
* 调用 Embedding 模型将所有文本块转换为向量。
* 存储为 `self.doc_vectors` (NumPy Array)。


* **方法 2: `search(query, top_k=10)**`
* **Step 1 (粗排)**: 使用sentence transformers提供的工具semantic_search计算 Query 向量与 `doc_vectors` 的相似度，并选取 Top-10。
* **Step 2 (精排)**: 使用CrossEncoder工具将 Query 和 Top-10 的文本对 (Query, Doc_Text) 输入 Reranker 模型进行重排。
* **Step 3 (输出)**: 返回经过重排序后的 Top-K 结果（包含文本、索引、置信度分数）。



### 模块 D: LLM 侧车管理 (`llm_bridge.py`)

负责管理本地 Ollama 进程及 API 调用。

***在1.0版本暂时不用实现。***

* **功能要求**：
1. **服务保活**：检查 Ollama 服务是否运行，未运行则通过 `subprocess` 启动。
2. **模型路由**：
3. **System Prompt 注入**：

---

## 4. 详细执行步骤 (Implementation Steps for Agent)

参考以下顺序编写代码，可以灵活调整：

### Step 1: 编写 `core/config.py`


### Step 2: 编写 `core/ingestion.py`

### Step 3: 编写 `core/search_engine.py` (核心难点)

### Step 4: 编写 `api_interface.py`

* 作为前端调用的入口类。
* 提供接口：(参考，具体实现具体考虑)
* `init_engine()`: 预加载模型（耗时操作，需异步或线程处理）。
* `process_file(path)`: 解析并向量化。
* `query(text)`: 执行搜索。



---

## 5. 开发注意事项 (Attention)

1. **内存管理**：`bge-m3` 和 `reranker-large` 较大。在 `init_engine` 时，请确保只加载一次模型实例 (Singleton Pattern)。
2. **跨语言能力**：`bge-m3` 原生支持中英跨语言，**无需**调用翻译 API 将中文 Query 转英文，直接搜即可。
3. **Mac 兼容性**：在 `requirements.txt` 中不要指定特定平台的二进制包。使用 `torch` 的自动设备选择逻辑至关重要。
4. **错误处理**：对于无法解析的 `.doc` (旧版 Word)，需抛出清晰异常，提示用户“请先另存为 .docx”。
5. **下载模型**：请在初始化模型时，先检测本地 ./models/ 目录下是否存在模型文件；若不存在，则设置 HF_ENDPOINT 环境变量为镜像站并下载存入该目录。
设置环境变量
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
6. **模型加载**：加载模型时，请务必设置 device 自动检测逻辑，并在 encode 时使用 convert_to_tensor=True 以确保最高精度与性能。
