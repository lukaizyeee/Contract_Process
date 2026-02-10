import sys
import os
import mammoth
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton, 
                             QLabel, QFileDialog, QSplitter, QProgressBar, QFrame,
                             QScrollArea, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette

# 确保能导入 core 模块
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
from docx import Document
from api_interface import init_engine, process_file, search_query

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
        left_title = QLabel("📄 原文预览")
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
        self.doc_view = QTextEdit()
        self.doc_view.setReadOnly(True)
        self.doc_view.setPlaceholderText("暂无文档内容...")
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
        self.doc_view.clear()
        self.upload_btn.setEnabled(False)

        # 预览原文
        try:
            with open(file_path, "rb") as docx_file:
                result = mammoth.convert_to_html(docx_file)
                html = result.value
                # 添加简单的 CSS 样式以优化显示
                styled_html = f"""
                <style>
                    body {{ font-family: 'Segoe UI', sans-serif; line-height: 1.8; color: #333; font-size: 16px; }}
                    h1, h2, h3 {{ color: #2c3e50; }}
                    table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    p {{ margin-bottom: 10px; }}
                    .highlight {{ background-color: #FFF200; color: black; font-weight: bold; padding: 2px 0; }}
                </style>
                {html}
                """
                self.doc_view.setHtml(styled_html)
        except Exception as e:
            self.doc_view.setText(f"预览失败: {e}")

        # 后端处理
        self.process_thread = WorkerThread("process", file_path=file_path)
        self.process_thread.finished.connect(self.on_process_finished)
        self.process_thread.error.connect(self.on_error)
        self.process_thread.start()

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
        
        # 1. 移除旧的高亮 (通过重新加载 HTML，这里简化处理，直接在当前 HTML 上操作可能较难完全清除，
        # 但 PyQt QTextEdit 的 find 功能可以直接高亮选区)
        
        # 使用 QTextEdit 的光标操作进行高亮
        cursor = self.doc_view.textCursor()
        cursor.clearSelection()
        
        # 清除之前的高亮 (重置整个文档的背景色不太可行，通常重新加载文档或只高亮当前)
        # 简单策略：先尝试查找并高亮
        
        # 移动光标到开始
        cursor.movePosition(cursor.Start)
        self.doc_view.setTextCursor(cursor)
        
        # 查找文本 (模糊匹配比较难，这里尝试精确匹配片段，或者取前20个字符搜索)
        # 由于 mammoth 转换后的 HTML 可能包含标签，直接搜索纯文本可能失败。
        # 更好的方法是：后端返回的 text 是纯文本，我们尝试在 doc_view 中搜索它。
        
        # 尝试搜索前 50 个字符（因为长文本可能跨标签）
        search_snippet = text[:50]
        found = self.doc_view.find(search_snippet)
        
        if found:
            # 如果找到了，设置高亮背景
            # 获取当前选区
            cursor = self.doc_view.textCursor()
            
            # 创建高亮格式
            fmt = cursor.charFormat()
            fmt.setBackground(QColor("#FFF200"))
            fmt.setForeground(QColor("black"))
            
            # 应用格式
            cursor.mergeCharFormat(fmt)
            
            # 清除选区，避免显示为“选中”状态（通常是灰色或蓝色）
            cursor.clearSelection()
            self.doc_view.setTextCursor(cursor)
            
            # 滚动到可见
            self.doc_view.ensureCursorVisible()
        else:
            print(f"Highlight warning: Could not find exact text snippet: {search_snippet}")

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
