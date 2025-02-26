import os
import subprocess
import json

from PyQt6.QtCore import Qt, QItemSelection
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem

class list_compacted_unpatched(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(['Mod', 'New CELL Warning'])
        self.horizontalHeaderItem(0).setToolTip('These are plugins which this program has compacted.\nTick the plugin for which you want to patch new files.\nSelect for which plugin you want to show the unpatched files.')
        self.horizontalHeaderItem(1).setToolTip('If you can see this column then one or more of the mods\nbelow have a new dependent plugin which modifies it\'s\nnew CELL record which may break because the master is ESL.')
        self.horizontalHeaderItem(1).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.verticalHeader().setHidden(True)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
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
        cell_changed = self.get_data_from_file('ESLifier_Data/cell_changed.json')
        self.clearContents()
        self.setRowCount(len(self.mod_list))
        self.setColumnHidden(1, True)
        for mod in self.mod_list:
            if os.path.basename(mod) in cell_changed:
                self.setColumnHidden(1, False)
                break

        for i in range(len(self.mod_list)):
            item = QTableWidgetItem(os.path.basename(self.mod_list[i]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(self.mod_list[i])
            self.setItem(i, 0, item)
            if os.path.basename(self.mod_list[i]) in cell_changed:
                item_error = QTableWidgetItem('Warning!')
                item_error.setToolTip('This mod has a dependent plugin that changes a new CELL record.\nThis may break the mod\'s new CELL.')
                self.setItem(i, 1, item_error)

        def something_changed(itemChanged):
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
                print(f"Error opening file explorer: {e}")

    def get_data_from_file(self, file):
        try:
            with open(file, 'r') as f:
                data = json.load(f)
        except:
            data = {}
        return data
