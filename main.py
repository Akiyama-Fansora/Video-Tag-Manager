# main.py - 程序启动入口
import sys
from PyQt5.QtWidgets import QApplication
from folder_video_manager import FolderVideoManager

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FolderVideoManager()
    window.show()
    sys.exit(app.exec_())