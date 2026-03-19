# 项目结构与功能指南

本文档记录**当前仓库的真实结构、职责边界和数据流**。如果你要理解或修改这个项目，请优先以本文件为准。

本文档只描述“当前代码中已经存在或已经约定清楚的内容”。未来规划请看 [master_plan.md](./master_plan.md)，具体审计目标请看 [audit_implementation_plan.md](./audit_implementation_plan.md)。

## 1. 当前目录结构

```text
code/
├── web_server.py
├── api_interface.py
├── needs-260211.txt
├── requirements.txt
├── core/
│   ├── config.py
│   ├── ingestion.py
│   ├── preview_generator.py
│   ├── search_engine.py
│   └── word_processor.py
├── doc/
│   ├── ai_instruction.md
│   ├── audit_implementation_plan.md
│   ├── implementation_plan.md
│   ├── master_plan.md
│   ├── project_structure.md
│   └── tasks.md
├── models/
│   ├── bge-m3/
│   └── bge-reranker-large/
├── static/
└── templates/
    └── index.html
```

补充说明：

* 仓库当前**没有** `tests/` 目录，`pytest` 依赖已存在，但测试体系尚未补齐。
* `models/` 用于本地缓存 Hugging Face 模型。
* `static/` 当前已挂载，但仓库内几乎没有实际静态资源。

## 2. 模块职责

### 2.1 Web 服务层

* [web_server.py](/Users/aizyeee/ZZH/dentons_work/code/web_server.py)
* 职责：
  * 创建 FastAPI 应用
  * 在启动阶段初始化搜索引擎
  * 提供上传、状态查询、下载接口
  * 使用 `ThreadPoolExecutor` 承载同步审计任务
  * 使用 `request_id` 隔离每次请求的临时文件目录
* 当前接口：
  * `GET /`
  * `GET /api/status`
  * `POST /api/audit`
  * `GET /api/download/{request_id}/{filename}`

### 2.2 编排层

* [api_interface.py](/Users/aizyeee/ZZH/dentons_work/code/api_interface.py)
* 职责：
  * 维护全局单例对象
  * 执行“审计 -> 预览 -> 注入锚点 -> 返回结果”的主流程
  * 暴露独立的检索引擎装载与查询函数
* 当前状态：
  * 主审计流程调用 `WordProcessor.audit_and_fix`
  * 主审计流程**没有**调用 `DocProcessor.process -> engine.load_document -> engine.search`
  * 语义检索能力存在，但与主审计链路仍是分离状态

### 2.3 核心模块

* [core/config.py](/Users/aizyeee/ZZH/dentons_work/code/core/config.py)
  * 负责设备检测和模型目录配置
  * 当前会设置 `HF_ENDPOINT=https://hf-mirror.com`

* [core/search_engine.py](/Users/aizyeee/ZZH/dentons_work/code/core/search_engine.py)
  * 提供 `bge-m3 + bge-reranker-large` 双阶段检索
  * 支持本地模型完整性检查、自动下载、向量化和重排
  * 必须作为单例使用

* [core/ingestion.py](/Users/aizyeee/ZZH/dentons_work/code/core/ingestion.py)
  * 使用 `python-docx` 读取 `.docx`
  * 将段落和表格切成 `Chunk`
  * 目前主要服务于独立检索流程，尚未接入主审计链路

* [core/word_processor.py](/Users/aizyeee/ZZH/dentons_work/code/core/word_processor.py)
  * 当前是审计主引擎
  * 负责规则识别和 OpenXML 修订注入
  * 当前已实现的主能力：
    * 中国手机号识别
    * 126/163 邮箱识别
    * 签字职位缺失的简单文本检查
    * 发票语句补充
    * 争议解决条款替换
    * 指定罚息文本删除
  * 当前未实现的主能力：
    * 基于语义检索的正文定位
    * Party 身份识别
    * 邮件与合同一致性检查
    * 银行账户变更条款检查
    * 退款条款补充
    * 代扣税条款补充
    * 基于姓名/职位语义判断的签字检查
  * 备注：
    * `add_comment` 当前不是标准 Word comment 写入，而是插入一个可见的 `[批注: ...]` 修订标记

* [core/preview_generator.py](/Users/aizyeee/ZZH/dentons_work/code/core/preview_generator.py)
  * 负责将修订后的 `.docx` 转为 HTML
  * 支持 `<w:ins>` / `<w:del>` 的可视化显示
  * 会尝试读取 comments part，但当前主流程写入的批注主要还是可见文本插入

### 2.4 前端

* [templates/index.html](/Users/aizyeee/ZZH/dentons_work/code/templates/index.html)
* 当前是单文件前端页面
* 职责：
  * 上传文件
  * 轮询模型状态
  * 渲染 HTML 预览
  * 展示审计卡片
  * 点击卡片后滚动并高亮文档内容

## 3. 当前主数据流

1. 用户在前端上传 `.docx`
2. `web_server.py` 为请求创建独立目录并保存原文件
3. `web_server.py` 在线程池中调用 `api_interface.audit_and_prepare_contract`
4. `api_interface.py` 调用 `WordProcessor.audit_and_fix`
5. `WordProcessor` 输出带修订痕迹的 `.docx`
6. `api_interface.py` 调用 `DocxPreviewGenerator.generate_html`
7. `api_interface.py` 根据 `audit_results` 在 HTML 中注入锚点 `id`
8. `web_server.py` 将 `audit_results + preview_html + download_url` 返回前端
9. 前端渲染结果，并在点击卡片时跳转到对应片段

## 4. 开发边界

以下约束仍然有效：

* 不要在底层模块中重复初始化 `SemanticSearchEngine`
* 不要把请求级状态写入全局变量
* 不要在 `WordProcessor` 中拼装前端 HTML
* 不要假设当前主审计链路已经完成语义化，若要新增语义审计，需要显式接入 `DocProcessor` 和 `SemanticSearchEngine`

## 5. 文档使用建议

* 想理解“仓库现在是什么”：先看本文件
* 想理解“项目想做成什么”：看 [master_plan.md](./master_plan.md)
* 想理解“核心业务需求是什么”：看 [needs-260211.txt](../needs-260211.txt) 和 [audit_implementation_plan.md](./audit_implementation_plan.md)
