import json

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon, QPalette, QColor
from PyQt6.QtWidgets import (QMainWindow, QApplication, QHBoxLayout, QVBoxLayout, QLabel, 
                             QWidget, QPushButton, QLineEdit, QMenuBar, QSpacerItem, QStackedLayout, QDialog, QFileDialog)

from QToggle import QtToggle

#TODO: fix scaling on width of widgets
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

        self.skyrim_folder_path_widget_init()
        self.output_folder_path_widget_init()
        self.update_header_widget_init()
        self.show_plugins_with_cells_widget_init()
        self.show_plugins_with_bsas_widget_init()

        self.set_init_widget_values()
        
        self.update_settings()

        settings_layout.addWidget(self.skyrim_folder_path_widget)
        settings_layout.addWidget(self.output_folder_path_widget)
        settings_layout.addWidget(self.update_header_widget)
        settings_layout.addWidget(self.show_plugins_with_cells_widget)
        settings_layout.addWidget(self.show_plugins_with_bsas_widget)
        settings_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.exclusions_layout = QHBoxLayout()
        self.exclusions_label = QLabel("Excluded Plugins")

    def button_maker(self, text, function, width):
        button = QPushButton()
        button.setText(text)
        button.clicked.connect(function)
        button.setFixedWidth(width)
        return button
    
    def skyrim_folder_path_clicked(self):
        path = self.file_dialog.getExistingDirectory(self, "Select the Skyrim Special Edition folder", self.settings['skyrim_folder_path'])
        if path != '':
            self.skyrim_folder_path.setText(path)
        self.update_settings()

    def output_folder_path_clicked(self):
        path = self.file_dialog.getExistingDirectory(self, "Select where you want the ouput folder", self.settings['output_folder_path'])
        if path != '':
            self.output_folder_path.setText(path)
        self.update_settings()

    def skyrim_folder_path_widget_init(self):
        skyrim_folder_path_layout = QHBoxLayout()
        self.skyrim_folder_path_widget = QWidget()
        self.skyrim_folder_path_widget.setToolTip("Set this to your Skyrim Special Edition folder that holds SkyrimSE.exe.")
        skyrim_folder_path_label = QLabel("Skyrim Folder Path")
        self.skyrim_folder_path = QLineEdit()
        skyrim_folder_path_button = self.button_maker('Explore...', self.skyrim_folder_path_clicked, 60)

        self.skyrim_folder_path_widget.setLayout(skyrim_folder_path_layout)
        skyrim_folder_path_layout.addWidget(skyrim_folder_path_label)
        skyrim_folder_path_layout.addSpacing(30)
        skyrim_folder_path_layout.addWidget(self.skyrim_folder_path)
        skyrim_folder_path_layout.addSpacing(10)
        skyrim_folder_path_layout.addWidget(skyrim_folder_path_button)
        
        self.skyrim_folder_path.setPlaceholderText('C:/Path/To/Skyrim Special Edition')
        self.skyrim_folder_path.setMinimumWidth(400)
        

    def output_folder_path_widget_init(self):
        output_folder_path_layout = QHBoxLayout()
        self.output_folder_path_widget = QWidget()
        self.output_folder_path_widget.setToolTip("Set where you want the output folder 'ESLifier Ouput' to be generated.")
        output_folder_path_label = QLabel("Output Folder Path")
        self.output_folder_path = QLineEdit()
        output_folder_path_button = self.button_maker('Explore...', self.output_folder_path_clicked, 60)

        self.output_folder_path_widget.setLayout(output_folder_path_layout)
        output_folder_path_layout.addWidget(output_folder_path_label)
        output_folder_path_layout.addSpacing(30)
        output_folder_path_layout.addWidget(self.output_folder_path)
        output_folder_path_layout.addSpacing(10)
        output_folder_path_layout.addWidget(output_folder_path_button)

        self.output_folder_path.setPlaceholderText('C:/Path/To/The/Output/Folder/')
        self.output_folder_path.setMinimumWidth(400)
        

    def update_header_widget_init(self):
        update_header_layout = QHBoxLayout()
        self.update_header_widget = QWidget()
        self.update_header_widget.setToolTip("Allow scanning and patching to use the new 1.71 header.\nRequires Backported Extended ESL Support on Skyrim versions below 1.6.1130.\nChanging this settings requires a re-scan.") #TODO: decide this description
        update_header_label = QLabel("Allow Form IDs below 0x000800 + Update plugin headers to 1.71")
        self.update_header_toggle = QtToggle()
        self.update_header_toggle.clicked.connect(self.update_settings)
        self.update_header_widget.setLayout(update_header_layout)
        update_header_layout.addWidget(update_header_label)
        update_header_layout.addSpacing(30)
        update_header_layout.addWidget(self.update_header_toggle)
        

    def show_plugins_with_cells_widget_init(self):
        show_plugins_with_cells_layout = QHBoxLayout()
        self.show_plugins_with_cells_widget = QWidget()
        self.show_plugins_with_cells_widget.setToolTip('Show or hide plugins with CELL records.\nEnabling this setting will require a re-scan if you scanned with it off.')
        show_plugins_with_cells_label = QLabel("Show plugins with CELL records")
        self.show_plugins_with_cells_toggle = QtToggle()
        self.show_plugins_with_cells_toggle.clicked.connect(self.update_settings)
        self.show_plugins_with_cells_widget.setLayout(show_plugins_with_cells_layout)
        show_plugins_with_cells_layout.addWidget(show_plugins_with_cells_label)
        show_plugins_with_cells_layout.addSpacing(30)
        show_plugins_with_cells_layout.addWidget(self.show_plugins_with_cells_toggle)

    def show_plugins_with_bsas_widget_init(self):
        show_plugins_with_bsas_layout = QHBoxLayout()
        self.show_plugins_with_bsas_widget = QWidget()
        self.show_plugins_with_bsas_widget.setToolTip('Show or hide plugins that have a BSA file.')
        show_plugins_with_bsas_label = QLabel("Show plugins with BSA files")
        self.show_plugins_with_bsas_toggle = QtToggle()
        self.show_plugins_with_bsas_toggle.clicked.connect(self.update_settings)
        self.show_plugins_with_bsas_widget.setLayout(show_plugins_with_bsas_layout)
        show_plugins_with_bsas_layout.addWidget(show_plugins_with_bsas_label)
        show_plugins_with_bsas_layout.addSpacing(30)
        show_plugins_with_bsas_layout.addWidget(self.show_plugins_with_bsas_toggle)
        

    def set_init_widget_values(self):
        if 'skyrim_folder_path' in self.settings.keys(): self.skyrim_folder_path.setText(self.settings['skyrim_folder_path'])
        else: self.settings['skyrim_folder_path'] = ''

        if 'output_folder_path' in self.settings.keys(): self.output_folder_path.setText(self.settings['output_folder_path'])
        else: self.settings['output_folder_path'] = ''

        if 'update_header' in self.settings.keys(): self.update_header_toggle.setChecked(self.settings['update_header'])
        else: self.update_header_toggle.setChecked(True)

        if 'show_cells' in self.settings.keys(): self.show_plugins_with_cells_toggle.setChecked(self.settings['show_cells'])
        else: self.show_plugins_with_cells_toggle.setChecked(True)

        if 'show_bsas' in self.settings.keys(): self.show_plugins_with_bsas_toggle.setChecked(self.settings['show_bsas'])
        else: self.show_plugins_with_bsas_toggle.setChecked(True)
        

    def save_settings_to_file(self):
        with open('ESLifier_Data/settings.json', 'w+', encoding='utf-8') as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=4)

    def update_settings(self):
        self.settings['skyrim_folder_path'] = self.skyrim_folder_path.text()
        self.settings['output_folder_path'] = self.output_folder_path.text()
        self.settings['update_header'] = self.update_header_toggle.isChecked()
        self.settings['show_cells'] = self.show_plugins_with_cells_toggle.isChecked()
        self.settings['show_bsas'] = self.show_plugins_with_bsas_toggle.isChecked()
        self.save_settings_to_file()
        
    def get_settings_from_file(self):
        try:
            with open('ESLifier_Data/settings.json', 'r') as f:
                settings = json.load(f)
                return settings
        except:
            return {}