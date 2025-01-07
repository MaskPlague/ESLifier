import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem

class list_unpatched(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels(['Files'])
        self.horizontalHeaderItem(0).setToolTip('These are the unpatched files.')
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.file_list = []
        self.cell_flags = []

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

        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.horizontalHeader().setStretchLastSection(True)
        
        self.create()

    def create(self):
        self.file_list = ['C:\\mods\\Mod1','C:\\mods\\Mod2', 'C:\\mods\\Mod3', 'C:\\mods\\Mod4', 'C:\\mods\\Mod5']
        self.setRowCount(len(self.file_list))

        for i in range(len(self.file_list)):
            item = QTableWidgetItem(os.path.basename(self.file_list[i]))
            #item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            #item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(self.file_list[i])
            self.setItem(i, 0, item)
            self.resizeRowToContents(i)

        def somethingChanged(itemChanged):
            self.blockSignals(True)
            if itemChanged.checkState() == Qt.CheckState.Checked:
                for x in self.selectedItems():
                    x.setCheckState(Qt.CheckState.Checked)
            else:
                for x in self.selectedItems():
                    x.setCheckState(Qt.CheckState.Unchecked)
            self.blockSignals(False)

        self.resizeColumnsToContents()
        self.itemChanged.connect(somethingChanged)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)


    def contextMenu(self, position):
        selectedItem = self.itemAt(position)
        if selectedItem:
            menu = QMenu(self)
            open_explorer_action = menu.addAction("Open in File Explorer")
            action = menu.exec(self.viewport().mapToGlobal(position))
            if action == open_explorer_action:
                self.open_in_explorer(selectedItem)

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
        
