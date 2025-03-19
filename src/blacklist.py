import os
import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLineEdit
from PyQt6.QtGui import QIcon

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
                image: url(:/images/checked.png);
            }
            QTableWidget::indicator:unchecked{
                image: url(:/images/unchecked.png);
            }
            QTableWidget::indicator:indeterminate{
                image:url(:/images/partially_checked.png);
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
            with open(file, 'r', encoding='utf-8') as f:
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

    def add_to_blacklist(self, mods_to_add):
        self.blacklist = self.get_data_from_file('ESLifier_Data/blacklist.json')
        for mod in mods_to_add:
            if mod not in self.blacklist:
                self.blacklist.append(mod)
        self.dump_to_file('ESLifier_Data/blacklist.json')
        self.create()

    def remove_from_blacklist(self):
        self.blacklist = self.get_data_from_file('ESLifier_Data/blacklist.json')
        mods_to_remove = []
        for i in range(self.rowCount()):
            if self.item(i,0).checkState() == Qt.CheckState.Checked:
                mods_to_remove.append(self.item(i,0).text())

        for mod in mods_to_remove:
            self.blacklist.remove(mod)
        self.dump_to_file('ESLifier_Data/blacklist.json')
        self.create()

    def dump_to_file(self, file):
        try:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(self.blacklist, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f'!Error: Failed to dump blacklist data to {file}')
            print(e)
        
class blacklist_window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(":/images/ESLifier.png"))
        self.setWindowTitle("Select Mods to Remove From the Blacklist")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QLineEdit {
                border: none;
                border-radius: 5px;
            }
            QLineEdit::focus {
                border: 1px solid black;
                border-radius: 5px;
            }
            QPushButton {
                border: 1px solid LightGrey;
                border-radius: 5px;
                background-color: LightGrey;
            }
            QPushButton::hover{
                border: 1px solid ghostwhite;
                border-radius: 5px;
                background-color: ghostwhite;
            }
            QLabel{
                color: White
            }
            """)
        self.blacklist = blacklist()
        blacklist_window_buttons_layout = QHBoxLayout()
        blacklist_window_buttons_widget = QWidget()
        blacklist_window_buttons_widget.setLayout(blacklist_window_buttons_layout)

        remove_selected_from_blacklist_button = QPushButton(' Remove Selected From Blacklist ')
        remove_selected_from_blacklist_button.clicked.connect(self.blacklist.remove_from_blacklist)
        cancel_button = QPushButton(' Cancel ')
        def cancel():
            self.hide()
            self.blacklist.uncheck_all()
            self.blacklist.clearSelection()
        cancel_button.clicked.connect(cancel)

        self.filter_blacklist = QLineEdit()
        self.filter_blacklist.setPlaceholderText("Filter ")
        self.filter_blacklist.setToolTip("Search Bar")
        self.filter_blacklist.setMinimumWidth(50)
        self.filter_blacklist.setMaximumWidth(150)
        self.filter_blacklist.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.filter_blacklist.setClearButtonEnabled(True)
        self.filter_blacklist.textChanged.connect(self.search)

        blacklist_window_buttons_layout.addWidget(remove_selected_from_blacklist_button)
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