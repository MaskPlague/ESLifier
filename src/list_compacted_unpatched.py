import os
import subprocess
import json

from PyQt6.QtCore import Qt, QItemSelection
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem

class list_compacted_unpatched(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(['Mod', 'New CELL Warning', 'SKSE DLL Warning'])
        self.horizontalHeaderItem(0).setToolTip('These are plugins which this program has compacted.\nTick the plugin for which you want to patch new files.\nSelect for which plugin you want to show the unpatched files.')
        self.horizontalHeaderItem(1).setToolTip('If you can see this column then one or more of the mods\nbelow have a new dependent plugin which modifies it\'s\nnew CELL record which may break because the master is ESL.')
        self.horizontalHeaderItem(2).setToolTip('If you can see this column then one or more of the mods\nbelow have a SKSE DLL that may rely on the uncompacted\n form ids which may be hard-coded into it.')
        self.horizontalHeaderItem(1).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.horizontalHeaderItem(2).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.verticalHeader().setHidden(True)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAutoScroll(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)
        self.mod_list = []

        self.setStyleSheet("""
            QTableWidget::item{
                border-top: 1px solid gray;
            }
            QTableWidget::item::selected{
                background-color: rgb(150,150,150);
            }
            QTableWidget::item::hover{
                background-color: rgb(200,200,200);
            }
            QTableWidget::indicator:checked{
                image: url(:/images/checked.png);
            }
            QTableWidget::indicator:unchecked{
                image: url(:/images/unchecked.png);
            }
            QTableWidget::indicator:indeterminate{
                image:url(:/images/partially_checked.png);
            }
        """)

        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.horizontalHeader().setStretchLastSection(True)
        
        self.create()

    def create(self):
        self.setSortingEnabled(False)
        cell_changed = self.get_data_from_file('ESLifier_Data/cell_changed.json')
        dll_dict = self.get_data_from_file('ESLifier_Data/dll_dict.json')
        self.clearContents()
        self.setRowCount(len(self.mod_list))
        self.setColumnHidden(1, True)
        self.setColumnHidden(2, True)
        checked_cell_changed_warning = False
        checked_skse_dll_warning = False
        for mod in self.mod_list:
            if not checked_cell_changed_warning and os.path.basename(mod) in cell_changed:
                self.setColumnHidden(1, False)
                checked_cell_changed_warning = True
            if not checked_skse_dll_warning and os.path.basename(mod).removeprefix('SKSE WARN - ').lower() in dll_dict:
                self.setColumnHidden(2, False)
                checked_skse_dll_warning = True
            if checked_cell_changed_warning and checked_skse_dll_warning:
                break

        for i in range(len(self.mod_list)):
            basename = os.path.basename(self.mod_list[i])
            item = QTableWidgetItem(basename)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(self.mod_list[i])
            if basename.startswith('SKSE WARN - '):
                item.setToolTip(None)
            self.setItem(i, 0, item)
            
            if basename in cell_changed:
                item_cell_changed_error = QTableWidgetItem('CELL Changed!')
                item_cell_changed_error.setToolTip('This mod has a dependent plugin that changes a new CELL record.\nThis may break the mod\'s new CELL.')
                self.setItem(i, 1, item_cell_changed_error)
            if basename.removeprefix('SKSE WARN - ').lower() in dll_dict:
                item_dll_error = QTableWidgetItem('DLL!')
                tooltip = "This mod's plugin name is present in the following dlls and\nmay be breaking them as they may rely on hard-coded form ids:"
                for dll in dll_dict[basename.removeprefix('SKSE WARN - ').lower()]:
                    tooltip += '\n- ' + os.path.basename(dll)
                item_dll_error.setToolTip(tooltip)
                self.setItem(i, 2, item_dll_error)

        def something_changed(itemChanged):
            multi_check = True
            if len(self.selectedItems()) < 2:
                multi_check = False
            if multi_check:
                if itemChanged.checkState() == Qt.CheckState.Checked:
                    for x in self.selectedItems():
                        if x.checkState() == Qt.CheckState.Unchecked:
                            x.setCheckState(Qt.CheckState.Checked)
                else:
                    for x in self.selectedItems():
                        if x.checkState() == Qt.CheckState.Checked:
                            x.setCheckState(Qt.CheckState.Unchecked)

        def item_selected():
            selected_items = self.selectedItems()
            mods_selected = [item.toolTip() for item in selected_items]
            self.parentWidget().parentWidget().parentWidget().list_unpatched_files.mods_selected = mods_selected
            self.parentWidget().parentWidget().parentWidget().list_unpatched_files.create()

        self.itemChanged.connect(something_changed)
        self.itemSelectionChanged.connect(item_selected)
        self.resizeColumnToContents(0)
        self.resizeRowsToContents()
        self.setSortingEnabled(True)

    def contextMenu(self, position):
        selectedItem = self.itemAt(position)
        if selectedItem:
            menu = QMenu(self)
            select_all_action = menu.addAction("Select All")
            check_all_action = menu.addAction("Check All")
            uncheck_all_action = menu.addAction("Uncheck All")
            invert_selection_action = menu.addAction("Invert Selection Checks")
            open_explorer_action = menu.addAction("Open in File Explorer")
            action = menu.exec(self.viewport().mapToGlobal(position))
            if action == open_explorer_action:
                self.open_in_explorer(selectedItem)
            if action == check_all_action:
                self.check_all()
            if action == uncheck_all_action:
                self.uncheck_all()
            if action == select_all_action:
                self.select_all()
            if action == invert_selection_action:
                selected_items = self.selectedItems()
                self.invert_selection(selected_items)

    def check_all(self):
        self.blockSignals(True)
        for i in range(self.rowCount()):
            if not self.isRowHidden(i) and self.item(i,0).checkState() == Qt.CheckState.Unchecked:
                self.item(i, 0).setCheckState(Qt.CheckState.Checked)
        self.blockSignals(False)

    def uncheck_all(self):
        self.blockSignals(True)
        for i in range(self.rowCount()):
            if self.item(i,0).checkState() == Qt.CheckState.Checked:
                self.item(i, 0).setCheckState(Qt.CheckState.Unchecked)
        self.blockSignals(False)

    def select_all(self):
        self.blockSignals(True)
        selection = QItemSelection()
        for row in range(self.rowCount()):
            if self.isRowHidden(row) == False:
                selection.select(self.model().index(row, 0), self.model().index(row, self.model().columnCount() - 1))
        selection_model = self.selectionModel()
        selection_model.select(selection, selection_model.SelectionFlag.ClearAndSelect)
        self.blockSignals(False)
    
    def invert_selection(self, selected_items):
        self.blockSignals(True)
        for item in selected_items:
            if item.checkState() == Qt.CheckState.Checked:
                if item.column() == 0:
                    item.setCheckState(Qt.CheckState.Unchecked)
            elif item.checkState() == Qt.CheckState.Unchecked:
                if item.column() == 0:
                    item.setCheckState(Qt.CheckState.Checked)
        self.blockSignals(False)

    def open_in_explorer(self, selectedItem):
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
                print(f"!Error opening file explorer: {e}")

    def get_data_from_file(self, file):
        try:
            with open(file, 'r') as f:
                data = json.load(f)
        except:
            data = {}
        return data
