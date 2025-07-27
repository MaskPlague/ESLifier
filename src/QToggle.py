from PyQt6.QtCore import Qt, QRect, QPoint
from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtGui import QPainter, QColor

class QtToggle(QCheckBox):
    def __init__(
        self,
        width = 30,
        bg_color = 'Light Grey',
        circle_color = 'Grey',
        active_color = 'White'
    ):
        super().__init__()
        
        self.setFixedWidth(width)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._bg_color = bg_color
        self._circle_color = circle_color
        self._active_color = active_color

    def hitButton(self, pos: QPoint):
        return self.contentsRect().contains(pos)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.setPen(Qt.PenStyle.NoPen)

        rect = QRect(0,0, self.width(), self.height())

        if not self.isChecked():
            p.setBrush(QColor(self._bg_color))
            p.drawRoundedRect(0, 0, rect.width(), self.height(), self.height() / 2, self.height() / 2)

            p.setBrush(QColor(self._circle_color))
            p.drawEllipse(2, 2, self.height() - 4 , self.height() - 4)
        else:
            p.setBrush(QColor(self._active_color))
            p.drawRoundedRect(0, 0, rect.width(), self.height(), self.height() / 2, self.height() / 2)

            p.setBrush(QColor(self._circle_color))
            p.drawEllipse(self.width() - (self.height() - 2), 2, self.height() - 4 , self.height() - 4)
        
        p.end()

    def change_color(self, bg_color='Light Grey', circle_color='Grey', active_color='White'):
        self._circle_color = circle_color
        self._active_color = active_color
        self._bg_color = bg_color
        #self.paintEvent(None)
        