import sys
from PyQt6.QtWidgets import QMainWindow, QTextEdit
from PyQt6.QtCore import Qt, QTimer

from queue import Queue


class output_stream(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.setCentralWidget(self.text_edit)
        self.list = []

        sys.stdout = self

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process_queue)
        self.timer.start(50)

        self.timer_clear = QTimer(self)
        self.timer_clear.timeout.connect(self.clean_up)

    def write(self, text):
        self.list.append(text)

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
            self.timer_clear.start(1500)
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


