import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor, QAction
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem
class ListCompactable(QListWidget):
    def __init__(self):
        super().__init__()
        modList = ['C:\\mods\\Mod1','C:\\mods\\Mod2', 'C:\\mods\\Mod3', 'C:\\mods\\Mod4', 'C:\\mods\\Mod5']
        dependencyList = [['C:\\mods\\Mod1','C:\\mods\\Mod2', 'C:\\mods\\Mod3', 'C:\\mods\\Mod4', 'C:\\mods\\Mod5'],
                          ['C:\\mods\\Mod2','C:\\mods\\Mod3', 'C:\\mods\\Mod4', 'C:\\mods\\Mod5', 'C:\\mods\\Mod6', 'C:\\mods\\Mod2','C:\\mods\\Mod3', 'C:\\mods\\Mod4', 'C:\\mods\\Mod5', 'C:\\mods\\Mod6'],
                          ['C:\\mods\\Mod3','C:\\mods\\Mod4', 'C:\\mods\\Mod5', 'C:\\mods\\Mod6', 'C:\\mods\\Mod7'],
                          ['C:\\mods\\Mod4','C:\\mods\\Mod5', 'C:\\mods\\Mod6', 'C:\\mods\\Mod7', 'C:\\mods\\Mod8'],
                          ['C:\\mods\\Mod5','C:\\mods\\Mod6', 'C:\\mods\\Mod7', 'C:\\mods\\Mod8', 'C:\\mods\\Mod9']]
        cellFlags = [True, False, False, True, True]
        
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

        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for i in range(len(modList)):
            item = QListWidgetItem(os.path.basename(modList[i]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(modList[i] + '\nDouble click to show/hide dependencies.')

            dependencies = QListWidget()
            dependencies.addItem("      Dependencies:")
            for dependency in dependencyList[i]:
                dItem = QListWidgetItem('       - '+os.path.basename(dependency))
                dItem.setFlags(dItem.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                dItem.setToolTip(dependency)
                dependencies.addItem(dItem)

            self.addItem(item)

            widgetHider = QListWidgetItem()
            widgetHider.setSizeHint(dependencies.sizeHint())
            widgetHider.setFlags(widgetHider.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.addItem(widgetHider)
            self.setItemWidget(widgetHider, dependencies)
        
        for i in range(self.count()):
            if i % 2 != 0:
                self.item(i).setHidden(True)

        def displayDependencies(itemClicked):
            if self.item(self.indexFromItem(itemClicked).row()+1).isHidden():
                self.item(self.indexFromItem(itemClicked).row()+1).setHidden(False)
            else:
                self.item(self.indexFromItem(itemClicked).row()+1).setHidden(True)


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
        self.itemDoubleClicked.connect(displayDependencies)
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

