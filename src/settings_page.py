import json
import os
import subprocess
import configparser

from PyQt6.QtCore import Qt, QRegularExpression, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QWidget, QPushButton, QLineEdit, QMessageBox, QFileDialog, QFrame, QColorDialog, QComboBox
from PyQt6.QtGui import QIcon, QColor

from blacklist import blacklist_window
from log_stream import write_error

from QToggle import QtToggle
class settings(QWidget):
    settings_updated = pyqtSignal()
    need_to_rebuild_lists = pyqtSignal()
    def __init__(self, COLOR_MODE):
        super().__init__()
        self.setFocus()
        settings_layout = QVBoxLayout()
        h_base_layout = QHBoxLayout()
        widget_holder = QWidget()
        widget_holder.setLayout(settings_layout)
        h_base_layout.addStretch(1)
        h_base_layout.addWidget(widget_holder)
        h_base_layout.addStretch(1)
        self.setLayout(h_base_layout)
        self.output_folder_name_valid = True
        self.settings = self.get_settings_from_file()
        self.default_settings = {}

        self.file_dialog = QFileDialog()
        self.file_dialog.setFileMode(QFileDialog.FileMode.Directory)

        self.file_dialog_2 = QFileDialog()
        self.file_dialog_2.setFileMode(QFileDialog.FileMode.ExistingFile)

        self.skyrim_folder_path_widget, self.skyrim_folder_path = self.create_path_widget(
            self.tr("Data Folder Path"),
            self.tr("Set this to your Skyrim Special Edition Data folder that holds Skyrim.esm."),
            self.tr('C:/Path/To/Skyrim Special Edition/Data'),
            self.skyrim_folder_path_clicked,
            'skyrim_folder_path'
        )
        self.output_folder_path_widget, self.output_folder_path = self.create_path_widget(
            self.tr("Output Folder Path"),
            self.tr("Set where you want the Output Folder to be generated."),
            self.tr('C:/Path/To/The/Output/Folder/'),
            self.output_folder_path_clicked,
            'output_folder_path'
        )
        self.output_folder_name_widget, self.output_folder_name = self.create_output_name_text_input_widget(
            self.tr("Output Folder Name"),
            self.tr("Change this to what you want to be the name of the Output Folder."),
            "ESLifier Output"
        )
        self.mo2_base_path_widget, self.mo2_base_path = self.create_path_widget(
            self.tr("MO2 Instance Directory"),
            self.tr("Set this to your modlist\'s MO2 Instance folder, the folder that holds 'ModOrganizer.ini'."),
            self.tr('C:/Path/To/MO2/Instance'),
            self.mo2_base_path_clicked,
            'mo2_base_path'
        )
        self.mo2_profile_widget, self.mo2_profile = self.create_combo_box_widget(
            self.tr("MO2 Profile"),
            self.tr("Set this to your modlist's MO2 profile."),
            self.tr("Select Profile"),
            'mo2_profile'
        )
        self.mo2_base_path.textChanged.connect(self.mo2_profile.clear)
        self.mo2_base_path.editingFinished.connect(self.mo2_profile.clear)
        self.mo2_base_path.editingFinished.connect(self.populate_mo2_profiles)
        self.vortex_data_path_widget, self.vortex_data_path = self.create_path_widget(
            self.tr("Vortex Data Path"),
            self.tr("Set this to Vortex's data folder (the folder that holds the \"state.v2\" and \"skyrimse\" folders)."),
            self.tr('C:/Users/USER/AppData/Roaming/Vortex or C:/ProgramData/vortex'),
            self.vortex_data_path_clicked,
            'vortex_data_path'
        )
        self.plugins_txt_path_widget, self.plugins_txt_path = self.create_path_widget(
            self.tr("Plugins.txt Path"),
            self.tr("Set this to your modlist\'s plugins.txt"),
            self.tr('C:/Path/To/plugins.txt'),
            self.plugins_txt_path_clicked,
            'plugins_txt_path'
        )
        self.mod_manager_mode_widget, self.mod_manager_mode_toggle = self.create_toggle_widget(
            self.tr("Mod Manager: None"),
            self.tr("Users without a mod manager should get a mod manager. ESLifier is not\n"\
                    "meant to be used with manual modding but should still work at least once."),
            "mod_manager_mode",
            active_color='deepskyblue',
            tri_state=True,
            default=0
        )
        self.mod_manager_mode_widget.layout().itemAt(2).widget().clicked.connect(self.mod_mananger_mode_clicked)
        self.mod_manager_mode_widget.layout().itemAt(2).widget().clicked.connect(self.skyrim_folder_path.clear)
        self.mod_manager_mode_widget.layout().itemAt(2).widget().clicked.connect(self.mo2_base_path.clear)
        self.mod_manager_mode_widget.layout().itemAt(2).widget().clicked.connect(self.vortex_data_path.clear)
        self.mod_manager_mode_widget.layout().itemAt(2).widget().clicked.connect(self.plugins_txt_path.clear)
        self.update_header_widget, self.update_header_toggle = self.create_toggle_widget(
            self.tr("Allow Form IDs below 0x000800 + Update plugin headers to 1.71"),
            self.tr("Allow scanning and patching to use the new 1.71 header.\n"\
                    "Requires Backported Extended ESL Support on Skyrim versions below 1.6.1130.\n"\
                    "Changing this settings requires a re-scan."),
            "update_header",
            default=True
        )
        self.show_esms_widget, self.show_esms_toggle = self.create_toggle_widget(
            self.tr("Show ESM Plugins"),
            self.tr("Display ESM plugins (.esm/ESM flagged)."),
            "show_esms",
            default=True
        )
        self.show_plugins_with_cells_widget, self.show_plugins_with_cells_toggle = self.create_toggle_widget(
            self.tr("Show plugins with new CELL records"),
            self.tr("Bugs related to cells have been fixed by SSE Engine Fixes v7+ for Skyrim 1.6.1170+.\n"\
                    "For users of SSE Engine Fixes v7+ ESLifier will ignore this setting and show them regardless.\n"\
                    "Display plugins with new CELL records."),
            "show_cells",
            default=True
        )
        self.enable_cell_changed_filter_widget, self.enable_cell_changed_filter_toggle = self.create_toggle_widget(
            self.tr("Hide ESM plugins with new CELL records that are overwritten"),
            self.tr("The related bug has been fixed by SSE Engine Fixes v7+ for Skyrim 1.6.1170+. Disable this filter.\n"\
                    "For users of SSE Engine Fixes v7+ ESLifier will ignore this setting and show them regardless.\n"\
                    "Hide ESM plugins with new CELL records that have been changed by a dependent plugin."),
            "enable_cell_changed_filter",
            default=False
        )
        self.enable_interior_cell_filter_widget, self.enable_interior_cell_filter_toggle = self.create_toggle_widget(
            self.tr("Hide plugins with new interior CELL records"),
            self.tr("This bug has been fixed by SSE Engine Fixes v7+ for Skyrim 1.6.1170+.\n"\
                    "For users of SSE Engine Fixes v7+ ESLifier will ignore this setting and show them regardless.\n"
                    "Hide plugins with new interior CELL records as they can have issues when reloading\n"\
                    "a save without restarting the game."),
            "enable_interior_cell_filter",
            default=False
        )
        self.enable_worldspaces_filter_widget, self.enable_worldspaces_filter_toggle = self.create_toggle_widget(
            self.tr("Hide plugins with new WRLD (worldspace) records"),
            self.tr("Hide plugins with new worldspaces records as they can have the landscape disappear\n"\
                    "(no ground) when flagged as ESL."),
            "filter_worldspaces",
            default=True
        )
        self.enable_weather_filter_widget, self.enable_weather_filter_toggle = self.create_toggle_widget(
            self.tr("Hide plugins with new WTHR (weather) records"),
            self.tr("Hide plugins with new weather records as they can be referenced in ENB presets which are not patched."),
            "filter_weathers",
            default=False
        )
        self.enable_seq_filter_widget, self.enable_seq_filter_toggle = self.create_toggle_widget(
            self.tr("Hide plugins that have SEQ files"),
            self.tr("Hide plugins that have SEQ files as ESL flagging it may cause dialogue for it to not work until you save and reload in game."),
            "filter_seq",
            default=False
        )
        self.enable_pex_filter_widget, self.enable_pex_filter_toggle = self.create_toggle_widget(
            self.tr("Hide plugins that have PEX files with GetModByName"),
            self.tr("Hide plugins that have PEX files that call the papyrus function 'GetModByName' on\n'\
                    'them as that function only works properly on non-ESL plugins."),
            "filter_pex",
            default=True
        )
        self.hide_left_columns_widget, self.hide_left_columns_text_input = self.create_text_input_widget(
            self.tr("Hide left list columns visually"),
            self.tr("Hide specified columns visually. This does not affect what plugins are displayed.\n"\
            "Specify the column names, comma seperated. Available: CELL, WRLD, SEQ, PEX, ESM\n"\
            "Example, hides the CELL and ESM flags: CELL,ESM"),
            "CELL,ESM",
            "left_hidden_columns",
            ''
        )
        self.hide_right_columns_widget, self.hide_right_columns_text_input = self.create_text_input_widget(
            self.tr("Hide right list columns visually"),
            self.tr("Hide specified columns visually. This does not affect what plugins are displayed.\n"\
            "Specify the column names, comma seperated. Available: CELL, WRLD, WTHR, SEQ, PEX, ESM, DEPENDENTS\n"\
            "Example, hides the ESM flag and the dependent plugins: ESM,DEPENDENT"),
            "ESM,DEPENDENTS",
            "right_hidden_columns",
            ''
        )
        self.show_plugins_possibly_refd_by_dlls_widget, self.show_plugins_possibly_refd_by_dlls_toggle = self.create_toggle_widget(
            self.tr("Show plugins that are in SKSE dlls"),
            self.tr("Show or hide plugins that may have Form IDs hard-coded in SKSE dlls."),
            "show_dlls",
            default=False
        )
        self.persistent_ids_widget, self.persistent_ids_toggle = self.create_toggle_widget(
            self.tr("Persist Form IDs between rebuilds"),
            self.tr("Make Form IDs re-compact to the same compacted Form IDs as the previous\n"\
            "run, regardless of changes to the plugin such as adding a new Form ID in\n"\
            "the middle of the existing Form IDs. (Doesn't work after clicking Reset Output)\n"\
            "(i.e. adding 0x9A0B to a mod that only had 0x9A0A and 0x9A0C where\n"\
            "the ids compacted to 0x80A and 0x80B respectively. Then the new Form ID\n"\
            "will compact from 0x9A0B to 0x90C since the first two IDs existed previously\n"\
            "but 0x9A0B did not and 0x90C is the next available compacted Form ID.)"),
            "persistent_ids",
            default=True
        )
        self.persistent_ids_toggle.clicked.connect(self.persistent_ids_clicked)
        self.free_non_existent_widget, self.free_non_existent_toggle = self.create_toggle_widget(
            self.tr("Free Non-Existent Form IDs"),
            self.tr("Allow ESLifier to free the allocation of a compacted Form ID if the\n"\
            "original Form ID that the compacted Form ID is allocated to no longer exists.\n"\
            "(i.e. if 0x9A0A no longer exists in the theoretical mod in the toolTip example\n"\
            "of \"Persist Form IDs between rebuilds\", then adding 0x9A0B becomes -> 0x80A\n"\
            "instead of 0x80C since 0x80A is free)"),
            "free_non_existent",
            default=False
        )
        self.enable_patch_new_widget, self.enable_patch_new_toggle = self.create_toggle_widget(
            self.tr("Enable the Patch New or Changed Files Button"),
            self.tr("Show the patch new button on the main page. Personally, I think it is useless\n"\
            "and annoying to maintain. However, I'm sure there is someone who uses it so I'm\n"\
            "keeping the option here to keep it enabled. Doesn't hash check if output has changed."),
            "enable_patch_new",
            default=False
        )
        self.hash_output_widget, self.hash_output_toggle = self.create_toggle_widget(
            self.tr("Hash the Output Folder to Detect Changes"),
            self.tr("Hash the output folder during certain actions to detect if a file has been changed\n"\
            "since ESLifier last patched it. Enabling this after you have already created an output will\n"\
            "not work correctly. Can be time consuming."),
            "hash_output",
            default=True
        )
        self.hash_plugins_warn_widget, self.hash_plugins_warn_toggle = self.create_toggle_widget(
            self.tr("Warn About Changed Plugins in Output Folder"),
            self.tr("Uses the output hash to also warn about plugins that have changed in the output."),
            "hash_plugins_warn",
            default=True
        )
        self.check_for_updates_widget, self.check_for_updates_toggle = self.create_toggle_widget(
            self.tr("Check for updates on start"),
            self.tr("Connect to GitHub on program start to check for updates"),
            "check_for_updates",
            default=True
        )
        self.blacklist_window = blacklist_window()
        self.edit_blacklist_widget = self.create_button_widget(
            self.tr("Remove Plugins From Blacklist"),
            self.tr('Show window to remove plugins from the blacklist. You can add\n'\
            'plugins to the blacklist by right clicking them on the Main page.'),
            self.tr('Edit Blacklist'),
            self.edit_blacklist_button_clicked
        )
        self.open_eslifier_data_widget = self.create_button_widget(
            self.tr("Open ESLifier's Data Folder"),
            self.tr("This opens the folder where all of the dictionaries and Form ID maps are stored."),
            self.tr("Open Folder"),
            self.open_eslifier_data
        )
        self.reset_settings_widget = self.create_button_widget(
            self.tr("Reset All Settings"),
            None,
            self.tr("Reset"),
            self.reset_settings_clicked
        )
        self.colors_select_widget = self.create_button_widget(
            self.tr("Change Background Colors"),
            self.tr("This opens a color picker for the background colors"),
            self.tr("Open Color Picker"),
            self.open_color_dialog
        )
        self.generate_cell_master_widget, self.generate_cell_master_toggle = self.create_toggle_widget(
            self.tr("Generate Cell Master"),
            self.tr("As of SSE Engine Fixes v7+ this is no longer necessary\n"\
            "for Skyrim version 1.6.1170+ and can be left disabled.\n"\
            "This generates a master cell plugin to circumvent\n"\
            "the ESM + ESL cell bug and the ESL worldspace bug.\n"\
            "(This does not fix the interior ESL save reload bug).\n"\
            "Requires an ESM plugin slot and is only useful if you\n"\
            "need to ESL flag more than one such plugin. Do not\n"
            "forget to activate the new ESLifier_Cell_Master.esm that\n"\
            "is generated. You may also need to re-sort your plugins.\n"\
            "This disables the cell changed flag/filter for ESMs and\n"\
            "the new worldspace flag/filter."),
            "generate_cell_master",
            default=False   
        )
        self.generate_cell_master_toggle.clicked.connect(self.cell_master_clicked)

        self.set_init_widget_values()
        
        self.update_settings_from_app_state()
        
        settings_layout.addWidget(self.mod_manager_mode_widget)
        settings_layout.addWidget(self.skyrim_folder_path_widget)
        settings_layout.addWidget(self.vortex_data_path_widget)
        settings_layout.addWidget(self.mo2_base_path_widget)
        settings_layout.addWidget(self.mo2_profile_widget)
        settings_layout.addWidget(self.output_folder_path_widget)
        settings_layout.addWidget(self.output_folder_name_widget)
        settings_layout.addWidget(self.plugins_txt_path_widget)

        column_wrapper = QHBoxLayout()
        column_wrapper_widget = QWidget()
        column_wrapper_widget.setLayout(column_wrapper)
        column_wrapper.setContentsMargins(0, 0, 0, 0)
        column_1 = QVBoxLayout()
        column_1.setContentsMargins(0, 0, 0, 0)
        c_widget_1 = QWidget()
        c_widget_1.setLayout(column_1)
        line = QFrame()
        line.setFrameStyle(QFrame.Shape.VLine | QFrame.Shadow.Sunken)
        if COLOR_MODE == 'Light':
            line.setStyleSheet('QFrame{background-color: lightgrey;}')
        column_2 = QVBoxLayout()
        column_2.setContentsMargins(0, 0, 0, 0)
        c_widget_2 = QWidget()
        c_widget_2.setLayout(column_2)
        column_wrapper.addWidget(c_widget_1)
        column_wrapper.addSpacing(10)
        column_wrapper.addWidget(line)
        column_wrapper.addSpacing(10)
        column_wrapper.addWidget(c_widget_2)
        
        settings_layout.addSpacing(20)
        settings_layout.addWidget(column_wrapper_widget)

        column_1.addWidget(self.update_header_widget)
        column_1.addWidget(self.show_esms_widget)
        column_1.addWidget(self.show_plugins_with_cells_widget)
        column_1.addWidget(self.enable_cell_changed_filter_widget)
        column_1.addWidget(self.enable_interior_cell_filter_widget)
        column_1.addWidget(self.enable_worldspaces_filter_widget)
        column_1.addWidget(self.enable_weather_filter_widget)
        column_1.addWidget(self.enable_seq_filter_widget)
        column_1.addWidget(self.enable_pex_filter_widget)
        column_1.addWidget(self.show_plugins_possibly_refd_by_dlls_widget)
        column_1.addWidget(self.generate_cell_master_widget)
        column_1.addWidget(self.hide_left_columns_widget)
        
        column_2.addWidget(self.persistent_ids_widget)
        column_2.addWidget(self.free_non_existent_widget)
        column_2.addWidget(self.hash_output_widget)
        column_2.addWidget(self.hash_plugins_warn_widget)
        column_2.addWidget(self.enable_patch_new_widget)
        column_2.addWidget(self.edit_blacklist_widget)
        column_2.addWidget(self.open_eslifier_data_widget)
        column_2.addWidget(self.colors_select_widget)
        column_2.addWidget(self.reset_settings_widget)
        column_2.addWidget(self.check_for_updates_widget)
        column_2.addWidget(self.hide_right_columns_widget)

        settings_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def open_color_dialog(self):
        inner_color = QColorDialog.getColor(QColor(self.inner_color), self, self.tr("Select Inner Color"))
        if inner_color.isValid():
            self.inner_color = inner_color.name()
        outer_color = QColorDialog.getColor(QColor(self.outer_color), self, self.tr("Select Outer Color"))
        if outer_color.isValid():
            self.outer_color = outer_color.name()
        self.settings_updated.emit()

    def button_maker(self, text, function, width):
        button = QPushButton()
        button.setText(text)
        button.clicked.connect(function)
        button.setFixedWidth(width)
        return button
    
    def select_file_path(self, dialog: QFileDialog, title, setting_key, line_edit: QLineEdit, filter):
        if filter != None:
            path, _ = dialog.getOpenFileName(self, title, self.settings.get(setting_key, ""), filter)
        else:
            path = dialog.getExistingDirectory(self, title, self.settings.get(setting_key, ""))
        if path:
            line_edit.setText(os.path.normpath(path))
        self.update_settings_from_app_state()
    
    def skyrim_folder_path_clicked(self):
        if not self.mod_manager_mode_toggle.isChecked():
            self.select_file_path(self.file_dialog, self.tr("Select the Skyrim Special Edition Data folder"), 'skyrim_folder_path', self.skyrim_folder_path, None)
        else:
            self.select_file_path(self.file_dialog, self.tr("Select your MO2 mods folder"), 'skyrim_folder_path', self.skyrim_folder_path, None)

    def output_folder_path_clicked(self):
        self.select_file_path(self.file_dialog, self.tr("Select where you want the output folder"), 'output_folder_path', self.output_folder_path, None)

    def get_mo2_profiles(self):
        mo2_base_dir = os.path.normpath(self.settings.get('mo2_base_path', ''))
        file = os.path.join(mo2_base_dir, "ModOrganizer.ini")
        if os.path.exists(file):
            ini = configparser.ConfigParser()
            
            ini.read(file, encoding='utf-8')

            if ini.has_option('Settings', 'base_directory'):
                mo2_base_dir = os.path.normpath(ini.get('Settings', 'base_directory'))

            if ini.has_option('Settings', 'profiles_directory'):
                mo2_profiles_dir = os.path.normpath(ini.get('Settings', 'profiles_directory'))
            else:
                mo2_profiles_dir = os.path.normpath(os.path.join(mo2_base_dir, "profiles"))
            self.settings['mo2_profiles_dir'] = mo2_profiles_dir
            profiles = set()
            for profile in os.listdir(mo2_profiles_dir):
                profiles.add(profile)
            return profiles

    def populate_mo2_profiles(self):
        profiles = self.get_mo2_profiles()
        current = self.mo2_profile.currentText()
        self.mo2_profile.clear()
        if profiles:
            self.mo2_profile.addItems(profiles)
            index = self.mo2_profile.findText(current)
            self.mo2_profile.setCurrentIndex(index)

    def mo2_base_path_clicked(self):
        self.select_file_path(self.file_dialog, self.tr("Select your MO2 instance folder"), 'mo2_base_path', self.mo2_base_path, None)
        self.populate_mo2_profiles()

    def vortex_data_path_clicked(self):
        self.select_file_path(self.file_dialog, self.tr("Select your vortex data folder"), 'vortex_data_path', self.vortex_data_path, None)

    def plugins_txt_path_clicked(self):
        self.select_file_path(self.file_dialog_2, self.tr("Select your plugins.txt"), 'plugins_txt_path', self.plugins_txt_path, self.tr("Load Order")+ " (plugins.txt)")

    def create_path_widget(self, label_text, tooltip, placeholder, click_function, settings_key):
        layout = QHBoxLayout()
        widget = QWidget()
        widget.setToolTip(tooltip)
        label = QLabel(label_text)
        line_edit = QLineEdit()
        line_edit.setText(self.settings.get(settings_key, ''))
        line_edit.editingFinished.connect(self.update_settings_from_app_state)
        button = self.button_maker(self.tr('Explore...'), click_function, 100)

        widget.setLayout(layout)
        layout.addWidget(label)
        layout.addSpacing(10)
        layout.addWidget(line_edit)
        layout.addSpacing(10)
        layout.addWidget(button)

        line_edit.setPlaceholderText(placeholder)
        line_edit.setMinimumWidth(400)
        line_edit.setMaximumWidth(550)
        self.default_settings[settings_key] = {"type": "path", "default": '', "widget": line_edit}
        return widget, line_edit

    def create_combo_box_widget(self, label_text, tooltip, placeholder, settings_key):
        layout = QHBoxLayout()
        widget = QWidget()
        widget.setToolTip(tooltip)
        label = QLabel(label_text)
        combo_box = QComboBox()
        combo_box.addItem(self.settings.get(settings_key, ''))
        combo_box.currentIndexChanged.connect(self.update_settings_from_app_state)

        widget.setLayout(layout)
        layout.addWidget(label)
        layout.addSpacing(10)
        layout.addWidget(combo_box)

        combo_box.setPlaceholderText(placeholder)

        def update_style():
            is_empty = "true" if combo_box.currentIndex() == -1 else "false"
            
            combo_box.setProperty("empty", is_empty)
            combo_box.style().unpolish(combo_box)
            combo_box.style().polish(combo_box)

        combo_box.setStyleSheet("""
            QComboBox[empty="true"] {
                background-color: #FFCCCC;
                border: 1px solid red;
            }
            QComboBox[empty="false"] {
            }
            """)
        combo_box.currentIndexChanged.connect(update_style)
        
        update_style()
        combo_box.setMinimumWidth(666)
        combo_box.setMaximumWidth(1000)
        self.default_settings[settings_key] = {"type": "combo_box", "default": '', "widget": combo_box}
        return widget, combo_box
    
    def create_toggle_widget(self, label_text, tooltip, setting_key, 
                             bg_color: str = 'Light Grey', circle_color: str = 'Grey',active_color: str = 'palegreen',partial_color: str = 'orange',
                             tri_state=False, default=False):
        layout = QHBoxLayout()
        widget = QWidget()
        widget.setToolTip(tooltip)
        label = QLabel(label_text)
        toggle = QtToggle(bg_color=bg_color, circle_color=circle_color, active_color=active_color, partial_color=partial_color, tri_state=tri_state)
        setting_value = self.settings.get(setting_key, default)
        if isinstance(setting_value, bool):
            toggle.setChecked(setting_value)
        else:
            toggle.setCheckState(Qt.CheckState(setting_value))
        toggle.clicked.connect(lambda: self.update_settings_from_app_state(setting_key))
        
        widget.setLayout(layout)
        layout.addWidget(label)
        layout.addSpacing(10)
        layout.addWidget(toggle)
        self.default_settings[setting_key] = {"type": "toggle", "default": default, "widget": toggle}
        return widget, toggle

    def mod_mananger_mode_clicked(self):
        if self.mod_manager_mode_toggle.checkState() == Qt.CheckState.Checked:
            self.mod_manager_mode_widget.layout().itemAt(0).widget().setText(self.tr("Mod Manager: MO2"))
            self.output_folder_path_widget.setToolTip(self.tr("Set where you want the Output Folder to be generated. For example: MO2's 'mods' folder."))
            self.mod_manager_mode_widget.setToolTip(
                self.tr("MO2 users should not launch this executible through MO2,\n"\
                        "Launching this program through MO2 drastically slows it down and may\n"\
                        "break certain functions."))
        elif self.mod_manager_mode_toggle.checkState() == Qt.CheckState.PartiallyChecked:
            self.mod_manager_mode_widget.layout().itemAt(0).widget().setText(self.tr("Mod Manager: Vortex"))
            self.output_folder_path_widget.setToolTip(self.tr("Set where you want the Output Folder to be generated. For example: Vortex's 'Mod Staging Folder'."))
            #self.skyrim_folder_path_widget.setToolTip(self.tr("Set this to your Skyrim Special Edition Data folder that holds Skyrim.esm."))
            #self.skyrim_folder_path_widget.layout().itemAt(0).widget().setText(self.tr("Data Folder Path"))
            #self.skyrim_folder_path.setPlaceholderText(self.tr('C:/Path/To/Skyrim Special Edition/Data'))
            self.mod_manager_mode_widget.setToolTip(
                self.tr("Vortex users can also set this to None to scan the way ESLiifer originally\n"\
                        "dealth with Vortex if you prefer/need that."))
        else:
            self.mod_manager_mode_widget.layout().itemAt(0).widget().setText(self.tr("Mod Manager: None"))
            self.output_folder_path_widget.setToolTip(self.tr("Set where you want the Output Folder to be generated."))
            self.mod_manager_mode_widget.setToolTip(
                self.tr("Users without a mod manager should get a mod manager. ESLifier is not\n"\
                        "meant to be used with manual modding but should still work at least once.\n"\
                        "You can also use this mode for the original way Vortex was dealt with."))
    
    def cell_master_clicked(self):
        if self.generate_cell_master_toggle.checkState() == Qt.CheckState.Checked:
            self.enable_cell_changed_filter_widget.setEnabled(False)
            self.enable_cell_changed_filter_toggle.change_color(circle_color='LightCoral', bg_color='Grey', active_color='Grey')
            self.enable_cell_changed_filter_widget.setToolTip(self.tr("Disabled by Generate Cell Master setting."))
            self.enable_worldspaces_filter_widget.setEnabled(False)
            self.enable_worldspaces_filter_toggle.change_color(circle_color='LightCoral', bg_color='Grey', active_color='Grey')
            self.enable_worldspaces_filter_widget.setToolTip(self.tr("Disabled by Generate Cell Master setting."))
        else:
            self.enable_cell_changed_filter_widget.setEnabled(True)
            self.enable_cell_changed_filter_toggle.change_color()
            self.enable_cell_changed_filter_widget.setToolTip(self.tr("Hide ESM plugins with new CELL records that have been changed by a dependent plugin."))
            self.enable_worldspaces_filter_widget.setEnabled(True)
            self.enable_worldspaces_filter_toggle.change_color()
            self.enable_worldspaces_filter_widget.setToolTip(self.tr("Hide plugins with new worldspaces records as they can have the landscape disappear\n"\
                                                            "(no ground) when flagged as ESL."))
    
    def persistent_ids_clicked(self):
        if self.persistent_ids_toggle.checkState() == Qt.CheckState.Checked:
            self.free_non_existent_widget.setEnabled(True)
            self.free_non_existent_widget.show()
        else:
            self.free_non_existent_widget.setEnabled(False)
            self.free_non_existent_widget.hide()

    def create_button_widget(self, label_text, tooltip, button_text, click_function):
        layout = QHBoxLayout()
        widget = QWidget()
        widget.setToolTip(tooltip)
        label = QLabel(label_text)
        button = QPushButton(button_text)
        button.setFixedWidth(100)
        button.clicked.connect(click_function)

        widget.setLayout(layout)
        layout.addWidget(label)
        layout.addSpacing(10)
        layout.addWidget(button)
        return widget
    
    def create_output_name_text_input_widget(self, label_text, tooltip, placeholder):
        layout = QHBoxLayout()
        widget = QWidget()
        widget.setToolTip(tooltip)
        label = QLabel(label_text)
        line_edit = QLineEdit()
        regex = QRegularExpression(
            r'^(?!'
                r'(?i)(COM[1-9]|LPT[1-9]|CON|NUL|PRN|AUX)(?:\.|$)'  # Reserved names
            r')'
            r'(?![.\s])'                            # No leading dot or space
            r'(?![.]{2,}$)'                         # Not just dots
            r'[^\\\/:*"?<>|]{1,254}'                # Valid characters (spaces allowed!)
            r'(?<![\s.])$'                          # No trailing space or dot
        )
        def hard_validate():
            line_edit.setText(line_edit.text().strip())
            text = line_edit.text()
            if regex.match(text).hasMatch() and 'eslifier' in text.lower():
                self.output_folder_name_valid = True
                self.update_settings_from_app_state()
            else:
                if 'eslifier' in text.lower():
                    QMessageBox.warning(None, self.tr("Invalid Output Name"), self.tr("'%1' is not a valid folder name.").replace("%1", text))
                else:
                    QMessageBox.warning(None, self.tr("Output Name missing 'ESLifier'"), self.tr("The output name must have 'ESLifier' (case insenstive) in it for safety purposes."))
                line_edit.setFocus()
                self.output_folder_name_valid = False

        line_edit.setText(self.settings.get('output_folder_name', "ESLifier Output"))
        line_edit.editingFinished.connect(hard_validate)

        widget.setLayout(layout)
        layout.addWidget(label)
        layout.addSpacing(10)
        layout.addWidget(line_edit)
        layout.addSpacing(10)
        layout.addSpacing(105)

        line_edit.setPlaceholderText(placeholder)
        line_edit.setMinimumWidth(400)
        line_edit.setMaximumWidth(550)
        self.default_settings['output_folder_name'] = {"type": "text", "default": "ESLifier Output", "widget": line_edit}
        return widget, line_edit
    
    def create_text_input_widget(self, label_text, tooltip, placeholder, setting_key, default=''):
        layout = QHBoxLayout()
        widget = QWidget()
        widget.setToolTip(tooltip)
        label = QLabel(label_text)
        line_edit = QLineEdit()

        line_edit.setText(self.settings.get(setting_key, ''))
        line_edit.editingFinished.connect(lambda: self.update_settings_from_app_state(setting_key))

        widget.setLayout(layout)
        layout.addWidget(label)
        layout.addSpacing(10)
        layout.addWidget(line_edit)

        line_edit.setPlaceholderText(placeholder)
        line_edit.setMinimumWidth(200)
        self.default_settings[setting_key] = {"type": "text", "default": default, "widget": line_edit}
        return widget, line_edit

    def edit_blacklist_button_clicked(self):
        self.blacklist_window.blacklist.create()
        self.blacklist_window.show()

    def open_eslifier_data(self):
        directory = os.path.join(os.getcwd(), 'ESLifier_data')
        try:
            if os.name == 'nt':
                os.startfile(directory)
            elif os.name == 'posix':
                subprocess.Popen(['xdg-open', os.path.dirname(directory)])
            else:
                subprocess.Popen(['open', os.path.dirname(directory)])
        except Exception as e:
            write_error(self.tr("Error opening file explorer: ") + str(e))

    def reset_settings_clicked(self):
        confirm = QMessageBox()
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setStyleSheet("""
            QMessageBox {
                background-color: lightcoral;
            }""")
        confirm.setText(self.tr("Are you sure you want to reset all settings?"))
        confirm.setWindowTitle(self.tr("Confirmation"))
        confirm.setWindowIcon(QIcon(":/images/ESLifier.png"))
        confirm.addButton(QMessageBox.StandardButton.Yes)
        confirm.addButton(QMessageBox.StandardButton.Cancel)
        confirm.button(QMessageBox.StandardButton.Cancel).setFocus()
        def acccepted():
            confirm.hide()
            if os.path.exists('ESLifier_Data/settings.json'):
                os.remove('ESLifier_Data/settings.json')
            self.settings.clear()
            for settings_key, setting_data in self.default_settings.items():
                setting_type = setting_data["type"]
                if setting_type == "toggle":
                    if isinstance(setting_data["default"], bool):
                        setting_data["widget"].setChecked(setting_data["default"])
                    else:
                        setting_data["widget"].setCheckState(Qt.CheckState((setting_data["default"])))
                elif setting_type == "path":
                    setting_data["widget"].clear()
                elif setting_type == "text":
                    setting_data["widget"].setText(setting_data["default"])
                elif setting_type == 'combo_box':
                    setting_data["widget"].clear()

            self.inner_color = '#713585'
            self.outer_color = 'Gray'
            self.update_settings_from_app_state()
        confirm.accepted.connect(acccepted)
        confirm.show()
        
    def set_init_widget_values(self):
        self.inner_color = self.settings.get('inner_color', '#713585')
        self.outer_color = self.settings.get('outer_color', 'Gray')
        self.populate_mo2_profiles()

    def save_settings_to_file(self):
        settings_file = os.path.normpath('ESLifier_Data/settings.json')
        if not os.path.exists(os.path.dirname(settings_file)):
            os.makedirs(os.path.dirname(settings_file))
        try:
            with open(settings_file, 'w+', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
        except:
            write_error(self.tr("Failed to save settings."))

    def update_settings_from_app_state(self, key = ''):
        self.settings['skyrim_folder_path'] = os.path.normpath(self.skyrim_folder_path.text()) if self.skyrim_folder_path.text() != '' else ''
        self.settings['output_folder_path'] = os.path.normpath(self.output_folder_path.text()) if self.output_folder_path.text() != '' else ''
        if self.output_folder_name_valid:
            self.settings['output_folder_name'] = self.output_folder_name.text()
        self.settings['mo2_base_path'] = os.path.normpath(self.mo2_base_path.text()) if self.mo2_base_path.text() != '' else ''
        self.settings['mo2_profile'] = self.mo2_profile.currentText()
        self.settings['plugins_txt_path'] = os.path.normpath(self.plugins_txt_path.text()) if self.plugins_txt_path.text() != '' else ''
        self.settings['vortex_data_path'] = os.path.normpath(self.vortex_data_path.text()) if self.vortex_data_path.text() != '' else ''
        self.settings['mod_manager_mode'] = self.mod_manager_mode_toggle.checkState().value
        self.settings['update_header'] = self.update_header_toggle.isChecked()
        self.settings['show_esms'] = self.show_esms_toggle.isChecked()
        self.settings['show_cells'] = self.show_plugins_with_cells_toggle.isChecked()
        self.settings['filter_seq'] = self.enable_seq_filter_toggle.isChecked()
        self.settings['filter_pex'] = self.enable_pex_filter_toggle.isChecked()
        self.settings['enable_cell_changed_filter'] = self.enable_cell_changed_filter_toggle.isChecked()
        self.settings['enable_interior_cell_filter'] = self.enable_interior_cell_filter_toggle.isChecked()
        self.settings['filter_worldspaces'] = self.enable_worldspaces_filter_toggle.isChecked()
        self.settings['filter_weathers'] = self.enable_weather_filter_toggle.isChecked()
        self.settings['left_hidden_columns'] = self.hide_left_columns_text_input.text()
        self.settings['right_hidden_columns'] = self.hide_right_columns_text_input.text()
        self.settings['show_dlls'] = self.show_plugins_possibly_refd_by_dlls_toggle.isChecked()
        self.settings['generate_cell_master'] = self.generate_cell_master_toggle.isChecked()
        self.settings['check_for_updates'] = self.check_for_updates_toggle.isChecked()
        self.settings['persistent_ids'] = self.persistent_ids_toggle.isChecked()
        self.settings['free_non_existent'] = self.free_non_existent_toggle.isChecked()
        self.settings['enable_patch_new'] = self.enable_patch_new_toggle.isChecked()
        self.settings['hash_output'] = self.hash_output_toggle.isChecked()
        self.settings['hash_plugins_warn'] = self.hash_plugins_warn_toggle.isChecked()
        self.settings['inner_color'] = self.inner_color
        self.settings['outer_color'] = self.outer_color

        self.mod_mananger_mode_clicked()
        if self.mod_manager_mode_toggle.checkState() == Qt.CheckState.Checked:
            self.mo2_base_path_widget.show()
            self.mo2_profile_widget.show()
            self.vortex_data_path_widget.hide()
            self.skyrim_folder_path_widget.hide()
            self.plugins_txt_path_widget.hide()
        elif self.mod_manager_mode_toggle.checkState() == Qt.CheckState.PartiallyChecked:
            self.vortex_data_path_widget.show()
            #self.skyrim_folder_path_widget.show()
            self.skyrim_folder_path_widget.hide()
            self.mo2_base_path_widget.hide()
            self.mo2_profile_widget.hide()
            self.plugins_txt_path_widget.hide()
        else:
            self.skyrim_folder_path_widget.show()
            self.plugins_txt_path_widget.show()
            self.vortex_data_path_widget.hide()
            self.mo2_base_path_widget.hide()
            self.mo2_profile_widget.hide()
        self.cell_master_clicked()
        self.persistent_ids_clicked()

        self.save_settings_to_file()

        if key in ('show_esms', 'show_cells', 'enable_cell_changed_filter', 'enable_interior_cell_filter', 
                   'filter_worldspaces', 'filter_weathers', 'show_dlls', 'generate_cell_master', 'reset',
                   'left_hidden_columns', 'right_hidden_columns', 'filter_seq', 'filter_pex'):
            self.need_to_rebuild_lists.emit()
        
    def get_settings_from_file(self):
        try:
            with open('ESLifier_Data/settings.json', 'r', encoding='utf-8') as f:
                settings: dict = json.load(f)
                if 'mo2_mode' in settings:
                    settings['mod_manager_mode'] = 2 if settings.pop('mo2_mode') else 1
                return settings
        except:
            return {}