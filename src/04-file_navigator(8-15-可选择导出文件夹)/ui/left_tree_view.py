import os
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QTreeView,
    QFileSystemModel, QFrame, QHeaderView, QFileIconProvider
)
from PyQt5.QtCore import QDir, pyqtSignal, QModelIndex, Qt
from PyQt5.QtGui import QIcon


class LeftTreeView(QWidget):
    """左侧浏览区域 - 包含快捷入口 + 文件系统目录树"""
    
    folder_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # ---------- 1. 快速访问（顶部） ----------
        self.quick_access_tree = QTreeWidget()
        self.quick_access_tree.setHeaderHidden(True)
        self.quick_access_tree.setIndentation(16)
        self.quick_access_tree.setAnimated(True)
        self.quick_access_tree.setMaximumHeight(200)
        self.quick_access_tree.itemDoubleClicked.connect(self._on_quick_access_double_click)

        root_item = QTreeWidgetItem(self.quick_access_tree)
        root_item.setText(0, "📌 快速访问")
        root_item.setExpanded(True)
        root_item.setFlags(root_item.flags() & ~Qt.ItemIsSelectable)

        self._add_quick_access_item(root_item, "📂 桌面", self._get_system_folder("Desktop"))
        self._add_quick_access_item(root_item, "📂 下载", self._get_system_folder("Downloads"))
        self._add_quick_access_item(root_item, "📂 文档", self._get_system_folder("Documents"))
        self._add_quick_access_item(root_item, "📂 图片", self._get_system_folder("Pictures"))
        self._add_quick_access_item(root_item, "📂 视频", self._get_system_folder("Videos"))
        self._add_quick_access_item(root_item, "📂 音乐", self._get_system_folder("Music"))

        layout.addWidget(self.quick_access_tree)

        # ---------- 分割线 ----------
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # ---------- 2. 文件系统树 ----------
        self.file_system_view = QTreeView()
        self.file_system_view.setHeaderHidden(True)
        self.file_system_view.setIndentation(20)
        self.file_system_view.setAnimated(True)

        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.rootPath())
        self.model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot | QDir.Drives)
        self.file_system_view.setModel(self.model)
        self.file_system_view.setRootIndex(self.model.index(""))
        for col in range(1, self.model.columnCount()):
            self.file_system_view.hideColumn(col)

        self.file_system_view.doubleClicked.connect(self._on_file_system_double_click)

        layout.addWidget(self.file_system_view)

        self._current_path = ""

    # ==================== 辅助方法 ====================

    def _get_system_folder(self, folder_name: str) -> str:
        home = Path.home()
        mapping = {
            "Desktop": home / "Desktop",
            "Downloads": home / "Downloads",
            "Documents": home / "Documents",
            "Pictures": home / "Pictures",
            "Videos": home / "Videos",
            "Music": home / "Music",
        }
        path = mapping.get(folder_name, home / folder_name)
        return str(path) if path.exists() else ""

    def _add_quick_access_item(self, parent: QTreeWidgetItem, display_name: str, path: str):
        item = QTreeWidgetItem(parent)
        item.setText(0, display_name)
        item.setData(0, Qt.UserRole, path)
        if path and os.path.exists(path):
            icon_provider = QFileIconProvider()
            icon = icon_provider.icon(QFileIconProvider.Folder)
            item.setIcon(0, icon)
        else:
            item.setIcon(0, self.style().standardIcon(self.style().SP_FileIcon))

    # ==================== 事件处理 ====================

    def _on_quick_access_double_click(self, item: QTreeWidgetItem, column: int):
        path = item.data(0, Qt.UserRole)
        if path and os.path.isdir(path):
            self.folder_selected.emit(path)
            self._highlight_in_file_system(path)

    def _on_file_system_double_click(self, index: QModelIndex):
        if not index.isValid():
            return
        file_path = self.model.filePath(index)
        if os.path.isdir(file_path):
            # ⭐ 折叠其他节点
            self._collapse_all_except(index)
            self.folder_selected.emit(file_path)

    # ⭐ 新增折叠方法
    def _collapse_all_except(self, current_index):
        if not current_index.isValid():
            return

        root_index = self.file_system_view.rootIndex()
        for i in range(self.model.rowCount(root_index)):
            index = self.model.index(i, 0, root_index)
            self.file_system_view.collapse(index)

        parent = current_index.parent()
        while parent.isValid():
            self.file_system_view.expand(parent)
            parent = parent.parent()

        self.file_system_view.scrollTo(current_index)

    def _highlight_in_file_system(self, path: str):
        index = self.model.index(path)
        if index.isValid():
            self.file_system_view.setCurrentIndex(index)
            self.file_system_view.scrollTo(index, QTreeView.PositionAtCenter)

    def set_current_folder(self, path: str):
        if os.path.isdir(path):
            self._highlight_in_file_system(path)