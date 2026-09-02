"""
模板编辑器 - 独立窗口
用于创建、编辑、保存文件夹分级模板
"""

import os
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QMessageBox, QFileDialog, QInputDialog,
    QHeaderView, QAbstractItemView, QApplication, QAction, QMenu
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QKeySequence

from core.template_manager import TemplateManager
from core.template_library import TemplateLibrary
from ui.template_library_dialog import TemplateLibraryDialog


# ==================== 后台扫描线程 ====================
class FolderScanWorker(QThread):
    scan_finished = pyqtSignal(list, list)
    scan_progress = pyqtSignal(str)
    scan_error = pyqtSignal(str)

    def __init__(self, root_path: str):
        super().__init__()
        self.root_path = root_path

    def run(self):
        try:
            self.scan_progress.emit("⏳ 正在扫描文件夹结构...")
            tree_data, hidden_folders = TemplateManager.scan_folder_structure(
                self.root_path,
                include_hidden=False
            )
            self.scan_finished.emit(tree_data, hidden_folders)
        except Exception as e:
            self.scan_error.emit(f"扫描失败：{str(e)}")


# ==================== 主窗口 ====================
class TemplateEditor(QDialog):
    template_saved = pyqtSignal(str)

    def __init__(self, parent=None, load_template_path=None):
        super().__init__(parent)
        self.setWindowTitle("📝 模板编辑器 - 文件夹分级方案")
        self.resize(820, 620)
        self.current_file_path = load_template_path
        self.is_modified = False
        self.current_root_path = ""
        self.scan_worker = None
        self.pending_hidden_folders = []
        self.current_library_name = None

        self._init_ui()
        self._init_actions()

        if load_template_path and os.path.exists(load_template_path):
            self._load_from_file(load_template_path)
        else:
            self._init_default_template()

    # ==================== UI 初始化 ====================
    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # ---------- 第一行：编辑工具栏 ----------
        toolbar1 = QHBoxLayout()

        self.btn_add_root = QPushButton("➕ 根节点")
        self.btn_add_root.clicked.connect(self.add_root_node)
        self.btn_add_root.setToolTip("添加一级文件夹 (Ctrl+Shift+N)")

        self.btn_add_child = QPushButton("📂 子节点")
        self.btn_add_child.clicked.connect(self.add_child_node)
        self.btn_add_child.setToolTip("在当前文件夹下添加子文件夹 (Ctrl+N)")

        self.btn_rename = QPushButton("✏️ 重命名")
        self.btn_rename.clicked.connect(self.rename_node)
        self.btn_rename.setToolTip("重命名当前文件夹 (F2)")

        self.btn_delete = QPushButton("🗑️ 删除")
        self.btn_delete.clicked.connect(self.delete_node)
        self.btn_delete.setToolTip("删除当前文件夹及其所有子级 (Delete)")

        self.btn_move_up = QPushButton("⬆️ 上移")
        self.btn_move_up.clicked.connect(self.move_up)
        self.btn_move_up.setToolTip("同级中上移 (Ctrl+↑)")

        self.btn_move_down = QPushButton("⬇️ 下移")
        self.btn_move_down.clicked.connect(self.move_down)
        self.btn_move_down.setToolTip("同级中下移 (Ctrl+↓)")

        self.btn_import_folder = QPushButton("📂 从文件夹识别")
        self.btn_import_folder.clicked.connect(self.import_from_folder)
        self.btn_import_folder.setToolTip("从现有文件夹结构识别并生成模板")

        self.btn_import_excel = QPushButton("📥 导入 Excel")
        self.btn_import_excel.clicked.connect(self.import_from_excel)
        self.btn_import_excel.setToolTip("从 Excel 文件导入模板结构")

        toolbar1.addWidget(self.btn_add_root)
        toolbar1.addWidget(self.btn_add_child)
        toolbar1.addWidget(self.btn_rename)
        toolbar1.addWidget(self.btn_delete)
        toolbar1.addWidget(self.btn_move_up)
        toolbar1.addWidget(self.btn_move_down)
        toolbar1.addStretch()
        toolbar1.addWidget(self.btn_import_folder)
        toolbar1.addWidget(self.btn_import_excel)

        main_layout.addLayout(toolbar1)

        # ---------- 第二行：模板管理工具栏 ----------
        toolbar2 = QHBoxLayout()

        self.btn_save = QPushButton("💾 保存模板 ▼")
        self.btn_save.setToolTip("保存模板 (Ctrl+S)")
        self.btn_save.clicked.connect(self._show_save_menu)

        self.btn_load = QPushButton("📂 加载模板")
        self.btn_load.clicked.connect(self.load_template)
        self.btn_load.setToolTip("从文件加载模板")

        self.btn_library = QPushButton("📚 模板库")
        self.btn_library.clicked.connect(self.open_library)
        self.btn_library.setToolTip("管理内置模板库")

        self.btn_delete_current = QPushButton("🗑️ 删除当前模板")
        self.btn_delete_current.clicked.connect(self.delete_current_template)
        self.btn_delete_current.setToolTip("删除当前加载的模板（从库中移除）")
        self.btn_delete_current.setEnabled(False)

        toolbar2.addWidget(self.btn_save)
        toolbar2.addWidget(self.btn_load)
        toolbar2.addWidget(self.btn_library)
        toolbar2.addStretch()
        toolbar2.addWidget(self.btn_delete_current)

        main_layout.addLayout(toolbar2)

        # ---------- 提示栏 ----------
        tip_label = QLabel("💡 支持拖拽调整层级 ｜ 快捷键：F2=重命名 ｜ Delete=删除 ｜ Ctrl+S=保存")
        tip_label.setStyleSheet("color: #7a8a9e; font-size: 12px; padding: 4px 0;")
        main_layout.addWidget(tip_label)

        # ---------- 树形控件 ----------
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["文件夹名称"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.setIndentation(20)
        self.tree.setAlternatingRowColors(True)

        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)

        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemChanged.connect(self._on_item_changed)

        main_layout.addWidget(self.tree)

        # ---------- 第三行：生成操作 ----------
        toolbar3 = QHBoxLayout()
        toolbar3.addStretch()
        self.btn_generate = QPushButton("✅ 生成空文件夹")
        self.btn_generate.clicked.connect(self.generate_folders)
        self.btn_generate.setStyleSheet("background: #28a745; color: white; font-weight: bold; padding: 8px 24px;")
        toolbar3.addWidget(self.btn_generate)
        toolbar3.addStretch()

        main_layout.addLayout(toolbar3)

        # ---------- 状态栏 ----------
        self.status_label = QLabel("就绪 | 新建模板")
        self.status_label.setStyleSheet("padding: 4px 8px; color: #7a8a9e; font-size: 12px; border-top: 1px solid #e8ecf1;")
        main_layout.addWidget(self.status_label)

        self._save_menu = None

    def _init_actions(self):
        save_action = QAction(self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self._save_as_json)
        self.addAction(save_action)

        rename_action = QAction(self)
        rename_action.setShortcut(QKeySequence("F2"))
        rename_action.triggered.connect(self.rename_node)
        self.addAction(rename_action)

        delete_action = QAction(self)
        delete_action.setShortcut(QKeySequence("Delete"))
        delete_action.triggered.connect(self.delete_node)
        self.addAction(delete_action)

    # ==================== 示例模板 ====================
    def _init_default_template(self):
        """初始化示例模板"""
        root = QTreeWidgetItem(self.tree)
        root.setText(0, "📁 项目资料")
        root.setExpanded(True)

        child1 = QTreeWidgetItem(root)
        child1.setText(0, "📁 01_合同文档")
        child1.setExpanded(True)

        sub1 = QTreeWidgetItem(child1)
        sub1.setText(0, "📁 已签署合同")
        sub2 = QTreeWidgetItem(child1)
        sub2.setText(0, "📁 待签署合同")

        child2 = QTreeWidgetItem(root)
        child2.setText(0, "📁 02_财务报表")
        child2.setExpanded(True)

        sub3 = QTreeWidgetItem(child2)
        sub3.setText(0, "📁 月度报表")
        sub4 = QTreeWidgetItem(child2)
        sub4.setText(0, "📁 年度报表")

        self.tree.expandAll()
        self.status_label.setText("就绪 | 示例模板已加载")
        self._mark_modified(False)

    # ==================== 保存下拉菜单 ====================
    def _show_save_menu(self):
        menu = QMenu(self)

        action_json = QAction("💾 保存为 JSON (.json)", self)
        action_json.triggered.connect(self._save_as_json)
        menu.addAction(action_json)

        action_excel = QAction("📤 导出为 Excel (.xlsx)", self)
        action_excel.triggered.connect(self._export_to_excel)
        menu.addAction(action_excel)

        menu.addSeparator()

        action_library = QAction("📚 保存到模板库", self)
        action_library.triggered.connect(self._save_to_library)
        menu.addAction(action_library)

        menu.exec_(self.btn_save.mapToGlobal(self.btn_save.rect().bottomLeft()))

    def _save_as_json(self):
        items = TemplateManager.get_root_items(self.tree)
        if not items:
            QMessageBox.warning(self, "提示", "模板为空，请至少添加一个文件夹")
            return

        if self.current_file_path and os.path.dirname(self.current_file_path):
            if TemplateManager.save_to_json(items, self.current_file_path):
                self._mark_modified(False)
                self.status_label.setText(f"✅ 已保存：{os.path.basename(self.current_file_path)}")
                self.template_saved.emit(self.current_file_path)
                self.btn_delete_current.setEnabled(False)
                self.current_library_name = None
            else:
                QMessageBox.warning(self, "保存失败", "保存模板失败")
        else:
            self._save_as_json_as()

    def _save_as_json_as(self):
        items = TemplateManager.get_root_items(self.tree)
        if not items:
            QMessageBox.warning(self, "提示", "模板为空，请至少添加一个文件夹")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "保存模板", "", "JSON 文件 (*.json)")
        if file_path:
            if not file_path.endswith('.json'):
                file_path += '.json'
            if TemplateManager.save_to_json(items, file_path):
                self.current_file_path = file_path
                self._mark_modified(False)
                self.status_label.setText(f"✅ 已保存：{os.path.basename(file_path)}")
                self.template_saved.emit(file_path)
                self.btn_delete_current.setEnabled(False)
                self.current_library_name = None
                QMessageBox.information(self, "保存成功", f"模板已保存：{file_path}")
            else:
                QMessageBox.warning(self, "保存失败", "保存模板失败")

    def _export_to_excel(self):
        items = TemplateManager.get_root_items(self.tree)
        if not items:
            QMessageBox.warning(self, "提示", "模板为空，无法导出")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "导出 Excel 模板", "", "Excel 文件 (*.xlsx)")
        if not file_path:
            return

        if TemplateManager.save_to_excel(items, file_path):
            self.status_label.setText(f"✅ 已导出 Excel：{os.path.basename(file_path)}")
            QMessageBox.information(self, "导出成功", f"Excel 已保存：{file_path}")
        else:
            QMessageBox.warning(self, "导出失败", "导出 Excel 失败")

    def _save_to_library(self):
        items = TemplateManager.get_root_items(self.tree)
        if not items:
            QMessageBox.warning(self, "提示", "模板为空，请至少添加一个文件夹")
            return

        name, ok = QInputDialog.getText(
            self,
            "保存到模板库",
            "请输入模板名称：",
            text=self.current_library_name or ""
        )
        if ok and name.strip():
            tree_data = TemplateManager.tree_to_dict(items)
            if TemplateLibrary.save_template(name.strip(), tree_data):
                self.status_label.setText(f"✅ 已保存到模板库：{name.strip()}")
                self.current_library_name = name.strip()
                self.btn_delete_current.setEnabled(True)
                QMessageBox.information(self, "成功", f"模板「{name.strip()}」已保存到模板库")
            else:
                QMessageBox.warning(self, "失败", "保存到模板库失败")

    def delete_current_template(self):
        if not self.current_library_name:
            QMessageBox.warning(self, "提示", "当前模板不在模板库中，无法删除")
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确认从模板库中删除「{self.current_library_name}」？\n此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if TemplateLibrary.delete_template(self.current_library_name):
                self.status_label.setText(f"🗑️ 已删除模板：{self.current_library_name}")
                self.current_library_name = None
                self.btn_delete_current.setEnabled(False)
                QMessageBox.information(self, "成功", "模板已从模板库删除")
            else:
                QMessageBox.warning(self, "失败", "删除失败")

    def open_library(self):
        dialog = TemplateLibraryDialog(self)
        dialog.load_template_signal.connect(self._load_from_library)
        dialog.exec_()

    def _load_from_library(self, name):
        data = TemplateLibrary.load_template(name)
        if data is not None:
            TemplateManager.dict_to_tree(data, self.tree)
            self.tree.expandAll()
            self.current_file_path = None
            self.current_library_name = name
            self._mark_modified(False)
            self.btn_delete_current.setEnabled(True)
            count = TemplateManager.get_folder_count(data)
            self.status_label.setText(f"✅ 已从模板库加载：{name}（{count} 个文件夹）")
        else:
            QMessageBox.warning(self, "加载失败", f"无法加载模板「{name}」")

    # ==================== 辅助方法 ====================
    def _mark_modified(self, modified=True):
        self.is_modified = modified
        if modified:
            self.setWindowTitle("📝 模板编辑器 - 已修改*")
        else:
            self.setWindowTitle("📝 模板编辑器 - 文件夹分级方案")

    def _on_selection_changed(self):
        item = self.tree.currentItem()
        if item:
            name = item.text(0).replace('📁 ', '')
            self.status_label.setText(f"当前选中：{name}")

    def _on_item_changed(self, item, column):
        pass

    def _get_selected_item(self):
        return self.tree.currentItem()

    def _get_display_name(self, item):
        return item.text(0).replace('📁 ', '').strip()

    def _count_nodes(self):
        return TemplateManager.get_folder_count_from_tree(self.tree)

    def _load_from_file(self, file_path):
        data = TemplateManager.load_from_json(file_path)
        if data is not None:
            TemplateManager.dict_to_tree(data, self.tree)
            self.tree.expandAll()
            self.current_file_path = file_path
            self.current_library_name = None
            self._mark_modified(False)
            self.btn_delete_current.setEnabled(False)
            self.status_label.setText(f"✅ 已加载：{os.path.basename(file_path)}")
            return True
        else:
            QMessageBox.warning(self, "加载失败", f"无法加载模板文件：{file_path}")
            return False

    # ==================== 节点操作 ====================
    def add_root_node(self):
        name, ok = QInputDialog.getText(self, "新建根节点", "请输入根文件夹名称：")
        if ok and name.strip():
            item = QTreeWidgetItem(self.tree)
            item.setText(0, f"📁 {name.strip()}")
            self.tree.setCurrentItem(item)
            self._mark_modified(True)
            self.status_label.setText(f"✅ 已添加根节点：{name.strip()}")

    def add_child_node(self):
        parent = self._get_selected_item()
        if not parent:
            QMessageBox.warning(self, "提示", "请先选中一个父文件夹")
            return

        parent_name = self._get_display_name(parent)
        name, ok = QInputDialog.getText(self, "新建子文件夹", f"在「{parent_name}」下新建子文件夹：")
        if ok and name.strip():
            item = QTreeWidgetItem(parent)
            item.setText(0, f"📁 {name.strip()}")
            parent.setExpanded(True)
            self.tree.setCurrentItem(item)
            self._mark_modified(True)
            self.status_label.setText(f"✅ 已添加子文件夹：{name.strip()}")

    def rename_node(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.warning(self, "提示", "请先选中一个文件夹")
            return

        old_name = self._get_display_name(item)
        new_name, ok = QInputDialog.getText(self, "重命名", "请输入新名称：", text=old_name)
        if ok and new_name.strip():
            item.setText(0, f"📁 {new_name.strip()}")
            self._mark_modified(True)
            self.status_label.setText(f"✅ 已重命名：{new_name.strip()}")

    def delete_node(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.warning(self, "提示", "请先选中一个文件夹")
            return

        name = self._get_display_name(item)
        child_count = item.childCount()

        if child_count > 0:
            reply = QMessageBox.question(
                self, "确认删除",
                f"确认删除「{name}」及其所有子文件夹？\n（共 {child_count} 个子文件夹）",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        else:
            reply = QMessageBox.question(
                self, "确认删除",
                f"确认删除「{name}」？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        parent = item.parent()
        if parent:
            parent.removeChild(item)
        else:
            index = self.tree.indexOfTopLevelItem(item)
            self.tree.takeTopLevelItem(index)

        self._mark_modified(True)
        self.status_label.setText(f"🗑️ 已删除：{name}")

    def move_up(self):
        item = self._get_selected_item()
        if not item:
            return

        parent = item.parent()
        if parent:
            index = parent.indexOfChild(item)
            if index > 0:
                parent.removeChild(item)
                parent.insertChild(index - 1, item)
                self.tree.setCurrentItem(item)
                self._mark_modified(True)
        else:
            index = self.tree.indexOfTopLevelItem(item)
            if index > 0:
                self.tree.takeTopLevelItem(index)
                self.tree.insertTopLevelItem(index - 1, item)
                self.tree.setCurrentItem(item)
                self._mark_modified(True)

    def move_down(self):
        item = self._get_selected_item()
        if not item:
            return

        parent = item.parent()
        if parent:
            index = parent.indexOfChild(item)
            if index < parent.childCount() - 1:
                parent.removeChild(item)
                parent.insertChild(index + 1, item)
                self.tree.setCurrentItem(item)
                self._mark_modified(True)
        else:
            index = self.tree.indexOfTopLevelItem(item)
            if index < self.tree.topLevelItemCount() - 1:
                self.tree.takeTopLevelItem(index)
                self.tree.insertTopLevelItem(index + 1, item)
                self.tree.setCurrentItem(item)
                self._mark_modified(True)

    # ==================== 从文件夹识别 ====================
    def import_from_folder(self):
        parent = self.parent()
        root_dir = None

        if parent and hasattr(parent, 'current_path_edit'):
            path = parent.current_path_edit.text().strip()
            if path and os.path.isdir(path):
                root_dir = path

        if not root_dir:
            root_dir = QFileDialog.getExistingDirectory(
                self,
                "选择要识别的文件夹",
                "",
                QFileDialog.ShowDirsOnly
            )
            if not root_dir:
                return

        reply = QMessageBox.question(
            self,
            "确认扫描",
            f"将扫描以下文件夹的目录结构：\n\n📂 {root_dir}\n\n"
            "程序将提取所有文件夹层级（忽略文件），生成模板。\n"
            "是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_import_folder.setEnabled(False)
        self.status_label.setText("⏳ 正在扫描文件夹结构...")

        self.scan_worker = FolderScanWorker(root_dir)
        self.scan_worker.scan_progress.connect(self.status_label.setText)
        self.scan_worker.scan_error.connect(self._on_scan_error)
        self.scan_worker.scan_finished.connect(self._on_scan_finished)
        self.scan_worker.start()

    def _on_scan_finished(self, tree_data, hidden_folders):
        self.btn_import_folder.setEnabled(True)

        if hidden_folders and not self._pending_hidden_folders:
            self.pending_hidden_folders = hidden_folders
            self._show_hidden_folder_dialog(tree_data, hidden_folders)
            return

        self._display_tree_data(tree_data)
        folder_count = TemplateManager.get_folder_count(tree_data)
        hidden_msg = f"，已跳过 {len(hidden_folders)} 个隐藏文件夹" if hidden_folders else ""
        self.status_label.setText(f"✅ 已从文件夹识别出 {folder_count} 个文件夹{hidden_msg}")
        self._mark_modified(True)

    def _on_scan_error(self, error_msg):
        self.btn_import_folder.setEnabled(True)
        self.status_label.setText(f"❌ {error_msg}")
        QMessageBox.warning(self, "扫描失败", error_msg)

    def _show_hidden_folder_dialog(self, tree_data, hidden_folders):
        folder_list = "\n".join([f"  📁 {Path(f).name}" for f in hidden_folders[:10]])
        if len(hidden_folders) > 10:
            folder_list += f"\n  ... 还有 {len(hidden_folders) - 10} 个"

        dialog = QMessageBox(self)
        dialog.setWindowTitle("⚠️ 检测到隐藏文件夹")
        dialog.setIcon(QMessageBox.Warning)
        dialog.setText(
            f"扫描发现以下隐藏文件夹：\n\n{folder_list}\n\n"
            "隐藏文件夹（以 . 开头）通常是系统或软件自动生成的配置目录。\n"
            "是否将这些隐藏文件夹包含到模板中？"
        )
        dialog.setInformativeText("💡 提示：通常建议跳过隐藏文件夹，保持模板整洁。")

        btn_include = dialog.addButton("✅ 包含", QMessageBox.AcceptRole)
        btn_skip = dialog.addButton("❌ 跳过", QMessageBox.RejectRole)
        btn_skip_all = dialog.addButton("❌ 全部跳过", QMessageBox.DestructiveRole)

        dialog.exec_()

        clicked_button = dialog.clickedButton()

        if clicked_button == btn_include:
            self._rescan_with_hidden(tree_data, hidden_folders, include_hidden=True)
        elif clicked_button == btn_skip:
            self.pending_hidden_folders = []
            self._display_tree_data(tree_data)
            folder_count = TemplateManager.get_folder_count(tree_data)
            self.status_label.setText(f"✅ 已从文件夹识别出 {folder_count} 个文件夹（已跳过隐藏文件夹）")
            self._mark_modified(True)
        elif clicked_button == btn_skip_all:
            self.pending_hidden_folders = []
            self._display_tree_data(tree_data)
            folder_count = TemplateManager.get_folder_count(tree_data)
            self.status_label.setText(f"✅ 已从文件夹识别出 {folder_count} 个文件夹（已跳过 {len(hidden_folders)} 个隐藏文件夹）")
            self._mark_modified(True)
        else:
            self.pending_hidden_folders = []
            self._display_tree_data(tree_data)
            folder_count = TemplateManager.get_folder_count(tree_data)
            self.status_label.setText(f"✅ 已从文件夹识别出 {folder_count} 个文件夹")
            self._mark_modified(True)

    def _rescan_with_hidden(self, tree_data, hidden_folders, include_hidden):
        self.pending_hidden_folders = []

        parent = self.parent()
        if parent and hasattr(parent, 'current_path_edit'):
            root_path = parent.current_path_edit.text().strip()
        else:
            root_path = os.path.dirname(hidden_folders[0]) if hidden_folders else ""

        if not root_path or not os.path.exists(root_path):
            self.status_label.setText("❌ 无法重新扫描，请重新选择文件夹")
            return

        self.btn_import_folder.setEnabled(False)
        self.status_label.setText("⏳ 正在重新扫描（包含隐藏文件夹）...")

        self.scan_worker = FolderScanWorker(root_path)
        self.scan_worker.scan_progress.connect(self.status_label.setText)
        self.scan_worker.scan_error.connect(self._on_scan_error)
        self.scan_worker.scan_finished.connect(
            lambda data, hidden: self._on_rescan_with_hidden_finished(data)
        )
        self.scan_worker.start()

    def _on_rescan_with_hidden_finished(self, tree_data):
        self.btn_import_folder.setEnabled(True)
        self._display_tree_data(tree_data)
        folder_count = TemplateManager.get_folder_count(tree_data)
        self.status_label.setText(f"✅ 已从文件夹识别出 {folder_count} 个文件夹（包含隐藏文件夹）")
        self._mark_modified(True)
        self.pending_hidden_folders = []

    def _display_tree_data(self, tree_data):
        self.tree.clear()
        TemplateManager.dict_to_tree(tree_data, self.tree)
        self.tree.expandAll()

    # ==================== Excel 导入 ====================
    def import_from_excel(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 Excel 模板文件", "", "Excel 文件 (*.xlsx *.xls)"
        )
        if not file_path:
            return

        data = TemplateManager.load_from_excel(file_path)
        if data is not None:
            TemplateManager.dict_to_tree(data, self.tree)
            self.tree.expandAll()
            self.current_file_path = None
            self.current_library_name = None
            self.btn_delete_current.setEnabled(False)
            self._mark_modified(True)
            count = TemplateManager.get_folder_count(data)
            self.status_label.setText(f"✅ 从 Excel 导入成功：{count} 个文件夹")
        else:
            QMessageBox.warning(self, "导入失败",
                "无法导入 Excel 文件，请检查格式是否正确。\n\n"
                "格式要求：\n"
                "• 第一列为「父级路径」\n"
                "• 第二列为「文件夹名」\n"
                "• 父级路径为空表示根节点\n"
                "• 路径分隔符使用 /"
            )

    # ==================== 加载模板 ====================
    def load_template(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "加载模板", "", "JSON 文件 (*.json)")
        if file_path:
            if self._load_from_file(file_path):
                self.current_file_path = file_path
                self.current_library_name = None
                self.btn_delete_current.setEnabled(False)

    # ==================== 生成空文件夹 ====================
    def generate_folders(self):
        items = TemplateManager.get_root_items(self.tree)
        if not items:
            QMessageBox.warning(self, "提示", "模板为空，请先创建或加载模板")
            return

        parent = self.parent()
        root_dir = None
        if parent and hasattr(parent, 'current_path_edit'):
            path = parent.current_path_edit.text().strip()
            if path and path != "请从左侧树双击选择，或点击「选择目录」按钮" and os.path.isdir(path):
                root_dir = path

        if not root_dir:
            root_dir = QFileDialog.getExistingDirectory(
                self, "选择目标目录（将在该目录下创建文件夹）", "", QFileDialog.ShowDirsOnly
            )
            if not root_dir:
                return

        count = self._count_nodes()
        tree_data = TemplateManager.tree_to_dict(items)
        preview = self._build_preview(tree_data)

        reply = QMessageBox.question(
            self,
            "确认生成空文件夹",
            f"将在以下位置创建 {count} 个文件夹：\n\n"
            f"📂 {root_dir}/\n{preview}\n\n"
            "💡 已存在的文件夹将被跳过（不覆盖）\n\n"
            "确认继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        success, message = TemplateManager.generate_folders(root_dir, tree_data)

        if success:
            self.status_label.setText(message)
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.warning(self, "失败", message)

    def _build_preview(self, tree_data, indent=0) -> str:
        if not tree_data:
            return "  （空模板）"
        preview = ""
        for node in tree_data:
            preview += "  " * (indent + 1) + f"📁 {node['name']}\n"
            if node.get('children'):
                preview += self._build_preview(node['children'], indent + 1)
        return preview.rstrip('\n')

    # ==================== 关闭确认 ====================
    def closeEvent(self, event):
        if self.is_modified:
            reply = QMessageBox.question(
                self, "未保存的修改",
                "模板已修改，是否保存？",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self._save_as_json()
                if self.is_modified:
                    event.ignore()
                    return
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        event.accept()