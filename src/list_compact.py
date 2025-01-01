import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem, QPushButton, QButtonGroup, QListWidget, QListWidgetItem

#TODO: add bsa_flag into table
class list_compactable(QTableWidget):
    def __init__(self):
        super().__init__()
        mod_list = ['C:\\mods\\Mod1','C:\\mods\\Mod2', 'C:\\mods\\Mod3', 'C:\\mods\\Mod4', 'C:\\mods\\Mod5']
        dependency_list = [['C:\\mods\\Mod1','C:\\mods\\Mod2', 'C:\\mods\\Mod3', 'C:\\mods\\Mod4', 'C:\\mods\\Mod5'],
                          ['C:\\mods\\Mod2','C:\\mods\\Mod3', 'C:\\mods\\Mod4', 'C:\\mods\\Mod5', 'C:\\mods\\Mod6', 'C:\\mods\\Mod2','C:\\mods\\Mod3', 'C:\\mods\\Mod4', 'C:\\mods\\Mod5', 'C:\\mods\\Mod6'],
                          ['C:\\mods\\Mod3','C:\\mods\\Mod4', 'C:\\mods\\Mod5', 'C:\\mods\\Mod6', 'C:\\mods\\Mod7'],
                          [],
                          ['C:\\mods\\Mod5','C:\\mods\\Mod6', 'C:\\mods\\Mod7', 'C:\\mods\\Mod8', 'C:\\mods\\Mod9']]
        cell_flags = [True, False, False, True, True]
        bsa_flag = [True, False, False, False, True]
        self.setRowCount(len(mod_list))
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(['*   Mod', 'CELL Records', 'Dependencies', ''])
        self.horizontalHeaderItem(0).setToolTip('This is the plugin name. Select which plugins you wish to compact.')
        self.horizontalHeaderItem(1).setToolTip('This is the CELL Record Flag. If an ESL plugin creates a new CELL\nand another mod changes that CELL then it\nmay not work due to an engine bug.')
        self.horizontalHeaderItem(2).setToolTip('If a plugin has other plugins with it as a master, they\nwill appear when the button is clicked. These will also have their\nForm IDs patched to reflect the Master plugin\'s changes.')
        self.verticalHeader().setHidden(True)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)

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

        self.button_group = QButtonGroup()

        def display_dependencies(modIndex):
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
                    border-bottom: 1px solid gray
                    }""")
                list_widget_dependency_list = QListWidget()
                for dependency in dependency_list[modIndex]:
                    item = QListWidgetItem(os.path.basename(dependency))
                    item.setToolTip(dependency)
                    list_widget_dependency_list.addItem(item)
                list_widget_dependency_list.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
                self.setCellWidget(index, 3, list_widget_dependency_list)
            self.resizeRowToContents(index)

        for i in range(len(mod_list)):
            item = QTableWidgetItem(os.path.basename(mod_list[i]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(mod_list[i])
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
            self.setItem(i, 0, item)
            if cell_flags[i]:
                item_compactible = QTableWidgetItem('New CELL')
                item_compactible.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(i, 1, item_compactible)
            if len(dependency_list[i]) > 0:
                dL = QPushButton("Show")
                dL.clicked.connect(lambda _, index=i: display_dependencies(index))
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

    def contextMenu(self, position):
        selectedItem = self.itemAt(position)
        if selectedItem:
            menu = QMenu(self)
            open_explorer_action = menu.addAction("Open in File Explorer")
            action = menu.exec(self.viewport().mapToGlobal(position))
            if action == open_explorer_action:
                self.open_in_explorer(selectedItem)

    def open_in_explorer(self, selected_item):
        file_path = selected_item.toolTip()#.replace('       - ','').replace('\nDouble click to show/hide dependencies.','')
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

