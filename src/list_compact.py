import os
import subprocess
import json
import itertools
from PyQt6.QtCore import Qt, QItemSelection
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem, QPushButton, QButtonGroup, QListWidget, QListWidgetItem
from blacklist import blacklist

class list_compactable(QTableWidget):
    def __init__(self):
        super().__init__()
        c = itertools.count()
        self.MOD_COL = next(c)
        self.CELL_COL = next(c)
        self.WRLD_COL = next(c)
        self.WTHR_COL = next(c)
        self.SKSE_COL = next(c)
        self.ESM_COL = next(c)
        self.DEP_COL = next(c)
        self.DEP_DISP_COL = next(c)
        self.HIDER_COL = next(c)
        self.COL_COUNT = next(c)
        self.setColumnCount(self.COL_COUNT)
        self.setHorizontalHeaderLabels(['*   Mod', 'CELL Records', 'WRLD Records', 'WTHR Records', 'SKSE DLL', 'ESM', 'Dependencies', '', 'Hider'])
        self.horizontalHeaderItem(self.MOD_COL).setToolTip('This is the plugin name. Select which plugins you wish to compact.')
        self.horizontalHeaderItem(self.CELL_COL).setToolTip('This is the CELL Record Flag. It can be completely ignored for users\n'+
                                                            'with SSE Engine Fixes v7+ on Skyrim 1.6.1170+.\n'+
                                                            'Otherwise, if an ESM+ESL plugin creates a new CELL and another mod\n'+
                                                            'changes that CELL then it may not work due to an engine bug. If an\n'+
                                                            'ESL plugin creates a new interior CELL then that cell may experience\n'+
                                                            'issues when reloading a save without restarting the game.\n'+
                                                            '"New  CELL" indicates the presence of a new CELL record.\n'+
                                                            '"!New Interior CELL!" indicates that a new CELL is an interior.\n'+
                                                            '"!!New CELL Changed!!" indicates that a new CELL record from an ESM is changed\n'+
                                                            'by a dependent plugin.\n'+
                                                            '"!!Maxed Masters!!" indicates that a plugin or its dependent plugins\n'+
                                                            'have the maximum amount of masters (254) and cannot add ESLifier_Cell_Master.esm\n'+
                                                            'as a master for the ESL+ESM cell bug and ESL worldspace bug workarounds.')
        self.horizontalHeaderItem(self.WRLD_COL).setToolTip('This is the WRLD Record Flag. It can be completely ignored for users\n'+
                                                            'with SSE Engine Fixes v7+ on Skyrim 1.6.1170+.\n'+
                                                            'Otherwise, if an plugin is flagged ESL\n'+
                                                            'then the new worldspace may have landscape issues (no ground).')
        self.horizontalHeaderItem(self.WTHR_COL).setToolTip('This is the WTHR Record Flag. This is an indicator if a mod has a new weather record\n'+
                                                            'Some mods weathers are referenced in ENB Presets which cannot be patched by ESLifier\n'+
                                                            'It is at the user\'s discretion if a plugin with new weather should be compacted.')
        self.horizontalHeaderItem(self.SKSE_COL).setToolTip('This is the skse DLL flag. If a dll has the plugin name in it then it may\n'+
                                                            'have a LookUpForm() call that may break after compacting a flagged plugin.')
        self.horizontalHeaderItem(self.ESM_COL).setToolTip('This is the ESM flag. If a plugin is an ESM then it will be flagged here.')
        self.horizontalHeaderItem(self.DEP_COL).setToolTip('If a plugin has other plugins with it as a master, they will appear when\n'+
                                                            'the button is clicked. These will also have their Form IDs automatically\n'+
                                                            'patched to reflect the Master plugin\'s changes.')
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
        self.storedSelection = QItemSelection()
        self.flag_dict = {}
        self.show_cells = True
        self.show_dlls = True
        self.show_esms = True
        self.filter_changed_cells = True
        self.filter_interior_cells = False
        self.filter_worldspaces = False
        self.filter_weather = False
        self.cell_master = False
        self.hidden_columns = ""
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
        hidden_columns = [col.strip().upper() for col in self.hidden_columns.split(',')]

        if self.show_cells and not "CELL" in hidden_columns: self.showColumn(self.CELL_COL)
        else: self.hideColumn(self.CELL_COL)

        if not self.show_dlls: self.hideColumn(self.SKSE_COL)
        else: self.showColumn(self.SKSE_COL)

        if self.filter_worldspaces or self.cell_master or 'WRLD' in hidden_columns: self.hideColumn(self.WRLD_COL) 
        else: self.showColumn(self.WRLD_COL)

        if self.filter_weather or "WTHR" in hidden_columns: self.hideColumn(self.WTHR_COL)
        else: self.showColumn(self.WTHR_COL)

        if self.show_esms and not "ESM" in hidden_columns: self.showColumn(self.ESM_COL)
        else: self.hideColumn(self.ESM_COL)

        if 'DEPENDENTS' in hidden_columns: self.hideColumn(self.DEP_COL), self.hideColumn(self.DEP_DISP_COL)
        else: self.showColumn(self.DEP_COL), self.showColumn(self.DEP_DISP_COL)


        self.dependency_list:dict = self.get_data_from_file("ESLifier_Data/dependency_dictionary.json", dict)
        self.compacted:dict = self.get_data_from_file("ESLifier_Data/compacted_and_patched.json", dict)
        self.dll_dict:dict = self.get_data_from_file("ESLifier_Data/dll_dict.json", dict)
        self.blacklist_list: list[str] = self.get_data_from_file('ESLifier_Data/blacklist.json', list)
        self.cell_changed:list[str] = self.get_data_from_file("ESLifier_Data/cell_changed.json", list)

        if self.cell_master:
            self.blacklist_list.extend(["ccafdsse001-dwesanctuary.esm",
                                        "ccbgssse025-advdsgs.esm",
                                        "ccbgssse031-advcyrus.esm",
                                        "cceejsse001-hstead.esm",
                                        "cceejsse005-cave.esm"])

        local_dict = self.flag_dict.copy()
        for mod in self.flag_dict:
            if os.path.basename(mod) in self.blacklist_list:
                local_dict.pop(mod)

        self.setRowCount(len(local_dict))

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

        for i, (plugin, flags) in enumerate(local_dict.items()):
            basename:str = os.path.basename(plugin)
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
                if not self.cell_master:
                    item_cell_flag.setToolTip('This mod has a new CELL record and no mods currently modify it.\n'+
                                            'It is currently safe to ESL flag it.')
                else:
                    item_cell_flag.setToolTip('This mod has a new CELL record. It is currently safe to ESL flag it')
                if not self.show_cells:
                    hide_row = True
                if basename in self.cell_changed and not self.cell_master:
                    item_cell_flag.setText('!!New CELL Changed!!')
                    item_cell_flag.setToolTip('This mod is an ESM with a new CELL record that is modified by\n'+
                                              'a dependent plugin. It is NOT recommended to ESL flag it as doing so\n'+
                                              'will break temporary references in the new CELL.')
                    if self.filter_changed_cells:
                        hide_row = True
                elif self.cell_master and 'maxed_masters' in flags and basename in self.cell_changed:
                    item_cell_flag.setText('!!Maxed Masters!!')
                    item_cell_flag.setToolTip('This mod is an ESM with a new CELL record that is modified by\n'+
                                              'a dependent plugin. It or one of its dependents has the max of\n'+
                                              '254 masters and cannot have the ESLifier_Cell_Master.esm plugin\n'+
                                              'added as a master and thus the ESM + ESL cell bug workaround cannot\n'+
                                              'be applied. It is NOT recommended to ESL flag it as doing so may\n'+
                                              'break temporary references in its new CELL(s).')
                    self.showColumn(self.CELL_COL)
                elif 'new_interior_cell' in flags:
                    item_cell_flag.setText('!New Interior CELL!')
                    item_cell_flag.setToolTip('This mod has at least one new CELL record that is an interior cell.\n'+
                                              'ESL interior cells do not reload gameplay changed references properly\n'+
                                              'on a save game load unless the game itself has restarted.')
                    if self.filter_interior_cells:
                        hide_row = True
                item_cell_flag.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(i, self.CELL_COL, item_cell_flag)
            if 'new_wrld' in flags and not self.cell_master:
                item_wrld_flag = QTableWidgetItem('!!New WRLD!!')
                item_wrld_flag.setToolTip('This mod has a new WRLD (worldspace) record which may lose landscape (the ground) when ESL flagged.')
                if self.filter_worldspaces:
                    hide_row = True
                self.setItem(i, self.WRLD_COL, item_wrld_flag)
            if 'new_wthr' in flags:
                item_wthr_flag = QTableWidgetItem('!New WTHR!')
                item_wthr_flag.setToolTip('This mod has a new WTHR (weather) record which can be referenced in\n'+
                                          'ENB presets which are not patched.')
                if self.filter_weather:
                    hide_row = True
                self.setItem(i, self.WTHR_COL, item_wthr_flag)
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
                item_hidden = QTableWidgetItem('')
                self.setCellWidget(i, self.DEP_COL, dL)
                self.setItem(i, self.DEP_COL,item_hidden)
            if hide_row:
                self.setItem(i, self.HIDER_COL, QTableWidgetItem('hide me'))

        def somethingChanged(item_changed):
            self.blockSignals(True)
            if item_changed in self.selectedItems():
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

    def get_data_from_file(self, file, data_type):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = data_type()
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
            add_to_blacklist_action = menu.addAction("Add Highlighted Mod(s) to Blacklist")
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
