import sys
import os
import traceback

from PyQt6.QtWidgets import QMainWindow, QTextEdit
from PyQt6.QtCore import Qt, QTimer


class log_stream(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Log Stream')
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint & ~Qt.WindowType.Dialog)
        self.setFixedWidth(700)
        self.setFixedHeight(300)
        self.move(
            parent.width() // 4,
            parent.height() // 4
        )
        self.hide()
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.setCentralWidget(self.text_edit)
        self.list = []
        if not os.path.exists("ESLifier_Data/"):
            os.makedirs("ESLifier_Data/")
        self.log_file = open("ESLifier_Data/ESLifier.log", 'w')

        sys.stdout = self
        sys.stderr = self
        sys.excepthook = self.exception_hook

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process_queue)
        self.timer.start(50)

        self.timer_clear = QTimer(self)
        self.timer_clear.timeout.connect(self.clean_up)

    def show(self):
        self.raise_()
        return super().show()

    def write(self, text):
        self.list.append(text)
        text = text.strip()
        if 'Process' not in text and 'Percentage' not in text and 'Gathered' not in text and 'CLEAR' not in text and text != '':
            self.log_file.write(text + '\n')
            self.log_file.flush()
    
    def exception_hook(self, exc_type, exc_value, exc_traceback):
        self.show()
        self.text_edit.setStyleSheet("background-color: red;")
        print("An error has occured, please report this bug to the github and include the ESLifier.log file found in ESLifier_Data.", file=sys.stderr)
        traceback.print_tb(exc_traceback, limit=3, file=sys.stdout)
        print(f"Unhandled exception: {exc_value}", file=sys.stderr)

    def flush(self):
        self.log_file.flush()
        return super().flush()

    def closeEvent(self, a0):
        super().closeEvent(a0)
        self.log_file.flush()
        self.log_file.close()

    def process_queue(self):
        self.timer.stop()
        length = len(self.list)
        count = 0

        for i in range(length):
            line = self.list.pop(0)
            self.update_text_widget(line)
            count += 1
            if count > 1000:
                break

        self.timer.start(50)

    def update_text_widget(self, text):
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        if "\033[F" in text or "\033[K" in text:
            # Parse ANSI codes to handle special behavior
            lines = self.text_edit.toPlainText().split("\n")
            # Handle ANSI codes
            if "\033[F" in text:  # Move up a line
                text = text.replace("\033[F", "")
                if lines:
                    lines.pop()  # Remove the last line as a simulation of 'move up'
                if lines:
                    lines.pop()

            if "\033[K" in text:  # Clear the current line
                text = text.replace("\033[K", "")
                if lines:
                    lines[-1] = ""  # Clear the last line
                if lines:
                    lines[-1] = ""

                # Update the widget content after processing ANSI codes
                if lines:
                    lines[-1] = text.strip()
            self.text_edit.setPlainText("\n".join(lines))
        elif 'CLEAR' == text:
            self.log_file.flush()
            self.timer_clear.start(1500)
        elif 'CLEAR ALT' == text:
            self.clear_alt()
        else:
            # Simply append new text if no ANSI codes are found
            self.text_edit.insertPlainText(text)

        # Ensure the cursor is at the end
        self.text_edit.setTextCursor(cursor)
        self.text_edit.verticalScrollBar().setValue(self.text_edit.verticalScrollBar().maximum())
    
    def clean_up(self):
        self.timer_clear.stop()
        self.text_edit.setPlainText(None)
        self.hide()
    
    def clear_alt(self):
        self.text_edit.setPlainText(None)



