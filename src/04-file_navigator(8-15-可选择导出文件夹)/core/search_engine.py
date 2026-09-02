"""
Everything 搜索引擎封装
支持：SDK (DLL) 方式 + es.exe 命令行方式（降级备用）
"""

import ctypes
import os
import platform
import subprocess
import time
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class EverythingEngine:
    """Everything 搜索引擎（支持 SDK + es.exe 双模式）"""

    SORT_DATE_MODIFIED_DESCENDING = 13

    def __init__(self):
        self.dll = None
        self.is_available = False
        self.everything_exe_path = None
        self.dll_path = None
        self.es_exe_path = None
        self.use_es_mode = False

        self._load_config()
        self._init_sdk()
        if not self.is_available:
            self._init_es_mode()

    # ==================== 配置文件管理 ====================
    def _get_config_path(self) -> str:
        config_dir = os.path.join(os.environ.get('APPDATA', ''), '档案智盘')
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, 'everything_path.json')

    def _load_config(self):
        config_path = self._get_config_path()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.dll_path = data.get('dll_path', '')
                    if self.dll_path and not os.path.exists(self.dll_path):
                        self.dll_path = None
                    self.es_exe_path = data.get('es_exe_path', '')
                    if self.es_exe_path and not os.path.exists(self.es_exe_path):
                        self.es_exe_path = None
            except Exception:
                pass

    def save_dll_path(self, dll_path: str):
        self.dll_path = dll_path
        self._save_config()

    def save_es_path(self, es_path: str):
        self.es_exe_path = es_path
        self._save_config()

    def _save_config(self):
        config_path = self._get_config_path()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'dll_path': self.dll_path,
                    'es_exe_path': self.es_exe_path
                }, f, indent=2)
        except Exception:
            pass

    # ==================== SDK 初始化 ====================
    def _init_sdk(self):
        if platform.system() != 'Windows':
            self.is_available = False
            return

        if self.dll_path and os.path.exists(self.dll_path):
            if self._try_load_dll(self.dll_path):
                self.everything_exe_path = self._find_everything_exe_from_dll(self.dll_path)
                return

        exe_path = self._get_everything_path_from_app_paths()
        if exe_path:
            dll_path = self._get_dll_from_exe_path(exe_path)
            if dll_path and self._try_load_dll(dll_path):
                self.dll_path = dll_path
                self.everything_exe_path = exe_path
                self.save_dll_path(dll_path)
                return

        found_path = self._find_dll_auto()
        if found_path and self._try_load_dll(found_path):
            self.dll_path = found_path
            self.everything_exe_path = self._find_everything_exe_from_dll(found_path)
            self.save_dll_path(found_path)
            return

        self.is_available = False
        self.dll = None

    def _try_load_dll(self, dll_path: str) -> bool:
        try:
            self.dll = ctypes.WinDLL(dll_path)
            self.dll.Everything_IsDBLoaded()
            self.is_available = True
            return True
        except Exception:
            self.is_available = False
            return False

    def _get_everything_path_from_app_paths(self) -> Optional[str]:
        if platform.system() != 'Windows':
            return None
        try:
            import winreg
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Everything.exe"
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                exe_path = winreg.QueryValueEx(key, "")[0]
                winreg.CloseKey(key)
                if exe_path and os.path.exists(exe_path):
                    return exe_path
            except FileNotFoundError:
                pass
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
                exe_path = winreg.QueryValueEx(key, "")[0]
                winreg.CloseKey(key)
                if exe_path and os.path.exists(exe_path):
                    return exe_path
            except FileNotFoundError:
                pass
        except Exception:
            pass
        return None

    def _get_dll_from_exe_path(self, exe_path: str) -> Optional[str]:
        if not exe_path:
            return None
        install_dir = os.path.dirname(exe_path)
        for dll_name in ["Everything64.dll", "Everything.dll"]:
            dll_path = os.path.join(install_dir, dll_name)
            if os.path.exists(dll_path):
                return dll_path
        return None

    def _find_dll_auto(self) -> Optional[str]:
        search_paths = [
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'Everything', 'Everything64.dll'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Everything', 'Everything64.dll'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Everything', 'Everything64.dll'),
        ]
        for path in search_paths:
            if os.path.exists(path):
                return path
        return None

    def _find_everything_exe_from_dll(self, dll_path: str) -> Optional[str]:
        install_dir = os.path.dirname(dll_path)
        exe_path = os.path.join(install_dir, "Everything.exe")
        if os.path.exists(exe_path):
            return exe_path
        return None

    # ==================== es.exe 模式 ====================
    def _init_es_mode(self):
        if platform.system() != 'Windows':
            self.is_available = False
            return

        if self.es_exe_path and os.path.exists(self.es_exe_path):
            self.is_available = True
            self.use_es_mode = True
            return

        found = self._find_es_exe()
        if found:
            self.es_exe_path = found
            self.is_available = True
            self.use_es_mode = True
            self.save_es_path(found)
            return

        self.is_available = False
        self.use_es_mode = False

    def _find_es_exe(self) -> Optional[str]:
        search_paths = []

        for drive in ['D:', 'C:', 'E:', 'F:']:
            for base in ['Everything', 'Program Files\\Everything', 'Program Files (x86)\\Everything']:
                search_paths.append(os.path.join(drive, base, 'es.exe'))

        if self.everything_exe_path:
            install_dir = os.path.dirname(self.everything_exe_path)
            search_paths.append(os.path.join(install_dir, "es.exe"))

        if self.dll_path:
            install_dir = os.path.dirname(self.dll_path)
            search_paths.append(os.path.join(install_dir, "es.exe"))

        for prog in [os.environ.get('PROGRAMFILES', 'C:\\Program Files'),
                     os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')]:
            search_paths.append(os.path.join(prog, 'Everything', 'es.exe'))

        search_paths.append(os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Everything', 'es.exe'))
        search_paths.append(os.path.join(os.getcwd(), 'es.exe'))

        for path in os.environ.get('PATH', '').split(';'):
            if path.strip():
                search_paths.append(os.path.join(path.strip(), 'es.exe'))

        seen = set()
        unique_paths = []
        for p in search_paths:
            if p not in seen:
                seen.add(p)
                unique_paths.append(p)

        for path in unique_paths:
            if path and os.path.exists(path):
                return path

        return None

    # ==================== 统一搜索接口 ====================
    def search(self, query: str, search_path: Optional[str] = None,
               search_mode: str = 'path', max_results: int = 500) -> List[Dict]:
        if self.use_es_mode:
            return self._search_via_es(query, search_path, search_mode, max_results)

        if not self.is_available or not self.dll:
            if self.es_exe_path and os.path.exists(self.es_exe_path):
                self.use_es_mode = True
                return self._search_via_es(query, search_path, search_mode, max_results)
            return []

        try:
            return self._search_via_sdk(query, search_path, search_mode, max_results)
        except Exception as e:
            print(f"[搜索] SDK 失败：{e}")
            if self.es_exe_path and os.path.exists(self.es_exe_path):
                self.use_es_mode = True
                return self._search_via_es(query, search_path, search_mode, max_results)
            return []

    # ==================== SDK 搜索 ====================
    def _search_via_sdk(self, query: str, search_path: Optional[str],
                        search_mode: str, max_results: int) -> List[Dict]:
        if search_mode == 'path' and search_path:
            full_query = f'path:"{search_path}" {query}'
        elif search_mode == 'parent' and search_path:
            full_query = f'parent:"{search_path}" {query}'
        else:
            full_query = query

        self.dll.Everything_SetSearchW(full_query)
        self.dll.Everything_SetSort(self.SORT_DATE_MODIFIED_DESCENDING)
        self.dll.Everything_SetMax(max_results)
        self.dll.Everything_Query(True)

        num_results = self.dll.Everything_GetNumResults()
        num_results = min(num_results, max_results)

        results = []
        for i in range(num_results):
            try:
                buff = ctypes.create_unicode_buffer(520)
                self.dll.Everything_GetResultFullPathNameW(i, buff, len(buff))
                path = buff.value
                if not path:
                    continue

                file_name_ptr = self.dll.Everything_GetResultFileName(i)
                file_name = file_name_ptr if file_name_ptr else os.path.basename(path)
                size_bytes = self.dll.Everything_GetResultSize(i)
                filetime = self.dll.Everything_GetResultDateModified(i)
                modified = self._filetime_to_datetime(filetime)
                is_dir = os.path.isdir(path)

                results.append({
                    'name': file_name,
                    'path': path,
                    'size_bytes': size_bytes,
                    'size': self._format_size(size_bytes),
                    'modified': modified,
                    'is_dir': is_dir,
                })
            except Exception:
                continue

        return results

    # ==================== es.exe 搜索（修复版：parent 也使用 -path） ====================
    def _search_via_es(self, query: str, search_path: Optional[str],
                       search_mode: str, max_results: int) -> List[Dict]:
        if not self.es_exe_path or not os.path.exists(self.es_exe_path):
            return []

        cmd = [self.es_exe_path, '-n', str(max_results)]

        # ⭐ 修复：parent 和 path 都使用 -path 参数（对中文支持更好）
        if search_mode in ['path', 'parent'] and search_path:
            cmd.extend(['-path', search_path])

        cmd.append(query)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
                encoding='utf-8',
                errors='ignore'
            )

            if result.returncode != 0:
                return []

            lines = result.stdout.strip().split('\n')
            if not lines or (len(lines) == 1 and not lines[0]):
                return []

            results = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    stat = os.stat(line)
                    size_bytes = stat.st_size
                    mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    is_dir = os.path.isdir(line)
                    name = os.path.basename(line)

                    results.append({
                        'name': name,
                        'path': line,
                        'size_bytes': size_bytes,
                        'size': self._format_size(size_bytes),
                        'modified': mtime,
                        'is_dir': is_dir,
                    })
                except (PermissionError, OSError):
                    continue

            return results

        except subprocess.TimeoutExpired:
            print("[搜索] es.exe 超时")
            return []
        except Exception as e:
            print(f"[搜索] es.exe 执行失败：{e}")
            return []

    def _filetime_to_datetime(self, filetime) -> str:
        if not filetime:
            return ''
        try:
            unix_timestamp = (filetime / 10000000) - 11644473600
            if unix_timestamp < 0:
                return ''
            dt = datetime.fromtimestamp(unix_timestamp)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return ''

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes < 0:
            return '-'
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def check_service_running(self) -> bool:
        if self.use_es_mode:
            return self.es_exe_path is not None and os.path.exists(self.es_exe_path)
        if not self.is_available or not self.dll:
            return False
        try:
            return bool(self.dll.Everything_IsDBLoaded())
        except Exception:
            return False

    def start_service(self) -> bool:
        if self.use_es_mode:
            return True
        if not self.everything_exe_path or not os.path.exists(self.everything_exe_path):
            return False
        try:
            subprocess.Popen(
                [self.everything_exe_path, '-startup'],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            for _ in range(10):
                time.sleep(0.5)
                if self.check_service_running():
                    return True
            return False
        except Exception:
            return False

    def ensure_service_running(self) -> Tuple[bool, str]:
        if self.use_es_mode:
            if self.es_exe_path and os.path.exists(self.es_exe_path):
                return True, "es.exe 就绪"
            return False, "es.exe 未找到"

        if not self.is_available:
            if self._init_es_mode() and self.es_exe_path:
                return True, "es.exe 就绪"
            return False, "Everything 未找到"

        if self.check_service_running():
            return True, "服务运行中"

        if self.start_service():
            return True, "服务已启动"

        return False, "Everything 服务未运行，请手动启动"

    def set_dll_path_manually(self, dll_path: str) -> bool:
        if not os.path.exists(dll_path):
            return False
        if self._try_load_dll(dll_path):
            self.dll_path = dll_path
            self.everything_exe_path = self._find_everything_exe_from_dll(dll_path)
            self.save_dll_path(dll_path)
            self.use_es_mode = False
            return True
        return False

    def set_es_path_manually(self, es_path: str) -> bool:
        if not os.path.exists(es_path):
            return False
        self.es_exe_path = es_path
        self.use_es_mode = True
        self.is_available = True
        self.save_es_path(es_path)
        return True


# ==================== 全局单例 ====================
_engine_instance = None


def get_search_engine() -> EverythingEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = EverythingEngine()
    return _engine_instance


def check_everything_status() -> Tuple[bool, str]:
    engine = get_search_engine()
    return engine.ensure_service_running()


def set_everything_dll_path(dll_path: str) -> bool:
    engine = get_search_engine()
    return engine.set_dll_path_manually(dll_path)


def set_es_path(es_path: str) -> bool:
    engine = get_search_engine()
    return engine.set_es_path_manually(es_path)