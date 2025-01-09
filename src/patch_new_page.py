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
        self.eslify_dictionary = {}
        self.new_files = {}
        self.new_dependencies = {}
        self.create()

    def create(self):
        scan_and_find_button = QPushButton("Scan All Files + Find Unpatched Files")
        find_button = QPushButton("Find Unpatched Files")
        patch_button = QPushButton("Patch Selected")


        eslifier_compacted_label = QLabel("ESLifier Compacted With Unpatched Files")
        unpatched_files_label = QLabel("Unpatched Files")

        eslifier_compacted_list = list_compacted_unpatched()
        unpacted_files_list = list_unpatched()

        h_layout = QHBoxLayout()
        h_widget = QWidget()
        h_widget.setLayout(h_layout)

        v_layout_1 = QVBoxLayout()
        self.setLayout(v_layout_1)

        v_layout_1.addWidget(scan_and_find_button)
        v_layout_1.addWidget(find_button)
        v_layout_1.addWidget(h_widget)
        v_layout_1.addWidget(patch_button)

        v_layout_2 = QVBoxLayout()
        v_widget_2 = QWidget()
        v_widget_2.setLayout(v_layout_2)
        v_layout_2.addWidget(eslifier_compacted_label)
        v_layout_2.addWidget(eslifier_compacted_list)
        
        v_layout_3 = QVBoxLayout()
        v_widget_3 = QWidget()
        v_widget_3.setLayout(v_layout_3)
        v_layout_3.addWidget(unpatched_files_label)
        v_layout_3.addWidget(unpacted_files_list)

        h_layout.addWidget(v_widget_2)
        h_layout.addWidget(v_widget_3)

    def scan_and_find(self):
        print('Scanning All Files:')
        scanner(self.skyrim_folder_path)
        print('Gettings Dependencies')
        dependecy_getter.scan(self.skyrim_folder_path)
        self.find()

    def find(self):
        try:
            with open("ESLifier_Data/compacted_and_patched.json", 'r') as f:
                compacted_and_patched = json.load(f)
            with open("ESLifier_Data/file_masters.json") as f:
                file_masters = json.load(f)
            with open("ESLifier_Data/dependency_dictionary.json") as f: 
                dependencies = json.load(f)
        except:
            return {}
        
        self.new_files = {}
        self.new_dependencies = {}

        for key, values in compacted_and_patched.items():
            if key.lower() in file_masters.keys(): 
                file_masters_list = file_masters[key]
            if key.lower() in dependencies.keys(): 
                dependencies_list = dependencies[key]
            if file_masters_list: 
                self.new_files[key] = []
            if dependencies_list: 
                self.new_dependencies[key] = []
            
            for value in file_masters_list[key]: 
                if value.lower() not in values: self.new_files[key].append[value.lower()]

            for value in dependencies_list[key]: 
                if value.lower() not in values: self.new_dependencies[key].append[value.lower()]


            


        

        

        

        