"""
导出配置管理器 - 保存/加载用户的导出字段选择
"""

import os
import json
from typing import List, Dict, Optional

# 所有可用字段（固定）
AVAILABLE_FIELDS = [
    {"id": "文件名", "default": True},
    {"id": "后缀", "default": False},
    {"id": "完整路径", "default": True},
    {"id": "文件大小", "default": True},
    {"id": "修改时间", "default": True},
    {"id": "所在文件夹", "default": False},
]


class ExportConfigManager:
    """导出配置管理器"""

    @staticmethod
    def get_config_path() -> str:
        """获取配置文件路径"""
        config_dir = os.path.join(os.environ.get('APPDATA', ''), '档案智盘')
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, 'export_config.json')

    @staticmethod
    def load_config() -> Dict:
        """
        加载导出配置

        Returns:
            dict: {
                'selected_fields': ['文件名', '完整路径', ...],
                'last_export_path': '',  # 上次导出路径（可选）
                'last_export_type': 'excel'  # 'excel' | 'zip'
            }
        """
        default_config = {
            'selected_fields': [f['id'] for f in AVAILABLE_FIELDS if f['default']],
            'last_export_path': '',
            'last_export_type': 'excel'
        }

        config_path = ExportConfigManager.get_config_path()
        if not os.path.exists(config_path):
            return default_config

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 确保 selected_fields 存在
                if 'selected_fields' not in data:
                    data['selected_fields'] = default_config['selected_fields']
                # 过滤掉无效字段（防止旧配置文件包含已删除的字段）
                valid_field_ids = [f['id'] for f in AVAILABLE_FIELDS]
                data['selected_fields'] = [f for f in data['selected_fields'] if f in valid_field_ids]
                if not data['selected_fields']:
                    data['selected_fields'] = default_config['selected_fields']
                return data
        except Exception:
            return default_config

    @staticmethod
    def save_config(selected_fields: List[str], last_export_path: str = '', last_export_type: str = 'excel') -> bool:
        """
        保存导出配置

        Args:
            selected_fields: 选择的字段列表
            last_export_path: 上次导出路径
            last_export_type: 导出类型 ('excel' | 'zip')

        Returns:
            bool: 是否成功
        """
        config_path = ExportConfigManager.get_config_path()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'selected_fields': selected_fields,
                    'last_export_path': last_export_path,
                    'last_export_type': last_export_type
                }, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    @staticmethod
    def get_available_fields() -> List[Dict]:
        """获取所有可用字段（含默认状态）"""
        return AVAILABLE_FIELDS

    @staticmethod
    def get_field_display_name(field_id: str) -> str:
        """获取字段显示名称"""
        mapping = {
            '文件名': '文件名',
            '后缀': '后缀',
            '完整路径': '完整路径',
            '文件大小': '文件大小',
            '修改时间': '修改时间',
            '所在文件夹': '所在文件夹',
        }
        return mapping.get(field_id, field_id)

    @staticmethod
    def get_field_mapping() -> Dict[str, str]:
        """获取字段ID到显示名称的映射"""
        return {
            '文件名': '文件名',
            '后缀': '后缀',
            '完整路径': '完整路径',
            '文件大小': '文件大小',
            '修改时间': '修改时间',
            '所在文件夹': '所在文件夹',
        }