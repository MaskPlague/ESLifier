import os
import subprocess
import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem, QPushButton, QButtonGroup, QListWidget, QListWidgetItem
from blacklist import blacklist

class list_compactable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(['*   Mod', 'CELL Records', 'BSA', 'Dependencies', ''])
        self.horizontalHeaderItem(0).setToolTip('This is the plugin name. Select which plugins you wish to compact.')
        self.horizontalHeaderItem(1).setToolTip('This is the CELL Record Flag. If an ESL plugin creates a new CELL\nand another mod changes that CELL then it may not work due to an engine bug.\n\"New  CELL\" indicates the presence of a new CELL record and \"New CELL Changed\"\nindicates that the new CELL record is changed by a dependent plugin.')
        self.horizontalHeaderItem(2).setToolTip('This is the BSA Flag. If a Bethesda Archive holds files that need\npatching, this program will not be able to patch them until they are extracted.\nHover over the BSA flag to see the relevant .bsa files for each mod.')
        self.horizontalHeaderItem(3).setToolTip('If a plugin has other plugins with it as a master, they will appear\nwhen the button is clicked. These will also have their\nForm IDs patched to reflect the Master plugin\'s changes.')
        self.verticalHeader().setHidden(True)
        self.setShowGrid(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenu)
        self.mod_list = []
        self.has_new_cells = []
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
                image: url(./images/checked.png);
            }
            QTableWidget::indicator:unchecked{
                image: url(./images/unchecked.png);
            }
            QTableWidget::indicator:indeterminate{
                image:url(./images/partially_checked.png);
            }
        """)

        self.create()

    def create(self):
        self.clearContents()
        self.dependency_list = self.get_data_from_file("ESLifier_Data/dependency_dictionary.json")
        self.compacted = self.get_data_from_file("ESLifier_Data/compacted_and_patched.json")
        self.bsa_dict = self.get_data_from_file("ESLifier_Data/bsa_dict.json")
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
            item = QTableWidgetItem(os.path.basename(self.mod_list[i]))
            if os.path.basename(self.mod_list[i]) in self.compacted.keys():
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.PartiallyChecked)
            else:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(self.mod_list[i])
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
            self.setItem(i, 0, item)
            self.setRowHidden(i, False)
            if os.path.basename(self.mod_list[i]) in self.has_new_cells:
                item_cell_flag = QTableWidgetItem('New CELL')
                item_cell_flag.setToolTip('This mod has a new CELL record and no mods currently modify it.\nIt is currently safe to ESL flag it.')
                if os.path.basename(self.mod_list[i]) in self.cell_changed:
                    item_cell_flag.setText('New CELL Changed')
                    item_cell_flag.setToolTip('This mod has a new CELL record\nand has a dependent plugin that modifies it.\nIt is NOT recommended to ESL flag it.')
                item_cell_flag.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(i, 1, item_cell_flag)
            full_name = os.path.basename(self.mod_list[i]).lower()
            name, _ = os.path.splitext(full_name)
            if any(("scripts_"+name) == value for value in self.bsa_dict.values()) or any(os.path.basename(self.mod_list[i]).lower() in value for value in self.bsa_dict.values()):
                item_bsa = QTableWidgetItem('BSA')
                item_bsa.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                tooltip = 'The following .bsa(s) need to be extracted as they contain\nfiles that may need patching and this program cannot scan them:\n(restart the program after doing so)\n\n'
                for key, values in self.bsa_dict.items():
                    if "scripts_" + name == values[0]:
                        tooltip += '- Contains Scripts: ' + key + '\n'
                    if name+".seq" in values:
                        tooltip += '- Contains mod SEQ file: ' + key + '\n'
                only_once = True
                for key, values in self.bsa_dict.items():
                    if full_name in values:
                        if only_once:
                            only_once = False
                            tooltip += f'- Contain\'s facegeom/facetint/voice files:\n'
                        tooltip += '    - ' + key + '\n'
                item_bsa.setToolTip(tooltip)
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

    def get_data_from_file(self, file):
        try:
            with open(file, 'r') as f:
                data = json.load(f)
        except:
            data = {}
        return data

    def contextMenu(self, position):
        selected_item = self.itemAt(position)
        if selected_item:
            menu = QMenu(self)
            select_all_action = menu.addAction("Select All")
            check_all_action = menu.addAction("Check All")
            uncheck_all_action = menu.addAction("Uncheck All")
            invert_selection_action = menu.addAction("Invert Selection")
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
                self.selectAll()
            if action == invert_selection_action:
                selected_items = self.selectedItems()
                self.invert_selection(selected_items)
            if action == add_to_blacklist_action:
                selected_items = self.selectedItems()
                self.add_to_blacklist(selected_items)

    def check_all(self):
        self.blockSignals(True)
        for i in range(self.rowCount()):
            if self.item(i,0).checkState() == Qt.CheckState.Unchecked:
                self.item(i, 0).setCheckState(Qt.CheckState.Checked)
        self.blockSignals(False)

    def uncheck_all(self):
        self.blockSignals(True)
        for i in range(self.rowCount()):
            if self.item(i,0).checkState() == Qt.CheckState.Checked:
                self.item(i, 0).setCheckState(Qt.CheckState.Unchecked)
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

        

