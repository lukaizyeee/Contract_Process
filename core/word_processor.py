import sys
import os
import subprocess
import time
from pathlib import Path

class WordProcessor:
    """
    Cross-platform Word Document Processor using native automation.
    Supports Windows (COM) and macOS (AppleScript).
    Ensures 'Track Changes' is enabled for all modifications.
    """
    
    def __init__(self):
        self.platform = sys.platform
        self._check_environment()

    def _check_environment(self):
        if self.platform == "win32":
            try:
                import win32com.client
            except ImportError:
                raise ImportError("Please run 'pip install pywin32' to use Word automation on Windows.")
        elif self.platform == "darwin":
            # macOS doesn't need extra pip libraries, but relies on osascript
            pass
        else:
            raise NotImplementedError(f"Platform {self.platform} is not supported for Word automation.")

    def append_text_with_revision(self, input_path: str, output_path: str, text_to_append: str):
        """
        Appends text to the end of the document with 'Track Changes' enabled.
        """
        input_abs_path = os.path.abspath(input_path)
        output_abs_path = os.path.abspath(output_path)

        if not os.path.exists(input_abs_path):
            raise FileNotFoundError(f"Input file not found: {input_abs_path}")

        if self.platform == "win32":
            self._modify_windows(input_abs_path, output_abs_path, text_to_append)
        elif self.platform == "darwin":
            self._modify_mac(input_abs_path, output_abs_path, text_to_append)

    def _modify_windows(self, input_path, output_path, text):
        import win32com.client as win32
        import pythoncom
        
        # Initialize COM library (needed for multi-threading environments)
        pythoncom.CoInitialize()
        
        word = None
        doc = None
        try:
            # Connect to existing Word instance or create new one
            try:
                word = win32.GetActiveObject("Word.Application")
            except Exception:
                word = win32.Dispatch("Word.Application")
            
            # Keep Word invisible/background
            word.Visible = False
            word.DisplayAlerts = False  # Suppress popups

            doc = word.Documents.Open(input_path)
            
            # Enable Track Changes
            doc.TrackRevisions = True
            
            # Append text at the end
            # Using Range to ensure we don't mess up selection
            rng = doc.Content
            rng.Collapse(Direction=0)  # 0 = wdCollapseEnd
            rng.InsertAfter(f"\n{text}")
            
            # Save As
            doc.SaveAs(output_path)
            
        except Exception as e:
            print(f"Error manipulating Word on Windows: {e}")
            raise e
        finally:
            if doc:
                try:
                    doc.Close(SaveChanges=False)
                except:
                    pass
            # We don't Quit() Word if it was already open, but here we assume batch processing
            # For safety in background tasks, we often Quit if we started it.
            # Simplified logic: If we created it, we should probably quit it.
            # But verifying that is complex. Let's just ensure we clean up doc.
            if word:
                 # Check if any other docs are open
                if word.Documents.Count == 0:
                    word.Quit()
            
            pythoncom.CoUninitialize()

    def _modify_mac(self, input_path, output_path, text):
        """
        Uses AppleScript to control Word on macOS.
        """
        # Escape quotes for AppleScript
        safe_input = input_path.replace('"', '\\"')
        safe_output = output_path.replace('"', '\\"')
        safe_text = text.replace('"', '\\"').replace('\n', '\\n')

        applescript = f'''
        tell application "Microsoft Word"
            activate
            -- Open the document
            set targetDoc to open "{safe_input}"
            
            -- Enable Track Changes
            set track revisions of targetDoc to true
            
            -- Append text at the end
            -- 'text object' of the document is the whole content
            -- we insert after it
            insert text "\\n{safe_text}" at after (text object of targetDoc)
            
            -- Save As (handling path format)
            -- AppleScript usually needs HFS paths or POSIX file objects for save as
            -- But standard POSIX path string often works in newer versions or requires conversion
            
            -- Safe method: close and save changes? No, we need Save As.
            save targetDoc in "{safe_output}" as "format document"
            
            close targetDoc
        end tell
        '''
        
        try:
            result = subprocess.run(
                ["osascript", "-e", applescript], 
                capture_output=True, 
                text=True, 
                check=True
            )
            # print("AppleScript Output:", result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"AppleScript Error: {e.stderr}")
            raise RuntimeError(f"Failed to automate Word on macOS: {e.stderr}")

if __name__ == "__main__":
    # Test script
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="Input file path")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--text", help="Text to append", default=" [Revison Added by AI] ")
    
    args = parser.parse_args()
    
    if args.input and args.output:
        processor = WordProcessor()
        print(f"Processing {args.input}...")
        processor.append_text_with_revision(args.input, args.output, args.text)
        print(f"Saved to {args.output}")
