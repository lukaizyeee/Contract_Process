import os
import re
import html
import threading
import tempfile
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
            from core.search_engine import SemanticSearchEngine
            _engine_instance = SemanticSearchEngine()
    return _engine_instance

def _inject_ids_into_html(html_content, audit_results):
    """
    根据 audit_results 中的 anchor 文本和 id，在 HTML 中插入相应的元素 ID。
    使用“文本漫游者”算法(Text Walker)，能够跨越 HTML 标签匹配文本，
    解决因样式、链接导致文本被标签截断而无法匹配的问题。
    """
    if not html_content or not audit_results:
        return html_content

    # 1. 解析 HTML 构建可见文本层 (visible_text) 和 索引映射 (index_map)
    # index_map[i] 表示 visible_text[i] 字符在原始 html_content 中的索引位置
    visible_chars = []
    index_map = []
    
    in_tag = False
    
    # 简单的状态机解析 HTML
    for i, char in enumerate(html_content):
        if char == '<':
            in_tag = True
        
        # 如果不在标签内，且不是换行符(可选，视情况而定，这里保留所有非标签字符)
        # 注意：Word 导出的 HTML 可能包含换行符，通常被视为空白。
        # 但 anchor 文本通常是 clean 的。
        # 我们收集所有非标签字符。
        if not in_tag:
            visible_chars.append(char)
            index_map.append(i)
        
        if char == '>':
            in_tag = False
            
    visible_text_str = "".join(visible_chars)
    
    # 2. 标记已占用的文本区域，防止重复或嵌套包裹
    # claimed[i] = True 表示 visible_text[i] 已被某个 audit item 占用
    claimed = [False] * len(visible_chars)
    
    replacements = [] # 存储待执行的替换操作: {'start': html_idx, 'end': html_idx, 'id': mark_id}
    
    for item in audit_results:
        mark_id = item.get('id')
        anchor_text = item.get('anchor', '').strip()
        
        if not mark_id or not anchor_text:
            continue
            
        # 构造搜索词：因为 visible_text 包含的是 HTML 转义后的字符（如 &amp;）
        # 而 anchor_text 是原始文本（如 &），所以需要转义 anchor 才能匹配
        search_term = html.escape(anchor_text)
        search_len = len(search_term)
        
        if search_len == 0:
            continue

        # 在可见文本中搜索
        start_pos = 0
        while True:
            found_idx = visible_text_str.find(search_term, start_pos)
            if found_idx == -1:
                break
            
            end_idx = found_idx + search_len
            
            # 检查该区域是否已被占用
            # 只要有一个字符被占用，就视为冲突，跳过当前匹配，继续寻找下一个
            is_claimed = False
            if end_idx <= len(claimed):
                is_claimed = any(claimed[found_idx:end_idx])
            
            if not is_claimed:
                # 找到有效且未被占用的匹配！
                
                # 1. 标记占用
                for k in range(found_idx, end_idx):
                    claimed[k] = True
                
                # 2. 计算原始 HTML 中的插入位置
                # 开始位置：匹配到的第一个字符在 HTML 中的索引
                orig_start = index_map[found_idx]
                
                # 结束位置：匹配到的最后一个字符在 HTML 中的索引 + 1 (即插入在字符之后)
                # visible_text[end_idx-1] 是最后一个字符
                orig_end = index_map[end_idx-1] + 1
                
                replacements.append({
                    'start': orig_start,
                    'end': orig_end,
                    'id': mark_id
                })
                
                # 当前 audit item 处理完毕，跳出循环（处理下一个 item）
                break
            
            # 如果被占用，从当前匹配位置后继续搜索
            start_pos = found_idx + 1

    # 3. 执行替换（倒序执行，以免破坏索引）
    replacements.sort(key=lambda x: x['start'], reverse=True)
    
    # 将字符串转为列表以便插入
    html_list = list(html_content)
    
    for rep in replacements:
        s = rep['start']
        e = rep['end']
        m_id = rep['id']
        
        # 先插入后面的结束标签
        html_list.insert(e, "</span>")
        # 再插入前面的开始标签
        html_list.insert(s, f'<span id="{m_id}">')
        
    return "".join(html_list)

def audit_and_prepare_contract(file_path: str):
    """
    核心业务函数：
    1. 自动审计并根据红线规则进行修订 (WordProcessor)
    2. 生成修订后的临时文档用于预览
    3. 返回审计结果(用于生成右侧卡片)和预览HTML
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件未找到: {file_path}")

    # 将修订后的文件保存到临时目录
    # 命名规则：原文件名_revised.docx
    base_name = os.path.basename(file_path)
    file_name_without_ext = os.path.splitext(base_name)[0]
    revised_filename = f"{file_name_without_ext}_revised.docx"
    
    # 确保文件保存在输入文件所在的目录，以避免多线程时的路径混乱
    # 输入文件已经在 temp_dir 中，所以直接使用其 dirname
    revised_path = os.path.join(os.path.dirname(file_path), revised_filename)

    try:
        # 1. 执行审计与自动修订，获取返回的卡片列表数据
        # 这个 audit_and_fix 是你在 word_processor.py 中新写的函数
        print(f"[审计开始] 输入文件: {file_path}")
        print(f"[审计输出] 目标路径: {revised_path}")
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
