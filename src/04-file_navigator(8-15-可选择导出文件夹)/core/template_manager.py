"""
模板数据管理 - 保存、加载、解析模板
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PyQt5.QtWidgets import QTreeWidgetItem


class TemplateManager:
    """模板数据管理器"""

    # ==================== 隐藏文件夹检测 ====================

    @staticmethod
    def is_hidden_folder(path: Path) -> bool:
        """判断是否为隐藏文件夹（名称以 . 开头）"""
        return path.name.startswith('.')

    @staticmethod
    def get_hidden_folders(root_path: str) -> List[str]:
        """扫描文件夹，收集所有隐藏文件夹路径"""
        hidden_folders = []

        def scan(path: Path):
            try:
                for child in path.iterdir():
                    if child.is_dir():
                        if TemplateManager.is_hidden_folder(child):
                            hidden_folders.append(str(child))
                        scan(child)
            except (PermissionError, OSError):
                pass

        root = Path(root_path)
        if root.is_dir():
            scan(root)
        return hidden_folders

    # ==================== 从文件夹识别结构 ====================

    @staticmethod
    def folder_to_template(root_path: str, include_hidden: bool = False) -> List[Dict]:
        """
        扫描文件夹，提取纯文件夹结构（忽略文件），返回树形字典
        包含根文件夹本身作为树的根节点

        Args:
            root_path: 要扫描的文件夹路径
            include_hidden: 是否包含隐藏文件夹（以 . 开头的文件夹）

        Returns:
            list: 树形结构的字典列表
        """
        def build_tree(path: Path) -> Dict:
            result = {'name': path.name, 'children': []}
            try:
                for child in path.iterdir():
                    if child.is_dir():
                        if not include_hidden and TemplateManager.is_hidden_folder(child):
                            continue
                        result['children'].append(build_tree(child))
            except (PermissionError, OSError):
                pass
            return result

        root = Path(root_path)
        if not root.is_dir():
            return []

        root_node = build_tree(root)
        if root_node['children']:
            return [root_node]
        else:
            return [{'name': root.name, 'children': []}]

    @staticmethod
    def scan_folder_structure(root_path: str, include_hidden: bool = False) -> Tuple[List[Dict], List[str]]:
        """
        扫描文件夹结构，同时返回树形数据和隐藏文件夹列表
        包含根文件夹本身作为树的根节点
        """
        hidden_folders = []
        found_hidden = []

        def build_tree_with_collect(path: Path) -> Dict:
            result = {'name': path.name, 'children': []}
            try:
                for child in path.iterdir():
                    if child.is_dir():
                        if TemplateManager.is_hidden_folder(child):
                            found_hidden.append(str(child))
                            if not include_hidden:
                                continue
                        result['children'].append(build_tree_with_collect(child))
            except (PermissionError, OSError):
                pass
            return result

        root = Path(root_path)
        if not root.is_dir():
            return [], []

        root_node = build_tree_with_collect(root)
        if root_node['children'] or root_node['name']:
            return [root_node], found_hidden
        else:
            return [], found_hidden

    # ==================== QTreeWidget 转换 ====================

    @staticmethod
    def tree_to_dict(tree_items: List) -> List[Dict]:
        """将 QTreeWidget 的树形结构转换为字典列表"""
        def convert_item(item) -> Dict:
            result = {
                'name': item.text(0).replace('📁 ', '').strip(),
                'children': []
            }
            for i in range(item.childCount()):
                child = item.child(i)
                result['children'].append(convert_item(child))
            return result

        result = []
        for item in tree_items:
            result.append(convert_item(item))
        return result

    @staticmethod
    def dict_to_tree(tree_data: List[Dict], tree_widget) -> None:
        """将字典列表还原到 QTreeWidget"""
        tree_widget.clear()

        def add_children(parent_item, children: List[Dict]):
            for child_data in children:
                name = child_data.get('name', '未命名')
                if parent_item is None:
                    item = QTreeWidgetItem(tree_widget)
                else:
                    item = QTreeWidgetItem(parent_item)
                item.setText(0, f"📁 {name}")
                if parent_item:
                    parent_item.addChild(item)
                else:
                    tree_widget.addTopLevelItem(item)
                add_children(item, child_data.get('children', []))

        add_children(None, tree_data)

    @staticmethod
    def get_root_items(tree_widget) -> List:
        """获取 QTreeWidget 的所有顶层项目"""
        return [tree_widget.topLevelItem(i) for i in range(tree_widget.topLevelItemCount())]

    # ==================== JSON 保存/加载 ====================

    @staticmethod
    def save_to_json(tree_items: List, file_path: str) -> bool:
        """将树形结构保存为 JSON 文件"""
        try:
            data = TemplateManager.tree_to_dict(tree_items)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存模板失败：{e}")
            return False

    @staticmethod
    def load_from_json(file_path: str) -> Optional[List[Dict]]:
        """从 JSON 文件加载模板数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"加载模板失败：{e}")
            return None

    # ==================== Excel 导出/导入 ====================

    @staticmethod
    def save_to_excel(tree_items: List, file_path: str) -> bool:
        """将树形结构导出为 Excel 文件"""
        try:
            rows = []

            def traverse(item, parent_path: str = ''):
                name = item.text(0).replace('📁 ', '').strip()
                rows.append({'父级路径': parent_path, '文件夹名': name})
                full_path = f"{parent_path}/{name}" if parent_path else name
                for i in range(item.childCount()):
                    traverse(item.child(i), full_path)

            for item in tree_items:
                traverse(item)

            import pandas as pd
            df = pd.DataFrame(rows)
            df.to_excel(file_path, index=False)
            return True
        except Exception as e:
            print(f"导出 Excel 失败：{e}")
            return False

    @staticmethod
    def load_from_excel(file_path: str) -> Optional[List[Dict]]:
        """从 Excel 文件加载模板"""
        try:
            import pandas as pd
            df = pd.read_excel(file_path)

            parent_col = None
            name_col = None
            for col in df.columns:
                col_lower = col.lower().strip()
                if '父' in col or 'parent' in col_lower or '路径' in col:
                    parent_col = col
                elif '文件夹' in col or '名' in col or 'name' in col_lower:
                    name_col = col

            if parent_col is None or name_col is None:
                parent_col = df.columns[0]
                name_col = df.columns[1]

            tree = []
            node_map = {}

            for _, row in df.iterrows():
                parent_path = str(row[parent_col]).strip() if pd.notna(row[parent_col]) else ''
                name = str(row[name_col]).strip() if pd.notna(row[name_col]) else ''
                if not name:
                    continue

                if parent_path == '' or parent_path == 'nan' or parent_path == 'None':
                    node = {'name': name, 'children': []}
                    tree.append(node)
                    node_map[name] = node
                else:
                    parts = parent_path.split('/')
                    current = None
                    for part in parts:
                        if current is None:
                            found = None
                            for root_node in tree:
                                if root_node['name'] == part:
                                    found = root_node
                                    break
                            if found is None:
                                found = {'name': part, 'children': []}
                                tree.append(found)
                            current = found
                        else:
                            found = None
                            for child in current['children']:
                                if child['name'] == part:
                                    found = child
                                    break
                            if found is None:
                                found = {'name': part, 'children': []}
                                current['children'].append(found)
                            current = found

                    node = {'name': name, 'children': []}
                    current['children'].append(node)
                    full_path = f"{parent_path}/{name}"
                    node_map[full_path] = node

            return tree
        except Exception as e:
            print(f"加载 Excel 失败：{e}")
            return None

    # ==================== 统计 ====================

    @staticmethod
    def get_folder_count(tree_data: List[Dict]) -> int:
        """统计文件夹总数"""
        count = 0

        def traverse(nodes):
            nonlocal count
            for node in nodes:
                count += 1
                traverse(node.get('children', []))

        traverse(tree_data)
        return count

    @staticmethod
    def get_folder_count_from_tree(tree_widget) -> int:
        """从 QTreeWidget 统计文件夹总数"""
        def count_items(item):
            cnt = 1
            for i in range(item.childCount()):
                cnt += count_items(item.child(i))
            return cnt

        total = 0
        for i in range(tree_widget.topLevelItemCount()):
            total += count_items(tree_widget.topLevelItem(i))
        return total

    # ==================== 生成空文件夹 ====================

    @staticmethod
    def generate_folders(root_dir: str, tree_data: List[Dict]) -> Tuple[bool, str]:
        """根据模板生成空文件夹"""
        if not tree_data:
            return False, "模板为空，没有可生成的内容"

        if not os.path.exists(root_dir):
            return False, f"根目录不存在：{root_dir}"

        created_count = 0
        skipped_count = 0
        error_count = 0
        error_list = []

        def create_nodes(base_path, nodes):
            nonlocal created_count, skipped_count, error_count, error_list
            for node in nodes:
                name = node.get('name', '未命名')
                folder_path = os.path.join(base_path, name)
                try:
                    if os.path.exists(folder_path):
                        skipped_count += 1
                    else:
                        os.makedirs(folder_path, exist_ok=True)
                        created_count += 1
                except Exception as e:
                    error_count += 1
                    error_list.append(f"{folder_path}: {str(e)}")

                create_nodes(folder_path, node.get('children', []))

        create_nodes(root_dir, tree_data)

        msg = f"✅ 已创建 {created_count} 个文件夹，{skipped_count} 个已存在（跳过）"
        if error_count > 0:
            msg += f"，{error_count} 个创建失败"
            if len(error_list) <= 3:
                msg += f"\n失败详情：{'; '.join(error_list)}"
            else:
                msg += f"\n失败详情：{'; '.join(error_list[:3])} ... 还有 {error_count - 3} 个"

        return True, msg