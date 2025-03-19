import json
import os
import subprocess
import shutil
import threading

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QWidget, QPushButton, QLineEdit, QMessageBox, QFileDialog
from PyQt6.QtGui import QIcon

from blacklist import blacklist_window

from QToggle import QtToggle
#TODO: popup when resetting bsa is complete
class settings(QWidget):
    def __init__(self):
        super().__init__()
        self.setFocus()
        settings_layout = QVBoxLayout()
        h_base_layout = QHBoxLayout()
        widgetHolder = QWidget()
        widgetHolder.setLayout(settings_layout)
        h_base_layout.addStretch(1)
        h_base_layout.addWidget(widgetHolder)
        h_base_layout.addStretch(1)
        widgetHolder.setMaximumWidth(1000)
        widgetHolder.setMinimumWidth(700)
        self.setLayout(h_base_layout)

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
            "Set where you want the Output Folder 'ESLifier Ouput' to be generated.",
            'C:/Path/To/The/Output/Folder/',
            self.output_folder_path_clicked
        )
        self.plugins_txt_path_widget, self.plugins_txt_path = self.create_path_widget(
            "Plugins.txt Path",
            "Set this to your modlist\'s plugins.txt",
            'C:/Path/To/plugins.txt',
            self.plugins_txt_path_clicked
        )
        self.bsab_path_widget, self.bsab_path = self.create_path_widget(
            "bsab.exe Path",
            "Set this to BSA Browser's CLI: bsab.exe",
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
        self.mo2_mode_widget.layout().itemAt(1).widget().clicked.connect(self.mo2_mode_clicked)
        self.update_header_widget, self.update_header_toggle = self.create_toggle_widget(
            "Allow Form IDs below 0x000800 + Update plugin headers to 1.71",
            "Allow scanning and patching to use the new 1.71 header.\n"+
            "Requires Backported Extended ESL Support on Skyrim versions below 1.6.1130.\n"+
            "Changing this settings requires a re-scan.",
            "update_header"
        )
        self.scan_esms_widget, self.scan_esms_toggle = self.create_toggle_widget(
            "Scan ESM Plugins",
            "Scan and include ESM plugins (.esm/ESM flagged).\n"+
            "Changing this setting will require a re-scan.",
            "scan_esms"
        )
        self.show_plugins_with_cells_widget, self.show_plugins_with_cells_toggle = self.create_toggle_widget(
            "Show plugins with new CELL records",
            "Show or hide plugins with new CELL records.\n"+
            "Enabling this setting will require a re-scan if you scanned with it off.",
            "show_cells"
        )
        self.enable_cell_changed_filter_widget, self.enable_cell_changed_filter_toggle = self.create_toggle_widget(
            "Hide plugins with new CELL records that are overwriten",
            "Hide plugins with new CELL records that have been changed by a dependent plugin.\n"+
            "Disabling this filter will require a re-scan.",
            "enable_cell_changed_filter"
        )
        self.enable_interior_cell_filter_widget, self.enable_interior_cell_filter_toggle = self.create_toggle_widget(
            "Hide plugins with new interior CELL records",
            "Hide plugins with new interior CELL records as they can have issues when reloading\n"+
            "a save without restarting the game. Disabling this filter will require a re-scan.",
            "enable_interior_cell_filter"
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
            "Only use this button when you have updated a mod and/or deleted the ESLifier Ouput.",
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

        settings_layout.addWidget(self.skyrim_folder_path_widget)
        settings_layout.addWidget(self.output_folder_path_widget)
        settings_layout.addWidget(self.plugins_txt_path_widget)
        settings_layout.addWidget(self.bsab_path_widget)
        settings_layout.addWidget(self.mo2_modlist_txt_path_widget)
        settings_layout.addWidget(self.mo2_mode_widget)
        settings_layout.addWidget(self.update_header_widget)
        settings_layout.addWidget(self.scan_esms_widget)
        settings_layout.addWidget(self.show_plugins_with_cells_widget)
        settings_layout.addWidget(self.enable_cell_changed_filter_widget)
        settings_layout.addWidget(self.enable_interior_cell_filter_widget)
        settings_layout.addWidget(self.show_plugins_possibly_refd_by_dlls_widget)
        settings_layout.addWidget(self.reset_extracted_bsa_list_widget)
        settings_layout.addWidget(self.edit_blacklist_widget)
        settings_layout.addWidget(self.open_eslifier_data_widget)
        settings_layout.addWidget(self.clear_form_id_maps_and_compacted_and_patched_widget)
        settings_layout.addWidget(self.reset_settings_widget)
        settings_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.exclusions_layout = QHBoxLayout()
        self.exclusions_label = QLabel("Excluded Plugins")

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
        self.select_file_path(self.file_dialog, "Select the Skyrim Special Edition folder", 'skyrim_folder_path', self.skyrim_folder_path, None)

    def output_folder_path_clicked(self):
        self.select_file_path(self.file_dialog, "Select where you want the ouput folder", 'output_folder_path', self.output_folder_path, None)

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
        button = self.button_maker('Explore...', click_function, 100)

        widget.setLayout(layout)
        layout.addWidget(label)
        layout.addSpacing(10)
        layout.addWidget(line_edit)
        layout.addSpacing(10)
        layout.addWidget(button)

        line_edit.setPlaceholderText(placeholder)
        line_edit.setMinimumWidth(400)
        line_edit.setMaximumWidth(420)
        
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
        layout.addWidget(button)
        return widget
    
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
            "delete the ESLifier Ouput to continue using the program without issue.\n")
        confirm.setWindowTitle("Confirmation")
        confirm.addButton(QMessageBox.StandardButton.Yes)
        confirm.addButton(QMessageBox.StandardButton.Cancel)
        confirm.button(QMessageBox.StandardButton.Cancel).setFocus()
        def accepted():
            confirm.hide()
            if os.path.exists('ESLifier_Data/Form_ID_Maps'):
                shutil.rmtree('ESLifier_Data/Form_ID_Maps')
            if os.path.exists('ESLifier_Data/Cell_IDs'):
                shutil.rmtree('ESLifier_Data/Cell_IDs')
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
            self.plugins_txt_path.clear()
            self.bsab_path.clear()
            self.mo2_modlist_txt_path.clear()
            self.mo2_mode_toggle.setChecked(False)
            self.update_header_toggle.setChecked(True)
            self.scan_esms_toggle.setChecked(False)
            self.show_plugins_with_cells_toggle.setChecked(True)
            self.show_plugins_possibly_refd_by_dlls_toggle.setChecked(False)
            self.enable_cell_changed_filter_toggle.setChecked(True)
            self.enable_interior_cell_filter_toggle.setChecked(False)
            self.update_settings()
        confirm.accepted.connect(acccepted)
        confirm.show()
        
    def set_init_widget_values(self):
        if 'skyrim_folder_path' in self.settings: self.skyrim_folder_path.setText(self.settings['skyrim_folder_path'])
        else: self.settings['skyrim_folder_path'] = ''

        if 'output_folder_path' in self.settings: self.output_folder_path.setText(self.settings['output_folder_path'])
        else: self.settings['output_folder_path'] = ''

        if 'plugins_txt_path' in self.settings: self.plugins_txt_path.setText(self.settings['plugins_txt_path'])
        else: self.settings['plugins_txt_path'] = ''

        if 'bsab_path' in self.settings: self.bsab_path.setText(self.settings['bsab_path'])
        else: self.settings['bsab_path'] = ''

        if 'mo2_modlist_txt_path' in self.settings: self.mo2_modlist_txt_path.setText(self.settings['mo2_modlist_txt_path'])
        else: self.settings['mo2_modlist_txt_path'] = ''

        if 'mo2_mode' in self.settings: self.mo2_mode_toggle.setChecked(self.settings['mo2_mode'])
        else: self.mo2_mode_toggle.setChecked(False)

        if 'update_header' in self.settings: self.update_header_toggle.setChecked(self.settings['update_header'])
        else: self.update_header_toggle.setChecked(True)

        if 'scan_esms' in self.settings: self.scan_esms_toggle.setChecked(self.settings['scan_esms'])
        else: self.scan_esms_toggle.setChecked(False)

        if 'show_cells' in self.settings: self.show_plugins_with_cells_toggle.setChecked(self.settings['show_cells'])
        else: self.show_plugins_with_cells_toggle.setChecked(True)

        if 'enable_cell_changed_filter' in self.settings: self.enable_cell_changed_filter_toggle.setChecked(self.settings['enable_cell_changed_filter'])
        else: self.enable_cell_changed_filter_toggle.setChecked(True)

        if 'enable_interior_cell_filter' in self.settings: self.enable_interior_cell_filter_toggle.setChecked(self.settings['enable_interior_cell_filter'])
        else: self.enable_interior_cell_filter_toggle.setChecked(False)

        if 'show_dlls' in self.settings: self.show_plugins_possibly_refd_by_dlls_toggle.setChecked(self.settings['show_dlls'])
        else: self.show_plugins_possibly_refd_by_dlls_toggle.setChecked(False)
        

    def save_settings_to_file(self):
        settings_file = 'ESLifier_Data/settings.json'
        if not os.path.exists(os.path.dirname(settings_file)):
            os.makedirs(os.path.dirname(settings_file))
        with open(settings_file, 'w+', encoding='utf-8') as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=4)

    def update_settings(self):
        self.settings['skyrim_folder_path'] = self.skyrim_folder_path.text()
        self.settings['output_folder_path'] = self.output_folder_path.text()
        self.settings['plugins_txt_path'] = self.plugins_txt_path.text()
        self.settings['bsab_path'] = self.bsab_path.text()
        self.settings['mo2_modlist_txt_path'] = self.mo2_modlist_txt_path.text()
        self.settings['mo2_mode'] = self.mo2_mode_toggle.isChecked()
        self.settings['update_header'] = self.update_header_toggle.isChecked()
        self.settings['scan_esms'] = self.scan_esms_toggle.isChecked()
        self.settings['show_cells'] = self.show_plugins_with_cells_toggle.isChecked()
        self.settings['enable_cell_changed_filter'] = self.enable_cell_changed_filter_toggle.isChecked()
        self.settings['enable_interior_cell_filter'] = self.enable_interior_cell_filter_toggle.isChecked()
        self.settings['show_dlls'] = self.show_plugins_possibly_refd_by_dlls_toggle.isChecked()

        self.mo2_mode_clicked()
        if self.mo2_mode_toggle.isChecked():
            self.mo2_modlist_txt_path_widget.show()
        else:
            self.mo2_modlist_txt_path_widget.hide()
        self.save_settings_to_file()
        
    def get_settings_from_file(self):
        try:
            with open('ESLifier_Data/settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
                return settings
        except:
            return {}