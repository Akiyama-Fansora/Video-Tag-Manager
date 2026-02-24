# ui_components.py - 自定义 UI 组件
import os
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QSlider, QStyle, QStyleOptionSlider
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

VIDEO_PATH_ROLE = Qt.UserRole + 1
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.webm', '.m4v'}

class ClickableSlider(QSlider):
    clicked = pyqtSignal(int)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            sr = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
            if sr.contains(event.pos()):
                super().mousePressEvent(event)
            else:
                new_pos = self.minimum() + (self.maximum() - self.minimum()) * (
                    (event.x() - self.contentsMargins().left()) /
                    (self.width() - self.contentsMargins().left() - self.contentsMargins().right())
                )
                self.setValue(int(new_pos))
                self.clicked.emit(self.value())
        else:
            super().mousePressEvent(event)

def create_tag_widget(tag_name, remove_callback):
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)

    label = QLabel(tag_name)
    label.setFont(QFont("SimHei", 10))
    label.setStyleSheet("background-color: #e0e0e0; padding: 3px 6px; border-radius: 4px;")
    layout.addWidget(label)

    delete_btn = QPushButton("×")
    delete_btn.setFixedSize(20, 20)
    delete_btn.setStyleSheet("""
        QPushButton {
            background-color: #ff6b6b;
            color: white;
            border-radius: 10px;
            font-weight: bold;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: #ff5252;
        }
    """)
    delete_btn.clicked.connect(lambda: remove_callback(tag_name))
    layout.addWidget(delete_btn)
    layout.addStretch()

    return widget