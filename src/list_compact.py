import os
import subprocess
import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem, QPushButton, QButtonGroup, QListWidget, QListWidgetItem

class list_compactable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(['*   Mod', 'CELL Records', 'BSA', 'Dependencies', ''])
        self.horizontalHeaderItem(0).setToolTip('This is the plugin name. Select which plugins you wish to compact.')
        self.horizontalHeaderItem(1).setToolTip('This is the CELL Record Flag. If an ESL plugin creates a new CELL\nand another mod changes that CELL then it\nmay not work due to an engine bug.')
        self.horizontalHeaderItem(2).setToolTip('This is the BSA Flag. If a Bethesda Archive holds files that need\npatching, this program will not be able to detect or patch them.')
        self.horizontalHeaderItem(3).setToolTip('If a plugin has other plugins with it as a master, they will appear\nwhen the button is clicked. These will also have their\nForm IDs patched to reflect the Master plugin\'s changes.')
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
        self.clearContents()
        self.dependency_list = self.get_data_from_file("ESLifier_Data/dependency_dictionary.json")
        
        self.setRowCount(len(self.mod_list))
    
        self.button_group = QButtonGroup()

        def display_dependencies(mod_key):
            index = self.currentRow()
            if self.cellWidget(index, 4):
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
                self.removeCellWidget(index, 4)
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
                self.setCellWidget(index, 4, list_widget_dependency_list)
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
            name, _ = os.path.splitext(os.path.basename(self.mod_list[i]).lower())
            if 'BSA_list' in self.dependency_list.keys() and any(name in bsa for bsa in self.dependency_list['BSA_list']):
                item_bsa = QTableWidgetItem('BSA')
                item_bsa.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(i,2, item_bsa)
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
                self.setCellWidget(i,3,dL)

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
        self.resizeRowsToContents()

    def get_data_from_file(self, file):
        try:
            with open(file, 'r') as f:
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


