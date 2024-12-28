import sys


from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon, QPalette, QColor
from PyQt6.QtWidgets import (QMainWindow, QApplication, QHBoxLayout, QVBoxLayout, QLabel, 
                             QWidget, QPushButton, QLineEdit, QMenuBar, QSpacerItem, QStackedLayout,)

class Settings(QWidget):
    def __init__(self):
        super().__init__()
        self.settingsWidget = QWidget()
        self.settingsLayout = QVBoxLayout()
        self.setLayout(self.settingsLayout)
