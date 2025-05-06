import sys
import os
import traceback
import threading
import webbrowser

from PyQt6.QtWidgets import QMainWindow, QTextEdit, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QAction

class log_stream(QMainWindow):
    def __init__(self, parent=None, version='0.0.0'):
        super().__init__(parent)
        self.setWindowTitle('Log Stream')
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint & ~Qt.WindowType.Dialog)
        self.setFixedSize(400, 300)
        self.center_on_parent()
        self.hide()
        self.missing_patchers = []
        self.errors = []
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.setCentralWidget(self.text_edit)
        self.list = []
        self.crash = False
        if not os.path.exists("ESLifier_Data/"):
            os.makedirs("ESLifier_Data/")
        self.log_file = open("ESLifier_Data/ESLifier.log", 'w', encoding='utf-8')
        self.log_file.write(f'ESLifier Version v{version}\n')
        self.log_file.write('Working directory is ' + os.getcwd() + '\n')
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
        if text.startswith('Warn:') and not 'red' in self.text_edit.styleSheet() and not 'lightblue' in self.text_edit.styleSheet():
            self.text_edit.setStyleSheet("background-color: lightblue")
        if text.startswith('Warn:'):
            missing = text[36:]
            if missing not in self.missing_patchers:
                self.missing_patchers.append(missing)
        if text.startswith('!Error'):
            self.errors.append(text.removeprefix('!Error'))
            
    def missing_patcher_warning(self):
        patcher_message = QMessageBox()
        patcher_message.setWindowTitle("Possible Missing Patcher")
        patcher_message.setIcon(QMessageBox.Icon.Warning)
        patcher_message.setWindowIcon(QIcon(":/images/ESLifier.png"))
        patcher_message.setStyleSheet("""
            QMessageBox {
                background-color: lightblue;
            }""")
        text = ("ESLifier has come across one or more files it currently doesn't have a patcher or exclusion for.\n"+
                "Check the ESLifier.log for more details.\n"+
                "Please create a patcher request in the GitHub.\n\n")
        count = 0
        for line in self.missing_patchers:
            count += 1
            if count <= 10:
                text += '\n' + line.strip()
        if count > 10:
            text += '\nand ' + str(count - 10) + ' more.'
        patcher_message.setText(text)
        patcher_message.addButton(QMessageBox.StandardButton.Ok)
        github_button = patcher_message.addButton("Open GitHub Issue Page", QMessageBox.ButtonRole.NoRole)
        def close():
            patcher_message.close()
        def open_github():
            webbrowser.open("https://github.com/MaskPlague/ESLifier/issues")
        patcher_message.accepted.connect(close)
        github_button.clicked.connect(open_github)
        self.missing_patchers.clear()
        patcher_message.show()

    def error_warning(self):
        error_message = QMessageBox()
        error_message.setWindowTitle("Errors Encountered")
        error_message.setIcon(QMessageBox.Icon.Warning)
        error_message.setWindowIcon(QIcon(":/images/ESLifier.png"))
        error_message.setStyleSheet("""
            QMessageBox {
                background-color: lightcoral;
            }""")
        text = ("ESLifier has experienced one or more errors.\n"+
                "Check the ESLifier.log for more details.\n"+
                "Any .pex files listed are likely corrupt and you need to find a patch to fix them.\n\n")
        count = 0
        for line in self.errors:
            count += 1
            if count <= 10:
                text += '\n' + line.strip()
        if count > 10:
            text += '\nand ' + str(count - 10) + ' more.'
        error_message.setText(text)
        error_message.addButton(QMessageBox.StandardButton.Ok)
        github_button = error_message.addButton("Open GitHub Issue Page", QMessageBox.ButtonRole.NoRole)
        def close():
            error_message.close()
        def open_github():
            webbrowser.open("https://github.com/MaskPlague/ESLifier/issues")
        error_message.accepted.connect(close)
        github_button.clicked.connect(open_github)
        self.errors.clear()
        error_message.show()

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
            if len(self.missing_patchers) > 0:
                self.missing_patcher_warning()
            if len(self.errors) > 0:
                self.error_warning()
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



