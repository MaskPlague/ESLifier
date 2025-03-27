import os
import json

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLineEdit
except ImportError:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLineEdit

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLineEdit

class blacklist(QTableWidget):
    def __init__(self, remove_mode):
        super().__init__()
        if remove_mode:
            self.setColumnCount(1)
            self.setHorizontalHeaderLabels(['*   Blacklisted Mod'])
            self.horizontalHeaderItem(0).setToolTip('These are the blacklisted plugins, select the mods you want to remove from the blacklist.')
        else:
            self.setColumnCount(5)
            self.setHorizontalHeaderLabels(['*   ESLify-able Mod', 'Needs Compacting', 'New Cell', 'New Interior Cell', 'New Worldspace'])
            self.horizontalHeaderItem(0).setToolTip('These are the ESLify-able plugins, select the mods you want to add to the blacklist.')
            self.horizontalHeaderItem(1).setToolTip('Whether the mod needs comapcting or just the ESL flag.')
            self.horizontalHeaderItem(2).setToolTip('If the plugin has a new cell.')
            self.horizontalHeaderItem(3).setToolTip('If the plugin has a new Interior CELL.')
            self.horizontalHeaderItem(4).setToolTip('If the plugin has a new worldspace.')
        self.verticalHeader().setHidden(True)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)
        self.blacklist = []
        self.blacklist_path = ''

    def create(self, remove_mode):
        self.setSortingEnabled(False)
        self.clearContents()
        if remove_mode:
            self.blacklist = self.get_data_from_file(self.blacklist_path)
            self.setRowCount(len(self.blacklist))
            for i in range(len(self.blacklist)):
                item = QTableWidgetItem(os.path.basename(self.blacklist[i]))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.setItem(i, 0, item)
                self.setRowHidden(i, False)
        else:
            self.setRowCount(len(self.blacklist))
            for i, (plugin, flags) in enumerate(self.blacklist.items()):
                item = QTableWidgetItem(plugin)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.setItem(i, 0, item)
                self.setRowHidden(i, False)
                if 'need_compacting' in flags:
                    item_compacting = QTableWidgetItem('Needs Compacting')
                    self.setItem(i, 1, item_compacting)
                if 'new_cell' in flags:
                    item_cell = QTableWidgetItem('New Cell')
                    self.setItem(i, 2, item_cell)
                if 'interior_cell' in flags:
                    item_interior = QTableWidgetItem('Interior Cell')
                    self.setItem(i, 3, item_interior)
                if 'new_wrld' in flags:
                    item_wrld = QTableWidgetItem('New Worldspace')
                    self.setItem(i, 4, item_wrld)


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
        self.resizeColumnsToContents()
        self.itemChanged.connect(somethingChanged)
        self.resizeRowsToContents()
        self.setSortingEnabled(True)

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

    def add_to_blacklist(self):
        blacklist = self.get_data_from_file(self.blacklist_path)
        mods_to_add = []
        for i in range(self.rowCount()):
            if self.item(i, 0).checkState() == Qt.CheckState.Checked:
                mods_to_add.append(self.item(i,0).text())

        for mod in mods_to_add:
            if mod not in blacklist:
                blacklist.append(mod)
            self.blacklist.pop(mod)
        self.dump_to_file(blacklist, self.blacklist_path)
        self.create(False)

    def remove_from_blacklist(self):
        self.blacklist = self.get_data_from_file(self.blacklist_path)
        mods_to_remove = []
        for i in range(self.rowCount()):
            if self.item(i,0).checkState() == Qt.CheckState.Checked:
                mods_to_remove.append(self.item(i,0).text())

        for mod in mods_to_remove:
            self.blacklist.remove(mod)
        self.dump_to_file(self.blacklist, self.blacklist_path)
        self.create(True)

    def dump_to_file(self, blacklist, file):
        try:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(blacklist, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f'!Error: Failed to dump blacklist data to {file}')
            print(e)
        
class blacklist_window(QMainWindow):
    def __init__(self, remove_mode):
        super().__init__()
        if remove_mode:
            self.setWindowTitle("Select Mods to Remove From the Blacklist")
        else:
            self.setWindowTitle("Select Mods to Add to Blacklist")

        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.blacklist = blacklist(remove_mode)
        self.setMinimumSize(800, 400)
        blacklist_window_buttons_layout = QHBoxLayout()
        blacklist_window_buttons_widget = QWidget()
        blacklist_window_buttons_widget.setLayout(blacklist_window_buttons_layout)

        cancel_button = QPushButton(' Done ')
        def cancel():
            self.hide()
            self.blacklist.uncheck_all()
            self.blacklist.clearSelection()
        cancel_button.clicked.connect(cancel)

        self.filter_blacklist = QLineEdit()
        self.filter_blacklist.setPlaceholderText("Filter ")
        self.filter_blacklist.setToolTip("Search Bar")
        self.filter_blacklist.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.filter_blacklist.setClearButtonEnabled(True)
        self.filter_blacklist.textChanged.connect(self.search)

        if remove_mode:
            remove_selected_from_blacklist_button = QPushButton(' Remove Selected From Blacklist ')
            remove_selected_from_blacklist_button.clicked.connect(self.blacklist.remove_from_blacklist)
            remove_selected_from_blacklist_button.clicked.connect(self.filter_blacklist.clear)
            blacklist_window_buttons_layout.addWidget(remove_selected_from_blacklist_button)
        else:
            add_selected_to_blacklist_button = QPushButton(' Add Selected to Blacklist ')
            add_selected_to_blacklist_button.clicked.connect(self.blacklist.add_to_blacklist)
            add_selected_to_blacklist_button.clicked.connect(self.filter_blacklist.clear)
            blacklist_window_buttons_layout.addWidget(add_selected_to_blacklist_button)
            
        blacklist_window_buttons_layout.addWidget(self.filter_blacklist)
        blacklist_window_buttons_layout.addWidget(cancel_button)
        blacklist_window_layout = QVBoxLayout()
        blacklist_window_layout.addWidget(self.blacklist)
        blacklist_window_layout.addWidget(blacklist_window_buttons_widget)
        blacklist_window_central_widget = QWidget()
        blacklist_window_central_widget.setLayout(blacklist_window_layout)
        self.setCentralWidget(blacklist_window_central_widget)

    def search(self):
        if len(self.filter_blacklist.text()) > 0:
            items = self.blacklist.findItems(self.filter_blacklist.text(), Qt.MatchFlag.MatchContains)
            if len(items) > 0:
                for i in range(self.blacklist.rowCount()):
                    self.blacklist.setRowHidden(i, False if (self.blacklist.item(i,0) in items) else True)
        else:
            for i in range(self.blacklist.rowCount()):
                self.blacklist.setRowHidden(i, False)