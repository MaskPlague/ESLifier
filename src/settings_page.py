import sys
import json

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon, QPalette, QColor
from PyQt6.QtWidgets import (QMainWindow, QApplication, QHBoxLayout, QVBoxLayout, QLabel, 
                             QWidget, QPushButton, QLineEdit, QMenuBar, QSpacerItem, QStackedLayout, QDialog, QFileDialog)
#TODO: fix scaling on width of widgets
class settings(QWidget):
    def __init__(self):
        super().__init__()
        self.settings_layout = QVBoxLayout()
        self.setLayout(self.settings_layout)
        self.setContentsMargins(100,50,100,50)
        self.settings = self.get_settings_from_file()
        self.skyrim_folder_path_widget_init()
        self.output_folder_path_widget_init()

        self.settings_layout.addWidget(self.skyrim_folder_path_widget)
        self.settings_layout.addWidget(self.output_folder_path_widget)

        self.update_header_layout = QHBoxLayout()
        self.update_header_label = QLabel("Allow Form IDs below 0x000800 + Update plugin headers to 1.71")

        self.show_plugins_with_cells_layout = QHBoxLayout()
        self.show_pluginswith_cells_label = QLabel("Show plugins with CELL records")

        self.exclusions_layout = QHBoxLayout()
        self.exclusions_label = QLabel("Excluded Plugins")

    def skyrim_folder_path_widget_init(self):
        skyrim_folder_path_layout = QHBoxLayout()
        self.skyrim_folder_path_widget = QWidget()
        self.skyrim_folder_path_widget.setToolTip("This should be the path to your Skyrim Special Edition folder that holds SkyrimSE.exe.")
        skyrim_folder_path_label = QLabel("Skyrim Folder Path")
        self.skyrim_folder_path = QLineEdit()
        self.skyrim_folder_path_widget.setLayout(skyrim_folder_path_layout)
        skyrim_folder_path_layout.addWidget(skyrim_folder_path_label)
        skyrim_folder_path_layout.addSpacing(30)
        skyrim_folder_path_layout.addWidget(self.skyrim_folder_path)

        self.skyrim_folder_path.setPlaceholderText('C:\\Path\\To\\Skyrim Special Edition\\')
        self.skyrim_folder_path.setMinimumWidth(400)
        if 'skyrim_folder_path' in self.settings.keys():
            self.skyrim_folder_path.setText(self.settings['skyrim_folder_path'])
        else:
            self.settings['skyrim_folder_path'] = ''

    def output_folder_path_widget_init(self):
        output_folder_path_layout = QHBoxLayout()
        self.output_folder_path_widget = QWidget()
        self.output_folder_path_widget.setToolTip("This should be the path to your Skyrim Special Edition folder that holds SkyrimSE.exe.")
        output_folder_path_label = QLabel("Output Folder Path")
        self.output_folder_path = QLineEdit()
        self.output_folder_path_widget.setLayout(output_folder_path_layout)
        output_folder_path_layout.addWidget(output_folder_path_label)
        output_folder_path_layout.addSpacing(30)
        output_folder_path_layout.addWidget(self.output_folder_path)

        self.output_folder_path.setPlaceholderText('C:\\Path\\To\\Skyrim Special Edition\\')
        self.output_folder_path.setToolTip("This should be the path to your Skyrim Special Edition folder that holds SkyrimSE.exe.")
        self.output_folder_path.setMinimumWidth(400)
        if 'output_folder_path' in self.settings.keys():
            self.output_folder_path.setText(self.settings['output_folder_path'])
        else:
            self.settings['output_folder_path'] = ''


    def save_settings_to_file(self):
        self.update_settings(self)
        with open('ESLifier_Data/settings.json', 'w+', encoding='utf-8') as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=4)

    def update_settings(self):
        self.settings['skyrim_folder_path'] = self.skyrim_folder_path.text()
        self.settings['output_folder_path'] = self.output_folder_path.text()
        print(self.settings)
        pass
        
    def get_settings_from_file(self):
        try:
            with open('ESLifier_Data/settings.json', 'r') as f:
                settings = json.load(f)
                return settings
        except:
            return {}