import os
import subprocess
import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem
from PyQt6.QtGui import QFontMetrics, QFont

class list_unpatched(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels(['Files'])
        self.horizontalHeaderItem(0).setToolTip('These are the unpatched files.')
        self.verticalHeader().setHidden(True)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.setAutoScroll(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.horizontalHeader().setStretchLastSection(True)
        self.customContextMenuRequested.connect(self.context_menu)
        self.file_dictionary = {}
        self.dependencies_dictionary = {}
        self.cell_flags = []
        self.mods_selected = []

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
        """)
        
        self.create()

    def create(self):
        self.clearContents()
        self.compacted_and_patched = self.get_data_from_file("ESLifier_Data/compacted_and_patched.json")
        size = 0
        for mod in self.mods_selected:
            if mod in self.file_dictionary.keys():
                size += len(self.file_dictionary[mod])
            if mod in self.dependencies_dictionary:
                size += len(self.dependencies_dictionary[mod])

        self.setRowCount(size)
        i = 0
        font = QFont()
        metric = QFontMetrics(font)
        for mod in self.mods_selected:
            x = 0
            if mod in self.dependencies_dictionary.keys():
                while x in range(len(self.dependencies_dictionary[mod])):
                    file = metric.elidedText(self.dependencies_dictionary[mod][x], Qt.TextElideMode.ElideLeft, 400)
                    item = QTableWidgetItem(file)
                    item.setToolTip(self.dependencies_dictionary[mod][x])
                    self.setItem(i, 0, item)
                    i += 1
                    x += 1
            if mod in self.file_dictionary.keys():
                while x in range(len(self.file_dictionary[mod])):
                    file = metric.elidedText(self.file_dictionary[mod][x], Qt.TextElideMode.ElideLeft, 400)
                    item = QTableWidgetItem(file)
                    item.setToolTip(self.dependencies_dictionary[mod][x])
                    self.setItem(i, 0, item)
                    i += 1
                    x += 1

        self.resizeRowsToContents()

    def get_data_from_file(self, file):
        try:
            with open(file, 'r') as f:
                data = json.load(f)
        except:
            data = {}
        return data

    def context_menu(self, position):
        selected_item = self.item(self.rowAt(position.y()), 0)
        if selected_item:
            menu = QMenu(self)
            open_explorer_action = menu.addAction("Open in File Explorer")
            action = menu.exec(self.viewport().mapToGlobal(position))
            if action == open_explorer_action:
                self.open_in_explorer(selected_item)

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
        
