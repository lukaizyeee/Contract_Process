import os
import html
import tempfile
import platform
import subprocess
from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.oxml.ns import qn

class DocxPreviewGenerator:
    """
    Generates HTML preview from DOCX. 
    Attempts to use Microsoft Word for high-fidelity conversion if available.
    Falls back to internal XML parsing for revision support.
    """
    
    STYLE_CSS = """
    <style>
        body { 
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; 
            padding: 20px; 
            line-height: 1.5; 
            color: #333;
            background-color: white;
        }
        p { margin-bottom: 10px; margin-top: 0; }
        
        /* Insertions: Green background, underline */
        ins { 
            background-color: #e6ffec; 
            color: #2da44e; 
            text-decoration: none; 
            border-bottom: 1px solid #2da44e; 
            padding: 0 1px;
        }
        
        /* Deletions: Red background, strikethrough */
        del { 
            background-color: #ffebe9; 
            color: #cf222e; 
            text-decoration: line-through; 
            padding: 0 1px;
        }
        
        /* Tables */
        table { border-collapse: collapse; width: 100%; margin-bottom: 15px; border: 1px solid #ccc; }
        td, th { border: 1px solid #ddd; padding: 6px; vertical-align: top; }
    </style>
    """

    def generate_html(self, file_path):
        """
        Main entry point for generating HTML preview.
        Attempts Word automation on Windows/macOS for high fidelity.
        """
        sys_platform = platform.system()
        if sys_platform == "Windows":
            try:
                return self.generate_html_via_word_win(file_path)
            except Exception as e:
                print(f"Word automation (Win) failed: {e}, falling back to XML parsing")
        elif sys_platform == "Darwin":
            try:
                return self.generate_html_via_word_mac(file_path)
            except Exception as e:
                print(f"Word automation (Mac) failed: {e}, falling back to XML parsing")
        
        return self.generate_html_from_xml(file_path)

    def generate_html_via_word_win(self, file_path):
        """
        Uses Word COM automation to export Filtered HTML (Windows).
        """
        import win32com.client
        import pythoncom
        
        pythoncom.CoInitialize()
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0 # wdAlertsNone
            
            abs_path = os.path.abspath(file_path)
            doc = word.Documents.Open(abs_path, ReadOnly=True)
            
            # Ensure track changes are visible
            doc.TrackRevisions = True
            word.ActiveWindow.View.ShowRevisionsAndComments = True
            word.ActiveWindow.View.RevisionsView = 0 # wdRevisionsViewFinal
            
            fd, temp_path = tempfile.mkstemp(suffix=".htm")
            os.close(fd)
            
            # wdFormatHTML = 8 (Standard HTML, better fidelity than Filtered HTML)
            doc.SaveAs2(temp_path, FileFormat=8)
            doc.Close(False)
            word.Quit()
            
            # We return the path instead of content to support _files folder
            return temp_path
        finally:
            pythoncom.CoUninitialize()

    def generate_html_via_word_mac(self, file_path):
        """
        Uses AppleScript to tell Word to save as HTML (macOS).
        """
        abs_path = os.path.abspath(file_path)
        # AppleScript needs a path it can write to
        temp_dir = tempfile.gettempdir()
        temp_html = os.path.join(temp_dir, f"preview_{os.getpid()}.html")
        
        # AppleScript for Word HTML export
        # format HTML = 8
        script = f'''
        tell application "Microsoft Word"
            set theDoc to open file name "{abs_path}"
            save as theDoc file name "{temp_html}" file format format HTML
            close theDoc saving no
        end tell
        '''
        subprocess.run(['osascript', '-e', script], check=True)
        
        return temp_html

    def _safe_cleanup_temp(self, temp_path):
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            files_folder = temp_path.replace(".html", "_files")
            if os.path.exists(files_folder):
                import shutil
                shutil.rmtree(files_folder)
        except:
            pass

    def _cleanup_word_html(self, html_content):
        """
        Simplifies Word's Filtered HTML to make it more compatible with QTextEdit.
        """
        import re
        # Remove XML namespaces and complex tags that confuse QTextEdit
        html_content = re.sub(r'<xml>.*?</xml>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<(meta|link|style|o:|v:|w:).*?>', '', html_content, flags=re.IGNORECASE)
        # Keep some basic structure but simplify
        return f"<html><body>{html_content}</body></html>"

    def generate_html_from_xml(self, file_path):
        """
        Parses the docx file and returns HTML string with revision markings and styles.
        """
        try:
            doc = Document(file_path)
        except Exception as e:
            return f"<html><body><p style='color:red'>Error loading document: {str(e)}</p></body></html>"

        html_output = ["<html><head><meta charset='utf-8'>", self.STYLE_CSS, "</head><body>"]

        for element in doc.element.body:
            if isinstance(element, CT_P):
                html_output.append(self._parse_paragraph(element))
            elif isinstance(element, CT_Tbl):
                html_output.append(self._parse_table(element))
        
        html_output.append("</body></html>")
        return "".join(html_output)

    def _parse_paragraph(self, p_element):
        content = ""
        pPr = p_element.find(qn('w:pPr'))
        p_styles = []
        
        # 1. Alignment
        if pPr is not None:
            jc = pPr.find(qn('w:jc'))
            if jc is not None:
                val = jc.get(qn('w:val'))
                if val in ['center', 'right', 'both']:
                    align = 'justify' if val == 'both' else val
                    p_styles.append(f"text-align: {align}")
        
        style_attr = f' style="{"; ".join(p_styles)}"' if p_styles else ""
        
        for child in p_element:
            tag = child.tag
            # 1. Standard text run (w:r)
            if tag == qn('w:r'):
                content += self._parse_run(child)
            # 2. Insertion (w:ins)
            elif tag == qn('w:ins'):
                ins_content = ""
                for sub_node in child.iter(qn('w:r')):
                    ins_content += self._parse_run(sub_node)
                if ins_content:
                    content += f"<ins>{ins_content}</ins>"
            # 3. Deletion (w:del)
            elif tag == qn('w:del'):
                del_text = self._get_del_text(child)
                if del_text:
                    content += f"<del>{html.escape(del_text)}</del>"
            # 4. Hyperlinks
            elif tag == qn('w:hyperlink'):
                for sub_node in child.iter(qn('w:r')):
                    content += self._parse_run(sub_node)
        
        if not content.strip():
            return "<p>&nbsp;</p>" # Keep empty lines
        return f"<p{style_attr}>{content}</p>"

    def _parse_run(self, run_element):
        """
        Parses a w:r element, extracting text and applying styles.
        """
        text = self._get_text(run_element)
        if not text:
            # Handle line breaks
            if run_element.find(qn('w:br')) is not None:
                return "<br/>"
            return ""
        
        text = html.escape(text)
        
        # Extract styles from w:rPr
        rPr = run_element.find(qn('w:rPr'))
        if rPr is not None:
            style_parts = []
            
            # 1. Font Size (w:sz) - unit is half-point
            sz = rPr.find(qn('w:sz'))
            if sz is not None:
                val = sz.get(qn('w:val'))
                if val and val.isdigit():
                    pt_size = int(val) / 2
                    style_parts.append(f"font-size: {pt_size}pt")
            
            # 2. Color (w:color) - hex
            color = rPr.find(qn('w:color'))
            if color is not None:
                val = color.get(qn('w:val'))
                if val and val != "auto":
                    style_parts.append(f"color: #{val}")
            
            # 3. Highlight (w:highlight)
            highlight = rPr.find(qn('w:highlight'))
            if highlight is not None:
                val = highlight.get(qn('w:val'))
                if val:
                    color_map = {
                        "yellow": "#FFFF00", "green": "#00FF00", "cyan": "#00FFFF",
                        "magenta": "#FF00FF", "blue": "#0000FF", "red": "#FF0000",
                        "darkBlue": "#00008B", "darkCyan": "#008B8B", "darkGreen": "#006400",
                        "darkMagenta": "#8B008B", "darkRed": "#8B0000", "darkYellow": "#808000",
                        "gray25": "#C0C0C0", "gray50": "#808080", "black": "#000000"
                    }
                    bg_color = color_map.get(val, val)
                    style_parts.append(f"background-color: {bg_color}")

            # 4. Bold / Italic / Underline
            if rPr.find(qn('w:b')) is not None:
                style_parts.append("font-weight: bold")
            if rPr.find(qn('w:i')) is not None:
                style_parts.append("font-style: italic")
            if rPr.find(qn('w:u')) is not None:
                style_parts.append("text-decoration: underline")

            # 5. Font Family (w:rFonts)
            rFonts = rPr.find(qn('w:rFonts'))
            if rFonts is not None:
                ascii_font = rFonts.get(qn('w:ascii'))
                eastAsia_font = rFonts.get(qn('w:eastAsia'))
                if eastAsia_font:
                    style_parts.append(f"font-family: '{eastAsia_font}', '{ascii_font or 'serif'}'")
                elif ascii_font:
                    style_parts.append(f"font-family: '{ascii_font}'")

            if style_parts:
                return f'<span style="{"; ".join(style_parts)}">{text}</span>'
        
        return text

    def _parse_table(self, tbl_element):
        rows = []
        for row in tbl_element.iter(qn('w:tr')):
            cells = []
            for cell in row.iter(qn('w:tc')):
                # Parse paragraphs inside cell
                cell_content = []
                for p in cell.iter(qn('w:p')):
                    # Re-use paragraph parsing logic but strip <p> tags for cell structure
                    p_html = self._parse_paragraph(p)
                    # Remove outer <p> tags to avoid double margin issues in table, or keep them?
                    # Let's keep them for internal spacing
                    cell_content.append(p_html)
                
                cell_html = "".join(cell_content)
                cells.append(f"<td>{cell_html}</td>")
            rows.append(f"<tr>{''.join(cells)}</tr>")
        return f"<table>{''.join(rows)}</table>"

    def _get_text(self, element):
        return "".join([node.text for node in element.iter(qn('w:t')) if node.text]) or ""

    def _get_del_text(self, element):
        text = ""
        for node in element.iter(qn('w:delText')):
            text += node.text or ""
        if not text:
            text = self._get_text(element)
        return text
