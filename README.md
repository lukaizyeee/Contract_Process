# Local Legal Contract Semantic Search Backend (Web Version)

这是一个**本地化、高精度、跨语言**的英文法律合同中文语义检索与审计系统。项目已从桌面应用 (Qt) 迁移至 **Web 架构 (B/S)**，旨在通过局域网共享高性能计算资源，提供轻量级、无安装的合同审查体验。

## 📚 项目文档导航 (Documentation Navigation)

为了帮助开发者和用户快速理解项目，我们将文档分为以下几类：

### 核心架构与规范
*   **[项目结构与功能指南 (project_structure.md)](./project_structure.md)**
    *   **必读**。定义了项目的目录结构、各模块（Web服务、API层、核心引擎）的职责边界、数据流向及开发防坑指南。
*   **[AI 工作指引 (ai_instruction.md)](./ai_instruction.md)**
    *   规定了 AI 助手在执行代码修改任务前的阅读规范，强调“先读后写”原则，确保代码风格和架构的一致性。

### 规划与实施
*   **[项目总览 (master_plan.md)](./master_plan.md)**
    *   阐述了项目的宏观愿景、核心价值（隐私优先、零安装）、技术约束及未来路线图。
*   **[实施计划 (implementation_plan.md)](./implementation_plan.md)**
    *   包含详细的技术栈选型（FastAPI, python-docx）、后端 API 设计及 Web 前端架构规范。
*   **[审计功能实现计划 (audit_implementation_plan.md)](./audit_implementation_plan.md)**
    *   专注于合同审计业务逻辑，详细描述了从正则匹配到语义检索的升级路径，以及具体的修订规则（如敏感信息批注、条款增删）。

### 进度追踪
*   **[任务状态 (tasks.md)](./tasks.md)**
    *   实时更新的项目进度追踪，包含已完成的功能（架构重构、预览生成）和待办事项（多用户支持、LLM集成）。

---

## 🚀 快速开始 (Quick Start)

### 1. 环境准备 (Mac Mini Server)

* 确保安装 Python 3.11+
* 安装依赖:

  ```bash
  pip install -r requirements.txt
  ```

### 2. 启动服务

在服务器端运行：

```bash
python web_server.py
```

终端将显示访问地址，例如：

* 本地访问: `http://127.0.0.1:8000`
* 局域网访问: `http://<本机IP>:8000` (如 `http://192.168.1.5:8000`)

### 3. 用户使用

* **无需安装**: 用户只需在同一局域网下的电脑或手机浏览器中输入上述 IP 地址。
* **功能**:
  * **合同预览**: 左侧展示高保真的合同 HTML 预览。
  * **智能审计**: 右侧自动列出合规性风险（如敏感信息、缺失条款）。
  * **交互高亮**: 点击右侧卡片，左侧原文自动滚动并高亮。
  * **下载修订**: 审计完成后，可一键下载带有红线修订痕迹的 `.docx` 文件。
