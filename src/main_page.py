import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QHBoxLayout, QVBoxLayout, QLabel, 
                             QWidget, QPushButton, QLineEdit, QSpacerItem,)

from list_eslify import list_eslable
from list_compact import list_compactable
from scanner import scanner

class main(QWidget):
    def __init__(self):
        super().__init__()
        self.create()
        self.skyrim_folder_path = ''

    def create(self):
        self.eslify = QLabel("ESLify")
        self.compact = QLabel("Compact + ESLify")
        self.info_eslify = QLabel("i")
        self.info_eslify.setToolTip("List of plugins that meet ESL conditions.")
        self.info_compact = QLabel("i")
        self.info_compact.setToolTip("List of plugins that can be compacted to fit ESL conditions." +
                         "\nThe \'Compact Selected\' button will also ESL the selected plugin(s).")

        self.list_eslify = list_eslable()
        self.list_compact = list_compactable()

        self.button_eslify = QPushButton()
        self.button_eslify.setText("ESLify Selected")

        self.button_compact = QPushButton()
        self.button_compact.setText("Compact/ESLify Selected")

        self.button_scan = QPushButton()
        self.button_scan.setText("Scan Mod Files")
        self.button_scan.setToolTip("This will scan the entire Skyrim Special Edition folder.\nThe time taken depends on how many files are present.\nScanning 800k files takes approximately a minute.")
        self.button_scan.clicked.connect(self.scan)
        
        self.filter_eslify = QLineEdit()
        self.filter_eslify.setPlaceholderText("Filter")
        self.filter_eslify.setToolTip("Search Bar")
        self.filter_eslify.setMinimumWidth(50)
        self.filter_eslify.setMaximumWidth(150)
        self.filter_eslify.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.filter_eslify.setClearButtonEnabled(True)
        self.filter_eslify.textChanged.connect(self.searchE)

        self.filter_compact = QLineEdit()
        self.filter_compact.setPlaceholderText("Filter")
        self.filter_compact.setMinimumWidth(50)
        self.filter_compact.setMaximumWidth(150)
        self.filter_compact.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.filter_compact.setClearButtonEnabled(True)
        self.filter_compact.textChanged.connect(self.searchC)

        self.main_layout = QVBoxLayout()
        self.settings_layout = QVBoxLayout()

        self.v_layout1 =  QVBoxLayout()
        self.v_layout2 =  QVBoxLayout()
        
        self.h_layout1 = QHBoxLayout()

        #Top of left Column
        self.h_layout2 = QHBoxLayout()
        self.h_layout2.addWidget(self.eslify)
        self.h_layout2.addWidget(self.info_eslify)
        self.h_layout2.setAlignment(Qt.AlignmentFlag.AlignLeft)

        #Bottom of left Column
        self.h_layout3 = QHBoxLayout()
        self.h_layout3.addWidget(self.button_eslify)
        self.h_layout3.addWidget(self.filter_eslify)


        #Top of right Column
        self.h_layout4 = QHBoxLayout()
        self.h_layout4.addWidget(self.compact)
        self.h_layout4.addWidget(self.info_compact)
        self.h_layout4.setAlignment(Qt.AlignmentFlag.AlignLeft)

        #Bottom of right Column
        self.h_layout5 = QHBoxLayout()
        self.h_layout5.addWidget(self.button_compact)
        self.h_layout5.addWidget(self.filter_compact)

        #Left Column
        self.h_layout1.addLayout(self.v_layout1)
        self.v_layout1.addLayout(self.h_layout2)
        self.v_layout1.addWidget(self.list_eslify)
        self.v_layout1.addLayout(self.h_layout3)

        self.h_layout1.addSpacing(20)

        #Right Column
        self.h_layout1.addLayout(self.v_layout2)
        self.v_layout2.addLayout(self.h_layout4)
        self.v_layout2.addWidget(self.list_compact)
        self.v_layout2.addLayout(self.h_layout5)

        self.main_layout.addWidget(self.button_scan)
        self.main_layout.addLayout(self.h_layout1)

        self.h_layout1.setContentsMargins(0,20,0,20)
        self.v_layout1.setContentsMargins(10,0,10,0)
        self.v_layout2.setContentsMargins(10,0,10,0)

        self.setLayout(self.main_layout)

    def searchE(self):
        if len(self.filter_eslify.text()) > 0:
            items = self.list_eslify.findItems(self.filter_eslify.text(), Qt.MatchFlag.MatchContains)
            if len(items) > 0:
                for i in range(self.list_eslify.rowCount()):
                    self.list_eslify.setRowHidden(i, False if (self.list_eslify.item(i,0) in items) else True)
        else:
            for i in range(self.list_eslify.rowCount()):
                self.list_eslify.setRowHidden(i, False)

    def searchC(self):
        if len(self.filter_compact.text()) > 0:
            items = self.list_compact.findItems(self.filter_compact.text(), Qt.MatchFlag.MatchContains)
            if len(items) > 0:
                for i in range(self.list_compact.rowCount()):
                    self.list_compact.setRowHidden(i, False if (self.list_compact.item(i,0) in items) else True)
        else:
            for i in range(self.list_compact.rowCount()):
                self.list_compact.setRowHidden(i, False)

    def scan(self):
        self.button_scan.setEnabled(False)
        print('Scanning All Files:')
        scanner.start_scan(self.skyrim_folder_path)
        print('Scanning Plugins:')
        
        self.button_scan.setEnabled(True)