# 全栈 Web 服务化部署方案 (Web-Based Deployment Plan)

本文档详细描述了如何将现有的 PyQt 桌面应用改造为 **B/S 架构 (Browser/Server)** 的全栈 Web 应用。改造后，用户无需安装任何客户端，只需在局域网内的浏览器访问服务器 IP 即可使用完整的合同审计与检索功能。

## 1. 架构设计 (Architecture Design)

### 1.1 核心目标

- **零客户端安装**：用户通过浏览器直接访问。
- **局域网共享**：Mac Mini 作为中心服务器，承担所有计算（文档解析、模型推理、网页托管）。
- **体验一致性**：保留原有的“左侧预览 + 右侧审计卡片”的双栏布局，以及“点击跳转高亮”的交互体验。

### 1.2 技术栈选型 (Tech Stack)

为了最大化利用现有 Python 代码并降低开发成本，推荐采用 **轻量级全栈方案**：

- **后端 (Backend)**: `FastAPI`
  - 高性能 Python Web 框架，天然支持异步，适合 AI 模型推理服务。
  - 直接复用现有的 `core/` 目录代码。
- **前端 (Frontend)**: `HTML5` + `JavaScript` (原生或轻量框架如 Vue.js CDN)
  - 直接嵌入在 FastAPI 中，无需独立的 Node.js 构建环境，部署极简。
  - 复用 `core/preview_generator.py` 生成的 HTML/CSS。
- **服务器 (Server)**: `Uvicorn`
  - 生产级 ASGI 服务器，支持并发。

---

## 2. 实施步骤 (Implementation Steps)

### 2.1 核心代码适配 (Core Adaptation for Concurrency)

为了支持多用户并发（Multi-User Concurrency），需修改 `api_interface.py` 中的临时文件处理逻辑，避免文件名冲突。

**修改 `api_interface.py` 中的 `audit_and_prepare_contract` 函数：**

- **当前逻辑**: 使用 `base_dir` 和固定的 `_revised.docx` 后缀，会导致并发冲突。
- **适配逻辑**:
  - 接收可选参数 `temp_dir`。
  - 如果提供了 `temp_dir`，则在该目录下生成唯一的修订文件（例如使用 `uuid`）。
  - 或者由调用方（FastAPI）负责传入一个唯一的临时路径。

### 2.2 后端改造 (Backend Refactoring)

在项目根目录新建 `web_server.py`，作为新的程序入口。

#### **功能职责**

1. **静态文件托管**: 提供前端页面 (HTML/JS/CSS)。
2. **API 接口**:
    - `POST /api/audit`: 接收上传的 `.docx` 文件，为每个请求创建独立临时目录，执行 `api_interface.py` 中的逻辑。
    - `GET /api/download/{request_id}/{filename}`: 提供修订后的 `.docx` 文件下载。

#### **代码复用策略**

- **直接调用**: `api_interface.py` 中的 `audit_and_prepare_contract` 函数无需修改，直接被 API 路由调用。

- **并发安全**: 使用 `tempfile.TemporaryDirectory` 为每个请求创建隔离环境。

### 2.3 前端重构 (Frontend Reconstruction)

在项目根目录新建 `templates/index.html`，复刻 `main_ui_qt.py` 的界面布局。

#### **布局结构 (Flexbox)**

- **左侧 (75%)**: `<iframe>` 或 `div` 容器，用于渲染后端返回的预览 HTML。

- **右侧 (25%)**: 审计卡片列表容器，样式参考 `AuditCard` 的 CSS。

#### **交互逻辑 (JavaScript)**

- **文件上传**: 监听 `<input type="file">` 的 `change` 事件，使用 `fetch` API 发送 `FormData` 给后端。

- **渲染卡片**: 接收后端返回的 JSON 数据 (`audit_results`)，动态生成 DOM 节点。
- **点击跳转**: 复用 `main_ui_qt.py` 中的 `jump_to_mark` JavaScript 逻辑（[main_ui_qt.py:L224](file:///Users/aizyeee/ZZH/dentons_work/code/main_ui_qt.py#L224)），实现平滑滚动和高亮。

---

## 3. 详细实施方案 (Detailed Plan)

### 步骤 1: 环境准备

服务器端 (Mac Mini) 安装依赖：

```bash
pip install fastapi uvicorn[standard] python-multipart jinja2 aiofiles
```

### 步骤 2: 创建 Web 服务入口 (`web_app.py`)

```python
import os
import shutil
import uuid
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pathlib import Path
import uvicorn
from concurrent.futures import ThreadPoolExecutor
import asyncio

# 复用现有核心逻辑
from api_interface import audit_and_prepare_contract

app = FastAPI(title="Legal Audit Web")

# 创建线程池以处理同步的审计任务，避免阻塞主线程
executor = ThreadPoolExecutor(max_workers=5) # 限制最大并发数为 5

# 全局临时目录，用于存放处理结果以便下载 (需定期清理)
# 注意：在生产环境中，应使用 Redis 或数据库记录 request_id 与文件路径的映射，并配合后台任务清理
GLOBAL_TEMP_DIR = Path(tempfile.gettempdir()) / "legal_audit_results"
GLOBAL_TEMP_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    # 返回前端页面 (index.html)
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/audit")
async def audit_document(file: UploadFile = File(...)):
    """
    处理文件上传 -> 审计 -> 返回结果
    支持多用户并发：每个请求在独立的临时目录中处理
    """
    request_id = str(uuid.uuid4())
    # 使用全局临时目录下的子目录，以便后续下载接口可以找到
    temp_dir = GLOBAL_TEMP_DIR / request_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # 1. 保存上传文件
        file_path = temp_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. 调用核心审计逻辑 (在线程池中运行)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor, 
            audit_and_prepare_contract, 
            str(file_path)
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
            
        # 3. 构造下载链接
        # revised_file_path 是绝对路径，我们需要提取文件名
        revised_filename = os.path.basename(result["revised_file_path"])
        download_url = f"/api/download/{request_id}/{revised_filename}"

        # 4. 返回结构化数据
        return JSONResponse({
            "status": "success",
            "audit_results": result["audit_results"],
            "preview_html": result["preview_html"],
            "download_url": download_url
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        # 出错时立即清理
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/{request_id}/{filename}")
async def download_file(request_id: str, filename: str):
    """
    提供修订后的文件下载
    """
    file_path = GLOBAL_TEMP_DIR / request_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found or expired")
    
    # 可以在此处添加逻辑：下载后是否立即删除？
    # 为了用户体验（可能多次下载），建议通过后台定时任务清理，而不是下载即删
    return FileResponse(
        path=file_path, 
        filename=filename, 
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )

if __name__ == "__main__":
    # 局域网访问配置
    # host="0.0.0.0" 表示允许局域网内其他设备访问
    # host="127.0.0.1" 表示仅允许本机访问（调试模式）
    print("启动服务...")
    print("本地访问: http://127.0.0.1:8000")
    print("局域网访问: http://<你的本机IP>:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 步骤 3: 创建前端页面 (`templates/index.html`)

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>合同智能审计系统</title>
    <style>
        /* 复刻 main_ui_qt.py 的样式 */
        body { margin: 0; display: flex; height: 100vh; font-family: 'Segoe UI', sans-serif; background: #F2F2F7; }
        
        /* 左侧预览区 */
        #preview-container { flex: 3; background: white; margin: 10px; border-radius: 10px; overflow: hidden; display: flex; flex-direction: column; }
        #doc-frame { flex: 1; border: none; width: 100%; height: 100%; }
        
        /* 右侧审计区 */
        #audit-panel { flex: 1; background: white; margin: 10px 10px 10px 0; border-radius: 10px; display: flex; flex-direction: column; padding: 15px; }
        .audit-card { 
            background: white; border: 1px solid #D1D1D6; border-radius: 8px; 
            padding: 12px; margin-bottom: 10px; cursor: pointer; transition: 0.2s;
        }
        .audit-card:hover { background: #F2F2F7; }
        .audit-card.error { border-left: 5px solid #FF3B30; }
        .audit-card.warning { border-left: 5px solid #FF9500; }
        
        /* 顶部工具栏 */
        .toolbar { padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
        .btn { padding: 8px 16px; background: #007AFF; color: white; border: none; border-radius: 6px; cursor: pointer; }
        .btn:disabled { background: #ccc; }
    </style>
</head>
<body>
    <!-- 左侧 -->
    <div id="preview-container">
        <div class="toolbar">
            <span style="font-weight: bold; color: #007AFF;">📄 合同预览</span>
            <div>
                <input type="file" id="fileInput" accept=".docx" style="display: none">
                <button class="btn" onclick="document.getElementById('fileInput').click()">上传合同</button>
                <a id="downloadBtn" class="btn" style="display:none; text-decoration:none; margin-left:10px; background:#34C759;">下载修订版</a>
            </div>
        </div>
        <!-- 用于渲染 HTML 内容的容器 -->
        <div id="doc-content" style="flex:1; overflow:auto; padding:20px;"></div>
    </div>

    <!-- 右侧 -->
    <div id="audit-panel">
        <h3 style="color: #007AFF; margin-top: 0;">🔍 审查建议</h3>
        <div id="audit-list" style="overflow-y: auto; flex: 1;">
            <div style="color: #888; text-align: center; margin-top: 20px;">请上传文档开始审计</div>
        </div>
    </div>

    <script>
        const fileInput = document.getElementById('fileInput');
        const auditList = document.getElementById('audit-list');
        const docContent = document.getElementById('doc-content');
        const downloadBtn = document.getElementById('downloadBtn');

        fileInput.addEventListener('change', async (e) => {
            if (!e.target.files[0]) return;
            
            const formData = new FormData();
            formData.append('file', e.target.files[0]);
            
            auditList.innerHTML = '<div style="text-align:center">⏳ 正在审计中...</div>';
            downloadBtn.style.display = 'none'; // 隐藏下载按钮
            
            try {
                const resp = await fetch('/api/audit', { method: 'POST', body: formData });
                const data = await resp.json();
                
                if (data.status === 'success') {
                    renderResult(data);
                } else {
                    alert('审计失败: ' + data.detail);
                }
            } catch (err) {
                alert('网络错误: ' + err.message);
            }
        });

        function renderResult(data) {
            // 1. 渲染预览 HTML (直接注入 Shadow DOM 以隔离样式，或者直接 innerHTML)
            docContent.innerHTML = data.preview_html;
            
            // 2. 显示下载按钮
            if (data.download_url) {
                downloadBtn.href = data.download_url;
                downloadBtn.style.display = 'inline-block';
            }
            
            // 3. 渲染右侧卡片
            auditList.innerHTML = '';
            data.audit_results.forEach(item => {
                const card = document.createElement('div');
                card.className = `audit-card ${item.level}`;
                card.innerHTML = `
                    <div style="font-weight:bold">
                        ${item.level === 'error' ? '🚩' : '⚠️'} ${item.title}
                    </div>
                    <div style="font-size: 0.9em; margin: 5px 0; color: #333;">${item.content}</div>
                    <div style="font-size: 0.8em; color: #888;">原文: "${item.anchor}"</div>
                `;
                card.onclick = () => jumpToMark(item.id);
                auditList.appendChild(card);
            });
        }

        // 复刻 main_ui_qt.py 中的跳转逻辑
        function jumpToMark(markId) {
            const el = document.getElementById(markId);
            if (!el) return;
            
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            // 高亮动画
            const originalBg = el.style.backgroundColor;
            el.style.backgroundColor = '#B8E6B8';
            el.style.transition = 'background-color 0.5s';
            
            setTimeout(() => {
                el.style.backgroundColor = originalBg;
            }, 2000);
        }
    </script>
</body>
</html>
```

---

## 4. 优势总结 (Benefits)

1. **极简部署**: 仅需在 Mac Mini 上运行 `web_app.py`。
2. **零依赖**: 客户端不需要安装 Python、Qt 或任何环境，只要有浏览器即可。
3. **无缝体验**: 前端逻辑完美复刻了原 Qt 版本的交互，用户无需重新学习。
4. **代码复用**: 核心的审计引擎 (`core/`) 和接口层 (`api_interface.py`) 代码无需任何修改，直接作为后端逻辑运行。
