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
from api_interface import audit_and_prepare_contract, init_engine

# 创建线程池以处理同步的审计任务，避免阻塞主线程
executor = ThreadPoolExecutor(max_workers=5)

# 全局临时目录，用于存放处理结果以便下载 (需定期清理)
# 注意：在生产环境中，应使用 Redis 或数据库记录 request_id 与文件路径的映射，并配合后台任务清理
GLOBAL_TEMP_DIR = Path(tempfile.gettempdir()) / "legal_audit_results"
GLOBAL_TEMP_DIR.mkdir(parents=True, exist_ok=True)

from contextlib import asynccontextmanager

MODEL_STATUS = {
    "state": "not_started",
    "message": "",
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    MODEL_STATUS["state"] = "loading"
    MODEL_STATUS["message"] = "正在初始化 AI 引擎..."
    print(MODEL_STATUS["message"], flush=True)

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(executor, init_engine)
        MODEL_STATUS["state"] = "ready"
        MODEL_STATUS["message"] = "AI 引擎初始化完成"
        print(MODEL_STATUS["message"], flush=True)
    except Exception as e:
        MODEL_STATUS["state"] = "error"
        MODEL_STATUS["message"] = f"AI 引擎初始化失败: {e}"
        print(MODEL_STATUS["message"], flush=True)
    yield

app = FastAPI(title="Legal Audit Web", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    # 返回前端页面 (index.html)
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/status")
async def get_status():
    return JSONResponse(
        {
            "model": MODEL_STATUS,
        }
    )

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
    # 增加 CORS 中间件以减少浏览器限制，尽管这不能解决 AP 隔离问题
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)
