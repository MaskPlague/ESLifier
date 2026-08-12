import os
import subprocess
import json

from PyQt6.QtCore import Qt, QItemSelection, pyqtSignal
from PyQt6.QtWidgets import (QTableWidget, QTableWidgetItem, QMessageBox, QFileDialog)
from PyQt6.QtGui import QIcon
from blacklist import blacklist
from log_stream import write_error

class list_parent_class(QTableWidget):
    list_created_signal = pyqtSignal()
    MOD_COL = 0
    CELL_COL = 0
    WRLD_COL = 0
    WTHR_COL = 0
    SKSE_COL = 0
    SEQ_COL = 0
    PEX_COL = 0
    ESM_COL = 0
    DEP_COL = 0
    DEP_DISP_COL = 0
    HIDER_COL = 0
    COL_COUNT = 0
    blacklist: blacklist = None
    file_dialog:QFileDialog = None
    save_file_dialog:QFileDialog = None
    check_previous_text:str = ''

    def __init__(self):
        super().__init__()

    def create_list():
        pass

    def hide_rows(self):
        for row in range(self.rowCount()):
            if self.item(row, self.HIDER_COL):
                self.setRowHidden(row, True)
            else:
                self.setRowHidden(row, False)
    
    def get_data_from_file(self, file, data_type):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = data_type()
        return data

    def check_all(self):
        self.blockSignals(True)
        for i in range(self.rowCount()):
            if not self.isRowHidden(i) and self.item(i,self.MOD_COL).checkState() == Qt.CheckState.Unchecked:
                self.item(i, self.MOD_COL).setCheckState(Qt.CheckState.Checked)
        self.blockSignals(False)
    
    def uncheck_all(self):
        self.blockSignals(True)
        for i in range(self.rowCount()):
            if self.item(i,self.MOD_COL).checkState() == Qt.CheckState.Checked:
                self.item(i, self.MOD_COL).setCheckState(Qt.CheckState.Unchecked)
        self.blockSignals(False)
    
    def select_all(self):
        self.blockSignals(True)
        selection = QItemSelection()
        for row in range(self.rowCount()):
            if not self.isRowHidden(row):
                selection.select(self.model().index(row, self.MOD_COL), self.model().index(row, self.model().columnCount() - 1))
        selection_model = self.selectionModel()
        selection_model.select(selection, selection_model.SelectionFlag.ClearAndSelect)
        self.blockSignals(False)

    def invert_selection(self, selected_items:list[QTableWidgetItem]):
        self.blockSignals(True)
        for item in selected_items:
            if item.checkState() == Qt.CheckState.Checked:
                if item.column() == self.MOD_COL:
                    item.setCheckState(Qt.CheckState.Unchecked)
            elif item.checkState() == Qt.CheckState.Unchecked:
                if item.column() == self.MOD_COL:
                    item.setCheckState(Qt.CheckState.Checked)
        self.blockSignals(False)

    def open_in_explorer(self, selectedItem:QTableWidgetItem):
        file_path = selectedItem.toolTip()
        
        if file_path:
            file_directory, _ = os.path.split(file_path)
            try:
                if os.name == 'nt':
                    os.startfile(file_directory)
                elif os.name == 'posix':
                    subprocess.Popen(['xdg-open', os.path.dirname(file_directory)])
                else:
                    subprocess.Popen(['open', os.path.dirname(file_directory)])
            except Exception as e:
                write_error(self.tr("Error opening file explorer: ") + str(e))

    def add_to_blacklist(self, selected_items: list[QTableWidgetItem]):
        mods = [item.text() for item in selected_items if item.column() == self.MOD_COL]
        self.blacklist.add_to_blacklist(mods)
        self.create_list()

    def select_file_path(self, dialog: QFileDialog, title, filter, mode:int=0):
        if mode == 0:
            path, _ = dialog.getOpenFileName(self, title, filter=filter)
        elif mode == 1:
            path, _ = dialog.getSaveFileName(self, title, filter=filter)
        if path:
            return os.path.normpath(path)
        else:
            return None

    def create_confirmation(self, title:str, text:str, color:str = '', icon:QMessageBox.Icon = QMessageBox.Icon.Warning, yes_no:bool=False):
        confirm = QMessageBox()
        confirm.setIcon(icon)
        confirm.setWindowIcon(QIcon(":/images/ESLifier.png"))
        if color != '':
            confirm.setStyleSheet("""
                QMessageBox {
                    background-color: """+color+""";
                }""")
        confirm.setWindowTitle(title)
        confirm.setText(text)
        if not yes_no:
            confirm.addButton(QMessageBox.StandardButton.Ok).setText(self.tr("Ok"))
            confirm.button(QMessageBox.StandardButton.Ok).setFocus()
            confirm.setDefaultButton(QMessageBox.StandardButton.Ok)
        else:
            confirm.addButton(QMessageBox.StandardButton.Yes).setText(self.tr("Yes"))
            confirm.addButton(QMessageBox.StandardButton.No).setText(self.tr("No"))
            confirm.button(QMessageBox.StandardButton.No).setFocus()
            confirm.setDefaultButton(QMessageBox.StandardButton.No)
        return confirm

    def check_previous_func():
        pass

    def import_check_state_from_file(self):
        path = self.select_file_path(self.file_dialog, self.check_previous_text, '*.json')
        if path is not None:
            if os.path.exists(path):
                previous_items = []
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        previous_items = json.load(f)
                except:
                    return
                if previous_items:
                    self.uncheck_all()
                    self.check_previous_func(previous_items, False)
                    self.message = self.create_confirmation(self.tr("Success"), 
                                                        self.tr("Import successful. Any items both in the imported list and scanned list have been selected."),
                                                        icon=QMessageBox.Icon.Information)
                    self.message.show()
                else:
                    self.message = self.create_confirmation(self.tr("Failed"), 
                                                        self.tr("Import Failed. File is empty or invalid."),
                                                        'lightcoral',
                                                        icon=QMessageBox.Icon.Warning)
                    self.message.show()
            else:
                self.message = self.create_confirmation(self.tr("Error"), 
                                                    self.tr("Selected file does not exist."),
                                                    'lightcoral',
                                                    icon=QMessageBox.Icon.Warning)
                self.message.show()

    def export_check_state_to_file(self):
        checked = []
        for row in range(self.rowCount()):
            if self.item(row, self.MOD_COL).checkState() == Qt.CheckState.Checked and not self.item(row, self.HIDER_COL):
                checked.append(self.item(row, self.MOD_COL).text())

        file_path = self.select_file_path(self.file_dialog, self.tr("Export Check State File As..."), filter='*.json', mode=1)
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(checked, f, indent=2)
                self.message = self.create_confirmation(self.tr("Success"), 
                                                        self.tr("Export successful. Current check state saved to %0").replace("%0", file_path),
                                                        icon=QMessageBox.Icon.Information)
                self.message.show()
            except Exception as e:
                self.message = self.create_confirmation(self.tr("Error"), 
                                                        self.tr("Error while exporting: ") + str(e),
                                                        'lightcoral',
                                                        icon=QMessageBox.Icon.Warning)
                self.message.show()