"""
测试打包功能
运行方式：python test_package.py
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.file_worker import FileWorker

# 自动获取桌面路径
desktop = str(Path.home() / "Desktop")


def test_package():
    print("=" * 50)
    print("测试：打包发布 (ZIP)")
    print("=" * 50)

    # 使用你的项目目录作为测试源（请根据实际情况修改）
    test_dir = r"D:\python_tool\04-file_navigator"

    if not os.path.exists(test_dir):
        print(f"❌ 路径不存在：{test_dir}")
        print("请修改 test_dir 变量为你电脑上真实存在的路径")
        return False

    # 1. 扫描
    worker = FileWorker()
    result = worker.scan_directory(
        root_dir=test_dir,
        extensions=None,  # 不过滤，全部打包
        detect_empty=True
    )

    print(f"✅ 扫描完成：{result['total_count']} 个文件，{len(result['empty_folders'])} 个空文件夹")

    # 模拟空文件夹选择：这里让用户输入
    empty_choice = 'skip'
    if result['empty_folders']:
        print("\n📂 检测到空文件夹：")
        for folder in result['empty_folders'][:10]:  # 最多显示10个
            print(f"   - {folder}")
        if len(result['empty_folders']) > 10:
            print(f"   ... 还有 {len(result['empty_folders']) - 10} 个")
        choice = input("\n是否打包空文件夹？(y/n，默认 n): ").strip().lower()
        empty_choice = 'include' if choice == 'y' else 'skip'

    # 2. 打包
    zip_path = os.path.join(desktop, "测试打包_文件清单.zip")
    print(f"\n📦 开始打包：{zip_path}")

    success = worker.export_package(
        output_zip_path=zip_path,
        include_excel=True,
        include_html=True,
        include_files=True,
        use_relative_path=True,  # 打包用相对路径
        empty_folder_choice=empty_choice
    )

    if success:
        print(f"\n✅ 打包成功！ZIP 文件已生成：{zip_path}")
        print("   📂 请解压后打开「文件清单.html」查看效果")
        print("   🔗 HTML 中的文件链接使用相对路径，解压后点击即可打开")
        return True
    else:
        print("\n❌ 打包失败")
        return False


def test_with_filter():
    """测试带过滤的打包"""
    print("\n" + "=" * 50)
    print("测试：带过滤的打包 (只打包 .py 文件)")
    print("=" * 50)

    test_dir = r"D:\python_tool\04-file_navigator"

    if not os.path.exists(test_dir):
        print(f"❌ 路径不存在：{test_dir}")
        return False

    worker = FileWorker()
    result = worker.scan_directory(
        root_dir=test_dir,
        extensions=['.py'],  # 只扫描 Python 文件
        detect_empty=True
    )

    print(f"✅ 扫描完成：{result['total_count']} 个 .py 文件")

    zip_path = os.path.join(desktop, "测试打包_仅Python文件.zip")
    print(f"\n📦 开始打包：{zip_path}")

    success = worker.export_package(
        output_zip_path=zip_path,
        include_excel=True,
        include_html=True,
        include_files=True,
        use_relative_path=True,
        empty_folder_choice='skip'
    )

    if success:
        print(f"\n✅ 打包成功！{zip_path}")
        return True
    else:
        print("\n❌ 打包失败")
        return False


if __name__ == "__main__":
    print("\n🚀 开始 FileWorker 打包功能测试\n")

    # 运行测试
    results = []
    results.append(("基础打包测试", test_package()))
    results.append(("过滤打包测试 (.py)", test_with_filter()))

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
        print("\n🎉 所有测试通过！打包功能已就绪。")
    else:
        print("\n⚠️ 部分测试失败，请检查上述错误信息。")