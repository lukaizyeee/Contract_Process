# 实施计划

本文档描述的是**更贴近当前代码状态的实施方案**，并明确后续扩展应从哪里继续推进。

## 1. 当前技术栈

| 组件 | 当前选型 | 状态 |
| :--- | :--- | :--- |
| Web 框架 | `FastAPI` | 已使用 |
| 应用服务器 | `Uvicorn` | 已使用 |
| 前端 | HTML + 原生 JS | 已使用 |
| 文档解析 | `python-docx` | 已使用 |
| 修订写入 | OpenXML 注入 | 已使用 |
| 语义召回 | `BAAI/bge-m3` | 已实现，未接入主审计链路 |
| 重排 | `BAAI/bge-reranker-large` | 已实现，未接入主审计链路 |
| 并发控制 | `ThreadPoolExecutor` | 已使用 |

## 2. 当前实现结构

### 2.1 Web 服务层

当前 [web_server.py](/Users/aizyeee/ZZH/dentons_work/code/web_server.py) 已经实现：

* `GET /`
* `GET /api/status`
* `POST /api/audit`
* `GET /api/download/{request_id}/{filename}`

当前做法：

* 启动时异步初始化搜索引擎
* 请求到来后将上传文件写入请求级目录
* 在线程池中执行同步审计
* 返回结构化 JSON 给前端

当前缺口：

* 没有后台清理任务，临时目录可能持续堆积
* CORS 中间件仅在 `__main__` 启动路径中添加
* 缺少更细粒度的错误分类和日志结构

### 2.2 编排层

当前 [api_interface.py](/Users/aizyeee/ZZH/dentons_work/code/api_interface.py) 的主流程是：

1. 计算修订版输出路径
2. 调用 `WordProcessor.audit_and_fix`
3. 调用 `DocxPreviewGenerator.generate_html`
4. 向 HTML 注入跳转锚点
5. 返回审计结果和预览内容

当前缺口：

* 搜索引擎虽已初始化，但主流程未装载文档向量
* `process_file_for_search` 和 `search_query` 还停留在备用接口状态

### 2.3 前端

当前 [templates/index.html](/Users/aizyeee/ZZH/dentons_work/code/templates/index.html) 是单文件 SPA，已实现：

* 上传 `.docx`
* 模型状态展示
* Loading 遮罩
* 审计分类展示
* 卡片跳转高亮
* 修订版下载

当前缺口：

* 无移动端特别适配
* 大文档渲染可能有性能问题
* 没有更细的错误 UI

### 2.4 核心处理

当前 [core/word_processor.py](/Users/aizyeee/ZZH/dentons_work/code/core/word_processor.py) 是审计主链路核心。

实现特点：

* 使用 `python-docx` 读写文档
* 通过 OpenXML 注入 `<w:ins>` / `<w:del>`
* 当前“批注”使用可见文本插入兜底，不是完整 Word comment 对象

## 3. 下一步实施重点

以 [needs-260211.txt](../needs-260211.txt) 为准，建议按下面顺序推进：

1. 校准基础语义和配置
   * 批注作者大小写是否严格使用 `dacheng`
   * 我方身份识别与称呼抽取
2. 接入语义审计主链路
   * `DocProcessor.process`
   * `SemanticSearchEngine.load_document`
   * 按审计点构造查询并定位段落
3. 补齐正文核心条款
   * 退款
   * 银行账户变更
   * 代扣税
4. 补齐文首文末审计
   * 中国人姓名识别
   * Title/represented by 检查
5. 最后再接 LLM

## 4. 工程建议

* 在实现语义审计前先补自动化测试样本
* 将审计结果增加 `source` 字段，例如 `rule`、`semantic`、`llm`
* 将“需求映射表”和“测试样本”绑定，避免文档和实现再次漂移
