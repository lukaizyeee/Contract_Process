import os
import html
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.oxml.ns import qn

class DocxPreviewGenerator:
    """
    Generates HTML preview from DOCX. 
    Uses internal XML parsing for revision support on all platforms.
    """
    
    STYLE_CSS = """
    <style>
        body { 
            font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            margin: 0;
            padding: 24px;
            line-height: 1.7;
            color: #1f2937;
            background-color: #f3f4f6;
        }
        .doc-page {
            max-width: 860px;
            margin: 0 auto;
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
            padding: 40px 44px;
        }
        p { margin: 0 0 12px 0; }
        h1, h2, h3, h4 { margin: 12px 0 10px; line-height: 1.35; }
        ul, ol { margin: 8px 0 12px 26px; }
        li { margin: 4px 0; }
        img { max-width: 100%; }
        
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
        table { border-collapse: collapse; width: 100%; margin-bottom: 16px; border: 1px solid #d1d5db; }
        td, th { border: 1px solid #d1d5db; padding: 8px 10px; vertical-align: top; }
        th { background: #f9fafb; }
    </style>
    """

    def generate_html(self, file_path):
        """
        Main entry point for generating HTML preview.
        Directly uses XML parsing for consistent behavior across all platforms.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"输入文件不存在: {file_path}")
        
        print(f"[预览生成] 使用内部 XML 解析器处理文件: {file_path}")
        return self.generate_html_from_xml(file_path)

    def generate_html_from_xml(self, file_path):
        """
        Parses the docx file and returns HTML string with revision markings and styles.
        """
        try:
            doc = Document(file_path)
        except Exception as e:
            return f"<html><body><p style='color:red'>Error loading document: {str(e)}</p></body></html>"
        # Try to extract comments from word/comments.xml (if present)
        self._comments_map = {}
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                if 'word/comments.xml' in zf.namelist():
                    data = zf.read('word/comments.xml')
                    # Parse comments.xml with namespaces
                    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                    root = ET.fromstring(data)
                    for c in root.findall('w:comment', ns):
                        cid = c.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id') or c.get('id')
                        # Gather all text nodes under this comment
                        texts = []
                        for t in c.findall('.//w:t', ns):
                            if t.text:
                                texts.append(t.text)
                        self._comments_map[cid] = ' '.join(texts).strip()
        except Exception:
            # Non-fatal: if comments can't be read, ignore
            self._comments_map = {}

        html_output = ["<html><head><meta charset='utf-8'>", self.STYLE_CSS, "</head><body><div class='doc-page'>"]

        for element in doc.element.body:
            if isinstance(element, CT_P):
                html_output.append(self._parse_paragraph(element))
            elif isinstance(element, CT_Tbl):
                html_output.append(self._parse_table(element))
        
        html_output.append("</div></body></html>")
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
            # 5. Comment range markers (ignore - handled at run level)
            elif tag == qn('w:commentRangeStart') or tag == qn('w:commentRangeEnd'):
                # These are structural markers; we don't render them directly
                continue
        
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
        
        # Check for comment references within this run
        comment_ref = run_element.find(qn('w:commentReference'))
        comment_html = ""
        if comment_ref is not None:
            # Attribute may be namespaced; try multiple keys
            cid = comment_ref.get(qn('w:id')) or comment_ref.get('w:id') or comment_ref.get('id')
            if cid and hasattr(self, '_comments_map'):
                comment_text = self._comments_map.get(cid)
                if comment_text:
                    safe = html.escape(comment_text)
                    comment_html = f'<sup style="color:#555;font-size:0.8em; margin-left:4px;" title="{safe}">[{cid}]</sup>'

        return text + comment_html

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
