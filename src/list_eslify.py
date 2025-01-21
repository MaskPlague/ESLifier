import os
import subprocess
import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem

from blacklist import blacklist

class list_eslable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(['*   Mod', 'CELL Records', ''])
        self.horizontalHeaderItem(0).setToolTip('This is the plugin name. Select which plugins you wish to flag as light.')
        self.horizontalHeaderItem(1).setToolTip('This is the CELL Record Flag. If an ESL plugin creates a new CELL\n and another mod changes that CELL then it\nmay not work due to an engine bug.')
        self.verticalHeader().setHidden(True)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)
        self.mod_list = []
        self.cell_flags = []

        self.blacklist = blacklist()

        self.setStyleSheet("""
            QTableWidget::item{
                border-top: 1px solid gray
            }
            QTableWidget::item::selected{
                background-color: rgb(150,150,150);
            }
            QTableWidget::item::hover{
                background-color: rgb(200,200,200);
            }
            QTableWidget::indicator:checked{
                image: url(./images/checked.png);
            }
            QTableWidget::indicator:unchecked{
                image: url(./images/unchecked.png);
            }
            QTableWidget::indicator:indeterminate{
                image:url(./images/partially_checked.png);
            }
        """)
        self.create()

    def create(self):
        self.clearContents()
        self.compacted = self.get_data_from_file("ESLifier_Data/compacted_and_patched.json")
        blacklist = self.get_data_from_file('ESLifier_Data/blacklist.json')
        if blacklist == {}:
            blacklist = []

        to_remove = []
        for mod in self.mod_list:
            if os.path.basename(mod) in blacklist:
                to_remove.append(mod)
                
        for mod in to_remove:
            self.mod_list.remove(mod)

        self.setRowCount(len(self.mod_list))

        for i in range(len(self.mod_list)):
            item = QTableWidgetItem(os.path.basename(self.mod_list[i]))
            if os.path.basename(self.mod_list[i]).lower() in self.compacted.keys():
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.PartiallyChecked)
            else:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(self.mod_list[i])
            self.setItem(i, 0, item)
            self.setRowHidden(i, False)
            if self.cell_flags[i]:
                item_cell_flag = QTableWidgetItem('New CELL')
                item_cell_flag.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(i, 1, item_cell_flag)

        def somethingChanged(itemChanged):
            self.blockSignals(True)
            if itemChanged.checkState() == Qt.CheckState.Checked:
                for x in self.selectedItems():
                    if x.column() == 0:
                        x.setCheckState(Qt.CheckState.Checked)
            else:
                for x in self.selectedItems():
                    if x.column() == 0:
                        x.setCheckState(Qt.CheckState.Unchecked)
            self.blockSignals(False)

        self.resizeColumnToContents(0)
        self.resizeColumnToContents(1)
        self.itemChanged.connect(somethingChanged)
        self.resizeRowsToContents()

    def get_data_from_file(self, file):
        try:
            with open(file, 'r') as f:
                data = json.load(f)
        except:
            data = {}
        return data

    
    def contextMenu(self, position):
        selected_item = self.itemAt(position)
        if selected_item:
            menu = QMenu(self)
            select_all_action = menu.addAction("Select All")
            check_all_action = menu.addAction("Check All")
            uncheck_all_action = menu.addAction("Uncheck All")
            invert_selection_action = menu.addAction("Invert Selection")
            open_explorer_action = menu.addAction("Open in File Explorer")
            add_to_blacklist_action = menu.addAction("Add Mod(s) to Blacklist")
            action = menu.exec(self.viewport().mapToGlobal(position))
            if action == open_explorer_action:
                self.open_in_explorer(selected_item)
            if action == check_all_action:
                self.check_all()
            if action == uncheck_all_action:
                self.uncheck_all()
            if action == select_all_action:
                self.selectAll()
            if action == invert_selection_action:
                selected_items = self.selectedItems()
                self.invert_selection(selected_items)
            if action == add_to_blacklist_action:
                selected_items = self.selectedItems()
                self.add_to_blacklist(selected_items)

    def check_all(self):
        self.blockSignals(True)
        for i in range(self.rowCount()):
            if self.item(i,0).checkState() == Qt.CheckState.Unchecked:
                self.item(i, 0).setCheckState(Qt.CheckState.Checked)
        self.blockSignals(False)

    def uncheck_all(self):
        self.blockSignals(True)
        for i in range(self.rowCount()):
            if self.item(i,0).checkState() == Qt.CheckState.Checked:
                self.item(i, 0).setCheckState(Qt.CheckState.Unchecked)
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

    def add_to_blacklist(self, selected_items):
        mods = [item.text() for item in selected_items if item.column() == 0]
        self.blacklist.add_to_blacklist(mods)
        self.create()
