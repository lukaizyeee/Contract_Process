# 实施计划：本地法律合同检索后端

## 1. 技术栈 (Tech Stack)

| 组件 | 选型 | 说明 |
| :--- | :--- | :--- |
| **语言** | Python 3.11 | 核心逻辑 |
| **文档解析** | `python-docx` | 用于解析段落和表格的 `.docx` 解析器 |
| **Embedding 模型** | `BAAI/bge-m3` | 多语言、长文本支持 |
| **Reranker 模型** | `BAAI/bge-reranker-large` | 高精度重排序 |
| **向量搜索** | `numpy` | 暴力全量内存计算 |
| **推理** | `sentence-transformers` | 模型加载与推理封装 |
| **模型管理** | `huggingface_hub` | 自动模型下载（支持镜像源） |
| **路径管理** | `pathlib` | 跨平台路径处理 |

## 2. 详细模块设计 (Detailed Module Design)

### 2.1 模块 A: 配置 (`core/config.py`)

* **职责**: 环境检测与全局设置。
* **关键特性**:
  * **操作系统检测**: `platform.system()` (Darwin/Windows)。
  * **设备检测**:
    * macOS: 检查 `torch.backends.mps.is_available()`。
    * Windows: 检查 `torch.cuda.is_available()`。
    * 后备 (Fallback): `cpu`。
  * **环境设置**: 设置 `HF_ENDPOINT` 为镜像站点（如 `https://hf-mirror.com`）以确保国内下载可靠。
  * **路径**: 定义相对于项目根目录的 `MODELS_DIR`。

### 2.2 模块 B: 数据摄取 (`core/ingestion.py`)

* **职责**: 将 `.docx` 转换为可检索的 `Chunks` (切片)。
* **关键逻辑**:
  * **数据结构**: `Chunk(text, original_index, source_type, metadata)`。
  * **清洗**: 标准化空白字符，移除空行。
  * **切片策略**:
    * 短段落 (< 400 字符): 保持完整。
    * 长段落: **滑动窗口 (Sliding Window)**。
      * 窗口大小: 3-5 个句子。
      * 重叠 (Overlap): 1-2 个句子。
  * **表格处理**: 将行视为单元，用分隔符 (`|`) 组合单元格文本。

### 2.3 模块 C: 检索引擎 (`core/search_engine.py`)

* **职责**: 管理模型并执行搜索流程。
* **类**: `SemanticSearchEngine` (推荐使用单例模式)。
* **初始化**:
  * 如果缺失则下载模型（检查文件完整性）。
  * 加载 `bge-m3` 和 `bge-reranker-large` 到检测到的设备。
* **方法**:
  * `load_document(chunks)`: 批量编码切片 -> `self.doc_vectors` (Tensor/NumPy)。使用 `convert_to_tensor=True`。
  * `search(query, top_k)`:
        1. **检索 (Retrieval)**: 编码查询。计算与 `doc_vectors` 的余弦相似度。检索 Top-N (例如 20-50)。
        2. **重排序 (Reranking)**: 从 Top-N 构建配对 `(query, doc_text)`。输入 Cross-Encoder。
        3. **输出 (Output)**: 按重排序分数排序，返回带有元数据的 Top-K。

### 2.4 模块 D: API 接口 (`api_interface.py`)

* **职责**: 前端交互的门面 (Facade)。
* **关键函数**:
  * `init_engine()`: 线程安全的引擎初始化。
  * `process_file_for_search(path)`: 解析 -> 切片 -> 加载到引擎。
  * `search_query(text)`: 执行搜索。
  * `audit_and_prepare_contract(path)`: (扩展功能) 运行基于规则的审计，生成预览 HTML，并注入用于 UI 高亮的 ID。

## 3. 开发规范 (Development Guidelines)

1. **内存管理**:
    * 模型较大。确保 `SemanticSearchEngine` 是单例 (Singleton)。
    * 避免不必要地复制大型向量数组。
2. **跨平台**:
    * **切勿** 使用字符串拼接路径（例如 `dir + "/" + file`）。**务必** 使用 `pathlib.Path` / 运算符。
    * 不要在 `requirements.txt` 中包含特定平台的二进制文件。
3. **错误处理**:
    * 优雅地处理 `.doc` (旧格式)，抛出清晰的错误提示要求使用 `.docx`。
    * 通过重试或清晰的说明处理模型下载失败（网络问题）。
4. **性能**:
    * 在 `sentence-transformers` 编码中使用 `convert_to_tensor=True`。
    * 通过库隐式使用 `torch.no_grad()`，但要注意 GPU 显存 (VRAM) 的使用。

## 4. 测试策略 (Testing Strategy)

* **单元测试**: 独立测试 `ingestion` 逻辑（滑动窗口正确性）。
* **集成测试**: 在示例文同上运行完整的 `Load -> Search` 流程。
* **设备测试**: 验证 Mac 上的 `mps` 加载和 Windows 上的 `cuda` 加载。
