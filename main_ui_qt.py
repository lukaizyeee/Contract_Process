import sys
import os
import mammoth
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton, 
                             QLabel, QFileDialog, QSplitter, QProgressBar, QFrame,
                             QScrollArea, QSizePolicy)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette

# 确保能导入 core 模块
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
from docx import Document
from api_interface import init_engine, process_file, search_query, get_document_preview

# --- 工作线程 ---
class WorkerThread(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, task_type, **kwargs):
        super().__init__()
        self.task_type = task_type
        self.kwargs = kwargs

    def run(self):
        try:
            if self.task_type == "init":
                init_engine()
                self.finished.emit("Engine Initialized")
            elif self.task_type == "process":
                res = process_file(self.kwargs['file_path'])
                self.finished.emit(res)
            elif self.task_type == "search":
                results = search_query(self.kwargs['query'])
                self.finished.emit(results)
            elif self.task_type == "preview":
                html = get_document_preview(self.kwargs['file_path'])
                self.finished.emit(html)
        except Exception as e:
            self.error.emit(str(e))

# --- 主窗口 ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Searching.app - 法律文档语义检索")
        self.resize(2200, 1500)
        self.setStyleSheet("""
            QMainWindow { background-color: #F2F2F7; }
            QLabel { color: #3A3A3C; font-family: 'Segoe UI', sans-serif; }
            QPushButton { 
                background-color: #007AFF; 
                color: white; 
                border-radius: 8px; 
                padding: 8px 16px; 
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #0062CC; }
            QLineEdit { 
                border: 1px solid #D1D1D6; 
                border-radius: 20px; 
                padding: 10px 18px; 
                background-color: white;
                font-size: 16px;
            }
            QTextEdit { 
                background-color: white; 
                border: none; 
                border-radius: 10px; 
                padding: 15px;
                font-size: 16px;
                line-height: 1.6;
            }
            QScrollArea { border: none; background-color: transparent; }
        """)

        # 初始化引擎
        # self.status_label = QLabel("正在初始化 AI 引擎...", self)
        # self.status_label.setAlignment(Qt.AlignCenter)
        # self.status_label.setStyleSheet("color: #8E8E93; font-size: 12px; margin-bottom: 5px;")
        
        self.init_thread = WorkerThread("init")
        self.init_thread.finished.connect(lambda: self.update_status("请先上传法律文档以开始分析"))
        self.init_thread.start()

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 10, 20, 20)
        main_layout.setSpacing(10)

        # 顶部状态 (移除)
        # main_layout.addWidget(self.status_label)

        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: #D1D1D6; }")

        # --- 左侧：原文预览 ---
        left_panel = QFrame()
        left_panel.setStyleSheet("QFrame { background-color: white; border-radius: 15px; }")
        left_layout = QVBoxLayout(left_panel)
        
        # 标题栏
        left_header = QHBoxLayout()
        left_title = QLabel("📄 原文预览 (修订模式)")
        left_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        left_title.setStyleSheet("color: #007AFF; border: none;")
        left_layout.addLayout(left_header)
        left_header.addWidget(left_title)
        
        # 分割线
        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setStyleSheet("background-color: #F2F2F7;")
        left_layout.addWidget(line1)

        # 文档内容区
        # self.doc_view = QTextEdit()
        # self.doc_view.setReadOnly(True)
        self.doc_view = QWebEngineView()
        # self.doc_view.setHtml("<html><body><p style='color:#8E8E93; text-align:center; margin-top:50px;'>请上传文档以预览</p></body></html>")
        left_layout.addWidget(self.doc_view)

        # 上传按钮
        self.upload_btn = QPushButton("上传文档")
        self.upload_btn.clicked.connect(self.upload_file)
        left_layout.addWidget(self.upload_btn)

        # --- 右侧：AI 对话 ---
        right_panel = QFrame()
        right_panel.setStyleSheet("QFrame { background-color: white; border-radius: 15px; }")
        right_layout = QVBoxLayout(right_panel)

        # 标题栏
        right_header = QHBoxLayout()
        right_title = QLabel("💬 AI 语义检索")
        right_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        right_title.setStyleSheet("color: #007AFF; border: none;")
        right_layout.addLayout(right_header)
        right_header.addWidget(right_title)

        # 分割线
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setStyleSheet("background-color: #F2F2F7;")
        right_layout.addWidget(line2)

        # 聊天记录区
        self.chat_area = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_area)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_layout.setSpacing(15)
        
        scroll = QScrollArea()
        scroll.setWidget(self.chat_area)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background-color: white; border: none; }")
        right_layout.addWidget(scroll)

        # 状态小字
        self.status_label = QLabel("准备就绪")
        self.status_label.setStyleSheet("color: #8E8E93; font-size: 13px; margin-left: 5px;")
        right_layout.addWidget(self.status_label)

        # 输入区
        input_layout = QHBoxLayout()
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("提问或检索关键词...")
        self.input_box.returnPressed.connect(self.handle_search)
        
        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedWidth(80)
        self.send_btn.clicked.connect(self.handle_search)

        input_layout.addWidget(self.input_box)
        input_layout.addWidget(self.send_btn)
        right_layout.addLayout(input_layout)

        # 添加到分割器
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([550, 550]) # 50:50 比例
        
        main_layout.addWidget(splitter)

    def add_message(self, role, text):
        msg_container = QWidget()
        msg_layout = QHBoxLayout(msg_container)
        msg_layout.setContentsMargins(0, 0, 0, 0)
        
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setFont(QFont("Segoe UI", 13))
        bubble.setContentsMargins(15, 12, 15, 12)
        
        # 计算气泡最大宽度
        max_width = 400
        
        if role == "user":
            bubble.setStyleSheet(f"""
                background-color: #007AFF; 
                color: white; 
                border-radius: 15px; 
                border-bottom-right-radius: 2px;
            """)
            msg_layout.addStretch()
            msg_layout.addWidget(bubble)
        else:
            bubble.setStyleSheet(f"""
                background-color: #E9E9EB; 
                color: #1C1C1E; 
                border-radius: 15px; 
                border-bottom-left-radius: 2px;
            """)
            msg_layout.addWidget(bubble)
            msg_layout.addStretch()
            
        # 简单的宽度限制逻辑 (PyQt 中 Label 自动换行需要配合布局)
        bubble.setMaximumWidth(max_width)
        self.chat_layout.addWidget(msg_container)
        
        # 滚动到底部
        QApplication.processEvents()
        sb = self.chat_area.parent().parent().verticalScrollBar()
        sb.setValue(sb.maximum())

    def upload_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文档", "", "Word Documents (*.docx)")
        if not file_path:
            return

        self.status_label.setText(f"正在解析 {os.path.basename(file_path)}...")
        self.doc_view.setHtml("") # Clear content
        self.upload_btn.setEnabled(False)

        # 1. 启动预览生成线程
        self.preview_thread = WorkerThread("preview", file_path=file_path)
        self.preview_thread.finished.connect(self.on_preview_finished)
        self.preview_thread.error.connect(lambda e: self.doc_view.setHtml(f"<html><body><p style='color:red'>预览失败: {e}</p></body></html>"))
        self.preview_thread.start()

        # 2. 启动后端处理线程
        self.process_thread = WorkerThread("process", file_path=file_path)
        self.process_thread.finished.connect(self.on_process_finished)
        self.process_thread.error.connect(self.on_error)
        self.process_thread.start()

    def on_preview_finished(self, html_content):
        # 设置 HTML 到 QWebEngineView
        # 如果 html_content 是文件路径（Word 导出模式），则使用 load
        if os.path.exists(html_content) and (html_content.endswith('.html') or html_content.endswith('.htm')):
             self.doc_view.load(QUrl.fromLocalFile(html_content))
        else:
             self.doc_view.setHtml(html_content)

    def update_status(self, text):
        self.status_label.setText(text)

    def on_process_finished(self, res):
        self.upload_btn.setEnabled(True)
        self.update_status(f"✅ 文档已就绪，共解析 {res['chunk_count']} 条语义片段")
        self.add_message("ai", f"已成功加载文档。您可以开始提问了，例如：‘关于合同终止条件的约定是什么？’")

    def handle_search(self):
        query = self.input_box.text().strip()
        if not query:
            return

        self.add_message("user", query)
        self.input_box.clear()
        self.update_status("正在检索...")
        self.send_btn.setEnabled(False)

        self.search_thread = WorkerThread("search", query=query)
        self.search_thread.finished.connect(self.on_search_finished)
        self.search_thread.error.connect(self.on_error)
        self.search_thread.start()

    def on_search_finished(self, results):
        self.send_btn.setEnabled(True)
        self.update_status("检索完成")
        
        if results:
            top = results[0]
            response = f"找到匹配内容 (置信度: {top['score']:.2f}):\n\n\"{top['text']}\""
            self.add_message("ai", response)
            
            # 在预览中高亮文本
            self.highlight_text(top['text'])
        else:
            self.add_message("ai", "在当前文档中未找到相关语义内容。")
            
    def highlight_text(self, text):
        if not text: return
        
        # 使用 JavaScript 在 WebEngineView 中高亮
        # 清除旧的高亮
        # 然后查找并高亮
        # 注意：QWebEngineView 的 findText 是异步的，且一次只能高亮一个
        # 我们使用 JS 来实现所有匹配项的高亮
        
        js_code = f"""
        (function() {{
            var searchTerm = "{text}";
            var bodyText = document.body.innerHTML;
            var searchRegExp = new RegExp(searchTerm, 'gi');
            
            // 简单的替换可能破坏 HTML 标签，这里仅作演示
            // 更好的做法是遍历文本节点
            
            // 使用 window.find (简单但只能选中一个)
            window.find(searchTerm);
            
            // 或者使用 Mark.js (如果引入了库)
            
            // 简单高亮实现：
            // document.designMode = "on";
            // var sel = window.getSelection();
            // sel.collapse(document.body, 0);
            // while (window.find(searchTerm)) {{
            //    document.execCommand("HiliteColor", false, "#FFF200");
            //    sel.collapseToEnd();
            // }}
            // document.designMode = "off";
        }})();
        """
        
        # 由于我们只想高亮找到的第一个或全部，QWebEngineView.findText 比较简单
        self.doc_view.findText(text)
        
        # 也可以尝试 JS 高亮全部（如果需要）
        # self.doc_view.page().runJavaScript(js_code)

    def on_error(self, err_msg):
        self.upload_btn.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.update_status("❌ 发生错误")
        self.add_message("ai", f"出错啦：{err_msg}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置全局字体
    font = QFont("Segoe UI", 14)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
