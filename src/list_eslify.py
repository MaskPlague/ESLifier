import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem

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
        self.mod_list = []
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
            QTableWidget::indicator:checked{
                image: url(./images/checked.png);
            }
            QTableWidget::indicator:unchecked{
                image: url(./images/unchecked.png);
            }
        """)

        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.create()

    def create(self):
        self.setRowCount(len(self.mod_list))

        for i in range(len(self.mod_list)):
            item = QTableWidgetItem(os.path.basename(self.mod_list[i]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(self.mod_list[i])
            self.setItem(i, 0, item)
            if self.cell_flags[i]:
                item_cell_flag = QTableWidgetItem('New CELL')
                self.setItem(i, 1, item_cell_flag)

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
        self.resizeRowsToContents()


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
        
