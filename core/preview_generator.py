from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.oxml.ns import qn
import html

class DocxPreviewGenerator:
    """
    Generates HTML preview from DOCX with Track Changes (Revisions) support.
    Extracts font size, color, and highlight from XML properties.
    """
    
    STYLE_CSS = """
    <style>
        body { 
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; 
            padding: 20px; 
            line-height: 1.6; 
            color: #333;
        }
        p { margin-bottom: 12px; }
        
        /* Insertions: Green background, underline */
        ins { 
            background-color: #e6ffec; 
            color: #2da44e; 
            text-decoration: none; 
            border-bottom: 1px solid #2da44e; 
            padding: 0 2px;
        }
        
        /* Deletions: Red background, strikethrough */
        del { 
            background-color: #ffebe9; 
            color: #cf222e; 
            text-decoration: line-through; 
            padding: 0 2px;
        }
        
        /* Tables */
        table { border-collapse: collapse; width: 100%; margin-bottom: 15px; }
        td, th { border: 1px solid #ddd; padding: 8px; }
    </style>
    """

    def generate_html(self, file_path):
        """
        Parses the docx file and returns HTML string with revision markings and styles.
        """
        try:
            doc = Document(file_path)
        except Exception as e:
            return f"<html><body><p style='color:red'>Error loading document: {str(e)}</p></body></html>"

        html_output = ["<html><head>", self.STYLE_CSS, "</head><body>"]

        for element in doc.element.body:
            if isinstance(element, CT_P):
                html_output.append(self._parse_paragraph(element))
            elif isinstance(element, CT_Tbl):
                html_output.append(self._parse_table(element))
        
        html_output.append("</body></html>")
        return "".join(html_output)

    def _parse_paragraph(self, p_element):
        content = ""
        for child in p_element:
            tag = child.tag
            # 1. Standard text run (w:r)
            if tag == qn('w:r'):
                content += self._parse_run(child)
            # 2. Insertion (w:ins)
            elif tag == qn('w:ins'):
                # ins usually contains w:r children
                ins_content = ""
                for sub_node in child.iter(qn('w:r')):
                    ins_content += self._parse_run(sub_node)
                if ins_content:
                    content += f"<ins>{ins_content}</ins>"
            # 3. Deletion (w:del)
            elif tag == qn('w:del'):
                # del text is usually in w:delText, no styling usually
                del_text = self._get_del_text(child)
                if del_text:
                    content += f"<del>{html.escape(del_text)}</del>"
            # 4. Hyperlinks
            elif tag == qn('w:hyperlink'):
                for sub_node in child.iter(qn('w:r')):
                    content += self._parse_run(sub_node)
        
        return f"<p>{content}</p>"

    def _parse_run(self, run_element):
        """
        Parses a w:r element, extracting text and applying styles (size, color).
        """
        text = self._get_text(run_element)
        if not text:
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
                    # Simple map for common word colors
                    color_map = {
                        "yellow": "#FFFF00", "green": "#00FF00", "cyan": "#00FFFF",
                        "magenta": "#FF00FF", "blue": "#0000FF", "red": "#FF0000",
                        "darkBlue": "#00008B", "darkCyan": "#008B8B", "darkGreen": "#006400",
                        "darkMagenta": "#8B008B", "darkRed": "#8B0000", "darkYellow": "#808000",
                        "gray25": "#C0C0C0", "gray50": "#808080", "black": "#000000"
                    }
                    bg_color = color_map.get(val, val)
                    style_parts.append(f"background-color: {bg_color}")

            # 4. Bold / Italic
            if rPr.find(qn('w:b')) is not None:
                style_parts.append("font-weight: bold")
            if rPr.find(qn('w:i')) is not None:
                style_parts.append("font-style: italic")

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
