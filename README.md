# Local Legal Contract Semantic Search Backend (Web Version)

这是一个**本地化、高精度、跨语言**的英文法律合同中文语义检索与审计系统。项目已从桌面应用 (Qt) 迁移至 **Web 架构 (B/S)**，旨在通过局域网共享高性能计算资源，提供轻量级、无安装的合同审查体验。

## 📚 项目文档 (Documentation)

请参考以下文档以了解项目的详细规划与进度：

* **[项目总览 (Master Plan)](./master_plan.md)**
  * 包含项目愿景、核心价值、架构概览及未来路线图。
* **[实施计划 (Implementation Plan)](./implementation_plan.md)**
  * 包含详细的技术栈选型、后端 API 设计、Web 前端规范及并发处理策略。
* **[Web 部署方案 (Web Deployment Plan)](./web_deployment_plan.md)**
  * 包含详细的 B/S 架构设计、并发支持、临时文件管理及部署指南。
* **[任务状态 (Tasks Status)](./tasks.md)**
  * 实时更新的项目进度追踪与待办事项清单。

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
