"""
FileWorker 模块独立测试脚本
运行方式：python test_file_worker.py
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.file_worker import FileWorker


def test_scan():
    """测试 1：遍历目录 + 空文件夹检测"""
    print("=" * 50)
    print("测试 1：遍历目录 + 空文件夹检测")
    print("=" * 50)
    
    # 选择一个你电脑上真实存在的、有文件的目录（比如当前项目目录）
    test_dir = r"D:\python_tool\04-file_navigator"  # 根据你的实际路径调整
    
    if not os.path.exists(test_dir):
        print(f"❌ 路径不存在：{test_dir}")
        print("请修改 test_dir 变量为你电脑上真实存在的路径")
        return False
    
    worker = FileWorker()
    result = worker.scan_directory(
        root_dir=test_dir,
        extensions=['.py', '.txt', '.md'],  # 只扫描 Python 文件
        detect_empty=True
    )
    
    print(f"✅ 扫描完成！")
    print(f"   📄 文件总数：{result['total_count']}")
    print(f"   ⏱️  耗时：{result['scan_time']:.2f} 秒")
    print(f"   📂 空文件夹数：{len(result['empty_folders'])}")
    
    if result['empty_folders']:
        print("   空文件夹列表：")
        for folder in result['empty_folders'][:5]:  # 只显示前5个
            print(f"      - {folder}")
        if len(result['empty_folders']) > 5:
            print(f"      ... 还有 {len(result['empty_folders']) - 5} 个")
    
    # 显示前3个文件信息
    print("\n   前3个文件示例：")
    for i, item in enumerate(result['files'][:3]):
        print(f"      {i+1}. {item['文件名']} ({item['文件大小']}) - {item['修改时间']}")
    
    return True


def test_export_excel():
    """测试 2：导出 Excel（含超链接 + 空文件夹 Sheet）"""
    print("\n" + "=" * 50)
    print("测试 2：导出 Excel（含超链接 + 空文件夹 Sheet）")
    print("=" * 50)
    
    test_dir = r"D:\python_tool\04-file_navigator"
    output_path = r"D:\python_tool\test_output.xlsx"
    
    if not os.path.exists(test_dir):
        print(f"❌ 路径不存在：{test_dir}")
        return False
    
    worker = FileWorker()
    worker.scan_directory(test_dir, extensions=['.py', '.txt'], detect_empty=True)
    
    success = worker.export_to_excel(
        output_path=output_path,
        with_hyperlink=True,
        include_empty_folders=True
    )
    
    if success:
        print(f"✅ Excel 导出成功：{output_path}")
        print("   📊 请打开 Excel 文件，检查：")
        print("      - 「完整路径」列是否显示为蓝色超链接")
        print("      - 点击超链接是否能打开文件")
        print("      - 是否有「空文件夹列表」Sheet")
        return True
    else:
        print(f"❌ Excel 导出失败")
        return False


def test_export_html():
    """测试 3：导出 HTML 可视化目录"""
    print("\n" + "=" * 50)
    print("测试 3：导出 HTML 可视化目录")
    print("=" * 50)
    
    test_dir = r"D:\python_tool\04-file_navigator"
    output_path = r"D:\python_tool\test_output.html"
    
    if not os.path.exists(test_dir):
        print(f"❌ 路径不存在：{test_dir}")
        return False
    
    worker = FileWorker()
    worker.scan_directory(test_dir, extensions=None, detect_empty=False)  # 不过滤，全量导出
    
    success = worker.export_to_html(
        output_path=output_path,
        title="档案智盘 - 目录树测试"
    )
    
    if success:
        print(f"✅ HTML 导出成功：{output_path}")
        print("   🌐 请用浏览器打开 HTML 文件，检查：")
        print("      - 目录树是否层级清晰")
        print("      - 点击文件是否能打开")
        print("      - 搜索功能是否正常")
        return True
    else:
        print(f"❌ HTML 导出失败")
        return False


def test_empty_folder_only():
    """测试 4：专门检测空文件夹（无文件）"""
    print("\n" + "=" * 50)
    print("测试 4：专门检测空文件夹")
    print("=" * 50)
    
    # 创建一个临时测试目录（含空文件夹）
    import tempfile
    import shutil
    
    temp_dir = tempfile.mkdtemp(prefix="档案智盘测试_")
    print(f"📂 创建临时测试目录：{temp_dir}")
    
    # 创建目录结构
    os.makedirs(os.path.join(temp_dir, "有文件的文件夹"), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "空文件夹1"), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "子级", "空文件夹2"), exist_ok=True)
    
    # 在有文件的文件夹里放一个文件
    with open(os.path.join(temp_dir, "有文件的文件夹", "test.txt"), 'w') as f:
        f.write("测试文件")
    
    worker = FileWorker()
    result = worker.scan_directory(temp_dir, extensions=None, detect_empty=True)
    
    print(f"   文件总数：{result['total_count']}")
    print(f"   空文件夹数：{len(result['empty_folders'])}")
    
    if len(result['empty_folders']) == 2:
        print("   ✅ 空文件夹检测正确！")
        for folder in result['empty_folders']:
            print(f"      - {folder}")
    else:
        print(f"   ❌ 预期 2 个空文件夹，实际检测到 {len(result['empty_folders'])} 个")
    
    # 清理临时目录
    shutil.rmtree(temp_dir)
    print(f"   🗑️  已清理临时目录")
    
    return len(result['empty_folders']) == 2


if __name__ == "__main__":
    print("\n🚀 开始 FileWorker 模块测试\n")
    
    # 运行所有测试
    results = []
    
    # 测试 1：扫描 + 空文件夹检测
    results.append(("扫描 + 空文件夹检测", test_scan()))
    
    # 测试 2：导出 Excel
    results.append(("导出 Excel（含超链接）", test_export_excel()))
    
    # 测试 3：导出 HTML
    results.append(("导出 HTML 目录", test_export_html()))
    
    # 测试 4：空文件夹专项测试
    results.append(("空文件夹专项测试", test_empty_folder_only()))
    
    # 汇总结果
    print("\n" + "=" * 50)
    print("📊 测试结果汇总")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"   {name}：{status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 所有测试通过！FileWorker 模块可以集成到主程序。")
    else:
        print("\n⚠️ 部分测试失败，请检查上述错误信息。")