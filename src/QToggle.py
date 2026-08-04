from PyQt6.QtCore import Qt, QRect, QPoint
from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtGui import QPainter, QColor

class QtToggle(QCheckBox):
    def __init__(
        self,
        width = 30,
        bg_color = 'Light Grey',
        circle_color = 'Grey',
        active_color = 'palegreen', #'White'
        partial_color = 'orange',
        tri_state = False
    ):
        super().__init__()
        
        self.setFixedWidth(width)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._bg_color = bg_color
        self._circle_color = circle_color
        self._active_color = active_color
        self._partial_color = partial_color
        self._tri_state = tri_state
        self.setTristate(tri_state)

    def hitButton(self, pos: QPoint):
        return self.contentsRect().contains(pos)

    def nextCheckState(self):
        state = self.checkState()
        if self._tri_state:
            if state == Qt.CheckState.Unchecked:
                self.setCheckState(Qt.CheckState.PartiallyChecked)
            elif state == Qt.CheckState.PartiallyChecked:
                self.setCheckState(Qt.CheckState.Checked)
            else:
                self.setCheckState(Qt.CheckState.Unchecked)
        else:
            if state == Qt.CheckState.Unchecked:
                self.setCheckState(Qt.CheckState.Checked)
            else:
                self.setCheckState(Qt.CheckState.Unchecked)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.setPen(Qt.PenStyle.NoPen)

        rect = QRect(0,0, self.width(), self.height())

        state = self.checkState()

        circle_size = self.height() - 4

        if state == Qt.CheckState.Unchecked: #Left
            p.setBrush(QColor(self._bg_color))
            p.drawRoundedRect(0, 0, rect.width(), self.height(), self.height() / 2, self.height() / 2)

            p.setBrush(QColor(self._circle_color))
            p.drawEllipse(2, 2, circle_size, circle_size)

        elif state == Qt.CheckState.PartiallyChecked: #Middle
            p.setBrush(QColor(self._partial_color))
            p.drawRoundedRect(0, 0, rect.width(), self.height(), self.height() / 2, self.height() / 2)

            p.setBrush(QColor(self._circle_color))
            x_center = (self.width() - circle_size) / 2
            p.drawEllipse(int(x_center), 2, circle_size, circle_size)

        elif state == Qt.CheckState.Checked: #Right
            p.setBrush(QColor(self._active_color))
            p.drawRoundedRect(0, 0, rect.width(), self.height(), self.height() / 2, self.height() / 2)

            p.setBrush(QColor(self._circle_color))
            x_right = self.width() - circle_size - 2
            p.drawEllipse(x_right, 2, circle_size, circle_size)
        
        p.end()

    def change_color(self, bg_color='Light Grey', circle_color='Grey', active_color='palegreen'):
        self._circle_color = circle_color
        self._active_color = active_color
        self._bg_color = bg_color
        