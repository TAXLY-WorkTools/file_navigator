import os
from pathlib import Path
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTextEdit, QLabel,
    QTreeWidgetItem, QHeaderView, QPushButton, QHBoxLayout,
    QStackedWidget, QMenu, QAction, QMessageBox, QApplication,
    QFileIconProvider
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPoint, QFileInfo
from PyQt5.QtGui import QColor


# ==================== 后台线程：加载文件夹内容 ====================
class FolderLoadWorker(QThread):
    result_ready = pyqtSignal(list, str)

    def __init__(self, folder_path, parent_path=None):
        super().__init__()
        self.folder_path = folder_path
        self.parent_path = parent_path

    def run(self):
        items = []
        try:
            path = Path(self.folder_path)
            if not path.is_dir():
                self.result_ready.emit(items, self.folder_path)
                return

            dirs = []
            files = []
            for child in path.iterdir():
                try:
                    if child.is_dir():
                        dirs.append(child)
                    else:
                        files.append(child)
                except (PermissionError, OSError):
                    continue

            dirs.sort(key=lambda x: x.name.lower())
            files.sort(key=lambda x: x.name.lower())

            for child in dirs:
                try:
                    stat = child.stat()
                    mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    items.append({
                        'name': child.name,
                        'is_dir': True,
                        'size': '-',
                        'mtime': mtime,
                        'type': '文件夹',
                        'path': str(child)
                    })
                except (PermissionError, OSError):
                    continue

            for child in files:
                try:
                    stat = child.stat()
                    size_bytes = stat.st_size
                    mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')

                    if size_bytes < 1024:
                        size_str = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        size_str = f"{size_bytes / 1024:.1f} KB"
                    elif size_bytes < 1024 * 1024 * 1024:
                        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                    else:
                        size_str = f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

                    file_type = child.suffix.upper() or '文件'
                    items.append({
                        'name': child.name,
                        'is_dir': False,
                        'size': size_str,
                        'mtime': mtime,
                        'type': file_type,
                        'path': str(child)
                    })
                except (PermissionError, OSError):
                    continue

        except Exception:
            pass

        self.result_ready.emit(items, self.folder_path)


# ==================== 主控件 ====================
class RightStackedWidget(QWidget):
    export_selected_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.icon_provider = QFileIconProvider()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # ---------- 页面1: 文件预览 (Preview) ----------
        self.preview_page = QWidget()
        preview_layout = QVBoxLayout(self.preview_page)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        # 预览标题栏
        title_bar = QHBoxLayout()
        self.preview_title = QLabel("📂 请从左侧树双击选择一个文件夹")
        self.preview_title.setStyleSheet("padding: 8px 12px; background: #f0f4ff; border-radius: 4px;")
        title_bar.addWidget(self.preview_title, 1)
        preview_layout.addLayout(title_bar)

        # 快捷操作工具栏
        toolbar = QHBoxLayout()
        self.btn_select_all = QPushButton("☑ 全选")
        self.btn_select_all.clicked.connect(self.select_all)
        self.btn_select_all.setToolTip("全选所有文件和文件夹")

        self.btn_deselect_all = QPushButton("☐ 取消全选")
        self.btn_deselect_all.clicked.connect(self.deselect_all)
        self.btn_deselect_all.setToolTip("取消所有勾选")

        self.btn_select_files = QPushButton("📄 仅选文件")
        self.btn_select_files.clicked.connect(self.select_only_files)
        self.btn_select_files.setToolTip("只勾选文件，不选文件夹")

        self.btn_select_folders = QPushButton("📁 仅选文件夹")
        self.btn_select_folders.clicked.connect(self.select_only_folders)
        self.btn_select_folders.setToolTip("只勾选文件夹，不选文件")

        toolbar.addWidget(self.btn_select_all)
        toolbar.addWidget(self.btn_deselect_all)
        toolbar.addWidget(self.btn_select_files)
        toolbar.addWidget(self.btn_select_folders)
        toolbar.addStretch()

        preview_layout.addLayout(toolbar)

        # 预览树形控件
        self.preview_tree = QTreeWidget()
        self.preview_tree.setColumnCount(4)
        self.preview_tree.setHeaderLabels(["文件名", "大小", "修改时间", "类型"])
        self.preview_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.preview_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.preview_tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.preview_tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.preview_tree.setIndentation(20)
        self.preview_tree.setAlternatingRowColors(True)

        # 启用复选框
        self.preview_tree.setSelectionMode(QTreeWidget.NoSelection)
        self.preview_tree.itemChanged.connect(self._on_item_check_changed)

        self.preview_tree.itemExpanded.connect(self.on_item_expanded)
        self.preview_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.preview_tree.customContextMenuRequested.connect(self._show_preview_context_menu)

        preview_layout.addWidget(self.preview_tree)

        # 预览底部信息
        self.preview_status = QLabel("就绪")
        self.preview_status.setStyleSheet("padding: 4px 8px; color: #7a8a9e; font-size: 12px;")
        preview_layout.addWidget(self.preview_status)

        # ---------- 页面2: 搜索结果 (Search) ----------
        self.search_result_widget = QWidget()
        search_layout = QVBoxLayout(self.search_result_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)

        self.search_summary_label = QLabel("🔍 等待搜索...")
        self.search_summary_label.setStyleSheet("padding: 8px 12px; background: #f0f4ff; border-radius: 4px;")
        search_layout.addWidget(self.search_summary_label)

        self.search_tree = QTreeWidget()
        self.search_tree.setColumnCount(4)
        self.search_tree.setHeaderLabels(["文件名", "所在文件夹", "大小", "修改时间"])
        self.search_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.search_tree.setIndentation(20)
        self.search_tree.setAlternatingRowColors(True)
        self.search_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.search_tree.customContextMenuRequested.connect(self._show_search_context_menu)
        search_layout.addWidget(self.search_tree)

        search_bottom_bar = QHBoxLayout()
        self.export_selected_btn = QPushButton("📊 导出选中为清单")
        self.export_selected_btn.setEnabled(False)
        self.export_selected_btn.clicked.connect(self._export_selected_search_results)
        search_bottom_bar.addWidget(self.export_selected_btn)
        search_bottom_bar.addStretch()
        search_layout.addLayout(search_bottom_bar)

        # ---------- 页面3: 进度日志 (Log) ----------
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("运行日志将显示在这里...")
        self.log_text.append("🚀 程序启动成功，等待操作...")

        # ---------- 堆叠视图 ----------
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.preview_page)          # index 0
        self.stacked_widget.addWidget(self.search_result_widget)  # index 1
        self.stacked_widget.addWidget(self.log_text)              # index 2

        self.layout.addWidget(self.stacked_widget)

        self.switch_to_preview()

        # 线程管理
        self.loader_threads = []
        self.loaded_nodes = set()

        self._updating_check_state = False

    # ==================== 视图切换 ====================
    def switch_to_preview(self):
        self.stacked_widget.setCurrentIndex(0)

    def switch_to_search(self):
        self.stacked_widget.setCurrentIndex(1)

    def switch_to_log(self):
        self.stacked_widget.setCurrentIndex(2)

    # ==================== 停止所有线程 ====================
    def stop_all_threads(self):
        for thread in self.loader_threads:
            if thread.isRunning():
                thread.quit()
                thread.wait()
        self.loader_threads.clear()

    # ==================== 刷新预览区 ====================
    def refresh_preview(self, folder_path):
        # 先停止所有旧线程，并断开它们的信号
        for thread in self.loader_threads:
            if thread.isRunning():
                try:
                    thread.result_ready.disconnect()
                except TypeError:
                    pass
                thread.quit()
                thread.wait()
        self.loader_threads.clear()

        if not folder_path or not os.path.exists(folder_path):
            self.preview_title.setText(f"📂 路径不存在：{folder_path}")
            self.preview_tree.clear()
            self.preview_status.setText("路径不存在")
            return

        if not os.path.isdir(folder_path):
            self.preview_title.setText(f"📂 不是文件夹：{folder_path}")
            self.preview_tree.clear()
            self.preview_status.setText("不是文件夹")
            return

        self.preview_tree.clear()
        self.loaded_nodes.clear()
        self.preview_title.setText(f"📂 {folder_path}")
        self.preview_status.setText("⏳ 正在加载...")

        loader = FolderLoadWorker(folder_path, parent_path=None)
        loader.result_ready.connect(self._on_root_load_ready)
        loader.finished.connect(lambda: self._thread_finished(loader))
        loader.finished.connect(loader.deleteLater)
        self.loader_threads.append(loader)
        loader.start()

    def _on_root_load_ready(self, items, folder_path):
        self.preview_tree.blockSignals(True)
        self.preview_tree.clear()
        self.loaded_nodes.clear()
        self._populate_tree_items(self.preview_tree.invisibleRootItem(), items)
        self.preview_tree.blockSignals(False)

        for i in range(self.preview_tree.topLevelItemCount()):
            item = self.preview_tree.topLevelItem(i)
            item.setExpanded(True)

        file_count = sum(1 for it in items if not it['is_dir'])
        folder_count = sum(1 for it in items if it['is_dir'])
        self.preview_status.setText(
            f"📄 {file_count} 个文件 ｜ 📁 {folder_count} 个文件夹 ｜ 共 {len(items)} 项"
        )

        if folder_path:
            self.loaded_nodes.add(folder_path)

    def _populate_tree_items(self, parent_item, items):
        for data in items:
            path = data['path']
            file_info = QFileInfo(path)
            icon = self.icon_provider.icon(file_info)

            if data['is_dir']:
                item = QTreeWidgetItem(parent_item)
                item.setText(0, data['name'])
                item.setIcon(0, icon)
                item.setText(1, data['size'])
                item.setText(2, data['mtime'])
                item.setText(3, data['type'])
                item.setData(0, Qt.UserRole, path)
                item.setCheckState(0, Qt.Unchecked)
                placeholder = QTreeWidgetItem(item)
                placeholder.setText(0, "⏳ 加载中...")
                placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsUserCheckable)
            else:
                item = QTreeWidgetItem(parent_item)
                item.setText(0, data['name'])
                item.setIcon(0, icon)
                item.setText(1, data['size'])
                item.setText(2, data['mtime'])
                item.setText(3, data['type'])
                item.setCheckState(0, Qt.Unchecked)

    def _thread_finished(self, thread):
        if thread in self.loader_threads:
            self.loader_threads.remove(thread)

    # ==================== 复选框逻辑 ====================
    def _on_item_check_changed(self, item, column):
        try:
            if column != 0 or self._updating_check_state:
                return

            if not (item.flags() & Qt.ItemIsUserCheckable):
                return

            check_state = item.checkState(0)

            path = item.data(0, Qt.UserRole)
            if path and os.path.isdir(path):
                self._updating_check_state = True
                self._set_children_check_state(item, check_state)
                self._updating_check_state = False

            self._update_parent_check_state(item)

            checked_count = self._count_checked_items()
            total_count = self._count_all_items()
            self.preview_status.setText(
                f"已勾选 {checked_count} 项 ｜ 共 {total_count} 项"
            )
        except Exception as e:
            print(f"❌ 勾选异常: {e}")
            import traceback
            traceback.print_exc()

    def _set_children_check_state(self, parent_item, state):
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child.flags() & Qt.ItemIsUserCheckable:
                child.setCheckState(0, state)
            if child.childCount() > 0:
                self._set_children_check_state(child, state)

    def _update_parent_check_state(self, item):
        parent = item.parent()
        if not parent:
            return

        if not (parent.flags() & Qt.ItemIsUserCheckable):
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

        self._update_parent_check_state(parent)

    # ==================== 统计方法 ====================
    def _count_checked_items(self):
        count = 0

        def _count_recursive(item):
            nonlocal count
            if item.flags() & Qt.ItemIsUserCheckable:
                if item.checkState(0) == Qt.Checked:
                    count += 1
                elif item.checkState(0) == Qt.PartiallyChecked:
                    count += 0.5
            for i in range(item.childCount()):
                _count_recursive(item.child(i))

        for i in range(self.preview_tree.topLevelItemCount()):
            _count_recursive(self.preview_tree.topLevelItem(i))
        return count

    def _count_all_items(self):
        count = 0

        def _count_recursive(item):
            nonlocal count
            if item.flags() & Qt.ItemIsUserCheckable:
                count += 1
            for i in range(item.childCount()):
                _count_recursive(item.child(i))

        for i in range(self.preview_tree.topLevelItemCount()):
            _count_recursive(self.preview_tree.topLevelItem(i))
        return count

    # ==================== 快捷操作 ====================
    def select_all(self):
        self._updating_check_state = True
        for i in range(self.preview_tree.topLevelItemCount()):
            item = self.preview_tree.topLevelItem(i)
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(0, Qt.Checked)
                self._set_children_check_state(item, Qt.Checked)
        self._updating_check_state = False
        self._update_status()

    def deselect_all(self):
        self._updating_check_state = True
        for i in range(self.preview_tree.topLevelItemCount()):
            item = self.preview_tree.topLevelItem(i)
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(0, Qt.Unchecked)
                self._set_children_check_state(item, Qt.Unchecked)
        self._updating_check_state = False
        self._update_status()

    def select_only_files(self):
        self._updating_check_state = True

        def _select_files_recursive(item):
            path = item.data(0, Qt.UserRole)
            if path and os.path.isfile(path):
                if item.flags() & Qt.ItemIsUserCheckable:
                    item.setCheckState(0, Qt.Checked)
            elif path and os.path.isdir(path):
                if item.flags() & Qt.ItemIsUserCheckable:
                    item.setCheckState(0, Qt.Unchecked)
            for i in range(item.childCount()):
                _select_files_recursive(item.child(i))

        for i in range(self.preview_tree.topLevelItemCount()):
            _select_files_recursive(self.preview_tree.topLevelItem(i))

        self._updating_check_state = False
        self._update_all_parents()
        self._update_status()

    def select_only_folders(self):
        self._updating_check_state = True

        def _select_folders_recursive(item):
            path = item.data(0, Qt.UserRole)
            if path and os.path.isdir(path):
                if item.flags() & Qt.ItemIsUserCheckable:
                    item.setCheckState(0, Qt.Checked)
                    self._set_children_check_state(item, Qt.Checked)
            elif path and os.path.isfile(path):
                if item.flags() & Qt.ItemIsUserCheckable:
                    item.setCheckState(0, Qt.Unchecked)
            for i in range(item.childCount()):
                _select_folders_recursive(item.child(i))

        for i in range(self.preview_tree.topLevelItemCount()):
            _select_folders_recursive(self.preview_tree.topLevelItem(i))

        self._updating_check_state = False
        self._update_all_parents()
        self._update_status()

    def _update_all_parents(self):
        for i in range(self.preview_tree.topLevelItemCount()):
            self._update_parent_check_state(self.preview_tree.topLevelItem(i))

    def _update_status(self):
        checked_count = self._count_checked_items()
        total_count = self._count_all_items()
        self.preview_status.setText(
            f"已勾选 {checked_count} 项 ｜ 共 {total_count} 项 ｜ ☑ 可勾选要导出的内容"
        )

    # ==================== 获取勾选文件路径 ====================
    def get_checked_paths(self):
        paths = []
        def _collect_recursive(item):
            if item.flags() & Qt.ItemIsUserCheckable:
                if item.checkState(0) == Qt.Checked:
                    path = item.data(0, Qt.UserRole)
                    if path and os.path.isfile(path):
                        paths.append(path)
            for i in range(item.childCount()):
                _collect_recursive(item.child(i))
        for i in range(self.preview_tree.topLevelItemCount()):
            _collect_recursive(self.preview_tree.topLevelItem(i))
        return paths

    def has_checked_items(self):
        return len(self.get_checked_paths()) > 0

    # ==================== 懒加载子节点 ====================
    def on_item_expanded(self, item):
        folder_path = item.data(0, Qt.UserRole)
        if not folder_path:
            return

        if folder_path in self.loaded_nodes:
            return

        if item.childCount() == 0:
            return

        first_child = item.child(0)
        if first_child.text(0) == "⏳ 加载中...":
            item.takeChildren()

            self.preview_status.setText(f"⏳ 正在加载 {Path(folder_path).name}...")

            loader = FolderLoadWorker(folder_path, parent_path=folder_path)
            loader.result_ready.connect(
                lambda items, path, parent=item: self._on_child_load_ready(items, path, parent)
            )
            loader.finished.connect(lambda: self._thread_finished(loader))
            loader.finished.connect(loader.deleteLater)
            self.loader_threads.append(loader)
            loader.start()

            self.loaded_nodes.add(folder_path)

    def _on_child_load_ready(self, items, folder_path, parent_item):
        # ⭐ 检查父项是否仍然有效（防止已删除对象报错）
        if not parent_item or not parent_item.treeWidget():
            # 父项已被删除，忽略此次加载结果
            self.loaded_nodes.discard(folder_path)  # 清除标记，允许下次重新加载
            return

        self.preview_tree.blockSignals(True)
        self._populate_tree_items(parent_item, items)
        self.preview_tree.blockSignals(False)

        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child.childCount() > 0:
                child.setExpanded(True)

        file_count = sum(1 for it in items if not it['is_dir'])
        folder_count = sum(1 for it in items if it['is_dir'])
        self.preview_status.setText(
            f"📄 {file_count} 个文件 ｜ 📁 {folder_count} 个文件夹 ｜ 已加载"
        )
        self.loaded_nodes.add(folder_path)

        self._update_parent_check_state(parent_item)

    # ==================== 预览区右键菜单 ====================
    def _show_preview_context_menu(self, position: QPoint):
        item = self.preview_tree.itemAt(position)
        if not item:
            return
        path = item.data(0, Qt.UserRole)
        if not path:
            return

        menu = QMenu()
        open_action = QAction("📂 打开", self)
        open_action.triggered.connect(lambda: self._open_item(path))
        menu.addAction(open_action)

        open_folder_action = QAction("📁 打开所在文件夹", self)
        open_folder_action.triggered.connect(lambda: self._open_folder(path))
        menu.addAction(open_folder_action)

        copy_action = QAction("📋 复制路径", self)
        copy_action.triggered.connect(lambda: self._copy_path(path))
        menu.addAction(copy_action)

        menu.exec_(self.preview_tree.viewport().mapToGlobal(position))

    # ==================== 搜索结果显示 ====================
    def display_search_results(self, results, keyword=""):
        self.search_summary_label.setText(
            f"🔍 搜索结果: \"{keyword}\" ｜ 找到 {len(results)} 个文件"
        )

        self.search_tree.clear()
        self.search_tree.setColumnCount(4)
        self.search_tree.setHeaderLabels(["文件名", "所在文件夹", "大小", "修改时间"])

        if not results:
            empty_item = QTreeWidgetItem(self.search_tree)
            empty_item.setText(0, "未找到匹配的文件")
            empty_item.setForeground(0, QColor(128, 128, 128))
            self.export_selected_btn.setEnabled(False)
            return

        for data in results:
            path = data.get('path', '')
            file_info = QFileInfo(path)
            icon = self.icon_provider.icon(file_info)

            item = QTreeWidgetItem(self.search_tree)
            item.setText(0, data['name'])
            item.setIcon(0, icon)
            item.setText(1, data.get('path', ''))
            item.setText(2, data.get('size', '-'))
            item.setText(3, data.get('modified', ''))
            item.setData(0, Qt.UserRole, path)

        self.export_selected_btn.setEnabled(True)

    def _show_search_context_menu(self, position: QPoint):
        item = self.search_tree.itemAt(position)
        if not item:
            return
        path = item.data(0, Qt.UserRole)
        if not path:
            return

        menu = QMenu()
        open_action = QAction("📂 打开", self)
        open_action.triggered.connect(lambda: self._open_item(path))
        menu.addAction(open_action)

        open_folder_action = QAction("📁 打开所在文件夹", self)
        open_folder_action.triggered.connect(lambda: self._open_folder(path))
        menu.addAction(open_folder_action)

        copy_action = QAction("📋 复制路径", self)
        copy_action.triggered.connect(lambda: self._copy_path(path))
        menu.addAction(copy_action)

        menu.exec_(self.search_tree.viewport().mapToGlobal(position))

    def _export_selected_search_results(self):
        selected_items = self.search_tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "提示", "请先勾选要导出的文件")
            return

        paths = []
        for item in selected_items:
            path = item.data(0, Qt.UserRole)
            if path and os.path.exists(path):
                paths.append(path)

        if not paths:
            QMessageBox.warning(self, "提示", "选中的文件不存在或已移动")
            return

        self.export_selected_signal.emit(paths)

    def _open_item(self, path):
        try:
            os.startfile(path)
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开：{e}")

    def _open_folder(self, path):
        try:
            import subprocess
            subprocess.Popen(['explorer', '/select,', path])
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件夹：{e}")

    def _copy_path(self, path):
        clipboard = QApplication.clipboard()
        clipboard.setText(path)

    def append_log(self, message):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )