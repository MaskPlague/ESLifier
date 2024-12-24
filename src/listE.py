import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem, QPushButton


class ListEslify(QTableWidget):
    def __init__(self):
        super().__init__()
        #TODO: get modlist from file
        modList = ['C:\\mods\\Mod1','C:\\mods\\Mod2', 'C:\\mods\\Mod3', 'C:\\mods\\Mod4', 'C:\\mods\\Mod5']
        dependencyList = [['C:\\mods\\Mod1','C:\\mods\\Mod2', 'C:\\mods\\Mod3', 'C:\\mods\\Mod4', 'C:\\mods\\Mod5'],
                          ['C:\\mods\\Mod2','C:\\mods\\Mod3', 'C:\\mods\\Mod4', 'C:\\mods\\Mod5', 'C:\\mods\\Mod6', 'C:\\mods\\Mod2','C:\\mods\\Mod3', 'C:\\mods\\Mod4', 'C:\\mods\\Mod5', 'C:\\mods\\Mod6'],
                          ['C:\\mods\\Mod3','C:\\mods\\Mod4', 'C:\\mods\\Mod5', 'C:\\mods\\Mod6', 'C:\\mods\\Mod7'],
                          ['C:\\mods\\Mod4','C:\\mods\\Mod5', 'C:\\mods\\Mod6', 'C:\\mods\\Mod7', 'C:\\mods\\Mod8'],
                          ['C:\\mods\\Mod5','C:\\mods\\Mod6', 'C:\\mods\\Mod7', 'C:\\mods\\Mod8', 'C:\\mods\\Mod9']]
        cellFlags = [True, False, False, True, True]
        self.setRowCount(len(modList))
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(['Mod', 'CELL Records', 'Dependencies'])#TODO: Remove dependencies from this file
        self.setSortingEnabled(True)

        self.setStyleSheet("""
            QListWidget::item::selected{
                background-color: rgb(150,150,150);
            }
            QListWidget::item::hover{
                background-color: rgb(200,200,200);
            }
            QListWidget::indicator:checked{
                image: url(./images/checked.png)
            }
            QListWidget::indicator:unchecked{
                image: url(./images/unchecked.png)
            }
        """)

        def button():
            print("test")

        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        for i in range(len(modList)):
            item = QTableWidgetItem(os.path.basename(modList[i]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(modList[i])
            self.setItem(i, 0, item)
            if cellFlags[i]:
                itemC = QTableWidgetItem('Has CELL')
                self.setItem(i, 1, itemC)
            if len(dependencyList[i]) > 0:
                dL = QPushButton("Test")
                dL.clicked.connect(button)
                #itemD = QTableWidgetItem('')
                #self.setItem(i, 2, itemD)
                self.setCellWidget(i,2,dL) #TODO: remove this and depency stuff from this file, implement in listC
            


        def somethingChanged(itemChanged):
            self.blockSignals(True)
            if itemChanged.checkState() == Qt.CheckState.Checked:
                for x in self.selectedItems():
                    x.setCheckState(Qt.CheckState.Checked)
            else:
                for x in self.selectedItems():
                    x.setCheckState(Qt.CheckState.Unchecked)
            self.blockSignals(False)

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
        file_path = selectedItem.toolTip().replace('       - ','').replace('\nDouble click to show/hide dependencies.','')
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
        
