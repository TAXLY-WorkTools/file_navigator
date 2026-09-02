"""
模板库管理对话框
"""

import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QInputDialog, QFileDialog, QAbstractItemView, QLabel
)
from PyQt5.QtCore import Qt, pyqtSignal

from core.template_library import TemplateLibrary


class TemplateLibraryDialog(QDialog):
    """模板库管理对话框"""

    load_template_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📚 模板库管理")
        self.resize(600, 400)
        self.setModal(True)

        self._init_ui()
        self._refresh_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # ---------- 工具栏 ----------
        toolbar = QHBoxLayout()

        self.btn_load = QPushButton("📂 加载")
        self.btn_load.clicked.connect(self._load_selected)
        self.btn_load.setToolTip("加载选中的模板到编辑器")

        self.btn_rename = QPushButton("✏️ 重命名")
        self.btn_rename.clicked.connect(self._rename_selected)
        self.btn_rename.setToolTip("重命名选中的模板")

        self.btn_delete = QPushButton("🗑️ 删除")
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_delete.setToolTip("删除选中的模板")

        self.btn_export = QPushButton("📤 导出")
        self.btn_export.clicked.connect(self._export_selected)
        self.btn_export.setToolTip("导出选中的模板为 JSON 文件")

        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.clicked.connect(self._refresh_list)

        toolbar.addWidget(self.btn_load)
        toolbar.addWidget(self.btn_rename)
        toolbar.addWidget(self.btn_delete)
        toolbar.addWidget(self.btn_export)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_refresh)

        layout.addLayout(toolbar)

        # ---------- 表格 ----------
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["#", "模板名称", "文件夹数", "创建时间"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)

        # 双击加载
        self.table.doubleClicked.connect(self._on_double_click)

        layout.addWidget(self.table)

        # ---------- 底部提示 ----------
        tip = QLabel("💡 双击模板名称可直接加载到编辑器")
        tip.setStyleSheet("color: #7a8a9e; font-size: 12px; padding: 4px 0;")
        layout.addWidget(tip)

        # ---------- 关闭按钮 ----------
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        self.btn_close = QPushButton("❌ 关闭")
        self.btn_close.clicked.connect(self.reject)
        close_layout.addWidget(self.btn_close)
        layout.addLayout(close_layout)

    def _refresh_list(self):
        """刷新模板列表"""
        templates = TemplateLibrary.load_index()
        self.table.setRowCount(len(templates))

        for row, t in enumerate(templates):
            name = t.get('name', '')
            folder_count = t.get('folder_count', 0)
            created = t.get('created', '')

            self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.setItem(row, 2, QTableWidgetItem(str(folder_count)))
            self.table.setItem(row, 3, QTableWidgetItem(created))

        if templates:
            self.table.selectRow(0)

    def _get_selected_name(self) -> str:
        """获取选中的模板名称"""
        row = self.table.currentRow()
        if row < 0:
            return ''
        item = self.table.item(row, 1)
        if not item:
            return ''
        return item.text()

    def _load_selected(self):
        """加载选中的模板"""
        name = self._get_selected_name()
        if not name:
            QMessageBox.warning(self, "提示", "请先选择一个模板")
            return
        self.load_template_signal.emit(name)
        self.accept()

    def _on_double_click(self):
        """双击表格加载"""
        self._load_selected()

    def _rename_selected(self):
        """重命名选中的模板"""
        name = self._get_selected_name()
        if not name:
            QMessageBox.warning(self, "提示", "请先选择一个模板")
            return

        new_name, ok = QInputDialog.getText(
            self, "重命名模板",
            f"将「{name}」重命名为：",
            text=name
        )
        if ok and new_name and new_name.strip():
            if new_name.strip() == name:
                return
            if TemplateLibrary.rename_template(name, new_name.strip()):
                self._refresh_list()
                QMessageBox.information(self, "成功", f"模板已重命名为「{new_name.strip()}」")
            else:
                QMessageBox.warning(self, "失败", "重命名失败，请检查名称是否已存在")

    def _delete_selected(self):
        """删除选中的模板"""
        name = self._get_selected_name()
        if not name:
            QMessageBox.warning(self, "提示", "请先选择一个模板")
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确认删除模板「{name}」？\n此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if TemplateLibrary.delete_template(name):
                self._refresh_list()
                QMessageBox.information(self, "成功", f"模板「{name}」已删除")
            else:
                QMessageBox.warning(self, "失败", "删除失败")

    def _export_selected(self):
        """导出选中的模板"""
        name = self._get_selected_name()
        if not name:
            QMessageBox.warning(self, "提示", "请先选择一个模板")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"导出模板「{name}」",
            f"{name}.json",
            "JSON 文件 (*.json)"
        )
        if not file_path:
            return

        if TemplateLibrary.export_template(name, file_path):
            QMessageBox.information(self, "成功", f"模板已导出：{file_path}")
        else:
            QMessageBox.warning(self, "失败", "导出失败")