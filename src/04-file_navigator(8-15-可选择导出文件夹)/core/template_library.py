"""
模板库管理器 - 保存/加载/删除/重命名/导出模板
"""

import os
import json
import shutil
from datetime import datetime
from typing import List, Dict, Optional


class TemplateLibrary:
    """模板库管理器"""

    @staticmethod
    def get_library_path() -> str:
        """获取模板库根目录"""
        config_dir = os.path.join(os.environ.get('APPDATA', ''), '档案智盘')
        lib_dir = os.path.join(config_dir, 'templates')
        os.makedirs(lib_dir, exist_ok=True)
        return lib_dir

    @staticmethod
    def get_index_path() -> str:
        """获取索引文件路径"""
        return os.path.join(TemplateLibrary.get_library_path(), 'index.json')

    @staticmethod
    def load_index() -> List[Dict]:
        """加载模板索引"""
        index_path = TemplateLibrary.get_index_path()
        if os.path.exists(index_path):
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('templates', [])
            except Exception:
                return []
        return []

    @staticmethod
    def save_index(templates: List[Dict]) -> bool:
        """保存模板索引"""
        index_path = TemplateLibrary.get_index_path()
        try:
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump({'templates': templates}, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    @staticmethod
    def _count_folders(tree_data: List[Dict]) -> int:
        """统计文件夹数量"""
        count = 0

        def traverse(nodes):
            nonlocal count
            for node in nodes:
                count += 1
                traverse(node.get('children', []))

        traverse(tree_data)
        return count

    @staticmethod
    def save_template(name: str, tree_data: List[Dict]) -> bool:
        """
        保存模板到库

        Args:
            name: 模板名称
            tree_data: 树形数据

        Returns:
            bool: 是否成功
        """
        if not name or not name.strip():
            return False

        lib_path = TemplateLibrary.get_library_path()
        # 生成文件名（去除特殊字符）
        safe_name = ''.join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        if not safe_name:
            safe_name = f"template_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        file_name = f"{safe_name}.json"
        file_path = os.path.join(lib_path, file_name)

        # 保存模板文件
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(tree_data, f, ensure_ascii=False, indent=2)
        except Exception:
            return False

        # 更新索引
        index = TemplateLibrary.load_index()
        # 检查是否已存在同名模板
        for i, t in enumerate(index):
            if t['name'] == name:
                # 删除旧文件
                old_file = os.path.join(lib_path, t.get('file', ''))
                if os.path.exists(old_file) and old_file != file_path:
                    try:
                        os.remove(old_file)
                    except Exception:
                        pass
                index[i] = {
                    'name': name,
                    'file': file_name,
                    'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'folder_count': TemplateLibrary._count_folders(tree_data)
                }
                return TemplateLibrary.save_index(index)

        # 新增
        index.append({
            'name': name,
            'file': file_name,
            'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'folder_count': TemplateLibrary._count_folders(tree_data)
        })
        return TemplateLibrary.save_index(index)

    @staticmethod
    def load_template(name: str) -> Optional[List[Dict]]:
        """
        从库加载模板

        Args:
            name: 模板名称

        Returns:
            list: 树形数据，失败返回 None
        """
        index = TemplateLibrary.load_index()
        for t in index:
            if t['name'] == name:
                file_path = os.path.join(TemplateLibrary.get_library_path(), t.get('file', ''))
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            return json.load(f)
                    except Exception:
                        return None
        return None

    @staticmethod
    def delete_template(name: str) -> bool:
        """删除模板"""
        index = TemplateLibrary.load_index()
        for i, t in enumerate(index):
            if t['name'] == name:
                file_path = os.path.join(TemplateLibrary.get_library_path(), t.get('file', ''))
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                del index[i]
                return TemplateLibrary.save_index(index)
        return False

    @staticmethod
    def rename_template(old_name: str, new_name: str) -> bool:
        """重命名模板"""
        if not new_name or not new_name.strip():
            return False
        if old_name == new_name:
            return True

        index = TemplateLibrary.load_index()
        for i, t in enumerate(index):
            if t['name'] == old_name:
                # 更新文件名
                old_file = t.get('file', '')
                safe_name = ''.join(c for c in new_name if c.isalnum() or c in (' ', '-', '_')).strip()
                if not safe_name:
                    safe_name = f"template_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                new_file = f"{safe_name}.json"
                lib_path = TemplateLibrary.get_library_path()
                old_path = os.path.join(lib_path, old_file)
                new_path = os.path.join(lib_path, new_file)
                if os.path.exists(old_path) and old_file != new_file:
                    try:
                        os.rename(old_path, new_path)
                    except Exception:
                        pass
                index[i] = {
                    'name': new_name,
                    'file': new_file,
                    'created': t.get('created', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    'folder_count': t.get('folder_count', 0)
                }
                return TemplateLibrary.save_index(index)
        return False

    @staticmethod
    def export_template(name: str, export_path: str) -> bool:
        """导出模板为 JSON 文件"""
        data = TemplateLibrary.load_template(name)
        if data is None:
            return False
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    @staticmethod
    def get_template_names() -> List[str]:
        """获取所有模板名称列表"""
        index = TemplateLibrary.load_index()
        return [t.get('name', '') for t in index if t.get('name')]

    @staticmethod
    def get_template_info(name: str) -> Optional[Dict]:
        """获取模板信息"""
        index = TemplateLibrary.load_index()
        for t in index:
            if t['name'] == name:
                return t
        return None