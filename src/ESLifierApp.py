import sys


from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QPalette, QColor
from PyQt6.QtWidgets import (QMainWindow, QApplication, QWidget, QMenuBar, QStackedLayout,)

from settingsPage import Settings
from mainPage import main

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        #TODO: Make settings Page
        #TODO: Make a scanner Page?
        #TODO: REALLY need to decide if i'm going to ONLY scan mod folders in the mod manager mods folder or scan the whole sse directory... I think i need to scan sse...
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
        
        self.mainWidget = main()
        self.settingsWidget = Settings()
        self.tabs = QStackedLayout()
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

    def mainSelected(self):
        self.tabs.setCurrentIndex(0)

    def settingsSelected(self):
        self.tabs.setCurrentIndex(1)


app = QApplication(sys.argv)
w = MainWindow()
w.show()
app.exec()