"""
文件夹选择对话框 - 用于自定义选择要导出的文件夹
"""

import os
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QLabel,
    QMessageBox, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QIcon


# ==================== 后台加载线程 ====================
class FolderScanWorker(QThread):
    """后台扫描文件夹结构（只扫描文件夹，不扫描文件）"""
    result_ready = pyqtSignal(list)

    def __init__(self, root_dir):
        super().__init__()
        self.root_dir = root_dir

    def run(self):
        items = []
        try:
            root_path = Path(self.root_dir)
            if not root_path.is_dir():
                self.result_ready.emit(items)
                return

            # 收集所有子文件夹（忽略文件）
            for item in root_path.rglob('*'):
                if item.is_dir():
                    # 跳过隐藏文件夹
                    if item.name.startswith('.'):
                        continue
                    items.append(str(item))
        except Exception:
            pass
        self.result_ready.emit(items)


class FolderSelectorDialog(QDialog):
    """文件夹选择对话框 - 树形勾选"""

    def __init__(self, root_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📁 选择要导出的文件夹")
        self.resize(500, 550)
        self.setModal(True)

        self.root_dir = root_dir
        self.selected_paths = []  # 用户确认的路径列表

        self._init_ui()
        self._load_folders()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 顶部提示
        tip_label = QLabel(f"📂 根目录: {self.root_dir}\n勾选要导出的文件夹（默认全部勾选）")
        tip_label.setStyleSheet("padding: 4px 8px; background: #f0f4ff; border-radius: 4px;")
        layout.addWidget(tip_label)

        # 工具栏
        toolbar = QHBoxLayout()
        self.btn_select_all = QPushButton("☑ 全选")
        self.btn_select_all.clicked.connect(self.select_all)
        self.btn_deselect_all = QPushButton("☐ 取消全选")
        self.btn_deselect_all.clicked.connect(self.deselect_all)
        toolbar.addWidget(self.btn_select_all)
        toolbar.addWidget(self.btn_deselect_all)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 树形控件
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["文件夹名称"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.setIndentation(20)
        self.tree.setAlternatingRowColors(True)

        # 启用复选框
        self.tree.setSelectionMode(QTreeWidget.NoSelection)
        self.tree.itemChanged.connect(self._on_item_changed)

        layout.addWidget(self.tree)

        # 底部统计和按钮
        bottom = QHBoxLayout()
        self.count_label = QLabel("已选 0 个文件夹")
        self.count_label.setStyleSheet("color: #2b6eb3; font-weight: bold;")
        bottom.addWidget(self.count_label)
        bottom.addStretch()

        self.btn_confirm = QPushButton("✅ 确认")
        self.btn_confirm.clicked.connect(self.confirm_selection)
        self.btn_cancel = QPushButton("❌ 取消")
        self.btn_cancel.clicked.connect(self.reject)

        bottom.addWidget(self.btn_confirm)
        bottom.addWidget(self.btn_cancel)
        layout.addLayout(bottom)

        # 加载提示
        self.status_label = QLabel("⏳ 正在加载文件夹结构...")
        self.status_label.setStyleSheet("color: #7a8a9e; font-size: 12px;")
        layout.addWidget(self.status_label)

    def _load_folders(self):
        """后台加载文件夹结构"""
        self.tree.clear()
        self.status_label.setText("⏳ 正在扫描文件夹...")
        self.btn_confirm.setEnabled(False)

        self.worker = FolderScanWorker(self.root_dir)
        self.worker.result_ready.connect(self._on_load_finished)
        self.worker.start()

    def _on_load_finished(self, paths):
        """加载完成，填充树"""
        self.tree.clear()
        if not paths:
            self.status_label.setText("⚠️ 未找到任何文件夹")
            self.btn_confirm.setEnabled(False)
            return

        # 构建树形结构
        root_item = QTreeWidgetItem(self.tree)
        root_item.setText(0, os.path.basename(self.root_dir))
        root_item.setData(0, Qt.UserRole, self.root_dir)
        root_item.setCheckState(0, Qt.Checked)  # 默认勾选
        root_item.setExpanded(True)

        # 按路径排序
        paths.sort()
        for path in paths:
            self._add_path_to_tree(root_item, path)

        # 统计并更新
        self._update_count()
        self.status_label.setText(f"✅ 加载完成，共 {len(paths)} 个文件夹")
        self.btn_confirm.setEnabled(True)

        # 展开所有节点
        self.tree.expandAll()

    def _add_path_to_tree(self, root_item, full_path):
        """将路径添加到树中（递归创建节点）"""
        # 相对路径
        rel = os.path.relpath(full_path, self.root_dir)
        if rel == '.':
            return

        parts = rel.split(os.sep)
        current = root_item

        for i, part in enumerate(parts):
            # 查找是否已存在该子节点
            found = None
            for j in range(current.childCount()):
                child = current.child(j)
                if child.text(0) == part:
                    found = child
                    break

            if found is None:
                # 创建新节点
                item = QTreeWidgetItem(current)
                item.setText(0, part)
                # 存储完整路径
                path_so_far = os.path.join(self.root_dir, *parts[:i+1])
                item.setData(0, Qt.UserRole, path_so_far)
                item.setCheckState(0, Qt.Checked)  # 默认勾选
                current.addChild(item)
                current = item
            else:
                current = found

    def _on_item_changed(self, item, column):
        """复选框状态变化时触发"""
        if column != 0:
            return
        # 递归设置子项
        state = item.checkState(0)
        self._set_children_state(item, state)
        # 更新父级状态
        self._update_parent_state(item)
        # 更新计数
        self._update_count()

    def _set_children_state(self, parent_item, state):
        """递归设置所有子项的复选框状态"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child.setCheckState(0, state)
            self._set_children_state(child, state)

    def _update_parent_state(self, item):
        """更新父级复选框状态（三态）"""
        parent = item.parent()
        if not parent:
            return

        checked_count = 0
        total_count = 0
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.flags() & Qt.ItemIsUserCheckable:
                total_count += 1
                if child.checkState(0) == Qt.Checked:
                    checked_count += 1
                elif child.checkState(0) == Qt.PartiallyChecked:
                    checked_count += 0.5

        if checked_count == 0:
            parent.setCheckState(0, Qt.Unchecked)
        elif checked_count >= total_count:
            parent.setCheckState(0, Qt.Checked)
        else:
            parent.setCheckState(0, Qt.PartiallyChecked)

        self._update_parent_state(parent)

    def _update_count(self):
        """统计被勾选的文件夹数量"""
        def count_recursive(item):
            cnt = 0
            if item.flags() & Qt.ItemIsUserCheckable:
                if item.checkState(0) == Qt.Checked:
                    cnt += 1
                elif item.checkState(0) == Qt.PartiallyChecked:
                    cnt += 0.5
            for i in range(item.childCount()):
                cnt += count_recursive(item.child(i))
            return cnt

        total = 0
        for i in range(self.tree.topLevelItemCount()):
            total += count_recursive(self.tree.topLevelItem(i))

        # 显示整数（四舍五入）
        display_count = int(round(total))
        self.count_label.setText(f"已选 {display_count} 个文件夹")

    def select_all(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.setCheckState(0, Qt.Checked)
            self._set_children_state(item, Qt.Checked)
        self._update_count()

    def deselect_all(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.setCheckState(0, Qt.Unchecked)
            self._set_children_state(item, Qt.Unchecked)
        self._update_count()

    def confirm_selection(self):
        """
        确认选择，返回选中的路径列表
        修复：只导出叶子节点（有 Checked 子级的父级不导出），避免层级混乱
        """
        # 第一步：收集所有 Checked 的路径
        all_checked_paths = []
        def collect_all_checked(item):
            if item.flags() & Qt.ItemIsUserCheckable:
                if item.checkState(0) == Qt.Checked:
                    path = item.data(0, Qt.UserRole)
                    if path and os.path.isdir(path):
                        all_checked_paths.append(path)
            for i in range(item.childCount()):
                collect_all_checked(item.child(i))

        for i in range(self.tree.topLevelItemCount()):
            collect_all_checked(self.tree.topLevelItem(i))

        if not all_checked_paths:
            QMessageBox.warning(self, "提示", "请至少选择一个文件夹")
            return

        # 第二步：过滤掉那些有 Checked 子级的节点（只保留叶子节点）
        leaf_paths = []
        for path in all_checked_paths:
            # 检查该路径是否作为父级被勾选（即它是否包含其他 Checked 的路径作为前缀）
            is_parent = False
            path_normalized = os.path.normpath(path)
            for other in all_checked_paths:
                if other == path:
                    continue
                other_normalized = os.path.normpath(other)
                # 如果 other 是 path 的子路径（即 other 在 path 内部）
                if other_normalized.startswith(path_normalized + os.sep):
                    is_parent = True
                    break
            if not is_parent:
                leaf_paths.append(path)

        # 如果全部被过滤掉（极端情况），则导出所有 Checked 路径
        if not leaf_paths:
            leaf_paths = all_checked_paths

        self.selected_paths = leaf_paths
        self.accept()

    def get_selected_paths(self):
        return self.selected_paths