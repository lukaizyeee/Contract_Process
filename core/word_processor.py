import os
import re
import sys
from pathlib import Path

from docx import Document
from docx.document import Document as DocxDocument


class WordProcessor:
    def __init__(self):
        self.platform = sys.platform
        self.my_country = "Philippines"
        self._check_environment()

    def _check_environment(self):
        if self.platform == "win32":
            try:
                import win32com.client  # noqa: F401
                import pythoncom  # noqa: F401
            except ImportError:
                raise ImportError("Please run 'pip install pywin32' on Windows")
        elif self.platform == "darwin":
            pass
        else:
            raise NotImplementedError(f"Platform {self.platform} not supported")

    def audit_and_fix(self, input_path, output_path):
        """执行红线审计并返回结果。Windows走COM，macOS走python-docx+AppleScript。"""
        input_abs_path = str(Path(input_path).resolve())
        output_abs_path = str(Path(output_path).resolve())

        if self.platform == "win32":
            return self._audit_and_fix_windows(input_abs_path, output_abs_path)

        if self.platform == "darwin":
            return self._audit_and_fix_macos(input_abs_path, output_abs_path)

        raise NotImplementedError(f"Platform {self.platform} not supported")

    def _audit_and_fix_windows(self, input_abs_path: str, output_abs_path: str):
        import pythoncom
        import win32com.client as win32

        pythoncom.CoInitialize()
        word = None
        doc = None
        audit_results = []

        try:
            try:
                word = win32.GetActiveObject("Word.Application")
            except Exception:
                word = win32.Dispatch("Word.Application")

            word.Visible = False
            word.DisplayAlerts = 0

            doc = word.Documents.Open(input_abs_path)
            doc.TrackRevisions = True

            audit_results.extend(self._check_sensitive_info_win(doc))
            audit_results.extend(self._check_signatories_text(doc.Content.Text))
            audit_results.extend(self._fix_payment_invoice_win(doc))
            audit_results.extend(self._fix_dispute_clause_win(doc))
            audit_results.extend(self._delete_penalty_win(doc))

            doc.SaveAs(output_abs_path)
            return audit_results

        except Exception as e:
            print(f"审计过程出错: {e}")
            return [{"id": "err", "level": "error", "title": "审计引擎异常", "content": str(e), "anchor": ""}]
        finally:
            if doc:
                try:
                    doc.Close(SaveChanges=True)
                except Exception:
                    pass
            if word:
                try:
                    if word.Documents.Count == 0:
                        word.Quit()
                except Exception:
                    pass
            pythoncom.CoUninitialize()

    def _audit_and_fix_macos(self, input_abs_path: str, output_abs_path: str):
        audit_results = []
        try:
            doc = Document(input_abs_path)
            full_text = self._collect_doc_text(doc)

            audit_results.extend(self._check_sensitive_info_text(full_text))
            audit_results.extend(self._check_signatories_text(full_text))
            audit_results.extend(self._fix_payment_invoice_docx(doc, full_text))
            audit_results.extend(self._fix_dispute_clause_docx(doc))
            audit_results.extend(self._delete_penalty_docx(doc))

            Path(output_abs_path).parent.mkdir(parents=True, exist_ok=True)
            doc.save(output_abs_path)

            return audit_results
        except Exception as e:
            print(f"macOS 审计过程出错: {e}")
            return [{"id": "err", "level": "error", "title": "审计引擎异常", "content": str(e), "anchor": ""}]

    @staticmethod
    def _collect_doc_text(doc: DocxDocument) -> str:
        paragraph_texts = [p.text for p in doc.paragraphs if p.text]
        table_texts = []
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells)
                if row_text.strip(" |"):
                    table_texts.append(row_text)
        return "\n".join(paragraph_texts + table_texts)

    @staticmethod
    def _check_sensitive_info_text(full_text: str):
        results = []
        phone_pattern = r"\+86\s?\d+"
        email_pattern = r"\b[A-Za-z0-9._%+-]+@(126|163)\.com\b"
        mark_counter = 0

        for pattern, msg in [
            (phone_pattern, "Please confirm: 中国电话 (+86)"),
            (email_pattern, "Please confirm: 126/163邮箱"),
        ]:
            for match in re.finditer(pattern, full_text):
                mark_id = f"mark_sensitive_{mark_counter}"
                mark_counter += 1
                results.append(
                    {
                        "id": mark_id,
                        "level": "warning",
                        "title": "敏感联系方式",
                        "content": f"识别到中国元素，建议确认：{msg}",
                        "anchor": match.group(),
                    }
                )
        return results

    @staticmethod
    def _check_signatories_text(full_text: str):
        results = []
        last_part = full_text[-500:]
        if "Position" not in last_part and "Title" not in last_part:
            results.append(
                {
                    "id": "sig_missing",
                    "level": "warning",
                    "title": "签字人职位缺失",
                    "content": "文末未检测到签字人职位抬头，请手动补全以符合合规要求。",
                    "anchor": "Signature",
                }
            )
        return results

    def _fix_payment_invoice_docx(self, doc: DocxDocument, full_text: str):
        results = []
        lower_text = full_text.lower()
        if "invoice" in lower_text and "prior to each payment" not in lower_text:
            for para in doc.paragraphs:
                if "payment" in para.text.lower():
                    para.add_run(
                        " Party B shall issue a valid and lawful invoice of the corresponding amount "
                        "to Party A prior to each payment made by Party A."
                    )
                    results.append(
                        {
                            "id": "mark_payment_invoice",
                            "level": "error",
                            "title": "缺失发票逻辑",
                            "content": "检测到付款条款但缺失‘先票后款’，已自动修订补充。",
                            "anchor": "prior to each payment",
                        }
                    )
                    break
        return results

    def _fix_dispute_clause_docx(self, doc: DocxDocument):
        results = []
        standard_dispute = (
            f"This Agreement shall be governed by and construed in accordance with the laws of {self.my_country}. "
            "Any dispute shall be submitted to the exclusive jurisdiction of the competent courts of Party A."
        )

        for para in doc.paragraphs:
            if "DISPUTE RESOLUTION" in para.text:
                para.text = "DISPUTE RESOLUTION\n" + standard_dispute
                results.append(
                    {
                        "id": "mark_dispute_resolution",
                        "level": "error",
                        "title": "争议解决修订",
                        "content": f"已将管辖权自动替换为我方所在地 ({self.my_country})。",
                        "anchor": "DISPUTE RESOLUTION",
                    }
                )
                break
        return results

    @staticmethod
    def _delete_penalty_docx(doc: DocxDocument):
        results = []
        patterns = ["late payment penalty", "penalty interest"]
        penalty_counter = 0

        for para in doc.paragraphs:
            original_text = para.text
            updated_text = original_text
            for pattern in patterns:
                if pattern in updated_text.lower():
                    mark_id = f"mark_penalty_{penalty_counter}"
                    penalty_counter += 1
                    results.append(
                        {
                            "id": mark_id,
                            "level": "error",
                            "title": "违约金删除",
                            "content": f"识别到罚息表述 '{pattern}'，已自动删除。",
                            "anchor": original_text[:30] if original_text else pattern,
                        }
                    )
                    updated_text = re.sub(pattern, "", updated_text, flags=re.IGNORECASE)
            if updated_text != original_text:
                para.text = re.sub(r"\s{2,}", " ", updated_text).strip()

        return results

    # --- Windows COM rules ---
    @staticmethod
    def _check_sensitive_info_win(doc):
        results = []
        phone_pattern = r"\+86\s?\d+"
        email_pattern = r"\b[A-Za-z0-9._%+-]+@(126|163)\.com\b"
        full_text = doc.Content.Text
        mark_counter = 0
        for pattern, msg in [
            (phone_pattern, "Please confirm: 中国电话 (+86)"),
            (email_pattern, "Please confirm: 126/163邮箱"),
        ]:
            matches = re.finditer(pattern, full_text)
            for match in matches:
                mark_id = f"mark_sensitive_{mark_counter}"
                mark_counter += 1
                find_range = doc.Content
                if find_range.Find.Execute(match.group()):
                    doc.Comments.Add(Range=find_range, Text=f"[{mark_id}] {msg}")
                    results.append(
                        {
                            "id": mark_id,
                            "level": "warning",
                            "title": "敏感联系方式",
                            "content": f"识别到中国元素，建议确认：{msg}",
                            "anchor": match.group(),
                        }
                    )
        return results

    @staticmethod
    def _fix_payment_invoice_win(doc):
        results = []
        text = doc.Content.Text.lower()
        if "invoice" in text and "prior to each payment" not in text:
            find_range = doc.Content
            if find_range.Find.Execute("payment"):
                new_text = (
                    " Party B shall issue a valid and lawful invoice of the corresponding amount "
                    "to Party A prior to each payment made by Party A."
                )
                find_range.InsertAfter(new_text)
                results.append(
                    {
                        "id": "mark_payment_invoice",
                        "level": "error",
                        "title": "缺失发票逻辑",
                        "content": "检测到付款条款但缺失‘先票后款’，已自动修订补充。",
                        "anchor": "prior to each payment",
                    }
                )
        return results

    def _fix_dispute_clause_win(self, doc):
        results = []
        standard_dispute = (
            f"This Agreement shall be governed by and construed in accordance with the laws of {self.my_country}. "
            "Any dispute shall be submitted to the exclusive jurisdiction of the competent courts of Party A."
        )
        find_range = doc.Content
        if find_range.Find.Execute("DISPUTE RESOLUTION"):
            find_range.Expand(Unit=4)
            find_range.Text = "DISPUTE RESOLUTION\n" + standard_dispute
            results.append(
                {
                    "id": "mark_dispute_resolution",
                    "level": "error",
                    "title": "争议解决修订",
                    "content": f"已将管辖权自动替换为我方所在地 ({self.my_country})。",
                    "anchor": "DISPUTE RESOLUTION",
                }
            )
        return results

    @staticmethod
    def _delete_penalty_win(doc):
        results = []
        patterns = ["late payment penalty", "penalty interest"]
        penalty_counter = 0
        for pattern in patterns:
            find_range = doc.Content
            while find_range.Find.Execute(pattern):
                find_range.Expand(Unit=4)
                anchor = find_range.Text[:30] if len(find_range.Text) > 30 else find_range.Text
                mark_id = f"mark_penalty_{penalty_counter}"
                penalty_counter += 1
                find_range.Delete()
                results.append(
                    {
                        "id": mark_id,
                        "level": "error",
                        "title": "违约金删除",
                        "content": f"识别到罚息表述 '{pattern}'，已自动删除。",
                        "anchor": anchor,
                    }
                )
        return results
