import os
import subprocess
import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem, QPushButton, QButtonGroup, QListWidget, QListWidgetItem

#TODO: add bsa_flag into table
class list_compactable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(['*   Mod', 'CELL Records', 'Dependencies', ''])
        self.horizontalHeaderItem(0).setToolTip('This is the plugin name. Select which plugins you wish to compact.')
        self.horizontalHeaderItem(1).setToolTip('This is the CELL Record Flag. If an ESL plugin creates a new CELL\nand another mod changes that CELL then it\nmay not work due to an engine bug.')
        self.horizontalHeaderItem(2).setToolTip('If a plugin has other plugins with it as a master, they\nwill appear when the button is clicked. These will also have their\nForm IDs patched to reflect the Master plugin\'s changes.')
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
                image: url(./images/checked.png)
            }
            QTableWidget::indicator:unchecked{
                image: url(./images/unchecked.png)
            }
        """)

        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)

        self.create()

    def create(self):
        self.dependency_list = self.get_dependency_list_from_file()
        self.bsa_flags = [True, False, False, False, True]
        self.setRowCount(len(self.mod_list))
    
        self.button_group = QButtonGroup()

        def display_dependencies(mod_key):
            index = self.currentRow()
            if self.cellWidget(index, 3):
                self.item(index, 0).setTextAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
                if self.item(index, 1):
                    self.item(index, 1).setTextAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignVCenter)
                self.sender().setText('Show')
                self.sender().setStyleSheet("""
                    QPushButton{
                        padding: 0px, 0px, 20px, 0px;
                        background-color: transparent;
                        border: none;
                    }""")
                self.removeCellWidget(index, 3)
            else:
                self.item(index, 0).setTextAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
                if self.item(index, 1):
                    self.item(index, 1).setTextAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop)
                self.sender().setText('Hide')
                self.sender().setStyleSheet("""
                    QPushButton{
                        padding: 0px, 0px, 20px, 0px;
                        background-color: transparent;
                        border: none;
                        border-bottom: 1px solid gray;
                        border-radius: none;
                    }""")
                list_widget_dependency_list = QListWidget()
                for dependency in self.dependency_list[mod_key]:
                    item = QListWidgetItem(os.path.basename(dependency))
                    item.setToolTip(dependency)
                    list_widget_dependency_list.addItem(item)
                list_widget_dependency_list.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
                self.setCellWidget(index, 3, list_widget_dependency_list)
            self.resizeRowToContents(index)

        for i in range(len(self.mod_list)):
            item = QTableWidgetItem(os.path.basename(self.mod_list[i]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(self.mod_list[i])
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
            self.setItem(i, 0, item)
            if self.cell_flags[i]:
                item_compactible = QTableWidgetItem('New CELL')
                item_compactible.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(i, 1, item_compactible)
            if self.dependency_list[os.path.basename(self.mod_list[i]).lower()] != []:
                dL = QPushButton("Show")
                dL.clicked.connect(lambda _, mod_key=os.path.basename(self.mod_list[i]).lower(): display_dependencies(mod_key))
                dL.setMaximumSize(90,22)
                dL.setMinimumSize(90,22)
                dL.setStyleSheet("""
                    QPushButton{
                    padding: 0px, 0px, 20px, 0px;
                    background-color: transparent;
                    border: none;
                    }""")
                self.button_group.addButton(dL)
                self.setCellWidget(i,2,dL)
            self.resizeRowToContents(i)

        def somethingChanged(item_changed):
            self.blockSignals(True)
            if item_changed.checkState() == Qt.CheckState.Checked:
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

    def get_dependency_list_from_file(self):
        try:
            with open("ESLifier_Data/dependency_dictionary.json", 'r') as f:
                data = json.load(f)
        except:
            data = {}
        return data

    def contextMenu(self, position):
        selectedItem = self.itemAt(position)
        if selectedItem:
            menu = QMenu(self)
            open_explorer_action = menu.addAction("Open in File Explorer")
            action = menu.exec(self.viewport().mapToGlobal(position))
            if action == open_explorer_action:
                self.open_in_explorer(selectedItem)

    def open_in_explorer(self, selected_item):
        file_path = selected_item.toolTip()
        if file_path:
            try:
                if os.name == 'nt':
                    os.startfile(file_path)
                elif os.name == 'posix':
                    subprocess.Popen(['xdg-open', os.path.dirname(file_path)])
                else:
                    subprocess.Popen(['open', os.path.dirname(file_path)])
            except Exception as e:
                print(f"Error opening file explorer: {e}")


