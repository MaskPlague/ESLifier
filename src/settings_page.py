import sys
import json

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon, QPalette, QColor
from PyQt6.QtWidgets import (QMainWindow, QApplication, QHBoxLayout, QVBoxLayout, QLabel, 
                             QWidget, QPushButton, QLineEdit, QMenuBar, QSpacerItem, QStackedLayout, QDialog, QFileDialog)

from QtToggle import QtToggle

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
        #self.setLayout(self.settings_layout)
        #self.setContentsMargins(100,50,100,50)
        #self.setMaximumWidth(1000)
        self.setLayout(h_base_layout)

        self.settings = self.get_settings_from_file()

        self.skyrim_folder_path_widget_init()
        self.output_folder_path_widget_init()
        self.update_header_widget_init()
        self.show_plugins_with_cells_widget_init()
        
        self.update_settings(self)

        settings_layout.addWidget(self.skyrim_folder_path_widget)
        settings_layout.addWidget(self.output_folder_path_widget)
        settings_layout.addWidget(self.update_header_widget)
        settings_layout.addWidget(self.show_plugins_with_cells_widget)
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
        print('clicked skyrim folder path')

    def output_folder_path_clicked(self):
        print('clicked output folder path')

    def skyrim_folder_path_widget_init(self):
        skyrim_folder_path_layout = QHBoxLayout()
        self.skyrim_folder_path_widget = QWidget()
        self.skyrim_folder_path_widget.setToolTip("This should be the path to your Skyrim Special Edition folder that holds SkyrimSE.exe.")
        skyrim_folder_path_label = QLabel("Skyrim Folder Path")
        self.skyrim_folder_path = QLineEdit()
        skyrim_folder_path_button = self.button_maker('Explore...', self.skyrim_folder_path_clicked, 60)

        self.skyrim_folder_path_widget.setLayout(skyrim_folder_path_layout)
        skyrim_folder_path_layout.addWidget(skyrim_folder_path_label)
        skyrim_folder_path_layout.addSpacing(30)
        skyrim_folder_path_layout.addWidget(self.skyrim_folder_path)
        skyrim_folder_path_layout.addSpacing(10)
        skyrim_folder_path_layout.addWidget(skyrim_folder_path_button)
        
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
        output_folder_path_button = self.button_maker('Explore...', self.output_folder_path_clicked, 60)

        self.output_folder_path_widget.setLayout(output_folder_path_layout)
        output_folder_path_layout.addWidget(output_folder_path_label)
        output_folder_path_layout.addSpacing(30)
        output_folder_path_layout.addWidget(self.output_folder_path)
        output_folder_path_layout.addSpacing(10)
        output_folder_path_layout.addWidget(output_folder_path_button)

        self.output_folder_path.setPlaceholderText('C:\\Path\\To\\Skyrim Special Edition\\')
        self.output_folder_path.setToolTip("Set where you want the output folder 'ESLifier Ouput' to be generated.")
        self.output_folder_path.setMinimumWidth(400)
        if 'output_folder_path' in self.settings.keys():
            self.output_folder_path.setText(self.settings['output_folder_path'])
        else:
            self.settings['output_folder_path'] = ''

    def update_header_widget_init(self):
        update_header_layout = QHBoxLayout()
        self.update_header_widget = QWidget()
        self.update_header_widget.setToolTip("Allow scanning and patching to use the new 1.71 header.\nRequires Backported Extended ESL Support on Skyrim versions below 1.6.1130.") #TODO: decide this description
        update_header_label = QLabel("Allow Form IDs below 0x000800 + Update plugin headers to 1.71")
        self.update_header_toggle = QtToggle()
        self.update_header_toggle.setChecked(True)
        self.update_header_widget.setLayout(update_header_layout)
        update_header_layout.addWidget(update_header_label)
        update_header_layout.addSpacing(30)
        update_header_layout.addWidget(self.update_header_toggle)

    def show_plugins_with_cells_widget_init(self):
        show_plugins_with_cells_layout = QHBoxLayout()
        self.show_plugins_with_cells_widget = QWidget()
        self.show_plugins_with_cells_widget.setToolTip('Show or hide plugins with CELL records.')
        show_plugins_with_cells_label = QLabel("Show plugins with CELL records")
        self.show_plugins_with_cells_toggle = QtToggle()
        self.show_plugins_with_cells_toggle.setChecked(True)
        self.show_plugins_with_cells_widget.setLayout(show_plugins_with_cells_layout)
        show_plugins_with_cells_layout.addWidget(show_plugins_with_cells_label)
        show_plugins_with_cells_layout.addSpacing(30)
        show_plugins_with_cells_layout.addWidget(self.show_plugins_with_cells_toggle)

    def save_settings_to_file(self):
        self.update_settings(self, self)
        with open('ESLifier_Data/settings.json', 'w+', encoding='utf-8') as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=4)

    def update_settings(_, self):
        self.settings['skyrim_folder_path'] = self.skyrim_folder_path.text()
        self.settings['output_folder_path'] = self.output_folder_path.text()
        self.settings['update_header'] = self.update_header_toggle.isChecked()
        self.settings['show_cells'] = self.show_plugins_with_cells_toggle.isChecked()
        print(self.settings)
        pass
        
    def get_settings_from_file(self):
        try:
            with open('ESLifier_Data/settings.json', 'r') as f:
                settings = json.load(f)
                return settings
        except:
            return {}