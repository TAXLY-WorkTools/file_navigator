"""
导出设置对话框 - 让用户选择导出字段
"""

import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QCheckBox, QGroupBox, QMessageBox,
    QFileDialog, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal

from core.export_config_manager import (
    ExportConfigManager,
    AVAILABLE_FIELDS
)
from ui.folder_selector_dialog import FolderSelectorDialog


class ExportSettingsDialog(QDialog):
    """
    导出设置对话框
    用户可选择导出的字段、保存类型等
    """

    # 信号：用户确认导出，传递 (selected_fields, export_type, output_path, only_folders, selected_folders)
    export_confirmed = pyqtSignal(list, str, str, bool, list)

    def __init__(self, parent=None, default_dir="", default_type="excel"):
        super().__init__(parent)
        self.setWindowTitle("📊 导出设置")
        self.resize(500, 520)  # 稍微调高
        self.setModal(True)

        self.default_dir = default_dir
        self.default_type = default_type

        # 加载配置
        self.config = ExportConfigManager.load_config()
        self.selected_fields = self.config.get('selected_fields', [])

        # 存储用户自定义选择的文件夹路径
        self.selected_folders = None  # None 表示导出全部

        self._init_ui()
        self._load_selected_fields()

    def _init_ui(self):
        """初始化界面"""
        main_layout = QVBoxLayout(self)

        # ---------- 目标目录 ----------
        dir_layout = QHBoxLayout()
        dir_label = QLabel("📂 目标目录：")
        dir_label.setFixedWidth(80)
        self.dir_display = QLabel(self.default_dir if self.default_dir else "(未选择)")
        self.dir_display.setStyleSheet("color: #1a2332; padding: 4px; border: 1px solid #d0d7e2; border-radius: 4px;")
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.dir_display, 1)
        main_layout.addLayout(dir_layout)

        # ---------- 导出类型 ----------
        type_layout = QHBoxLayout()
        type_label = QLabel("📁 导出类型：")
        type_label.setFixedWidth(80)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Excel 清单 (.xlsx)", "ZIP 资料包 (.zip)"])
        if self.config.get('last_export_type') == 'zip':
            self.type_combo.setCurrentIndex(1)
        else:
            self.type_combo.setCurrentIndex(0)
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.type_combo, 1)
        main_layout.addLayout(type_layout)

        # ---------- 字段选择 ----------
        group = QGroupBox("📄 选择导出字段")
        group_layout = QVBoxLayout()

        # 全选/取消全选按钮
        btn_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("☑ 全选")
        self.btn_select_all.clicked.connect(self._select_all)
        self.btn_deselect_all = QPushButton("☐ 取消全选")
        self.btn_deselect_all.clicked.connect(self._deselect_all)
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_deselect_all)
        btn_layout.addStretch()
        group_layout.addLayout(btn_layout)

        # 字段复选框（分两列）
        field_layout = QHBoxLayout()
        self.checkboxes = []

        col1_layout = QVBoxLayout()
        col2_layout = QVBoxLayout()

        for i, field in enumerate(AVAILABLE_FIELDS):
            cb = QCheckBox(field['id'])
            cb.setChecked(field['default'])
            self.checkboxes.append(cb)
            if i % 2 == 0:
                col1_layout.addWidget(cb)
            else:
                col2_layout.addWidget(cb)

        field_layout.addLayout(col1_layout)
        field_layout.addLayout(col2_layout)
        group_layout.addLayout(field_layout)

        group.setLayout(group_layout)
        main_layout.addWidget(group)

        # ---------- 仅导出文件夹选项 ----------
        self.only_folders_checkbox = QCheckBox("📁 仅导出文件夹（不含文件）")
        self.only_folders_checkbox.setToolTip("只导出文件夹结构，不包含任何文件")
        self.only_folders_checkbox.stateChanged.connect(self._on_only_folders_toggled)
        main_layout.addWidget(self.only_folders_checkbox)

        # ⭐ 新增：自定义选择按钮（仅在勾选后显示）
        self.custom_folder_layout = QHBoxLayout()
        self.custom_folder_layout.setContentsMargins(30, 0, 0, 0)
        self.btn_custom_folders = QPushButton("📂 自定义选择文件夹...")
        self.btn_custom_folders.clicked.connect(self._on_custom_folders_clicked)
        self.btn_custom_folders.setEnabled(False)
        self.custom_folder_status = QLabel("（默认导出全部文件夹）")
        self.custom_folder_status.setStyleSheet("color: #7a8a9e; font-size: 12px;")
        self.custom_folder_layout.addWidget(self.btn_custom_folders)
        self.custom_folder_layout.addWidget(self.custom_folder_status)
        self.custom_folder_layout.addStretch()
        main_layout.addLayout(self.custom_folder_layout)

        # ---------- 提示 ----------
        tip_label = QLabel("💡 程序会自动记住您选择的字段，下次导出时自动恢复")
        tip_label.setStyleSheet("color: #7a8a9e; font-size: 12px;")
        main_layout.addWidget(tip_label)

        # ---------- 底部按钮 ----------
        bottom_layout = QHBoxLayout()

        self.btn_cancel = QPushButton("❌ 取消")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_export = QPushButton("✅ 确认导出")
        self.btn_export.setStyleSheet("background: #28a745; color: white; font-weight: bold;")
        self.btn_export.clicked.connect(self._on_export_clicked)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_cancel)
        bottom_layout.addWidget(self.btn_export)

        main_layout.addLayout(bottom_layout)

        # 初始状态
        self._on_only_folders_toggled(Qt.Unchecked)

    def _on_only_folders_toggled(self, state):
        """当勾选“仅导出文件夹”时，禁用字段选择，启用自定义按钮"""
        enabled = state != Qt.Checked
        for cb in self.checkboxes:
            cb.setEnabled(enabled)
        # 如果勾选了仅导出文件夹，自动取消所有字段勾选（因为不需要）
        if state == Qt.Checked:
            for cb in self.checkboxes:
                cb.setChecked(False)
            self.btn_custom_folders.setEnabled(True)
        else:
            self._load_selected_fields()
            self.btn_custom_folders.setEnabled(False)
            self.selected_folders = None  # 取消勾选时重置
            self.custom_folder_status.setText("（默认导出全部文件夹）")

    def _load_selected_fields(self):
        """加载保存的字段选择状态"""
        if self.selected_fields:
            field_ids = [f['id'] for f in AVAILABLE_FIELDS]
            for cb in self.checkboxes:
                field_id = cb.text()
                cb.setChecked(field_id in self.selected_fields)

    def _select_all(self):
        if not self.only_folders_checkbox.isChecked():
            for cb in self.checkboxes:
                cb.setChecked(True)

    def _deselect_all(self):
        for cb in self.checkboxes:
            cb.setChecked(False)

    def _on_custom_folders_clicked(self):
        """打开自定义文件夹选择对话框"""
        if not self.only_folders_checkbox.isChecked():
            return

        root_dir = self.dir_display.text()
        if not os.path.isdir(root_dir):
            QMessageBox.warning(self, "提示", f"目标目录不存在或无效：{root_dir}")
            return

        dialog = FolderSelectorDialog(root_dir, self)
        dialog.exec_()
        selected = dialog.get_selected_paths()
        if selected:
            self.selected_folders = selected
            self.custom_folder_status.setText(f"（已选 {len(selected)} 个文件夹）")
        else:
            # 用户可能取消了，保留原有状态
            pass

    def _on_export_clicked(self):
        """确认导出按钮点击"""
        # 1. 获取选中的字段（如果未勾选仅导出文件夹）
        selected_fields = []
        if not self.only_folders_checkbox.isChecked():
            selected_fields = [cb.text() for cb in self.checkboxes if cb.isChecked()]
            if not selected_fields:
                QMessageBox.warning(self, "提示", "请至少选择一个导出字段")
                return

        # 2. 获取导出类型
        export_type = "excel" if self.type_combo.currentIndex() == 0 else "zip"
        ext = ".xlsx" if export_type == "excel" else ".zip"

        # 3. 弹出保存文件对话框
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存清单",
            os.path.join(self.default_dir, f"文件清单{ext}"),
            f"文件清单 (*{ext})"
        )
        if not file_path:
            return

        # 4. 保存配置（仅保存字段，不保存仅导出文件夹状态）
        ExportConfigManager.save_config(
            selected_fields=selected_fields,
            last_export_path=file_path,
            last_export_type=export_type
        )

        # 5. 发射信号，传递 only_folders 和 selected_folders
        only_folders = self.only_folders_checkbox.isChecked()
        # 如果 only_folders 为 False，selected_folders 应为 None
        if not only_folders:
            selected_folders = None
        else:
            selected_folders = self.selected_folders  # 可能是 None 或路径列表

        self.export_confirmed.emit(selected_fields, export_type, file_path, only_folders, selected_folders)

        # 6. 关闭对话框
        self.accept()