from __future__ import annotations
import sys
import os
import traceback
import threading
import webbrowser
import shutil
import queue
import subprocess
from datetime import datetime

from PyQt6.QtWidgets import QMainWindow, QTextEdit, QMessageBox, QProgressBar, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon

import builtins
DEBUG = not getattr(sys, 'frozen', False)
_ls: log_stream = None
def write_to_file(text:str):
    _ls.write_to_file(text)

def write_normal(text:str, to_file:bool=True):
    _ls.write_normal(text, to_file)

def write_remove(remove_num_lines:int, text:str, write_to_file:bool=False, prunable:bool=False):
    _ls.write_remove(remove_num_lines, text, write_to_file, prunable)

def write_insert(insert_location:int, text:str, write_to_file:bool=False):
    _ls.write_insert(insert_location, text, write_to_file)

def write_progress(percent: int, remove_num_lines:int, text:str):
    _ls.write_progress(percent, remove_num_lines, text)

def write_main_progress(percent: int, remove_num_lines:int, text:str, write_to_file:bool=True):
    _ls.write_main_progress(percent, remove_num_lines, text, write_to_file)

def write_patching(percent:int, text:str):
    _ls.write_patching(percent, text)

def write_warning(text:str):
    _ls.write_warning(text)

def write_error(text:str, is_exception_msg:bool=False):
    _ls.write_error(text, is_exception_msg)

def write_ineligible(text:str):
    _ls.write_ineligible(text)

def clear_and_close_log():
    _ls.clear_and_close_log()

def clear_and_leave_log_open():
    _ls.clear_and_leave_log_open()


#For Debugging
if DEBUG:
    class print_hijacker():
        original_print_func = None
        intercept_print = False

        def __init__(self, lines, file):
            self.original_print_func = print
            builtins.print = self.print_to_log
            self.lines = lines
            self.file = file

        def print_to_log(self, *args, **kwargs):
            if DEBUG:
                sys.__stdout__.write(f"LOG: {args}\n")
                sys.__stdout__.flush()
                #write_to_file(str(args))
            elif 'original' in kwargs:
                kwargs.pop('original')
                self.original_print_func(*args, **kwargs)
            else:
                sys.stdout.write(*args)

        def print_to_console(self, *args, **kwargs):
            for line in args:
                sys.__stdout__.write(f"{line}\n")
            sys.__stdout__.flush()
LOG_REFRESH_RATE = 17
QUEUE_PROCESS_RATE = 10
class log_stream(QMainWindow):
    _instance = None
    _init = False
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(log_stream, cls).__new__(cls)
        return cls._instance

    def __init__(self, parent=None, version='0.0.0', ESLIFIER_DATA_FOLDER='', ESLIFIER_LOG_FILE='', PROGRAM_NAME='', IMAGES_PATH=''):
        if self._init:
            return
        self._init = True
        super().__init__(parent)
        global _ls
        self.ESLIFIER_DATA_FOLDER = ESLIFIER_DATA_FOLDER
        self.ESLIFIER_LOG_FILE = ESLIFIER_LOG_FILE
        self.IMAGES_PATH = IMAGES_PATH
        _ls = log_stream()
        self.setWindowTitle('Log Stream')
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint & ~Qt.WindowType.Dialog)
        self.setFixedSize(400, 300)
        self.missing_patchers = set()
        self.errors = set()
        self.ineligible = set()
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.main_percentage = 0
        self.main_progress_bar = QProgressBar()
        self.main_progress_bar.setTextVisible(False)
        self.main_progress_bar.setStyleSheet("""
                                QProgressBar {
                                    background-color: #999999;
                                    border: 0px;
                                    padding: 0px;
                                    max-height: 10px;
                                }
                                QProgressBar::chunk {
                                    background: #03f8fc;
                                    width:1px
                                }""")
        self.percentage = 0
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""QProgressBar {
                                    background-color: #999999;
                                    border: 0px;
                                    padding: 0px;
                                    max-height: 5px;
                                }""")
        self.progress_bar_busy_mode = False
        self.main_progress_bar_busy_mode = False
        self.hide()
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        main_layout.addWidget(self.main_progress_bar)
        main_layout.addWidget(self.progress_bar)
        main_layout.addSpacing(5)
        main_layout.addWidget(self.text_edit)
        self.setCentralWidget(main_widget)
        self.display_queue = queue.Queue()
        self.crash = False
        self.running = True
        self.center_on_parent()
        self.lines = []
        self.error_start = self.tr("[Error] ")
        self.warning_start = self.tr("[Warning] ")
        
        if not os.path.exists(ESLIFIER_DATA_FOLDER):
            os.makedirs(ESLIFIER_DATA_FOLDER)

        max_logs = 3

        for i in range(max_logs, -1, -1):
            src = os.path.join(ESLIFIER_DATA_FOLDER, f"ESLifier_{i-1}.log") if i > 0 else ESLIFIER_LOG_FILE
            dst = os.path.join(ESLIFIER_DATA_FOLDER, f"ESLifier_{i}.log")
            try:
                if os.path.exists(dst):
                    os.remove(dst)
                if os.path.exists(src):
                    shutil.copy(src, dst)
            except OSError:
                pass 
        try:
            self.log_file = open(ESLIFIER_LOG_FILE, 'w', encoding='utf-8')
        except OSError:
            self.ESLIFIER_LOG_FILE = os.path.join(ESLIFIER_DATA_FOLDER, f"ESLifier_{os.getpid()}.log")
            self.log_file = open(self.ESLIFIER_LOG_FILE, 'w', encoding='utf-8')
        write_to_file(f'{PROGRAM_NAME} Version v{version}')
        write_to_file('Working directory is ' + os.getcwd())
        if DEBUG:
            self.write_to_file("Debug Mode Enabled for Printing")
            self.hijack_print = print_hijacker(self.lines, self.log_file)
        #sys.stdout = self
        #sys.stderr = self
        sys.excepthook = self.exception_hook
        threading.excepthook = self.threading_exception_hook

        self.queue_timer = QTimer(self)
        self.queue_timer.setSingleShot(True)
        self.queue_timer.timeout.connect(self.process_queue)
        self.queue_timer.start(QUEUE_PROCESS_RATE)

        self.refresh_log_timer = QTimer(self)
        self.refresh_log_timer.timeout.connect(self.refresh_log)
        self.refresh_log_timer.setInterval(LOG_REFRESH_RATE)
        self.refresh_log_timer.setSingleShot(False)
        self.refresh_log_timer.start()

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
        self.main_percentage = 0
        self.timer_clear.stop()
        return super().show()
    
    def hide(self):
        self.progress_bar.reset()
        self.main_progress_bar.reset()
        return super().hide()
    
    def clear_and_close_log(self):
        self.display_queue.put(("", 3))  # 3 clear and close
    
    def clear_and_leave_log_open(self):
        self.display_queue.put(("", 4))  # 4 clear and leave open
    
    def write_to_file(self, text:str):
        if self.log_file.closed:
            return
        formatted_datetime = '[' + datetime.now().isoformat(timespec='milliseconds') + ']'
        self.log_file.write(f"{formatted_datetime} {text}\n")
        self.log_file.flush()

    def write_normal(self, text:str, write_to_file:bool=True):
        self.display_queue.put((text, 0))    # 0 Normal
        if write_to_file:
            self.write_to_file(text)

    def write_remove(self, remove_num_lines:int, text:str, write_to_file:bool=False, prunable:bool=False):
        self.display_queue.put((text, 1, remove_num_lines, prunable)) # 1 remove
        if write_to_file:
            self.write_to_file(text)

    def write_insert(self, insert_location:int, text:str, write_to_file:bool=False):
        self.display_queue.put((text, 5, insert_location))  # 5 insert
        if write_to_file:
            self.write_to_file(text)

    def write_progress(self, percent: int, remove_num_lines:int, text:str):
        self.percentage = percent
        self.write_remove(remove_num_lines, text, False, True)

    def write_main_progress(self, percent: int, remove_num_lines:int, text:str, write_to_file:bool=True):
        self.main_percentage = percent
        self.write_remove(remove_num_lines, text, write_to_file, False)

    def write_patching(self, percent:int, text:str):
        self.display_queue.put((text, 0))    # 0 Normal
        self.main_percentage = percent
        self.write_to_file(text)

    def write_warning(self, text:str):
        self.missing_patchers.add(text)
        self.write_to_file(self.warning_start+text)
        self.display_queue.put(("warning", 6))    # 6 warning color change

    def write_error(self, text:str, is_exception_msg:bool=False):
        text = str(text)
        self.display_queue.put((self.error_start+text, 0))    # 0 Normal
        if not is_exception_msg:
            self.errors.add(text)
        self.write_to_file(self.error_start+text)

    def write_ineligible(self, text:str):
        self.ineligible.add(text)
        self.write_to_file(text)
            
    def missing_patcher_warning(self):
        patcher_message = QMessageBox()
        patcher_message.setWindowTitle(self.tr("Possible Missing Patcher"))
        patcher_message.setIcon(QMessageBox.Icon.Warning)
        patcher_message.setWindowIcon(QIcon(self.IMAGES_PATH+"ESLifier.png"))
        patcher_message.setStyleSheet("""
            QMessageBox {
                background-color: lightblue;
            }""")
        text = (self.tr("ESLifier has come across one or more files it currently doesn't have a patcher or exclusion for.\n"\
                "Check the ESLifier.log for more details.\n"\
                "Please create a patcher request in the GitHub.") +
                "\n\n")
        count = 0
        for line in self.missing_patchers:
            count += 1
            if count <= 10:
                text += '\n' + line.strip()
        if count > 10:
            text += '\n' + self.tr('and %1 more.').replace("%1", str(count - 10))
        patcher_message.setText(text)
        patcher_message.addButton(QMessageBox.StandardButton.Ok)
        github_button = patcher_message.addButton(self.tr("Open GitHub Issue Page"), QMessageBox.ButtonRole.NoRole)
        def close():
            patcher_message.close()
        def open_github():
            webbrowser.open("https://github.com/MaskPlague/ESLifier/issues")
            patcher_message.show()
        patcher_message.accepted.connect(close)
        github_button.clicked.connect(open_github)
        patcher_message.show()
        self.missing_patchers.clear()

    def error_warning(self):
        error_message = QMessageBox()
        error_message.setWindowTitle(self.tr("Errors Encountered"))
        error_message.setIcon(QMessageBox.Icon.Warning)
        error_message.setWindowIcon(QIcon(self.IMAGES_PATH+"ESLifier.png"))
        error_message.setStyleSheet("""
            QMessageBox {
                background-color: lightcoral;
            }""")
        text = (self.tr("ESLifier has experienced one or more errors.\n"\
                "Check the ESLifier.log for more details.\n"\
                "Any .pex files listed are likely corrupt and you need to find a patch to fix them.") + 
                "\n\n")
        count = 0
        github_button = error_message.addButton(self.tr("Open GitHub Issue Page"), QMessageBox.ButtonRole.NoRole)
        github_link = "https://github.com/MaskPlague/ESLifier/issues"
        for line in self.errors:
            count += 1
            if line.strip().lower().endswith('cwhcm_setchangeonquestprog_03.pex'):
                text += '\n' + (self.tr("User needs to download and install the following mod, click reset BSA, and then re-scan:") + "\n"\
                                "   OCW - Script Fix - cwhcm_setchangeonquestprog_03")
                github_button.setText(self.tr("Open OCW Script Fix mod page"))
                github_link = "https://www.nexusmods.com/skyrimspecialedition/mods/62720"
                continue
            if count <= 10:
                text += '\n' + line.strip()

        if count > 10:
            text += '\n' + self.tr('and %1 more.').replace("%1", str(count - 10))
        error_message.setText(text)
        error_message.addButton(QMessageBox.StandardButton.Ok)
        def close():
            error_message.close()
        def open_github():
            webbrowser.open(github_link)
            error_message.show()
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
        eligibility_warning.setWindowTitle(self.tr("Cell Master Patching Warning"))
        text = self.tr("ESLifier has either come across one or more pex/ini files that are currently unpatchable.\n"\
                "This is because there is currently no programmed method to replace a necessary\n"\
                "plugin name with ESLifier_Cell_Master.esm in pex files and, certain ini files assume that\n"\
                "every form ID in the ini is from the same plugin. The errors show the plugin name\n"\
                "that needs replacing, the form ID change, and the pex/ini file that isn't patched yet.\n\n")
        count = 0
        for line in self.ineligible:
            count += 1
            if count <= 10:
                text += '\n' + line.strip()
        if count > 10:
            text += '\n' + self.tr('and %1 more.').replace("%1", str(count - 10))
        eligibility_warning.setText(text)
        eligibility_warning.addButton(QMessageBox.StandardButton.Ok)
        def close():
            eligibility_warning.hide()
        eligibility_warning.accepted.connect(close)
        eligibility_warning.show()
        self.ineligible.clear()

    def open_log(self):
        log_file = os.path.join(os.getcwd(), self.ESLIFIER_LOG_FILE)
        if os.path.exists(log_file):
            try:
                if os.name == 'nt':
                    os.startfile(log_file)
                elif os.name == 'posix':
                    subprocess.Popen(['xdg-open', log_file])
                else:
                    subprocess.Popen(['open', log_file])
            except Exception as e:
                write_error(self.tr("Error opening file:: ") + str(e))

    def report_crash(self, label:str, exc_value, exc_traceback):
        self.crash = True
        parts = [
            self.tr("An exception has occured, please report this bug to the github and include the ESLifier.log file found in %0.")
            .replace("%0", self.ESLIFIER_DATA_FOLDER),
            ''.join(traceback.format_tb(exc_traceback, 5)),
            f"Unhandled exception: {exc_value}",
            '',
        ]
        self.write_to_file(f'{label} -> Extended Traceback for debugging:\n' + ''.join(traceback.format_tb(exc_traceback, 10)))
        self.write_to_file(f"Unhandled exception: {exc_value}")
        with self.display_queue.mutex:
            self.display_queue.queue.clear()
        self.display_queue.put(("", 7, parts))    # 7 crash
        try:
            self.open_log()
        except:
            pass

    def exception_hook(self, exc_type, exc_value, exc_traceback):
        self.report_crash('exception_hook', exc_value, exc_traceback)

    def threading_exception_hook(self, args: threading.ExceptHookArgs):
        self.report_crash('threading_exception_hook', args.exc_value, args.exc_traceback)

    def closeEvent(self, a0):
        self.running = False
        self.queue_timer.stop()
        if not self.log_file.closed:
            self.log_file.flush()
            self.log_file.close()
        super().closeEvent(a0)

    def close(self):
        self.running = False
        self.queue_timer.stop()
        if not self.log_file.closed:
            self.log_file.flush()
            self.log_file.close()
        super().close()

    def process_queue(self):
        try:
            self.process_queue_once()
        finally:
            if self.running:
                self.queue_timer.start(QUEUE_PROCESS_RATE)

    def process_queue_once(self):
        length = self.display_queue.qsize()
        #keep_range = length - 50 if length > 50 else 0
        for i in range(length):
            if self.display_queue.empty():
                break
            text, *args = self.display_queue.get()
            #if args[0] == 1 and args[2] and i < keep_range:
            #    continue
            self.apply_item(text, *args)

    def apply_item(self, text:str, *args) -> bool:
        arg_0 = args[0]
        if DEBUG and not (arg_0 == 1 and args[2]):
            self.hijack_print.print_to_console(text)
        if arg_0 == 1:
            if args[1] == 1:
                try:
                    self.lines.pop()
                except:
                    pass
            elif args[1] == -1:
                self.lines.clear()
            else:
                for _ in range(args[1]):
                    try:
                        self.lines.pop()
                    except:
                        break
            self.lines.append(text)
            return True
        elif arg_0 == 3: # clear and close
            self.percentage = 100
            #write_to_file("clearing, screen log snapshot:\n" + '\n'.join(self.lines))
            self.log_file.flush()
            self.timer_clear.start(1500)
            return False
        elif arg_0 == 4: # clear and leave open
            #write_to_file("alt clearing, screen log snapshot:\n" + '\n'.join(self.lines))
            self.clear_alt()
            return True
        elif arg_0 == 5:
            self.lines.insert(args[1], text)
            return True
        elif arg_0 == 6:
            if not 'red' in self.text_edit.styleSheet() and not 'lightblue' in self.text_edit.styleSheet():
                self.text_edit.setStyleSheet("background-color: lightblue")
            return False
        elif arg_0 == 7: # crash, runs on the GUI thread
            self.show()
            self.lines.clear()
            self.lines.extend(args[1])
            self.text_edit.setStyleSheet("background-color: red;")
            self.running = False
            return True
        else:   #args[0] == 0 # Simply append new text
            self.lines.append(text)
            return True

    def refresh_progress_bar(self):
        if not self.isHidden() and self.progress_bar.value() != self.percentage:
            if self.percentage == 0:
                if not self.progress_bar_busy_mode:
                    self.progress_bar_busy_mode = True
                    self.progress_bar.setRange(0,0)
                    self.progress_bar.setStyleSheet("""
                        QProgressBar {
                            background-color: #999999;
                            border: 0px;
                            padding: 0px;
                            max-height: 5px;
                        }
                        QProgressBar::chunk {
                            background-color: qlineargradient(spread:reflect, x1:0, y1:0, x2:0.5, y2:0, stop:0 #999999, stop:1 #03f8fc);
                        }""")
                    self.progress_bar.setValue(self.percentage)
            else:
                if self.progress_bar_busy_mode:
                    self.progress_bar_busy_mode = False
                    self.progress_bar.setRange(0,100)
                    self.progress_bar.setStyleSheet("""
                        QProgressBar {
                            background-color: #999999;
                            border: 0px;
                            padding: 0px;
                            max-height: 5px;
                        }
                        QProgressBar::chunk {
                            background: #03f8fc;
                            width:1px
                        }
                    """)
                if not self.progress_bar.paintingActive():
                    self.progress_bar.setValue(self.percentage)

    def refresh_main_progress_bar(self):
        if not self.isHidden() and self.main_progress_bar.value() != self.main_percentage:
            if self.main_percentage == 0:
                if not self.main_progress_bar_busy_mode:
                    self.main_progress_bar_busy_mode = True
                    self.main_progress_bar.setRange(0,0)
                    self.main_progress_bar.setStyleSheet("""
                        QProgressBar {
                            background-color: #999999;
                            border: 0px;
                            padding: 0px;
                            max-height: 10px;
                        }
                        QProgressBar::chunk {
                            background-color: qlineargradient(spread:reflect, x1:0, y1:0, x2:0.5, y2:0, stop:0 #999999, stop:1 #03f8fc);
                        }""")
                    self.main_progress_bar.setValue(self.main_percentage)
            else:
                if self.main_progress_bar_busy_mode:
                    self.main_progress_bar_busy_mode = False
                    self.main_progress_bar.setRange(0,100)
                    self.main_progress_bar.setStyleSheet("""
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
                if not self.main_progress_bar.paintingActive():
                    self.main_progress_bar.setValue(self.main_percentage)

    def refresh_log(self):
        self.refresh_progress_bar()
        self.refresh_main_progress_bar()
        self.refresh_text_widget()

    def refresh_text_widget(self):
        lines_copy = self.lines.copy()
        self.text_edit.setPlainText('\n'.join(lines_copy))
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.verticalScrollBar().setValue(self.text_edit.verticalScrollBar().maximum())

    def clean_up(self):
        if not self.crash:
            self.lines.clear()
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
            self.lines.clear()
            self.text_edit.setPlainText(None)
            self.log_file.flush()
