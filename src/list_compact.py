import os
import subprocess
import json

from PyQt6.QtCore import Qt, QItemSelection
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem, QPushButton, QButtonGroup, QListWidget, QListWidgetItem
from blacklist import blacklist

class list_compactable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(6)
        self.setHorizontalHeaderLabels(['*   Mod', 'CELL Records', 'SKSE DLL', 'Dependencies', '', 'Hider'])
        self.horizontalHeaderItem(0).setToolTip('This is the plugin name. Select which plugins you wish to compact.')
        self.horizontalHeaderItem(1).setToolTip('This is the CELL Record Flag. If an ESL plugin creates a new CELL\n'+
                                                'and another mod changes that CELL then it may not work due to an engine bug.\n'+
                                                'If an ESL plugin creates a new interior CELL then that cell may experience\n'+
                                                'issues when reloading a save without restarting the game.\n'+
                                                '"New  CELL" indicates the presence of a new CELL record.\n'+
                                                '"!New Interior CELL!" indicates that a new CELL is an interior.\n'+
                                                '"!!New CELL Changed!!" indicates that a new CELL record is changed by a dependent plugin.')
        self.horizontalHeaderItem(2).setToolTip('This is the skse DLL flag. If a dll has the plugin name in it then it may\n'+
                                                'have a LookUpForm() call that may break after compacting a flagged plugin.')
        self.horizontalHeaderItem(3).setToolTip('If a plugin has other plugins with it as a master, they will appear when\n'+
                                                'the button is clicked. These will also have their Form IDs patched to\n'+
                                                'reflect the Master plugin\'s changes.')
        self.setColumnHidden(5, True)
        self.horizontalHeader().sortIndicatorChanged.connect(self.hide_rows)
        self.verticalHeader().setHidden(True)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.setAutoScroll(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)
        self.mod_list = []
        self.has_new_cells = []
        self.has_interior_cells = []
        self.filter_changed_cells = True

        self.blacklist = blacklist()

        self.setStyleSheet("""
            QTableWidget::item{
                border-top: 1px solid gray;
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
        self.dependency_list = self.get_data_from_file("ESLifier_Data/dependency_dictionary.json")
        self.compacted = self.get_data_from_file("ESLifier_Data/compacted_and_patched.json")
        self.dll_dict = self.get_data_from_file("ESLifier_Data/dll_dict.json")
        blacklist = self.get_data_from_file('ESLifier_Data/blacklist.json')
        self.cell_changed = self.get_data_from_file("ESLifier_Data/cell_changed.json")
        if blacklist == {}:
            blacklist = []

        if self.filter_changed_cells:
            if self.cell_changed == {}:
                self.cell_changed = []
            blacklist.extend(self.cell_changed)

        to_remove = []
        for mod in self.mod_list:
            if os.path.basename(mod) in blacklist:
                to_remove.append(mod)
                
        for mod in to_remove:
            self.mod_list.remove(mod)

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
            basename = os.path.basename(self.mod_list[i])
            item = QTableWidgetItem(basename)
            if basename in self.compacted:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.PartiallyChecked)
            else:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(self.mod_list[i])
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
            self.setItem(i, 0, item)
            self.setRowHidden(i, False)
            if basename in self.has_new_cells:
                item_cell_flag = QTableWidgetItem('New CELL')
                item_cell_flag.setToolTip('This mod has a new CELL record and no mods currently modify it.\nIt is currently safe to ESL flag it.')
                if basename in self.cell_changed:
                    item_cell_flag.setText('!!New CELL Changed!!')
                    item_cell_flag.setToolTip('This mod has at least one new CELL record that is an interior cell.\n'+
                                              'ESL interior cells do not reload properly on save game load until\n'+
                                              'the game has restarted.')
                    item_cell_flag.setToolTip('This mod has a new CELL record\nand has a dependent plugin that modifies it.\nIt is NOT recommended to ESL flag it.')
                elif basename in self.has_interior_cells:
                    item_cell_flag.setText('!New Interior CELL!')
                    item_cell_flag.setToolTip('This mod has at least one new CELL record that is an interior cell.\n'+
                                              'ESL created interior cells sometimes do not reload properly on a save\n'+
                                              'game load, until the game itself has restarted.')
                item_cell_flag.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(i, 1, item_cell_flag)
            if basename.lower() in self.dll_dict:
                item_dll = QTableWidgetItem('!SKSE DLL!')
                tooltip = 'This mod\'s plugin name is present in the following SKSE dlls\nand may break them if a hard-coded form id is present:\n'
                for dll in self.dll_dict[basename.lower()]:
                    tooltip += '- ' + os.path.basename(dll)
                item_dll.setToolTip(tooltip)
                self.setItem(i, 2, item_dll)
            if self.dependency_list[basename.lower()] != []:
                dL = QPushButton("Show")
                dL.clicked.connect(lambda _, mod_key=basename.lower(): display_dependencies(mod_key))
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
            multi_check = True
            if len(self.selectedItems()) < 2:
                multi_check = False
            if multi_check:
                if item_changed.checkState() == Qt.CheckState.Checked:
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
        self.resizeColumnToContents(2)
        self.resizeColumnToContents(3)
        self.itemChanged.connect(somethingChanged)
        self.resizeRowsToContents()

    def hide_rows(self):
        for row in range(self.rowCount()):
            if self.item(row, 5):
                self.setRowHidden(row, True)
            else:
                self.setRowHidden(row, False)

    def get_data_from_file(self, file):
        try:
            with open(file, 'r') as f:
                data = json.load(f)
        except:
            data = {}
        return data

    def contextMenu(self, position):
        row = self.rowAt(position.y())
        col = self.columnAt(position.x())

        if col == 4 and self.cellWidget(row, 3) and self.cellWidget(row, 3).text() == 'Hide':
            list_widget = self.cellWidget(row, 4)
            selected_item = list_widget.itemAt(list_widget.mapFromGlobal(self.viewport().mapToGlobal(position)))
            if not selected_item:
                selected_item = self.item(row,0)
        else:
            selected_item = self.item(row, 0)

        if selected_item:
            menu = QMenu(self)
            select_all_action = menu.addAction("Select All")
            check_all_action = menu.addAction("Check All")
            uncheck_all_action = menu.addAction("Uncheck All")
            invert_selection_action = menu.addAction("Invert Selection Checks")
            open_explorer_action = menu.addAction("Open in File Explorer")
            add_to_blacklist_action = menu.addAction("Add Mod(s) to Blacklist")
            action = menu.exec(self.viewport().mapToGlobal(position))
            if action == open_explorer_action:
                self.open_in_explorer(selected_item)
            if action == check_all_action:
                self.check_all()
            if action == uncheck_all_action:
                self.uncheck_all()
            if action == select_all_action:
                self.select_all()
            if action == invert_selection_action:
                selected_items = self.selectedItems()
                self.invert_selection(selected_items)
            if action == add_to_blacklist_action:
                selected_items = self.selectedItems()
                self.add_to_blacklist(selected_items)

    def check_all(self):
        self.blockSignals(True)
        for i in range(self.rowCount()):
            if not self.isRowHidden(i) and self.item(i,0).checkState() == Qt.CheckState.Unchecked:
                self.item(i, 0).setCheckState(Qt.CheckState.Checked)
        self.blockSignals(False)

    def uncheck_all(self):
        self.blockSignals(True)
        for i in range(self.rowCount()):
            if self.item(i,0).checkState() == Qt.CheckState.Checked:
                self.item(i, 0).setCheckState(Qt.CheckState.Unchecked)
        self.blockSignals(False)
    
    def select_all(self):
        self.blockSignals(True)
        selection = QItemSelection()
        for row in range(self.rowCount()):
            if self.isRowHidden(row) == False:
                selection.select(self.model().index(row, 0), self.model().index(row, self.model().columnCount() - 1))
        selection_model = self.selectionModel()
        selection_model.select(selection, selection_model.SelectionFlag.ClearAndSelect)
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

    def add_to_blacklist(self, selected_items):
        mods = [item.text() for item in selected_items if item.column() == 0]
        self.blacklist.add_to_blacklist(mods)
        self.create()

        

