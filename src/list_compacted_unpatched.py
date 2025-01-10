import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem

class list_compacted_unpatched(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels(['Mod'])
        self.horizontalHeaderItem(0).setToolTip('These are plugins which this program has compacted.\nTick the plugin for which you want to patch new files.\nSelect for which plugin you want to show the unpatched files.')
        self.verticalHeader().setHidden(True)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.mod_list = []

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
        
        self.create()

    def create(self):
        self.clearContents()
        self.setRowCount(len(self.mod_list))

        for i in range(len(self.mod_list)):
            item = QTableWidgetItem(os.path.basename(self.mod_list[i]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(self.mod_list[i])
            self.setItem(i, 0, item)

        def something_changed(itemChanged):
            self.blockSignals(True)
            if itemChanged.checkState() == Qt.CheckState.Checked:
                for x in self.selectedItems():
                    x.setCheckState(Qt.CheckState.Checked)
            else:
                for x in self.selectedItems():
                    x.setCheckState(Qt.CheckState.Unchecked)
            self.blockSignals(False)

        def item_selected():
            selected_items = self.selectedItems()
            mods_selected = [item.toolTip() for item in selected_items]
            self.parentWidget().parentWidget().parentWidget().unpatched_files_list.mods_selected = mods_selected
            self.parentWidget().parentWidget().parentWidget().unpatched_files_list.create()


        self.resizeColumnsToContents()
        self.itemChanged.connect(something_changed)
        self.itemSelectionChanged.connect(item_selected)
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
