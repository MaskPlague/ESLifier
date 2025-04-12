import os
import subprocess
import json

from PyQt6.QtCore import Qt, QItemSelection
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem, QPushButton, QButtonGroup, QListWidget, QListWidgetItem
from blacklist import blacklist

class list_compactable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.COL_COUNT = 8
        self.MOD_COL = 0
        self.CELL_COL = 1
        self.WRLD_COL = 2
        self.SKSE_COL = 3
        self.ESM_COL = 4
        self.DEP_COL = 5
        self.DEP_DISP_COL = 6
        self.HIDER_COL = 7
        self.setColumnCount(self.COL_COUNT)
        self.setHorizontalHeaderLabels(['*   Mod', 'CELL Records', 'WRLD Records', 'SKSE DLL', 'ESM', 'Dependencies', '', 'Hider'])
        self.horizontalHeaderItem(self.MOD_COL).setToolTip('This is the plugin name. Select which plugins you wish to compact.')
        self.horizontalHeaderItem(self.CELL_COL).setToolTip('This is the CELL Record Flag. If an ESM+ESL plugin creates a new CELL\n'+
                                                'and another mod changes that CELL then it may not work due to an engine bug.\n'+
                                                'If an ESL plugin creates a new interior CELL then that cell may experience\n'+
                                                'issues when reloading a save without restarting the game.\n'+
                                                '"New  CELL" indicates the presence of a new CELL record.\n'+
                                                '"!New Interior CELL!" indicates that a new CELL is an interior.\n'+
                                                '"!!New CELL Changed!!" indicates that a new CELL record from an ESM is changed by a dependent plugin.')
        self.horizontalHeaderItem(self.WRLD_COL).setToolTip('This is the WRLD Record Flag. If an plugin is flagged ESL\n'+
                                                       'then the new worldspace may have landscape issues (no ground).')
        self.horizontalHeaderItem(self.SKSE_COL).setToolTip('This is the skse DLL flag. If a dll has the plugin name in it then it may\n'+
                                                'have a LookUpForm() call that may break after compacting a flagged plugin.')
        self.horizontalHeaderItem(self.ESM_COL).setToolTip('This is the ESM flag. If a plugin is an ESM then it will be flagged here.')
        self.horizontalHeaderItem(self.DEP_COL).setToolTip('If a plugin has other plugins with it as a master, they will appear when\n'+
                                                'the button is clicked. These will also have their Form IDs patched to\n'+
                                                'reflect the Master plugin\'s changes.')
        self.setColumnHidden(self.HIDER_COL, True)
        self.horizontalHeader().sortIndicatorChanged.connect(self.hide_rows)
        self.verticalHeader().setHidden(True)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAutoScroll(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)
        self.flag_dict = {}
        self.show_cells = True
        self.show_dlls = True
        self.show_esms = True
        self.filter_changed_cells = True
        self.filter_interior_cells = False
        self.filter_worldspaces = False
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
        self.setSortingEnabled(False)
        self.clearContents()
        if not self.show_cells: 
            self.hideColumn(self.CELL_COL)
        else:
            self.showColumn(self.CELL_COL)
        if not self.show_dlls:
            self.hideColumn(self.SKSE_COL)
        else:
            self.showColumn(self.SKSE_COL)
        if self.filter_worldspaces: 
            self.hideColumn(self.WRLD_COL)
        else:
            self.showColumn(self.WRLD_COL)
        if not self.show_esms:
            self.hideColumn(self.ESM_COL)
        else:
            self.showColumn(self.ESM_COL)
        self.dependency_list = self.get_data_from_file("ESLifier_Data/dependency_dictionary.json")
        self.compacted = self.get_data_from_file("ESLifier_Data/compacted_and_patched.json")
        self.dll_dict = self.get_data_from_file("ESLifier_Data/dll_dict.json")
        blacklist = self.get_data_from_file('ESLifier_Data/blacklist.json')
        self.cell_changed = self.get_data_from_file("ESLifier_Data/cell_changed.json")
        if blacklist == {}:
            blacklist = []

        to_remove = []
        for mod in self.flag_dict:
            if os.path.basename(mod) in blacklist:
                to_remove.append(mod)
        
        for mod in to_remove:
            self.flag_dict.pop(mod)

        self.setRowCount(len(self.flag_dict))
        self.button_group = QButtonGroup()

        def display_dependencies(mod_key):
            index = self.currentRow()
            if self.cellWidget(index, self.DEP_DISP_COL):
                self.item(index, self.MOD_COL).setTextAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
                if self.item(index, self.CELL_COL):
                    self.item(index, self.CELL_COL).setTextAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignVCenter)
                if self.item(index, self.WRLD_COL):
                    self.item(index, self.WRLD_COL).setTextAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignVCenter)
                self.sender().setText('Show')
                self.sender().setStyleSheet("""
                    QPushButton{
                        padding: 0px, 0px, 20px, 0px;
                        background-color: transparent;
                        border: none;
                    }""")
                self.removeCellWidget(index, self.DEP_DISP_COL)
            else:
                self.item(index, self.MOD_COL).setTextAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
                if self.item(index, self.CELL_COL):
                    self.item(index, self.CELL_COL).setTextAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop)
                if self.item(index, self.WRLD_COL):
                    self.item(index, self.WRLD_COL).setTextAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop)
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
                count = 0
                cumulative_tooltip = ''
                for dependency in self.dependency_list[mod_key]:
                    count += 1
                    if count <= 15:
                        item = QListWidgetItem(os.path.basename(dependency))
                        item.setToolTip(dependency)
                        list_widget_dependency_list.addItem(item)
                    else:
                        cumulative_tooltip += os.path.basename(dependency) + '\n'
                if count > 15:
                    item = QListWidgetItem(f'+{count-15} more...')
                    item.setToolTip(cumulative_tooltip.strip())
                    list_widget_dependency_list.addItem(item)
                list_widget_dependency_list.setSizeAdjustPolicy(QTableWidget.SizeAdjustPolicy.AdjustToContents)
                self.setCellWidget(index, self.DEP_DISP_COL, list_widget_dependency_list)
            self.resizeRowToContents(index)

        for i, (plugin, flags) in enumerate(self.flag_dict.items()):
            basename = os.path.basename(plugin)
            item = QTableWidgetItem(basename)
            if basename in self.compacted:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.PartiallyChecked)
            else:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(plugin)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
            self.setItem(i, self.MOD_COL, item)
            self.setRowHidden(i, False)
            hide_row = False
            if 'new_cell' in flags:
                item_cell_flag = QTableWidgetItem('New CELL')
                item_cell_flag.setToolTip('This mod has a new CELL record and no mods currently modify it.\n'+
                                          'It is currently safe to ESL flag it.')
                if not self.show_cells:
                    hide_row = True
                if basename in self.cell_changed:
                    item_cell_flag.setText('!!New CELL Changed!!')
                    item_cell_flag.setToolTip('This mod is an ESM with a new CELL record that is modified by\n'+
                                              'a dependent plugin. It is NOT recommended to ESL flag it as doing so\n'+
                                              'may break temporary child references in the new CELL.')
                    if self.filter_changed_cells:
                        hide_row = True
                elif 'new_interior_cell' in flags:
                    item_cell_flag.setText('!New Interior CELL!')
                    item_cell_flag.setToolTip('This mod has at least one new CELL record that is an interior cell.\n'+
                                              'ESL created interior cells sometimes do not reload properly on a save\n'+
                                              'game load, until the game itself has restarted.')
                    if self.filter_interior_cells:
                        hide_row = True
                item_cell_flag.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(i, self.CELL_COL, item_cell_flag)
            if 'new_wrld' in flags:
                item_wrld_flag = QTableWidgetItem('!!New WRLD!!')
                item_wrld_flag.setToolTip('This mod has a new WRLD (worldspace) record which may lose landscape (the ground) when ESL flagged.')
                if self.filter_worldspaces:
                    hide_row = True
                self.setItem(i, self.WRLD_COL, item_wrld_flag)
            if basename.lower() in self.dll_dict:
                item_dll = QTableWidgetItem('!!SKSE DLL!!')
                tooltip = 'This mod\'s plugin name is present in the following SKSE dlls and\nmay break their FormLookup() function calls if a hard-coded form id is present:'
                for dll in self.dll_dict[basename.lower()]:
                    tooltip += '\n- ' + os.path.basename(dll)
                item_dll.setToolTip(tooltip)
                if not self.show_dlls:
                    hide_row = True
                self.setItem(i, self.SKSE_COL, item_dll)
            if 'is_esm' in flags:
                item_esm_flag = QTableWidgetItem('ESM')
                item_esm_flag.setToolTip('This mod is an ESM.')
                if not self.show_esms:
                    hide_row = True
                self.setItem(i, self.ESM_COL, item_esm_flag)
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
                item_hidden = QTableWidgetItem('')
                self.setCellWidget(i, self.DEP_COL,dL)
                self.setItem(i, self.DEP_COL,item_hidden)

            if hide_row:
                self.setItem(i, self.HIDER_COL, QTableWidgetItem('hide me'))

        def somethingChanged(item_changed):
            self.blockSignals(True)
            multi_check = True
            if len(self.selectedItems()) < 2:
                multi_check = False
            if multi_check:
                if item_changed.checkState() == Qt.CheckState.Checked:
                    for x in self.selectedItems():
                        if x.column() == self.MOD_COL:
                            x.setCheckState(Qt.CheckState.Checked)
                else:
                    for x in self.selectedItems():
                        if x.column() == self.MOD_COL:
                            x.setCheckState(Qt.CheckState.Unchecked)
            self.blockSignals(False)

        self.hide_rows()
        self.resizeColumnsToContents()
        self.itemChanged.connect(somethingChanged)
        self.resizeRowsToContents()
        self.setSortingEnabled(True)

    def hide_rows(self):
        for row in range(self.rowCount()):
            if self.item(row, self.HIDER_COL):
                self.setRowHidden(row, True)
            else:
                self.setRowHidden(row, False)

    def get_data_from_file(self, file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
        return data

    def contextMenu(self, position):
        row = self.rowAt(position.y())
        col = self.columnAt(position.x())

        if col == self.DEP_DISP_COL and self.cellWidget(row, self.DEP_COL) and self.cellWidget(row, self.DEP_COL).text() == 'Hide':
            list_widget = self.cellWidget(row, self.DEP_DISP_COL)
            selected_item = list_widget.itemAt(list_widget.mapFromGlobal(self.viewport().mapToGlobal(position)))
            if not selected_item:
                selected_item = self.item(row, self.MOD_COL)
        else:
            selected_item = self.item(row, self.MOD_COL)

        if selected_item:
            menu = QMenu(self)
            select_all_action = menu.addAction("Select All")
            check_all_action = menu.addAction("Check All")
            uncheck_all_action = menu.addAction("Uncheck All")
            invert_selection_action = menu.addAction("Invert Selection Checks")
            check_previously_compacted_action = menu.addAction("Check Previously Compacted")
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
            if action == check_previously_compacted_action:
                self.check_previously_compacted()
            if action == invert_selection_action:
                selected_items = self.selectedItems()
                self.invert_selection(selected_items)
            if action == add_to_blacklist_action:
                selected_items = self.selectedItems()
                self.add_to_blacklist(selected_items)

    def check_all(self):
        self.blockSignals(True)
        for i in range(self.rowCount()):
            if not self.isRowHidden(i) and self.item(i,self.MOD_COL).checkState() == Qt.CheckState.Unchecked:
                self.item(i, self.MOD_COL).setCheckState(Qt.CheckState.Checked)
        self.blockSignals(False)

    def uncheck_all(self):
        self.blockSignals(True)
        for i in range(self.rowCount()):
            if self.item(i,self.MOD_COL).checkState() == Qt.CheckState.Checked:
                self.item(i, self.MOD_COL).setCheckState(Qt.CheckState.Unchecked)
        self.blockSignals(False)
    
    def select_all(self):
        self.blockSignals(True)
        selection = QItemSelection()
        for row in range(self.rowCount()):
            if self.isRowHidden(row) == False:
                selection.select(self.model().index(row, self.MOD_COL), self.model().index(row, self.model().columnCount() - 1))
        selection_model = self.selectionModel()
        selection_model.select(selection, selection_model.SelectionFlag.ClearAndSelect)
        self.blockSignals(False)

    def check_previously_compacted(self):
        self.blockSignals(True)
        if os.path.exists('ESLifier_Data/previously_compacted.json'):
            try:
                with open('ESLifier_Data/previously_compacted.json', 'r', encoding='utf-8') as f:
                    previously_compacted = json.load(f)
                    f.close()
                for row in range(self.rowCount()):
                    if self.isRowHidden(row) == False and self.item(row, self.MOD_COL).checkState() == Qt.CheckState.Unchecked and self.item(row, self.MOD_COL).text() in previously_compacted:
                        self.item(row, self.MOD_COL).setCheckState(Qt.CheckState.Checked)
            except Exception as e:
                print('!Error: Failed to get previously_compacted.json')
                print(e)

        self.blockSignals(False)
    
    def invert_selection(self, selected_items):
        self.blockSignals(True)
        for item in selected_items:
            if item.checkState() == Qt.CheckState.Checked:
                if item.column() == self.MOD_COL:
                    item.setCheckState(Qt.CheckState.Unchecked)
            elif item.checkState() == Qt.CheckState.Unchecked:
                if item.column() == self.MOD_COL:
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
