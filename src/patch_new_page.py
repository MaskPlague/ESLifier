import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QHBoxLayout, QVBoxLayout, QLabel, 
                             QWidget, QPushButton, QLineEdit, QSpacerItem,)

from scanner import scanner
from dependency_getter import dependecy_getter
from list_compacted_unpatched import list_compacted_unpatched
from list_unpatched_files import list_unpatched

#patched dict - hold key patched name, values patched files do a scan and compare old dict to new dict
class patch_new(QWidget):
    def __init__(self):
        super().__init__()
        self.skyrim_folder_path = ''
        self.create()

    def create(self):
        find_button = QPushButton("Find Unpatched Files")
        find_button.clicked.connect(self.scan_and_find)
        patch_button = QPushButton("Patch Selected")

        eslifier_compacted_label = QLabel("ESLifier Compacted With Unpatched Files")
        unpatched_files_label = QLabel("Unpatched Files")

        self.eslifier_compacted_list = list_compacted_unpatched()
        self.unpatched_files_list = list_unpatched()

        h_layout = QHBoxLayout()
        h_widget = QWidget()
        h_widget.setLayout(h_layout)

        v_layout_1 = QVBoxLayout()
        self.setLayout(v_layout_1)

        v_layout_1.addWidget(find_button)
        v_layout_1.addWidget(h_widget)
        v_layout_1.addWidget(patch_button)
        v_layout_1.addSpacing(22)

        v_layout_2 = QVBoxLayout()
        v_widget_2 = QWidget()
        v_widget_2.setLayout(v_layout_2)
        v_layout_2.addWidget(eslifier_compacted_label)
        v_layout_2.addWidget(self.eslifier_compacted_list)
        
        v_layout_3 = QVBoxLayout()
        v_widget_3 = QWidget()
        v_widget_3.setLayout(v_layout_3)
        v_layout_3.addWidget(unpatched_files_label)
        v_layout_3.addWidget(self.unpatched_files_list)

        h_layout.addWidget(v_widget_2)
        h_layout.addSpacing(20)
        h_layout.addWidget(v_widget_3)


        h_layout.setContentsMargins(0,0,0,0)
        v_layout_2.setContentsMargins(0,11,0,1)
        v_layout_3.setContentsMargins(0,11,0,1)

        v_layout_1.setContentsMargins(21,11,21,1)

    def scan_and_find(self):
        print('Scanning All Files:')
        scanner(self.skyrim_folder_path)
        print('Gettings Dependencies')
        dependecy_getter.scan(self.skyrim_folder_path)
        print('Gettings New Dependencies and Files')
        self.find()

        self.unpatched_files_list.create()
        self.eslifier_compacted_list.create()

    def find(self):
        try:
            with open("ESLifier_Data/compacted_and_patched.json", 'r', encoding='utf-8') as f:
                compacted_and_patched = json.load(f)
            with open("ESLifier_Data/file_masters.json", 'r', encoding='utf-8') as f:
                file_masters = json.load(f)
            with open("ESLifier_Data/dependency_dictionary.json", 'r', encoding='utf-8') as f: 
                dependencies = json.load(f)
        except Exception as e:
            return {}
        
        new_files = {}
        new_dependencies = {}

        for key, values in compacted_and_patched.items():
            if key in file_masters.keys(): 
                file_masters_list = file_masters[key]
            if key in dependencies.keys(): 
                dependencies_list = dependencies[key]
            if file_masters_list: 
                new_files[key] = []
            if dependencies_list: 
                new_dependencies[key] = []
            
            for value in file_masters_list: 
                if value.lower() not in values: new_files[key].append(value)

            for value in dependencies_list: 
                if value.lower() not in values: new_dependencies[key].append(value)

        mod_list = [key for key in new_dependencies.keys()]
        self.eslifier_compacted_list.mod_list = mod_list
        self.unpatched_files_list.file_dictionary = new_files


            


        

        

        

        