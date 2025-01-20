import os
import subprocess
import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem

class blacklist(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels(['*   Blacklisted Mod'])
        self.horizontalHeaderItem(0).setToolTip('These are the blacklisted plugins, select the mods you want to remove from the blacklist.')
        self.verticalHeader().setHidden(True)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)
        self.blacklist = []

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
        self.blacklist = self.get_data_from_file('ESLifier_Data/blacklist.json')
        self.setRowCount(len(self.blacklist))

        for i in range(len(self.blacklist)):
            item = QTableWidgetItem(os.path.basename(self.blacklist[i]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.setItem(i, 0, item)
            self.setRowHidden(i, False)

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
            data = []
        return data

    def contextMenu(self, position):
        selected_item = self.itemAt(position)
        if selected_item:
            menu = QMenu(self)
            select_all_action = menu.addAction("Select All")
            check_all_action = menu.addAction("Check All")
            uncheck_all_action = menu.addAction("Uncheck All")
            action = menu.exec(self.viewport().mapToGlobal(position))
            if action == check_all_action:
                self.check_all()
            if action == uncheck_all_action:
                self.uncheck_all()
            if action == select_all_action:
                self.selectAll()

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

    def add_to_blacklist(self, mod_to_add):
        self.blacklist = self.get_data_from_file('ESLifier_Data/blacklist.json')
        if mod_to_add not in self.blacklist:
            self.blacklist.append(mod_to_add)
            self.dump_to_file('ESLifier_Data/blacklist.json')
            self.create()

    def remove_from_blacklist(self, mods_to_remove):
        self.blacklist = self.get_data_from_file('ESLifier_Data/blacklist.json')
        for mod in mods_to_remove:
            self.blacklist.remove(mod)
        self.dump_to_file('ESLifier_Data/blacklist.json')
        self.create()

    def dump_to_file(self, file):
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(self.blacklist, f, ensure_ascii=False, indent=4)

        
        
