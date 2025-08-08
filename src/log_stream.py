import sys
import os
import traceback
import threading
import webbrowser
import shutil
import queue
from datetime import datetime

from PyQt6.QtWidgets import QMainWindow, QTextEdit, QMessageBox, QProgressBar, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon

class log_stream(QMainWindow):
    def __init__(self, parent=None, version='0.0.0'):
        super().__init__(parent)
        self.setWindowTitle('Log Stream')
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint & ~Qt.WindowType.Dialog)
        self.setFixedSize(400, 300)
        self.missing_patchers = []
        self.errors = []
        self.ineligible = []
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.percentage = 0
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.hide()
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addSpacing(10)
        main_layout.addWidget(self.text_edit)
        self.setCentralWidget(main_widget)
        self.list = queue.Queue()
        self.crash = False
        self.running = True
        self.center_on_parent()

        if not os.path.exists("ESLifier_Data/"):
            os.makedirs("ESLifier_Data/")

        max_logs = 3

        for i in range(max_logs, -1, -1):
            src = os.path.join("ESLifier_Data", f"ESLifier_{i-1}.log") if i > 0 else "ESLifier_Data/ESLifier.log"
            dst = os.path.join("ESLifier_Data", f"ESLifier_{i}.log")
            if os.path.exists(dst):
                os.remove(dst)
            if os.path.exists(src):
                shutil.copy(src, dst)
        self.log_file = open("ESLifier_Data/ESLifier.log", 'w', encoding='utf-8')
        formatted_datetime = '[' + datetime.now().isoformat(timespec='milliseconds') + ']\n'
        self.log_file.write(formatted_datetime)
        self.log_file.write(f'ESLifier Version v{version}\n')
        self.log_file.write('Working directory is ' + os.getcwd() + '\n')
        self.log_file.flush()
        
        sys.stdout = self
        sys.stderr = self
        sys.excepthook = self.exception_hook
        threading.excepthook = self.threading_exception_hook

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.process_queue)
        self.timer.start(50)

        self.timer_clear = QTimer(self)
        self.timer_clear.setSingleShot(True)
        self.timer_clear.timeout.connect(self.clean_up)

    def center_on_parent(self):
        parent = self.parent()
        if parent != None:
            x = (parent.geometry().width() // 2) - (self.geometry().width() // 2)
            y = (parent.geometry().height() // 2) - (self.geometry().height() // 2)
            self.move(x,y)

    def show(self):
        self.raise_()
        #self.hide()
        self.percentage = 0
        return super().show()
    
    def hide(self):
        self.progress_bar.reset()
        return super().hide()

    def write(self, text: str):
        text = str(text)
        if not text.startswith('~'):
            self.list.put(text)
        text = text.strip().removeprefix('\033[F\033[K')
        if (text.startswith(('!', '~')) 
            or not text.startswith(('-  Gathered:', '-  Winning', '-    Processed', '-  Percentage', '-    Percentage', '-  Extracting:', 'CLEAR')) 
            and text != ''):
            formatted_datetime = '[' + datetime.now().isoformat(timespec='milliseconds') + '] '
            self.log_file.write(formatted_datetime + text.removeprefix('~') + '\n')
            self.log_file.flush()
        if text.startswith('Warn:') and not 'red' in self.text_edit.styleSheet() and not 'lightblue' in self.text_edit.styleSheet():
            self.text_edit.setStyleSheet("background-color: lightblue")
        if text.startswith('Warn:'):
            missing = text[36:]
            if missing not in self.missing_patchers:
                self.missing_patchers.append(missing)
        if text.startswith('!Error'):
            self.errors.append(text.removeprefix('!Error'))
        if '%' in text and '.' in text and ('-    Processed:' in text or '% Patching:' in text):
            pindex = text.index('.')
            if ':' in text:
                cindex = text.index(':')
                if cindex < pindex:
                    self.percentage = int(text[cindex+1:pindex])
                else:
                    self.percentage = int(text[:pindex])
            else:
                self.percentage = int(text[:pindex])
        if text.startswith('~Ineligible:'):
            ineligible = text[12:]
            self.ineligible.append(ineligible)
            
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
        patcher_message.show()
        self.missing_patchers.clear()

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
        github_button = error_message.addButton("Open GitHub Issue Page", QMessageBox.ButtonRole.NoRole)
        github_link = "https://github.com/MaskPlague/ESLifier/issues"
        for line in self.errors:
            count += 1
            if line.strip().lower().endswith('cwhcm_setchangeonquestprog_03.pex'):
                text += '\n' + ("User needs to download and install the following mod and then re-scan:\n" +
                                "   OCW - Script Fix - cwhcm_setchangeonquestprog_03")
                github_button.setText("Open OCW Script Fix mod page")
                github_link = "https://www.nexusmods.com/skyrimspecialedition/mods/62720"
                continue
            if count <= 10:
                text += '\n' + line.strip()

        if count > 10:
            text += '\nand ' + str(count - 10) + ' more.'
        error_message.setText(text)
        error_message.addButton(QMessageBox.StandardButton.Ok)
        def close():
            error_message.close()
        def open_github():
            webbrowser.open(github_link)
        error_message.accepted.connect(close)
        github_button.clicked.connect(open_github)
        error_message.show()
        self.errors.clear()

    def ineligible_warning(self):
        eligibility_warning = QMessageBox()
        eligibility_warning.setStyleSheet("""
            QMessageBox {
                background-color: lightcoral;
            }""")
        eligibility_warning.setWindowTitle("Cell Master Patching Warning")
        text = ("ESLifier has come across one or more pex files that are currently unpatchable.\n"+
                "This is because there is currently no programmed method to replace a necessary\n"+
                "plugin name with ESLifier_Cell_Master.esm. The errors show the plugin name\n"+
                "that needs replacing and the pex file that isn't patched yet.\n\n")
        count = 0
        for line in self.ineligible:
            count += 1
            if count <= 10:
                text += '\n' + line.strip()
        if count > 10:
            text += '\nand ' + str(count - 10) + ' more.'
        eligibility_warning.setText(text)
        eligibility_warning.addButton(QMessageBox.StandardButton.Ok)
        def close():
            eligibility_warning.hide()
        eligibility_warning.accepted.connect(close)
        eligibility_warning.show()
        self.ineligible.clear()


    def exception_hook(self, exc_type, exc_value, exc_traceback):
        self.crash = True
        self.running = False
        self.show()
        self.text_edit.setStyleSheet("background-color: red;")
        print("\nAn exception has occured, please report this bug to the github and include the ESLifier.log file found in ESLifier_Data.\n")
        traceback.print_tb(exc_traceback, limit=5)
        print(f"Unhandled exception: {exc_value}")
        print('\n')
        try:
            self.log_file.write('exception_hook -> Extended Traceback for debugging:')
            traceback.print_tb(exc_traceback, limit=10, file=self.log_file)
            self.log_file.flush()
        except:
            pass

    def threading_exception_hook(self, args: threading.ExceptHookArgs):
        self.crash = True
        self.running = False
        self.show()
        self.text_edit.setStyleSheet("background-color: red;")
        print("\nAn exception has occured, please report this bug to the github and include the ESLifier.log file found in ESLifier_Data.\n")
        traceback.print_tb(args.exc_traceback, limit=5)
        print(f"Unhandled exception: {args.exc_value}")
        print('\n')
        try:
            self.log_file.write('threading_exception_hook -> Extended Traceback for debugging:')
            traceback.print_tb(args.exc_traceback, limit=10, file=self.log_file)
            self.log_file.flush()
        except:
            pass


    def flush(self):
        if not self.log_file.closed:
            self.log_file.flush()

    def closeEvent(self, a0):
        self.running = False
        self.timer.stop()
        if not self.log_file.closed:
            self.log_file.flush()
            self.log_file.close()
        super().closeEvent(a0)

    def close(self):
        self.running = False
        self.timer.stop()
        if not self.log_file.closed:
            self.log_file.flush()
            self.log_file.close()
        super().close()

    def process_queue(self):
        if not self.isHidden() and self.progress_bar.value() != self.percentage:
            if self.percentage == 0:
                self.progress_bar.setRange(0,0)
                self.progress_bar.setStyleSheet("""
                    QProgressBar {
                        background-color: #999999;
                        border: 0px;
                        padding: 0px;
                        max-height: 10px;
                    }
                    QProgressBar::chunk {
                        background-color: qlineargradient(spread:reflect, x1:0, y1:0, x2:0.5, y2:0, stop:0 #999999, stop:1 #03f8fc);
                    }""")
                self.progress_bar.setValue(self.percentage)
            else:
                self.progress_bar.setRange(0,100)
                self.progress_bar.setStyleSheet("""
                    QProgressBar {
                        background-color: #999999;
                        border: 0px;
                        padding: 0px;
                        max-height: 10px;
                    }
                        QProgressBar::chunk {
                        background: #03f8fc;
                        width:1px
                    }
                """)
                if not self.progress_bar.paintingActive():
                    self.progress_bar.setValue(self.percentage)
        length = self.list.qsize()
        for _ in range(length):
            if self.list.empty():
                break
            line = self.list.get()
            self.update_text_widget(line)
        if self.running:
            self.timer.start(50)

        self.timer.start(50)

    def update_text_widget(self, text):
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        if text.startswith("\033[F\033[K"):
            lines = self.text_edit.toPlainText().split('\n')[:-3]
            lines.append(text.removeprefix('\033[F\033[K'))
            self.text_edit.setPlainText('\n'.join(lines))
        elif 'CLEAR' == text:
            self.percentage = 100
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
        if not self.crash:
            self.text_edit.setPlainText(None)
            self.hide()
        if len(self.missing_patchers) > 0:
            self.missing_patcher_warning()
        if len(self.errors) > 0:
            self.error_warning()
        if len(self.ineligible) > 0:
            self.ineligible_warning()
    
    def clear_alt(self):
        if not self.crash:
            self.text_edit.setPlainText(None)
            self.log_file.flush()



