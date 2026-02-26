import os
import re
import threading
import tempfile
from core.search_engine import SemanticSearchEngine
from core.ingestion import DocProcessor
from core.preview_generator import DocxPreviewGenerator 

# 全局实例
_engine_instance = None
_processor = DocProcessor()
_word_processor = None
_preview_generator = DocxPreviewGenerator() 
_lock = threading.Lock()

def _get_word_processor():
    global _word_processor
    if _word_processor is None:
        from core.word_processor import WordProcessor
        _word_processor = WordProcessor()
    return _word_processor

def init_engine():
    global _engine_instance
    with _lock:
        if _engine_instance is None:
            _engine_instance = SemanticSearchEngine()
    return _engine_instance

def _inject_ids_into_html(html_content, audit_results):
    """
    根据 audit_results 中的 anchor 文本和 id，在 HTML 中插入相应的元素 ID。
    这样点击右侧批注时，JavaScript 可以根据 ID 定位并高亮相应的 HTML 元素。
    """
    result_html = html_content
    for item in audit_results:
        mark_id = item.get('id')
        anchor_text = item.get('anchor', '').strip()
        
        if not mark_id or not anchor_text:
            continue
        
        # 转义特殊字符用于正则表达式
        escaped_anchor = re.escape(anchor_text)
        
        # 方法1：尝试在 HTML 中直接找到该文本，并用带 ID 的 span 包围它
        # 查找 >anchor_text< 的模式（即文本包含在 HTML 标签之间）
        pattern = f'({escaped_anchor})'
        replacement = f'<span id="{mark_id}">\\1</span>'
        
        # 只替换第一个出现的匹配
        result_html = re.sub(pattern, replacement, result_html, count=1)
    
    return result_html

def audit_and_prepare_contract(file_path: str):
    """
    核心业务函数：
    1. 自动审计并根据红线规则进行修订 (WordProcessor)
    2. 生成修订后的临时文档用于预览
    3. 返回审计结果(用于生成右侧卡片)和预览HTML
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件未找到: {file_path}")

    # 创建一个临时文件来保存修订后的文档，防止破坏原件
    # 如果你想直接生成在同目录下，可以改成 path_revised.docx
    temp_dir = tempfile.gettempdir()
    base_name = os.path.basename(file_path)
    revised_path = os.path.join(temp_dir, f"revised_{base_name}")

    try:
        # 1. 执行审计与自动修订，获取返回的卡片列表数据
        # 这个 audit_and_fix 是你在 word_processor.py 中新写的函数
        print(f"[审计开始] 输入文件: {file_path}")
        word_processor = _get_word_processor()
        audit_results = word_processor.audit_and_fix(file_path, revised_path)
        print(f"[审计完成] 发现 {len(audit_results)} 处修改")

        # 2. 生成预览 HTML
        # 注意：这里预览的是修订后的文件，所以能看到删除线和插入内容
        print(f"[生成预览] 正在处理修订文件: {revised_path}")
        preview_result = _preview_generator.generate_html(revised_path)

        # 兼容两种返回：1) HTML文件路径；2) HTML内容字符串
        preview_html_content = None
        preview_html_path = None

        if isinstance(preview_result, str) and os.path.exists(preview_result):
            preview_html_path = preview_result
            print(f"[预览路径] {preview_html_path}")

            # 读取 HTML 文件内容，因为 UI 需要的是内容字符串而不是文件路径
            # Word 导出的 HTML 可能不是 UTF-8 编码，尝试多种编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin-1']
            for encoding in encodings:
                try:
                    with open(preview_html_path, 'r', encoding=encoding) as f:
                        preview_html_content = f.read()
                    print(f"[预览加载] 成功使用编码: {encoding}")
                    break
                except (UnicodeDecodeError, LookupError):
                    continue

            if preview_html_content is None:
                # 如果上述编码都失败，使用 errors='replace' 强制读取
                with open(preview_html_path, 'r', encoding='utf-8', errors='replace') as f:
                    preview_html_content = f.read()
                print(f"[预览加载] 使用 UTF-8 with errors='replace'")
        elif isinstance(preview_result, str) and "<html" in preview_result.lower():
            preview_html_content = preview_result
            print("[预览加载] 预览生成器返回 HTML 内容字符串")
        else:
            raise ValueError("预览生成器未返回有效的 HTML 内容或路径")
        
        print(f"[预览加载] HTML 内容长度: {len(preview_html_content)} 字符")
        
        # 在返回前，在 HTML 中为所有批注的锚点文本添加 ID
        preview_html_content = _inject_ids_into_html(preview_html_content, audit_results)

        return {
            "status": "success",
            "audit_results": audit_results,  # 这里的列表直接给 MainWindow 的 add_audit_card 使用
            "preview_html": preview_html_content,
            "revised_file_path": revised_path,
            "preview_html_path": preview_html_path
        }
    except FileNotFoundError as e:
        print(f"[错误] 文件未找到: {e}")
        return {
            "status": "error", 
            "message": f"文件处理失败：{str(e)}"
        }
    except Exception as e:
        print(f"[错误] 审计过程异常: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error", 
            "message": f"审计失败：{str(e)}"
        }

def process_file_for_search(file_path: str):
    """
    如果还需要语义检索功能，保留此函数。
    """
    if _engine_instance is None:
        init_engine()
    
    chunks = _processor.process(file_path)
    _engine_instance.load_document(chunks)
    return {"status": "success", "chunk_count": len(chunks)}

def search_query(text: str, top_k: int = 10):
    if _engine_instance is None:
        raise RuntimeError("引擎未初始化")
    return _engine_instance.search(text, top_k=top_k)

# --- 保持向下兼容或供 main.py 调用 ---

def get_document_preview(file_path: str):
    """单独获取预览"""
    try:
        return _preview_generator.generate_html(file_path)
    except Exception as e:
        return f"<html><body><p>预览生成失败: {str(e)}</p></body></html>"

if __name__ == "__main__":
    # 测试代码
    test_file = "your_contract.docx" # 替换为你本地的测试合同
    if os.path.exists(test_file):
        print(f"开始测试审计流程: {test_file}")
        report = audit_and_prepare_contract(test_file)
        if report["status"] == "success":
            print(f"审计完成，发现 {len(report['audit_results'])} 处修改。")
            for item in report["audit_results"]:
                print(f"- [{item['level']}] {item['title']}: {item['content']}")