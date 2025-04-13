import json
import os
import subprocess
import shutil
import threading

from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QWidget, QPushButton, QLineEdit, QMessageBox, QFileDialog, QFrame
from PyQt6.QtGui import QIcon

from blacklist import blacklist_window

from QToggle import QtToggle
class settings(QWidget):
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

        self.file_dialog = QFileDialog()
        self.file_dialog.setFileMode(QFileDialog.FileMode.Directory)

        self.file_dialog_2 = QFileDialog()
        self.file_dialog_2.setFileMode(QFileDialog.FileMode.ExistingFile)

        self.skyrim_folder_path_widget, self.skyrim_folder_path = self.create_path_widget(
            "Data Folder Path",
            "Set this to your Skyrim Special Edition Data folder that holds Skyrim.esm.",
            'C:/Path/To/Skyrim Special Edition/Data',
            self.skyrim_folder_path_clicked
        )
        self.output_folder_path_widget, self.output_folder_path = self.create_path_widget(
            "Output Folder Path",
            "Set where you want the Output Folder 'ESLifier Compactor Ouput' to be generated.",
            'C:/Path/To/The/Output/Folder/',
            self.output_folder_path_clicked
        )
        self.output_folder_name_widget, self.output_folder_name = self.create_text_input_widget(
            "Output Folder Name",
            "Change this to what you want to be the name of the Output Folder.",
            "ESLifier Compactor Output"
        )
        self.overwrite_path_widget, self.overwrite_path = self.create_path_widget(
            "Overwrite Path",
            "Set this to your modlist\'s overwrite folder",
            'C:/Path/To/Overwrite',
            self.overwrite_path_clicked
        )
        self.plugins_txt_path_widget, self.plugins_txt_path = self.create_path_widget(
            "Plugins.txt Path",
            "Set this to your modlist\'s plugins.txt",
            'C:/Path/To/plugins.txt',
            self.plugins_txt_path_clicked
        )
        self.bsab_path_widget, self.bsab_path = self.create_path_widget(
            "bsab.exe Path",
            "Set this to BSA Browser's CLI: bsab.exe\n"+
            "Do NOT rename 'BSA Browser.exe' to bsab.exe",
            'C:/Path/To/BSA Browser\'s/bsab.exe',
            self.bsab_path_clicked
        )
        self.mo2_modlist_txt_path_widget, self.mo2_modlist_txt_path = self.create_path_widget(
            "Modlist.txt Path",
            "Set this to your profile's modlist.txt",
            'C:/Path/To/MO2/profiles/profile_name/modlist.txt',
            self.mo2_modlist_txt_path_clicked
        )
        self.mo2_mode_widget, self.mo2_mode_toggle = self.create_toggle_widget(
            "Enabled MO2 Mode",
            "MO2 users should not launch this executible through MO2 and\n"+
            "instead enable this setting. This will change the paths and scanner\n"+
            "method to scan the MO2 mods folder and get winning file conflicts.\n"+
            "Launching this program through MO2 drastically slows down the scanner.",
            "mo2_mode"
        )
        self.mo2_mode_widget.layout().itemAt(2).widget().clicked.connect(self.mo2_mode_clicked)
        self.mo2_mode_widget.layout().itemAt(2).widget().clicked.connect(self.skyrim_folder_path.clear)
        self.mo2_mode_widget.layout().itemAt(2).widget().clicked.connect(self.overwrite_path.clear)
        self.update_header_widget, self.update_header_toggle = self.create_toggle_widget(
            "Allow Form IDs below 0x000800 + Update plugin headers to 1.71",
            "Allow scanning and patching to use the new 1.71 header.\n"+
            "Requires Backported Extended ESL Support on Skyrim versions below 1.6.1130.\n"+
            "Changing this settings requires a re-scan.",
            "update_header"
        )
        self.show_esms_widget, self.show_esms_toggle = self.create_toggle_widget(
            "Show ESM Plugins",
            "Show ESM plugins (.esm/ESM flagged).",
            "show_esms"
        )
        self.show_plugins_with_cells_widget, self.show_plugins_with_cells_toggle = self.create_toggle_widget(
            "Show plugins with new CELL records",
            "Show or hide plugins with new CELL records.",
            "show_cells"
        )
        self.enable_cell_changed_filter_widget, self.enable_cell_changed_filter_toggle = self.create_toggle_widget(
            "Hide ESM plugins with new CELL records that are overwritten",
            "Hide ESM plugins with new CELL records that have been changed by a dependent plugin.",
            "enable_cell_changed_filter"
        )
        self.enable_interior_cell_filter_widget, self.enable_interior_cell_filter_toggle = self.create_toggle_widget(
            "Hide plugins with new interior CELL records",
            "Hide plugins with new interior CELL records as they can have issues when reloading\n"+
            "a save without restarting the game.",
            "enable_interior_cell_filter"
        )
        self.enable_worldspaces_filter_widget, self.enable_worldspaces_filter_toggle = self.create_toggle_widget(
            "Hide plugins with new WRLD (worldspace) records",
            "Hide plugins with new worldspaces records as they can have the landscape disappear\n"+
            "(no ground) when flagged as ESL.",
            "filter_worldspaces"
        )
        self.show_plugins_possibly_refd_by_dlls_widget, self.show_plugins_possibly_refd_by_dlls_toggle = self.create_toggle_widget(
            "Show plugins that are in SKSE dlls",
            "Show or hide plugins that may have Form IDs hard-coded in SKSE dlls.",
            "show_dlls"
        )
        self.reset_extracted_bsa_list_widget = self.create_button_widget(
            "Reset Extracted BSA List and Delete Extracted Files",
            'ESLifier uses the Extracted BSA list to ensure that it does not need to\n'+
            'go through the tedious process of extracting all releveant files in BSAs\n'+
            'each time it scans. Use this button if a BSA has new files or you have\n'+
            'deleted a mod that had a BSA.',
            'Reset BSA',
            self.reset_extracted_bsa_list_clicked
        )
        self.blacklist_window = blacklist_window()
        self.edit_blacklist_widget = self.create_button_widget(
            "Remove Plugins From Blacklist",
            'Show window to remove plugins from the blacklist. You can add\n'+
            'plugins to the blacklist by right clicking them on the Main page.',
            'Edit Blacklist',
            self.edit_blacklist_button_clicked
        )
        self.open_eslifier_data_widget = self.create_button_widget(
            "Open ESLifier's Data Folder",
            "This opens the folder where all of the dictionaries and Form ID maps are stored.",
            "Open Folder",
            self.open_eslifier_data
        )
        self.clear_form_id_maps_and_compacted_and_patched_widget = self.create_button_widget(
            "Delete All Form ID Maps and Compacted/Patched History",
            "The Form ID Maps are used for patching any new files and plugins.\n" +
            "The Compacted and Patched History is for getting what files and plugins\n" +
            "are newly added after a mod was compacted and its dependents patched.\n\n" +
            "Only use this button when you have updated a mod and/or deleted the ESLifier Compactor Ouput.",
            "Delete All",
            self.clear_form_id_maps_and_compacted_and_patched_clicked
        )
        self.reset_settings_widget = self.create_button_widget(
            "Reset All Settings",
            None,
            "Reset",
            self.reset_settings_clicked
        )

        self.set_init_widget_values()
        
        self.update_settings()
        
        settings_layout.addWidget(self.mo2_mode_widget)
        settings_layout.addWidget(self.skyrim_folder_path_widget)
        settings_layout.addWidget(self.output_folder_path_widget)
        settings_layout.addWidget(self.output_folder_name_widget)
        settings_layout.addWidget(self.overwrite_path_widget)
        settings_layout.addWidget(self.plugins_txt_path_widget)
        settings_layout.addWidget(self.mo2_modlist_txt_path_widget)
        settings_layout.addWidget(self.bsab_path_widget)

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
        if COLOR_MODE:
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
        column_1.addWidget(self.show_plugins_possibly_refd_by_dlls_widget)
        column_2.addWidget(self.reset_extracted_bsa_list_widget)
        column_2.addWidget(self.edit_blacklist_widget)
        column_2.addWidget(self.open_eslifier_data_widget)
        column_2.addWidget(self.clear_form_id_maps_and_compacted_and_patched_widget)
        column_2.addWidget(self.reset_settings_widget)

        settings_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def button_maker(self, text, function, width):
        button = QPushButton()
        button.setText(text)
        button.clicked.connect(function)
        button.setFixedWidth(width)
        return button
    
    def select_file_path(self, dialog, title, setting_key, line_edit, filter):
        if filter != None:
            path, _ = dialog.getOpenFileName(self, title, self.settings.get(setting_key, ""), filter)
        else:
            path = dialog.getExistingDirectory(self, title, self.settings.get(setting_key, ""))
        if path:
            line_edit.setText(path)
        self.update_settings()
    
    def skyrim_folder_path_clicked(self):
        if not self.mo2_mode_toggle.isChecked():
            self.select_file_path(self.file_dialog, "Select the Skyrim Special Edition Data folder", 'skyrim_folder_path', self.skyrim_folder_path, None)
        else:
            self.select_file_path(self.file_dialog, "Select your MO2 mods folder", 'skyrim_folder_path', self.skyrim_folder_path, None)

    def output_folder_path_clicked(self):
        self.select_file_path(self.file_dialog, "Select where you want the output folder", 'output_folder_path', self.output_folder_path, None)

    def overwrite_path_clicked(self):
        self.select_file_path(self.file_dialog, "Select your MO2 overwrite folder", 'overwrite_path', self.overwrite_path, None)

    def mo2_modlist_txt_path_clicked(self):
        self.select_file_path(self.file_dialog_2, "Select your MO2 profile\'s modlist.txt", 'mo2_modlist_txt_path', self.mo2_modlist_txt_path, "Modlist (modlist.txt)")

    def plugins_txt_path_clicked(self):
        self.select_file_path(self.file_dialog_2, "Select your plugins.txt", 'plugins_txt_path', self.plugins_txt_path, "Load Order (plugins.txt)")

    def bsab_path_clicked(self):
        self.select_file_path(self.file_dialog_2, "Select BSA Browser's bsab.exe", 'bsab_path', self.bsab_path, "BSA Browser CLI (bsab.exe)")

    def create_path_widget(self, label_text, tooltip, placeholder, click_function):
        layout = QHBoxLayout()
        widget = QWidget()
        widget.setToolTip(tooltip)
        label = QLabel(label_text)
        line_edit = QLineEdit()
        line_edit.editingFinished.connect(self.update_settings)
        button = self.button_maker('Explore...', click_function, 100)

        widget.setLayout(layout)
        layout.addWidget(label)
        layout.addSpacing(10)
        layout.addWidget(line_edit)
        layout.addSpacing(10)
        layout.addWidget(button)

        line_edit.setPlaceholderText(placeholder)
        line_edit.setMinimumWidth(400)
        line_edit.setMaximumWidth(550)
        
        return widget, line_edit
    
    def create_toggle_widget(self, label_text, tooltip, setting_key):
        layout = QHBoxLayout()
        widget = QWidget()
        widget.setToolTip(tooltip)
        label = QLabel(label_text)
        toggle = QtToggle()
        toggle.setChecked(self.settings.get(setting_key, False))
        toggle.clicked.connect(self.update_settings)
        
        widget.setLayout(layout)
        layout.addWidget(label)
        layout.addSpacing(10)
        layout.addWidget(toggle)

        return widget, toggle

    def mo2_mode_clicked(self):
        if self.mo2_mode_toggle.checkState() == Qt.CheckState.Checked:
            self.skyrim_folder_path_widget.setToolTip("Set this to your Mod Organizer 2 mod's folder that holds all of your installed mods.")
            self.skyrim_folder_path_widget.layout().itemAt(0).widget().setText("MO2 Mod\'s Folder Path")
            self.skyrim_folder_path.setPlaceholderText('C:/Path/To/MO2/mods')
        else:
            self.skyrim_folder_path_widget.setToolTip("Set this to your Skyrim Special Edition Data folder that holds Skyrim.esm.")
            self.skyrim_folder_path_widget.layout().itemAt(0).widget().setText("Data Folder Path")
            self.skyrim_folder_path.setPlaceholderText('C:/Path/To/Skyrim Special Edition/Data')

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
    
    def create_text_input_widget(self, label_text, tooltip, placeholder):
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
            if regex.match(text).hasMatch():
                self.output_folder_name_valid = True
                self.update_settings()
            else:
                QMessageBox.warning(None, "Invalid Name", f"'{text}' is not a valid folder name.")
                line_edit.setFocus()
                self.output_folder_name_valid = False

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
        
        return widget, line_edit
    
    def reset_extracted_bsa_list_clicked(self):
        confirm = QMessageBox()
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setWindowIcon(QIcon(":/images/ESLifier.png"))
        confirm.setStyleSheet("""
            QMessageBox {
                background-color: lightcoral;
            }""")
        confirm.setText(
            "Are you sure you want to reset the Extracted BSA List?\n" +
            "This will cause the next scan to take significantly longer as the BSA files will\n"+ 
            "need to be extracted again and irrelevant script files will need to be filtered.\n\n"+
            "This can take a short bit and will freeze the UI\n"+
            "or you can manually delete the \"bsa_extracted/\" folder\n"+
            "and then click this button.")
        confirm.setWindowTitle("Confirmation")
        confirm.addButton(QMessageBox.StandardButton.Yes)
        confirm.addButton(QMessageBox.StandardButton.Cancel)
        confirm.button(QMessageBox.StandardButton.Cancel).setFocus()
        def accepted():
            confirm.hide()
            if os.path.exists('ESLifier_Data/extracted_bsa.json'):
                os.remove('ESLifier_Data/extracted_bsa.json')
            if os.path.exists('bsa_extracted/'):
                def delete_directory(dir_path):
                    try:
                        shutil.rmtree(dir_path)
                    except Exception as e:
                        pass

                def delete_subdirectories_threaded(parent_dir):
                    threads = []
                    for item in os.listdir(parent_dir):
                        item_path = os.path.join(parent_dir, item)
                        if os.path.isdir(item_path):
                            thread = threading.Thread(target=delete_directory, args=(item_path,))
                            threads.append(thread)
                            thread.start()

                    for thread in threads:
                        thread.join()
                delete_subdirectories_threaded('bsa_extracted/')
        confirm.accepted.connect(accepted)
        confirm.show()

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
            print(f"Error opening file explorer: {e}")

    def clear_form_id_maps_and_compacted_and_patched_clicked(self):
        confirm = QMessageBox()
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setWindowIcon(QIcon(":/images/ESLifier.png"))
        confirm.setStyleSheet("""
            QMessageBox {
                background-color: lightcoral;
            }""")
        confirm.setText(
            "Are you sure you want to delete all of the Form ID Maps and the Compacted and Patched History?\n" +
            "This will prevent the 'Patch New' functionality from working and will require you to manually " +
            "delete the ESLifier Compactor Ouput to continue using the program without issue.\n")
        confirm.setWindowTitle("Confirmation")
        confirm.addButton(QMessageBox.StandardButton.Yes)
        confirm.addButton(QMessageBox.StandardButton.Cancel)
        confirm.button(QMessageBox.StandardButton.Cancel).setFocus()
        def accepted():
            confirm.hide()
            if os.path.exists('ESLifier_Data/Form_ID_Maps'):
                shutil.rmtree('ESLifier_Data/Form_ID_Maps')
            if os.path.exists('ESLifier_Data/compacted_and_patched.json'):
                try:
                    with open('ESLifier_Data/compacted_and_patched.json', 'r', encoding='utf-8') as fcp:
                        compacted_and_patched_dict = json.load(fcp)
                        with open('ESLifier_Data/previously_compacted.json', 'w', encoding='utf-8') as fpc:
                            previously_compacted = [key for key in compacted_and_patched_dict.keys()]
                            json.dump(previously_compacted, fpc, ensure_ascii=False, indent=4)
                            fpc.close()
                        fcp.close()
                    os.remove('ESLifier_Data/compacted_and_patched.json')
                except Exception as e:
                    print("!Error: Failed in Compacted and Patched deletion process.")
                    print(e)

        confirm.accepted.connect(accepted)
        confirm.show()

    def reset_settings_clicked(self):
        confirm = QMessageBox()
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setStyleSheet("""
            QMessageBox {
                background-color: lightcoral;
            }""")
        confirm.setText("Are you sure you want to reset all settings?")
        confirm.setWindowTitle("Confirmation")
        confirm.setWindowIcon(QIcon(":/images/ESLifier.png"))
        confirm.addButton(QMessageBox.StandardButton.Yes)
        confirm.addButton(QMessageBox.StandardButton.Cancel)
        confirm.button(QMessageBox.StandardButton.Cancel).setFocus()
        def acccepted():
            confirm.hide()
            if os.path.exists('ESLifier_Data/settings.json'):
                os.remove('ESLifier_Data/settings.json')
            self.settings.clear()
            self.skyrim_folder_path.clear()
            self.output_folder_path.clear()
            self.output_folder_name.setText('ESLifier Compactor Output')
            self.overwrite_path.clear()
            self.plugins_txt_path.clear()
            self.bsab_path.clear()
            self.mo2_modlist_txt_path.clear()
            self.mo2_mode_toggle.setChecked(False)
            self.update_header_toggle.setChecked(True)
            self.show_esms_toggle.setChecked(True)
            self.show_plugins_with_cells_toggle.setChecked(True)
            self.show_plugins_possibly_refd_by_dlls_toggle.setChecked(False)
            self.enable_cell_changed_filter_toggle.setChecked(True)
            self.enable_interior_cell_filter_toggle.setChecked(False)
            self.enable_worldspaces_filter_toggle.setChecked(True)
            self.update_settings()
        confirm.accepted.connect(acccepted)
        confirm.show()
        
    def set_init_widget_values(self):
        self.skyrim_folder_path.setText(self.settings.get('skyrim_folder_path', ''))
        self.output_folder_path.setText(self.settings.get('output_folder_path', ''))
        self.output_folder_name.setText(self.settings.get('output_folder_name', 'ESLifier Compactor Output'))
        self.overwrite_path.setText(self.settings.get('overwrite_path', ''))
        self.plugins_txt_path.setText(self.settings.get('plugins_txt_path', ''))
        self.bsab_path.setText(self.settings.get('bsab_path', ''))
        self.mo2_modlist_txt_path.setText(self.settings.get('mo2_modlist_txt_path' ,''))
        self.mo2_mode_toggle.setChecked(self.settings.get('mo2_mode', False))
        self.update_header_toggle.setChecked(self.settings.get('update_header', True))
        self.show_esms_toggle.setChecked(self.settings.get('show_esms', True))
        self.show_plugins_with_cells_toggle.setChecked(self.settings.get('show_cells', True))
        self.enable_cell_changed_filter_toggle.setChecked(self.settings.get('enable_cell_changed_filter', True))
        self.enable_interior_cell_filter_toggle.setChecked(self.settings.get('enable_interior_cell_filter', False))
        self.enable_worldspaces_filter_toggle.setChecked(self.settings.get('filter_worldspaces', True))
        self.show_plugins_possibly_refd_by_dlls_toggle.setChecked(self.settings.get('show_dlls', False))

    def save_settings_to_file(self):
        settings_file = 'ESLifier_Data/settings.json'
        if not os.path.exists(os.path.dirname(settings_file)):
            os.makedirs(os.path.dirname(settings_file))
        with open(settings_file, 'w+', encoding='utf-8') as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=4)

    def update_settings(self):
        self.settings['skyrim_folder_path'] = os.path.normpath(self.skyrim_folder_path.text()) if self.skyrim_folder_path.text() != '' else ''
        self.settings['output_folder_path'] = os.path.normpath(self.output_folder_path.text()) if self.output_folder_path.text() != '' else ''
        if self.output_folder_name_valid:
            self.settings['output_folder_name'] = self.output_folder_name.text()
        self.settings['overwrite_path'] = os.path.normpath(self.overwrite_path.text()) if self.overwrite_path.text() != '' else ''
        self.settings['plugins_txt_path'] = os.path.normpath(self.plugins_txt_path.text()) if self.plugins_txt_path.text() != '' else ''
        self.settings['bsab_path'] = os.path.normpath(self.bsab_path.text()) if self.bsab_path.text() != '' else ''
        self.settings['mo2_modlist_txt_path'] = os.path.normpath(self.mo2_modlist_txt_path.text()) if self.mo2_modlist_txt_path.text() != '' else ''
        self.settings['mo2_mode'] = self.mo2_mode_toggle.isChecked()
        self.settings['update_header'] = self.update_header_toggle.isChecked()
        self.settings['show_esms'] = self.show_esms_toggle.isChecked()
        self.settings['show_cells'] = self.show_plugins_with_cells_toggle.isChecked()
        self.settings['enable_cell_changed_filter'] = self.enable_cell_changed_filter_toggle.isChecked()
        self.settings['enable_interior_cell_filter'] = self.enable_interior_cell_filter_toggle.isChecked()
        self.settings['filter_worldspaces'] = self.enable_worldspaces_filter_toggle.isChecked()
        self.settings['show_dlls'] = self.show_plugins_possibly_refd_by_dlls_toggle.isChecked()

        self.mo2_mode_clicked()
        if self.mo2_mode_toggle.isChecked():
            self.mo2_modlist_txt_path_widget.show()
            self.overwrite_path_widget.show()
        else:
            self.mo2_modlist_txt_path_widget.hide()
            self.overwrite_path_widget.hide()
        self.save_settings_to_file()
        
    def get_settings_from_file(self):
        try:
            with open('ESLifier_Data/settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
                return settings
        except:
            return {}