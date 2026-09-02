import sys
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("档案智盘")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())