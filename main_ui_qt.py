import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QLabel, 
                             QFileDialog, QSplitter, QFrame, QScrollArea, QSizePolicy)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QFont


def _preload_engine_before_ui():
    """Block startup until model initialization/download completes."""
    from api_interface import init_engine

    print("[启动] 正在初始化语义检索引擎（可能下载模型，请稍候）...", flush=True)
    init_engine()
    print("[启动] 模型初始化完成，准备打开主窗口。", flush=True)

# 模拟导入后端接口，实际使用时请确保 api_interface.py 在路径中
# from api_interface import init_engine, process_file, get_document_preview

# --- 自定义批注卡片组件 ---
class AuditCard(QFrame):
    """右侧审计结果卡片"""
    def __init__(self, mark_id, level, title, content, anchor_text, on_click_callback):
        super().__init__()
        self.mark_id = mark_id
        self.on_click_callback = on_click_callback
        
        # 颜色配置：error(红色), warning(橙色)
        color = "#FF3B30" if level == "error" else "#FF9500"
        
        self.setObjectName("AuditCard")
        self.setStyleSheet(f"""
            #AuditCard {{
                background-color: white;
                border: 1px solid #D1D1D6;
                border-left: 5px solid {color};
                border-radius: 10px;
                padding: 12px;
            }}
            #AuditCard:hover {{
                background-color: #F2F2F7;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # 标题行
        title_label = QLabel(f"{'🚩' if level=='error' else '⚠️'} {title}")
        title_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title_label.setStyleSheet("color: #1C1C1E; border: none;")
        
        # 建议内容
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setFont(QFont("Segoe UI", 11))
        content_label.setStyleSheet("color: #3A3A3C; border: none;")

        # 锚点文本预览
        anchor_label = QLabel(f"原文位置: \"{anchor_text}\"")
        anchor_label.setStyleSheet("color: #8E8E93; font-size: 13px; font-style: italic; border: none;")

        layout.addWidget(title_label)
        layout.addWidget(content_label)
        layout.addWidget(anchor_label)

        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if self.on_click_callback:
            self.on_click_callback(self.mark_id)
        super().mousePressEvent(event)

# --- 主窗口 ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Searching.app - 法律合同智能合规审计")
        self.resize(1200, 750)
        self.setStyleSheet("QMainWindow { background-color: #F2F2F7; }")

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: #D1D1D6; }")

        # --- 左侧：原文预览区 ---
        left_panel = QFrame()
        left_panel.setStyleSheet("QFrame { background-color: white; border-radius: 15px; }")
        left_layout = QVBoxLayout(left_panel)
        
        left_header = QHBoxLayout()
        left_title = QLabel("📄 合同预览 (修订预览模式)")
        left_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        left_title.setStyleSheet("color: #007AFF;")
        
        self.upload_btn = QPushButton("上传合同文档")
        self.upload_btn.setFixedWidth(120)
        self.upload_btn.clicked.connect(self.handle_upload)
        
        # 放大 / 缩小 按钮
        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setFixedSize(28, 28)
        self.zoom_out_btn.setToolTip("缩小预览")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.zoom_out_btn.setStyleSheet("font-size:14px;")

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedSize(28, 28)
        self.zoom_in_btn.setToolTip("放大预览")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_in_btn.setStyleSheet("font-size:14px;")
        
        left_header.addWidget(left_title)
        left_header.addStretch()
        left_header.addWidget(self.zoom_out_btn)
        left_header.addWidget(self.zoom_in_btn)
        left_header.addWidget(self.upload_btn)
        left_layout.addLayout(left_header)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #F2F2F7;")
        left_layout.addWidget(line)

        self.doc_view = QWebEngineView()
        # 初始缩放比例
        self.zoom_factor = 1.0
        self.doc_view.setZoomFactor(self.zoom_factor)
        left_layout.addWidget(self.doc_view)

        # --- 右侧：审计建议区 ---
        right_panel = QFrame()
        right_panel.setStyleSheet("QFrame { background-color: white; border-radius: 15px; }")
        right_panel.setFixedWidth(450)
        right_layout = QVBoxLayout(right_panel)

        right_title = QLabel("🔍 合规审查建议")
        right_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        right_title.setStyleSheet("color: #007AFF; margin-bottom: 5px;")
        right_layout.addWidget(right_title)

        # 批注卡片滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        self.audit_list_widget = QWidget()
        self.audit_list_layout = QVBoxLayout(self.audit_list_widget)
        self.audit_list_layout.setAlignment(Qt.AlignTop)
        self.audit_list_layout.setSpacing(10)
        
        self.scroll_area.setWidget(self.audit_list_widget)
        right_layout.addWidget(self.scroll_area)

        # 底部状态展示
        self.status_label = QLabel("等待上传文档...")
        self.status_label.setStyleSheet("color: #8E8E93; font-size: 12px; padding: 5px;")
        right_layout.addWidget(self.status_label)

        # 添加到分割器
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)

    # --- 逻辑处理 ---
    def handle_upload(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择合同", "", "Word Documents (*.docx)")
        if file_path:
            self.status_label.setText("🔍 正在进行合规性审计...")
            self.upload_btn.setEnabled(False) # 防止重复点击
            
            # 这里的 audit_and_prepare_contract 是我们在 api_interface 里新定义的
            from api_interface import audit_and_prepare_contract
            
            # 为了防止界面卡死，实际建议用 QThread。这里先写同步逻辑确认功能：
            try:
                result = audit_and_prepare_contract(file_path)
                if result["status"] == "success":



                    # 在 self.doc_view.setHtml(result["preview_html"]) 之前
                    print(f"DEBUG: 预览HTML长度为: {len(result['preview_html'])}")
                    if len(result['preview_html']) < 100:
                        print(f"DEBUG: 预览内容异常: {result['preview_html']}")
                    # 1. 更新 HTML 预览
                    self.doc_view.setHtml(result["preview_html"])
                    
                    # 2. 清空并填充右侧审计卡片
                    self.clear_audit_list()
                    for item in result["audit_results"]:
                        self.add_audit_card(
                            item['id'], item['level'], item['title'], 
                            item['content'], item['anchor']
                        )
                    self.status_label.setText(f"✅ 审计完成，发现 {len(result['audit_results'])} 处修改")
                else:
                    self.status_label.setText(f"❌ 审计失败: {result.get('message')}")
            except Exception as e:
                self.status_label.setText(f"❌ 发生错误: {str(e)}")
            finally:
                self.upload_btn.setEnabled(True)

    def add_audit_card(self, mark_id, level, title, content, anchor_text):
        card = AuditCard(mark_id, level, title, content, anchor_text, self.jump_to_mark)
        self.audit_list_layout.addWidget(card)

    def jump_to_mark(self, mark_id):
        """点击卡片：先平滑滚动到目标位置，再高亮 3 秒然后恢复"""
        js_code = f"""
            (function() {{
                var el = document.getElementById('{mark_id}');
                if (!el) return;

                var startY = window.pageYOffset;
                var targetY = el.getBoundingClientRect().top + window.pageYOffset - 150;
                var duration = 800; // ms
                var start = null;

                function ease(t) {{
                    return t < 0.5 ? 2*t*t : -1 + (4 - 2*t)*t;
                }}

                function step(timestamp) {{
                    if (!start) start = timestamp;
                    var elapsed = timestamp - start;
                    var progress = Math.min(elapsed / duration, 1);
                    var y = startY + (targetY - startY) * ease(progress);
                    window.scrollTo(0, y);

                    if (progress < 1) {{
                        requestAnimationFrame(step);
                    }} else {{
                        // 滚动完成后再执行高亮
                        try {{
                            var prev = el.getAttribute('data-prev-bg');
                            if (prev === null) {{
                                var cs = window.getComputedStyle(el);
                                prev = cs && cs.backgroundColor ? cs.backgroundColor : '';
                                el.setAttribute('data-prev-bg', prev);
                            }}
                        }} catch(e) {{ /* ignore */ }}

                        el.style.backgroundColor = '#B8E6B8';
                        el.style.transition = 'background-color 0.5s ease-out';

                        setTimeout(function() {{
                            var original = el.getAttribute('data-prev-bg') || '';
                            el.style.backgroundColor = original || 'transparent';
                            el.removeAttribute('data-prev-bg');
                        }}, 3000);
                    }}
                }}

                requestAnimationFrame(step);
            }})();
        """
        self.doc_view.page().runJavaScript(js_code)

    def zoom_in(self):
        """放大预览"""
        try:
            self.zoom_factor = min(self.zoom_factor + 0.1, 3.0)
            self.doc_view.setZoomFactor(self.zoom_factor)
        except Exception:
            pass

    def zoom_out(self):
        """缩小预览"""
        try:
            self.zoom_factor = max(self.zoom_factor - 0.1, 0.3)
            self.doc_view.setZoomFactor(self.zoom_factor)
        except Exception:
            pass

    def clear_audit_list(self):
        while self.audit_list_layout.count():
            item = self.audit_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def mock_audit_process(self, file_path):
        """模拟后端返回审计结果数据"""
        self.clear_audit_list()
        
        # 模拟展示 HTML 内容 (实际由 get_document_preview 生成)
        mock_html = """
        <html><body style='font-family: sans-serif; padding: 20px; line-height: 1.6;'>
            <h2>PAYROLL SERVICE AGREEMENT</h2>
            <p>Contact: <span>+86 13800000000</span> (Global check)</p>
            <p>1. Payment terms: The client shall remit funds...</p>
            <p style='background-color: #e1f5fe; border-bottom: 2px dashed blue;'>
                [Revision] <span>prior to each payment made by Party A</span>
            </p>
            <p><span>DISPUTE RESOLUTION</span>: This Agreement shall be governed by and construed in accordance with the laws of Philippines.</p>
            <p>Bank: <span>Unionbank of the Philippines</span></p>
        </body></html>
        """
        self.doc_view.setHtml(mock_html)

        # 模拟根据你提出的红线规则生成的批注
        results = [
            {"id": "mark_sensitive_0", "level": "warning", "title": "敏感联系方式", "content": "全文不得有中国电话 (+86)，请确认是否保留。", "anchor": "+86 13800000000"},
            {"id": "mark_payment_invoice", "level": "error", "title": "发票条款自动补全", "content": "检测到缺失先票后款约定，已按照红线规则自动插入补全条款。", "anchor": "prior to each payment made by Party A"},
            {"id": "mark_dispute_resolution", "level": "error", "title": "争议解决修订", "content": "已将管辖权自动替换为我方所在地 (Philippines)。", "anchor": "DISPUTE RESOLUTION"}
        ]

        for res in results:
            self.add_audit_card(res['id'], res['level'], res['title'], res['content'], res['anchor'])
        
        self.status_label.setText(f"✅ 审计完成：发现 {len(results)} 处合规性建议")

if __name__ == "__main__":
    # Ensure terminal output is shown immediately (no delayed flush)
    stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(stdout_reconfigure):
        stdout_reconfigure(line_buffering=True)
    stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
    if callable(stderr_reconfigure):
        stderr_reconfigure(line_buffering=True)

    _preload_engine_before_ui()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())