import os
import webbrowser
from pathlib import Path
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLineEdit, QComboBox, QLabel, 
    QFileDialog, QSplitter, QMessageBox, QTableWidgetItem,
    QInputDialog, QAction
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from ui.left_tree_view import LeftTreeView
from ui.right_stacked_widget import RightStackedWidget
from config import SEARCH_SCOPE_OPTIONS, DEFAULT_EXTENSIONS
from core.file_worker import FileWorker
from core.search_engine import (
    get_search_engine,
    check_everything_status,
    set_everything_dll_path,
    set_es_path
)
from ui.template_editor import TemplateEditor
from ui.export_settings_dialog import ExportSettingsDialog
from core.export_config_manager import ExportConfigManager


# ==================== 导出工作线程 ====================
class ExportWorker(QThread):
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    done_signal = pyqtSignal(bool, str)

    def __init__(self, root_dir, output_path, file_ext, selected_fields=None, export_type='excel', 
                 include_paths=None, only_folders=False, include_folders=None):
        super().__init__()
        self.root_dir = root_dir
        self.output_path = output_path
        self.file_ext = file_ext
        self.selected_fields = selected_fields
        self.export_type = export_type
        self.include_paths = include_paths
        self.only_folders = only_folders
        self.include_folders = include_folders  # ⭐ 新增：用户自定义选择的文件夹路径列表

    def run(self):
        try:
            worker = FileWorker()

            # 如果仅导出文件夹
            if self.only_folders:
                # ⭐ 如果用户自定义选择了文件夹，则传入 include_folders
                success = worker.export_folders_only(
                    output_path=self.output_path,
                    root_dir=self.root_dir,
                    include_hidden=False,
                    include_paths=self.include_folders  # 可能为 None 或列表
                )
                if success:
                    self.log_signal.emit(f"✅ 文件夹结构导出成功：{self.output_path}")
                    self.done_signal.emit(True, self.output_path)
                else:
                    self.done_signal.emit(False, "文件夹结构导出失败")
                return

            # 原有导出文件逻辑
            result = worker.scan_directory(
                root_dir=self.root_dir,
                extensions=None,
                detect_empty=True
            )

            if self.include_paths:
                filtered_files = [f for f in result['files'] if f['完整路径'] in self.include_paths]
                result['files'] = filtered_files
                result['total_count'] = len(filtered_files)

            file_count = result['total_count']
            empty_folders = result['empty_folders']

            self.log_signal.emit(f"📂 扫描完成：{file_count} 个文件")
            if empty_folders:
                self.log_signal.emit(f"📂 检测到 {len(empty_folders)} 个空文件夹（默认跳过）")
            if self.include_paths:
                self.log_signal.emit(f"📋 已过滤：只导出被勾选的 {file_count} 个文件")

            if self.file_ext == '.xlsx':
                success = worker.export_to_excel(
                    output_path=self.output_path,
                    selected_fields=self.selected_fields,
                    with_hyperlink=True,
                    include_empty_folders=False
                )
                if success:
                    self.log_signal.emit(f"✅ Excel 导出成功：{self.output_path}")
                    self.done_signal.emit(True, self.output_path)
                else:
                    self.done_signal.emit(False, "Excel 导出失败")
            elif self.file_ext == '.zip':
                success = worker.export_package(
                    output_zip_path=self.output_path,
                    include_excel=True,
                    include_html=True,
                    include_files=True,
                    use_relative_path=True,
                    empty_folder_choice='skip'
                )
                if success:
                    self.log_signal.emit(f"✅ ZIP 打包成功：{self.output_path}")
                    self.done_signal.emit(True, self.output_path)
                else:
                    self.done_signal.emit(False, "ZIP 打包失败")
            else:
                self.done_signal.emit(False, f"不支持的文件格式：{self.file_ext}")
        except Exception as e:
            import traceback
            self.log_signal.emit(f"❌ 错误：{traceback.format_exc()}")
            self.done_signal.emit(False, str(e))


# ==================== 搜索线程 ====================
class SearchWorker(QThread):
    result_signal = pyqtSignal(list)
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, keyword, scope, current_dir=None, custom_path=None):
        super().__init__()
        self.keyword = keyword
        self.scope = scope
        self.current_dir = current_dir
        self.custom_path = custom_path

    def run(self):
        try:
            engine = get_search_engine()
            search_path = None
            search_mode = 'none'

            if self.scope == "当前目录":
                if self.current_dir and os.path.isdir(self.current_dir):
                    search_path = self.current_dir
                    search_mode = 'parent'
                else:
                    self.error_signal.emit("当前目录无效，请先在左侧树选择文件夹")
                    return
            elif self.scope == "当前目录及子目录":
                if self.current_dir and os.path.isdir(self.current_dir):
                    search_path = self.current_dir
                    search_mode = 'path'
                else:
                    self.error_signal.emit("当前目录无效，请先在左侧树选择文件夹")
                    return
            elif self.scope == "自定义路径":
                if self.custom_path and os.path.isdir(self.custom_path):
                    search_path = self.custom_path
                    search_mode = 'path'
                else:
                    self.error_signal.emit("自定义路径无效，请检查路径是否正确")
                    return

            self.log_signal.emit(f"🔍 正在搜索：{self.keyword} (范围：{self.scope})")
            results = engine.search(self.keyword, search_path, search_mode, max_results=500)

            if results:
                self.log_signal.emit(f"✅ 找到 {len(results)} 个文件")
            else:
                self.log_signal.emit("ℹ️ 未找到匹配的文件")
            self.result_signal.emit(results)
        except Exception as e:
            self.error_signal.emit(f"搜索失败：{str(e)}")


# ==================== 主窗口 ====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("档案智盘 v1.0")
        self.resize(1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # ---------- 第一行：目录定位行 ----------
        top_row = QHBoxLayout()
        self.btn_select_dir = QPushButton("📁 选择目录")
        self.btn_select_dir.setFixedWidth(100)
        self.current_path_edit = QLineEdit()
        self.current_path_edit.setReadOnly(True)
        self.current_path_edit.setPlaceholderText("请从左侧树双击选择，或点击「选择目录」按钮")

        top_row.addWidget(self.btn_select_dir)
        top_row.addWidget(self.current_path_edit, 1)
        main_layout.addLayout(top_row)

        # ---------- 第二行：操作按钮 + 右对齐搜索栏 ----------
        action_row = QHBoxLayout()

        self.btn_export = QPushButton("📊 导出清单")
        self.btn_generate = QPushButton("📂 生成模板")

        action_row.addWidget(self.btn_export)
        action_row.addWidget(self.btn_generate)

        action_row.addStretch()

        self.search_scope_combo = QComboBox()
        scope_options = list(SEARCH_SCOPE_OPTIONS) + ["自定义路径"]
        self.search_scope_combo.addItems(scope_options)
        self.search_scope_combo.setFixedWidth(150)
        self.search_scope_combo.currentIndexChanged.connect(self._on_search_scope_changed)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入关键词搜索...")
        self.search_input.setFixedWidth(250)
        self.search_input.returnPressed.connect(self.on_search_clicked)

        self.btn_search = QPushButton("🔍 搜索")
        self.btn_search.setFixedWidth(80)
        self.btn_search.clicked.connect(self.on_search_clicked)

        action_row.addWidget(QLabel("范围:"))
        action_row.addWidget(self.search_scope_combo)
        action_row.addWidget(self.search_input)
        action_row.addWidget(self.btn_search)

        main_layout.addLayout(action_row)

        # ---------- 中间核心区域 ----------
        splitter = QSplitter(Qt.Horizontal)
        self.left_tree = LeftTreeView()
        splitter.addWidget(self.left_tree)
        self.right_stack = RightStackedWidget()
        splitter.addWidget(self.right_stack)
        splitter.setSizes([300, 700])
        main_layout.addWidget(splitter)

        # ---------- 底部状态栏 ----------
        self.statusBar().showMessage("就绪 | 默认过滤: " + ", ".join(DEFAULT_EXTENSIONS))

        # ---------- 菜单栏 ----------
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("设置")
        reconfig_action = QAction("⚙️ 重新配置 Everything 路径", self)
        reconfig_action.triggered.connect(self._reconfigure_everything)
        settings_menu.addAction(reconfig_action)

        self.bind_signals()
        self._init_search_engine()

    def bind_signals(self):
        self.left_tree.folder_selected.connect(self.on_folder_selected)
        self.btn_select_dir.clicked.connect(self.on_select_dir_clicked)

        self.btn_export.clicked.connect(lambda: self.on_action_button_clicked("📊 导出清单"))
        self.btn_generate.clicked.connect(lambda: self.on_action_button_clicked("📂 生成模板"))

        self.right_stack.export_selected_btn.clicked.connect(
            lambda: self.on_action_button_clicked("📊 导出选中清单")
        )

    def on_action_button_clicked(self, button_name):
        self.right_stack.switch_to_log()
        if "导出清单" in button_name:
            self.do_export()
        elif "生成模板" in button_name:
            self.open_template_editor()
        else:
            self.right_stack.append_log(f"🔄 点击：{button_name} (功能开发中)")

    def open_template_editor(self):
        try:
            editor = TemplateEditor(self)
            editor.template_saved.connect(self.on_template_saved)
            editor.exec_()
        except Exception as e:
            self.right_stack.append_log(f"❌ 打开模板编辑器失败：{e}")
            QMessageBox.critical(self, "错误", f"打开模板编辑器失败：{e}")

    def on_template_saved(self, file_path):
        self.right_stack.append_log(f"✅ 模板已保存：{file_path}")
        self.statusBar().showMessage(f"模板已保存：{os.path.basename(file_path)}")

    # ==================== 导出功能 ====================
    def do_export(self):
        root_dir = self.current_path_edit.text().strip()
        if not root_dir or root_dir == "请从左侧树双击选择，或点击「选择目录」按钮":
            QMessageBox.warning(self, "提示", "请先在左侧树双击选择一个文件夹")
            return
        if not os.path.exists(root_dir):
            QMessageBox.warning(self, "提示", f"目录不存在：{root_dir}")
            return

        checked_paths = self.right_stack.get_checked_paths()
        if checked_paths:
            self.right_stack.append_log(f"📋 检测到 {len(checked_paths)} 个被勾选的文件，将只导出这些文件")
        else:
            self.right_stack.append_log("📋 未检测到勾选，将导出全部文件")

        config = ExportConfigManager.load_config()
        last_type = config.get('last_export_type', 'excel')

        dialog = ExportSettingsDialog(self, default_dir=root_dir, default_type=last_type)
        dialog.export_confirmed.connect(
            lambda fields, exp_type, path, only_folders, selected_folders: 
                self._on_export_settings_confirmed(fields, exp_type, path, checked_paths, only_folders, selected_folders)
        )
        dialog.exec_()

    def _on_export_settings_confirmed(self, selected_fields, export_type, output_path, checked_paths, only_folders, selected_folders):
        root_dir = self.current_path_edit.text().strip()
        ext = os.path.splitext(output_path)[1].lower()

        self.right_stack.switch_to_log()
        self.right_stack.append_log(f"⏳ 正在快速统计文件数量...")
        self.statusBar().showMessage("正在预检文件数量...")
        self.btn_export.setEnabled(False)

        # 如果仅导出文件夹，跳过快速计数
        if only_folders:
            self._start_export_with_fields(root_dir, output_path, ext, selected_fields, export_type, checked_paths, only_folders, selected_folders)
            return

        worker = FileWorker()
        count = worker.count_files_fast(root_dir, limit=200)

        if count == -1:
            self.right_stack.append_log("⚠️ 无法统计文件数量（权限不足），继续执行...")
            self._start_export_with_fields(root_dir, output_path, ext, selected_fields, export_type, checked_paths, only_folders, selected_folders)
        elif count > 200:
            reply = QMessageBox.question(
                self,
                "文件数量过多，确认继续？",
                f"检测到 {count}+ 个文件，导出可能需要较长时间，是否继续？\n\n"
                f"💡 建议：文件数超过 200 时，推荐使用「ZIP打包」格式。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._start_export_with_fields(root_dir, output_path, ext, selected_fields, export_type, checked_paths, only_folders, selected_folders)
            else:
                self.right_stack.append_log(f"ℹ️ 用户取消导出（文件数超过 200）")
                self.statusBar().showMessage("已取消")
                self.btn_export.setEnabled(True)
        else:
            self.right_stack.append_log(f"📊 统计结果：{count} 个文件")
            self._start_export_with_fields(root_dir, output_path, ext, selected_fields, export_type, checked_paths, only_folders, selected_folders)

    def _start_export_with_fields(self, root_dir, output_path, ext, selected_fields, export_type, checked_paths, only_folders, selected_folders):
        self.right_stack.append_log(f"⏳ 正在处理，请稍候... (后台运行)")
        if only_folders:
            self.right_stack.append_log(f"📋 仅导出文件夹结构")
            if selected_folders is not None:
                self.right_stack.append_log(f"📋 已自定义选择 {len(selected_folders)} 个文件夹")
        else:
            self.right_stack.append_log(f"📋 导出字段：{', '.join(selected_fields)}")
        if checked_paths and not only_folders:
            self.right_stack.append_log(f"📋 已过滤：只导出 {len(checked_paths)} 个被勾选的文件")
        self.statusBar().showMessage("正在后台处理...")

        self.worker_thread = ExportWorker(
            root_dir, output_path, ext,
            selected_fields=selected_fields,
            export_type=export_type,
            include_paths=checked_paths,
            only_folders=only_folders,
            include_folders=selected_folders  # ⭐ 传递自定义选择的文件夹
        )
        self.worker_thread.log_signal.connect(self.right_stack.append_log)
        self.worker_thread.status_signal.connect(self.statusBar().showMessage)
        self.worker_thread.done_signal.connect(self.on_export_finished)
        self.worker_thread.start()

    def on_export_finished(self, success, msg):
        self.btn_export.setEnabled(True)
        if success:
            self.right_stack.append_log(f"✅ 操作完成：{msg}")
            self.statusBar().showMessage(f"完成：{os.path.basename(msg)}")
            self._open_file_location(msg)
        else:
            self.right_stack.append_log(f"❌ 操作失败：{msg}")
            self.statusBar().showMessage("操作失败")

    def _open_file_location(self, file_path):
        try:
            import subprocess
            subprocess.Popen(['explorer', '/select,', file_path])
        except Exception:
            pass

    # ==================== 搜索功能 ====================
    def _init_search_engine(self):
        available, status = check_everything_status()
        
        if available:
            self.btn_search.setEnabled(True)
            self.search_input.setEnabled(True)
            mode = "es.exe" if get_search_engine().use_es_mode else "SDK"
            self.right_stack.append_log(f"✅ Everything 已就绪 ({mode})")
            self.statusBar().showMessage(f"搜索就绪 ({mode})")
            return
        
        reply = QMessageBox.question(
            self,
            "未找到 Everything",
            f"⚠️ 自动检测失败：{status}\n\n"
            "请选择以下方式之一配置搜索功能：\n"
            "1. 选择 es.exe（Everything 便携版命令行工具）\n"
            "2. 选择 Everything64.dll（Everything 安装版动态库）\n\n"
            "💡 如果您尚未安装 Everything，请先前往官网下载：\n"
            "   https://www.voidtools.com/downloads/\n\n"
            "是否现在配置？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            self._show_file_selector()
        else:
            self.right_stack.append_log("ℹ️ 用户跳过 Everything 配置，搜索功能不可用")
            self.btn_search.setEnabled(False)
            self.search_input.setEnabled(False)
            self.statusBar().showMessage("⚠️ 搜索不可用：请配置 Everything")

    def _show_file_selector(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 es.exe 或 Everything64.dll",
            "",
            "所有支持的文件 (*.exe *.dll);;es.exe (*.exe);;DLL 文件 (*.dll)"
        )
        
        if not file_path:
            self.right_stack.append_log("ℹ️ 用户取消配置，搜索功能不可用")
            self.btn_search.setEnabled(False)
            self.search_input.setEnabled(False)
            self.statusBar().showMessage("⚠️ 搜索不可用")
            return
        
        file_name = os.path.basename(file_path).lower()
        
        success = False
        if file_name == 'es.exe' or file_name.endswith('.exe'):
            success = set_es_path(file_path)
            if success:
                self.right_stack.append_log(f"✅ 已加载 es.exe: {file_path}")
                self.statusBar().showMessage("搜索就绪 (es.exe)")
            else:
                QMessageBox.warning(self, "加载失败", f"无法加载 es.exe：{file_path}")
        elif file_name == 'everything64.dll' or file_name == 'everything.dll':
            success = set_everything_dll_path(file_path)
            if success:
                self.right_stack.append_log(f"✅ 已加载 DLL: {file_path}")
                self.statusBar().showMessage("搜索就绪 (DLL)")
            else:
                QMessageBox.warning(self, "加载失败", f"无法加载 DLL：{file_path}\n\n请确认 Everything 服务正在运行。")
        else:
            QMessageBox.warning(self, "文件类型错误", 
                f"请选择 es.exe 或 Everything64.dll\n您选择的文件：{file_name}")
            self._show_file_selector()
            return
        
        if success:
            self.btn_search.setEnabled(True)
            self.search_input.setEnabled(True)
        else:
            retry = QMessageBox.question(
                self,
                "加载失败",
                "加载失败，是否重新选择？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if retry == QMessageBox.Yes:
                self._show_file_selector()
            else:
                self.right_stack.append_log("⚠️ 用户取消配置，搜索功能不可用")
                self.btn_search.setEnabled(False)
                self.search_input.setEnabled(False)
                self.statusBar().showMessage("⚠️ 搜索不可用")

    def _reconfigure_everything(self):
        self._show_file_selector()

    def _on_search_scope_changed(self, index):
        scope = self.search_scope_combo.currentText()
        if scope == "自定义路径":
            path, ok = QInputDialog.getText(
                self,
                "自定义搜索路径",
                "请输入搜索路径（绝对路径，如 D:\\项目\\2026）：",
                text=self.current_path_edit.text() or ""
            )
            if ok and path.strip():
                if os.path.isdir(path.strip()):
                    self.search_scope_combo.setItemData(index, path.strip(), Qt.UserRole)
                    self.right_stack.append_log(f"📂 自定义搜索路径：{path.strip()}")
                else:
                    QMessageBox.warning(self, "提示", f"路径不存在或不是文件夹：{path.strip()}")
                    self.search_scope_combo.setCurrentIndex(0)
            else:
                self.search_scope_combo.setCurrentIndex(0)

    def on_search_clicked(self):
        keyword = self.search_input.text().strip()
        scope = self.search_scope_combo.currentText()

        if not keyword:
            QMessageBox.information(self, "提示", "请输入搜索关键词")
            return

        available, status = check_everything_status()
        if not available:
            reply = QMessageBox.question(
                self,
                "Everything 未就绪",
                f"⚠️ Everything 状态：{status}\n\n"
                "请确保 Everything 已安装并运行。\n"
                "是否重新配置 Everything 路径？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self._show_file_selector()
            return

        current_dir = self.current_path_edit.text().strip()
        if not current_dir or current_dir == "请从左侧树双击选择，或点击「选择目录」按钮":
            QMessageBox.warning(self, "提示", "请先在左侧树选择一个文件夹")
            return
        if not os.path.isdir(current_dir):
            QMessageBox.warning(self, "提示", f"当前目录无效：{current_dir}")
            return

        custom_path = None
        if scope == "自定义路径":
            custom_path = self.search_scope_combo.itemData(
                self.search_scope_combo.currentIndex(), Qt.UserRole
            )
            if not custom_path or not os.path.isdir(custom_path):
                QMessageBox.warning(self, "提示", "请先设置有效的自定义搜索路径")
                self._on_search_scope_changed(self.search_scope_combo.currentIndex())
                return

        self.right_stack.switch_to_search()

        self.search_worker = SearchWorker(keyword, scope, current_dir=current_dir, custom_path=custom_path)
        self.search_worker.result_signal.connect(self._on_search_results)
        self.search_worker.log_signal.connect(self.right_stack.append_log)
        self.search_worker.status_signal.connect(self.statusBar().showMessage)
        self.search_worker.error_signal.connect(self._on_search_error)
        self.search_worker.start()

        self.btn_search.setEnabled(False)
        self.search_input.setEnabled(False)

    def _on_search_results(self, results):
        self.btn_search.setEnabled(True)
        self.search_input.setEnabled(True)
        self.right_stack.display_search_results(results, keyword=self.search_input.text().strip())

    def _on_search_error(self, error_msg):
        self.btn_search.setEnabled(True)
        self.search_input.setEnabled(True)
        self.right_stack.append_log(f"❌ {error_msg}")
        QMessageBox.warning(self, "搜索失败", error_msg)

    # ==================== 其他槽函数 ====================
    def on_folder_selected(self, path):
        self.current_path_edit.setText(path)
        self.right_stack.switch_to_preview()
        self.right_stack.refresh_preview(path)
        self.right_stack.append_log(f"📂 选定工作目录: {path}")
        self.statusBar().showMessage(f"当前目录: {path}")

    def on_select_dir_clicked(self):
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择工作目录",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if dir_path:
            self.current_path_edit.setText(dir_path)
            self.right_stack.append_log(f"📂 通过弹窗选定: {dir_path}")
            self.statusBar().showMessage(f"当前目录: {dir_path}")
        else:
            self.right_stack.append_log("ℹ️ 用户取消了目录选择")