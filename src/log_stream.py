import sys
import os
import traceback
import threading

from PyQt6.QtWidgets import QMainWindow, QTextEdit
from PyQt6.QtCore import Qt, QTimer


class log_stream(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Log Stream')
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint & ~Qt.WindowType.Dialog)
        self.setFixedSize(400, 300)
        self.center_on_parent()
        self.hide()
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.setCentralWidget(self.text_edit)
        self.list = []
        self.crash = False
        if not os.path.exists("ESLifier_Data/"):
            os.makedirs("ESLifier_Data/")
        self.log_file = open("ESLifier_Data/ESLifier.log", 'w', encoding='utf-8')
        self.log_file.write('ESLifier Version v0.5.18-alpha\n')
        self.log_file.flush()

        sys.stdout = self
        sys.stderr = self
        sys.excepthook = self.exception_hook
        threading.excepthook = self.custom_exception_hook

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process_queue)
        self.timer.start(50)

        self.timer_clear = QTimer(self)
        self.timer_clear.timeout.connect(self.clean_up)

    def center_on_parent(self):
        x = (self.parent().geometry().width() // 2) - (self.geometry().width() // 2)
        y = (self.parent().geometry().height() // 2) - (self.geometry().height() // 2)
        self.move(x,y)

    def show(self):
        self.raise_()
        #self.hide()
        return super().show()

    def write(self, text):
        if not text.startswith('~'):
            self.list.append(text)
        text = text.strip().removeprefix('\033[F\033[K')
        if text.startswith(('!', '~')) or ('Process' not in text and 'Percentage' not in text and 'Gathered' not in text and 
            'Extracting:' not in text and 'CLEAR' not in text and text != '\033[F\033[K' and text != ''):
            self.log_file.write(text.removeprefix('~') + '\n')
            self.log_file.flush()
    
    def exception_hook(self, exc_type, exc_value, exc_traceback):
        self.crash = True
        self.show()
        self.text_edit.setStyleSheet("background-color: red;")
        print("\nAn exception has occured, please report this bug to the github and include the ESLifier.log file found in ESLifier_Data.\n")
        traceback.print_tb(exc_traceback, limit=5)
        print(f"Unhandled exception: {exc_value}")
        print('\n')

    def custom_exception_hook(self, args: threading.ExceptHookArgs):
        self.crash = True
        self.show()
        self.text_edit.setStyleSheet("background-color: red;")
        print("\nAn exception has occured, please report this bug to the github and include the ESLifier.log file found in ESLifier_Data.\n")
        traceback.print_tb(args.exc_traceback, limit=5)
        print(f"Unhandled exception: {args.exc_value}")
        print('\n')

    def flush(self):
        self.log_file.flush()

    def closeEvent(self, a0):
        super().closeEvent(a0)
        self.log_file.flush()
        self.log_file.close()

    def process_queue(self):
        self.timer.stop()
        length = len(self.list)
        count = 0

        for _ in range(length):
            line = self.list.pop(0)
            self.update_text_widget(line)
            count += 1
            if count > 1000:
                break

        self.timer.start(50)

    def update_text_widget(self, text):
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        if "\033[F\033[K" in text:
            lines = self.text_edit.toPlainText().split('\n')[:-3]
            lines.append(text.removeprefix('\033[F\033[K'))
            self.text_edit.setPlainText('\n'.join(lines))
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
        if not self.crash:
            self.text_edit.setPlainText(None)
            self.hide()
    
    def clear_alt(self):
        if not self.crash:
            self.text_edit.setPlainText(None)



