import os

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel, QDialog
except ImportError:
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel, QDialog
            

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel, QDialog

class notification_display_dialog(QDialog):
    def __init__(self, icon_path):
        super().__init__()
        self.MOD_COL = 0
        self.CELL_COL = 1
        self.WRLD_COL = 2
        self.WTHR_COL = 3
        self.COL_COUNT = 4
        self.setMinimumWidth(900)
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        self.setWindowIcon(QIcon(icon_path + '\\ESLifier.ico'))
        self.setWindowTitle("ESLifier Notifications")

        self.master_not_enabled_label = QLabel("The ESLifier_Cell_Master.esm plugin exists but has not been enabled in the plugin list\n" \
                                                "which can cause a CTD.")
        main_layout.addWidget(self.master_not_enabled_label)

        self.lost_to_overwrite_table = self.make_table(1)
        self.lost_to_overwrite_table_label = QLabel("The following files are present in both MO2's Overwrite folder and ESLifier's output.\n"\
                                                "This means that ESLifier is likely losing a file conflict and needs these files move to\n"\
                                                "a mod that it can win the conflict with.")
        main_layout.addWidget(self.lost_to_overwrite_table_label)
        main_layout.addWidget(self.lost_to_overwrite_table)

        self.conflict_changes_table = self.make_table(1)
        self.conflict_changes_table_label = QLabel("The following files have had their conflicts change since ESLifier last ran:\n"\
                                                    "(Run the Patch New button in ESLifier.exe)")
        main_layout.addWidget(self.conflict_changes_table_label)
        main_layout.addWidget(self.conflict_changes_table)

        self.hash_mismatch_table = self.make_table(1)
        self.hash_mismatch_table_label = QLabel("The following files have been altered or removed since ESLifier last ran:\n"\
                                                "(Run the Patch New button in ESLifier.exe)")
        main_layout.addWidget(self.hash_mismatch_table_label)
        main_layout.addWidget(self.hash_mismatch_table)

        self.needs_flag_table = self.make_table(self.COL_COUNT)
        self.needs_flag_table_label = QLabel("The following plugins can be flagged as esl:")
        main_layout.addWidget(self.needs_flag_table_label)
        main_layout.addWidget(self.needs_flag_table)

        self.needs_compacting_flag_table = self.make_table(self.COL_COUNT)
        self.needs_compacting_flag_table_label = QLabel("The following plugins can be flagged as esl after compacting:")
        main_layout.addWidget(self.needs_compacting_flag_table_label)
        main_layout.addWidget(self.needs_compacting_flag_table)

    def make_table(self, columns: int):
        table = QTableWidget()
        table.setColumnCount(columns)
        if columns == 1:
            table.horizontalHeader().hide()
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAutoScroll(False)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        return table

    def create(self, hash_mismatches: list, conlfict_changes: list, lost_to_overwrite: list, needs_flag_dict: dict, needs_compacting_flag_dict: dict, master_not_enabled: bool):

        if master_not_enabled:
            self.master_not_enabled_label.show()
        else:
            self.master_not_enabled_label.hide()

        self.lost_to_overwrite_table.hide()
        self.lost_to_overwrite_table.clear()
        self.lost_to_overwrite_table_label.hide()

        self.conflict_changes_table.hide()
        self.conflict_changes_table.clear()
        self.conflict_changes_table_label.hide()

        self.hash_mismatch_table.hide()
        self.hash_mismatch_table.clear()
        self.hash_mismatch_table_label.hide()

        self.needs_flag_table.clear()
        self.needs_flag_table.hide()
        self.needs_flag_table_label.hide()

        self.needs_compacting_flag_table.clear()
        self.needs_compacting_flag_table.hide()
        self.needs_compacting_flag_table_label.hide()

        if len(lost_to_overwrite) > 0:
            self.lost_to_overwrite_table_label.show()
            self.populate_flag_table(self.lost_to_overwrite_table, lost_to_overwrite)

        if len(conlfict_changes) > 0:
            self.conflict_changes_table_label.show()
            self.populate_flag_table(self.conflict_changes_table, conlfict_changes)

        if len(hash_mismatches) > 0:
            self.hash_mismatch_table_label.show()
            self.populate_flag_table(self.hash_mismatch_table, hash_mismatches)

        if len(needs_flag_dict) > 0:
            self.needs_flag_table_label.show()
            self.populate_flag_table(self.needs_flag_table, needs_flag_dict)

        if len(needs_compacting_flag_dict) > 0:
            self.needs_compacting_flag_table_label.show()
            self.populate_flag_table(self.needs_compacting_flag_table, needs_compacting_flag_dict, weather=True)

        self.show()
        self.raise_()

    def populate_flag_table(self, table: QTableWidget, data: dict | list, weather = False):
        table.show()
        table.setRowCount(len(data))
        table.setSortingEnabled(False)
        if isinstance(data, dict):
            headers = ['Mod', 'Cell Flag', 'Worldspace Flag']
            if weather:
                headers.append('Weather Flag')
                table.showColumn(self.WTHR_COL)
            else:
                table.hideColumn(self.WTHR_COL)
            table.setHorizontalHeaderLabels(headers)
            for i, (plugin, flags) in enumerate(data.items()):
                basename = os.path.basename(plugin)
                item = QTableWidgetItem(basename)
                item.setToolTip(plugin)
                table.setItem(i, self.MOD_COL, item)
                if 'new_cell' in flags:
                    item_cell_flag = QTableWidgetItem('New CELL')
                    if 'new_interior_cell' in flags:
                        item_cell_flag.setText('New Interior CELL')
                    table.setItem(i, self.CELL_COL, item_cell_flag)
                if 'new_wrld' in flags:
                    item_wrld_flag = QTableWidgetItem('New Worldspace')
                    table.setItem(i, self.WRLD_COL, item_wrld_flag)
                if 'new_wthr' in flags:
                    item_wthr_flag = QTableWidgetItem('New Weather')
                    table.setItem(i, self.WTHR_COL, item_wthr_flag)
        else:
            for i, file in enumerate(data):
                item_contents = QTableWidgetItem()
                item_contents.setText(file)
                table.setItem(i, 0, item_contents)
                
        table.setSortingEnabled(True)
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
            