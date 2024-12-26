import sys


from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon, QPalette, QColor
from PyQt6.QtWidgets import (QMainWindow, QApplication, QHBoxLayout, QVBoxLayout, QLabel, 
                             QWidget, QPushButton, QLineEdit, QMenuBar, QSpacerItem, QStackedLayout,)

from listE import ListEslify
from listC import ListCompactable

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("ESLifier")

        mainMenuAction = QAction("Main", self)
        mainMenuAction.triggered.connect(self.mainSelected)

        settingMenuAction = QAction("Settings", self)
        settingMenuAction.triggered.connect(self.settingsSelected)

        topMenu = QMenuBar()
        topMenu.addAction(mainMenuAction)
        topMenu.addAction(settingMenuAction)
        topMenu.setStyleSheet("""
            QMenuBar {
                background-color: rgb(70,70,70);
                color: rgb(255,255,255);
                border-bottom: 1px solid rgb(255,255,255)
            }
            QMenuBar::item {
                background-color: rgb(70,70,70);
                color: rgb(255,255,255);
            }
            QMenuBar::item::selected {
                background-color: rgb(100,100,100);
            }
            """)

        self.createMainMenu()
        self.createSettingsMenu()
    
        self.tabs.addWidget(self.mainWidget)
        self.tabs.addWidget(self.settingsWidget)
        self.tabs.setCurrentIndex(0)

        displayWidget = QWidget()
        displayWidget.setLayout(self.tabs)
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("Gray"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("Black"))
        palette.setColor(QPalette.ColorRole.Button, QColor("Light Grey"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("White"))
        self.setPalette(palette)

        self.setCentralWidget(displayWidget)
        self.setMenuBar(topMenu)
    
    def createMainMenu(self):
        self.eslify = QLabel("ESLify")
        self.compact = QLabel("Compact + ESLify")
        self.infoE = QLabel("i")
        self.infoE.setToolTip("List of plugins that meet ESL conditions.")
        self.infoC = QLabel("i")
        self.infoC.setToolTip("List of plugins that can be compacted to fit ESL conditions." +
                         "\nThe \'Compact Selected\' button will also ESL the selected plugin(s).")

        self.listE = ListEslify()
        self.listC = ListCompactable()

        self.buttonEslify = QPushButton()
        self.buttonEslify.setText("ESLify Selected")

        self.buttonCompact = QPushButton()
        self.buttonCompact.setText("Compact/ESLify Selected")

        self.buttonSearch = QPushButton()
        self.buttonSearch.setText("Search Mods")

        self.filterE = QLineEdit()
        self.filterE.setPlaceholderText("Filter")
        self.filterE.setToolTip("Search Bar")
        self.filterE.setMinimumWidth(50)
        self.filterE.setMaximumWidth(150)
        self.filterE.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.filterE.setClearButtonEnabled(True)
        self.filterE.textChanged.connect(self.searchE)

        self.filterC = QLineEdit()
        self.filterC.setPlaceholderText("Filter")
        self.filterC.setMinimumWidth(50)
        self.filterC.setMaximumWidth(150)
        self.filterC.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.filterC.setClearButtonEnabled(True)
        self.filterC.textChanged.connect(self.searchC)

        self.mainLayout = QVBoxLayout()
        self.settingsLayout = QVBoxLayout()
        self.tabs = QStackedLayout()

        self.vLayout1 =  QVBoxLayout()
        self.vLayout2 =  QVBoxLayout()
        
        self.hLayout1 = QHBoxLayout()

        #Top of left Column
        self.hLayout2 = QHBoxLayout()
        self.hLayout2.addWidget(self.eslify)
        self.hLayout2.addWidget(self.infoE)
        self.hLayout2.setAlignment(Qt.AlignmentFlag.AlignLeft)

        #Bottom of left Column
        self.hLayout3 = QHBoxLayout()
        self.hLayout3.addWidget(self.buttonEslify)
        self.hLayout3.addWidget(self.filterE)


        #Top of right Column
        self.hLayout4 = QHBoxLayout()
        self.hLayout4.addWidget(self.compact)
        self.hLayout4.addWidget(self.infoC)
        self.hLayout4.setAlignment(Qt.AlignmentFlag.AlignLeft)

        #Bottom of right Column
        self.hLayout5 = QHBoxLayout()
        self.hLayout5.addWidget(self.buttonCompact)
        self.hLayout5.addWidget(self.filterC)

        #Left Column
        self.hLayout1.addLayout(self.vLayout1)
        self.vLayout1.addLayout(self.hLayout2)
        self.vLayout1.addWidget(self.listE)
        self.vLayout1.addLayout(self.hLayout3)

        spacer = QSpacerItem(20, self.height())
        self.hLayout1.addSpacerItem(spacer)

        #Right Column
        self.hLayout1.addLayout(self.vLayout2)
        self.vLayout2.addLayout(self.hLayout4)
        self.vLayout2.addWidget(self.listC)
        self.vLayout2.addLayout(self.hLayout5)

        self.mainLayout.addWidget(self.buttonSearch)
        self.mainLayout.addLayout(self.hLayout1)

        self.hLayout1.setContentsMargins(0,20,0,20)
        self.vLayout1.setContentsMargins(10,0,10,0)
        self.vLayout2.setContentsMargins(10,0,10,0)

        self.mainWidget = QWidget()
        self.mainWidget.setLayout(self.mainLayout)

    def createSettingsMenu(self):
        self.settingsWidget = QWidget()
        self.settingsWidget.setLayout(self.settingsLayout)

    def mainSelected(self):
        self.tabs.setCurrentIndex(0)

    def settingsSelected(self):
        self.tabs.setCurrentIndex(1)

    def searchE(self):
        if len(self.filterE.text()) > 0:
            items = self.listE.findItems(self.filterE.text(), Qt.MatchFlag.MatchContains)
            if len(items) > 0:
                for i in range(self.listE.rowCount()):
                    self.listE.setRowHidden(i, False if (self.listE.item(i,0) in items) else True)
        else:
            for i in range(self.listE.rowCount()):
                self.listE.setRowHidden(i, False)

    def searchC(self):
        if len(self.filterC.text()) > 0:
            items = self.listC.findItems(self.filterC.text(), Qt.MatchFlag.MatchContains)
            if len(items) > 0:
                for i in range(self.listC.rowCount()):
                    self.listC.setRowHidden(i, False if (self.listC.item(i,0) in items) else True)
        else:
            for i in range(self.listC.rowCount()):
                self.listC.setRowHidden(i, False)
        






app = QApplication(sys.argv)
w = MainWindow()
w.show()
app.exec()