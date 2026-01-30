"""
烹饪菜谱提取流程 - 交互式菜单
===========================
提供简单的命令行菜单，用户可以选择要运行的阶段或全部运行
"""

import sys
from pathlib import Path
from main_pipeline import CookingRecipePipeline


def print_menu():
    """打印主菜单"""
    print("\n" + "="*70)
    print("🍳 烹饪菜谱提取完整流程 - 交互式菜单")
    print("="*70)
    print("\n请选择要运行的操作：")
    print("\n【完整流程】")
    print("  1. 运行全部阶段（1-5）")
    print("  2. 仅运行 1-4 阶段（不进行菜谱对比）")
    print("\n【单独运行阶段】")
    print("  3. 仅运行阶段一：初步提取")
    print("  4. 仅运行阶段二：精细化分析")
    print("  5. 仅运行阶段三：视觉补充")
    print("  6. 仅运行阶段四：最终整合")
    print("  7. 仅运行阶段五：菜谱对比（检测多个结果并对比）")
    print("\n【自定义运行】")
    print("  8. 自定义选择要运行的阶段")
    print("\n【其他】")
    print("  0. 退出程序")
    print("\n" + "="*70)


def get_folder_path():
    """获取要处理的文件夹路径"""
    while True:
        folder_path = input("\n请输入要处理的文件夹路径（或按 Enter 使用默认路径）: ").strip()
        
        if not folder_path:
            # 使用默认路径
            folder_path = r"C:\Users\magic\Desktop\烹饪\蒸蛋"
        
        folder = Path(folder_path)
        if folder.exists():
            print(f"✓ 已选择文件夹: {folder_path}")
            return folder_path
        else:
            print(f"❌ 文件夹不存在: {folder_path}")
            print("   请检查路径并重试")


def get_config_path():
    """获取配置文件路径"""
    while True:
        config_path = input("\n请输入配置文件路径（或按 Enter 使用默认 config.json）: ").strip()
        
        if not config_path:
            config_path = "config.json"
        
        config_file = Path(config_path)
        if config_file.exists():
            print(f"✓ 已选择配置文件: {config_path}")
            return config_path
        else:
            print(f"⚠️  配置文件不存在: {config_path}")
            overwrite = input("  是否继续使用该路径？(y/n): ").strip().lower()
            if overwrite in ['y', 'yes']:
                return config_path


def get_custom_stages():
    """获取自定义选择的阶段"""
    print("\n请选择要运行的阶段（多个阶段用逗号分隔）：")
    print("  1: 阶段一（初步提取）")
    print("  2: 阶段二（精细化分析）")
    print("  3: 阶段三（视觉补充）")
    print("  4: 阶段四（最终整合）")
    print("  5: 阶段五（菜谱对比）")
    print("  例：输入 '1,2,4' 表示运行阶段 1、2、4")
    
    while True:
        stages_input = input("\n请输入阶段编号（如 1,2,3）: ").strip()
        
        if not stages_input:
            print("❌ 输入不能为空")
            continue
        
        try:
            stages = [int(s.strip()) for s in stages_input.split(",")]
            
            # 验证阶段号
            if all(s in [1, 2, 3, 4, 5] for s in stages):
                # 计算要跳过的阶段
                all_stages = [1, 2, 3, 4, 5]
                skip_stages = [s for s in all_stages if s not in stages]
                print(f"✓ 已选择阶段：{stages}")
                print(f"  跳过阶段：{skip_stages}")
                return skip_stages
            else:
                print("❌ 阶段号必须在 1-5 之间")
        except ValueError:
            print("❌ 输入格式错误，请输入数字并用逗号分隔")


def run_pipeline(folder_path: str, config_path: str, skip_stages: list):
    """运行流程"""
    try:
        pipeline = CookingRecipePipeline(folder_path, config_path)
        results = pipeline.run_full_pipeline(recursive=True, skip_stages=skip_stages)
        return results
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断操作")
        return None
    except Exception as e:
        print(f"\n❌ 流程执行出错: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数 - 交互式菜单"""
    
    print("\n🍳 欢迎使用烹饪菜谱提取完整流程工具")
    
    # 获取文件夹和配置路径
    folder_path = get_folder_path()
    config_path = get_config_path()
    
    while True:
        print_menu()
        choice = input("请选择操作（0-8）: ").strip()
        
        if choice == "0":
            print("\n👋 感谢使用，再见！")
            sys.exit(0)
        
        elif choice == "1":
            # 运行全部阶段
            print("\n🚀 开始运行全部阶段（1-5）...")
            run_pipeline(folder_path, config_path, [])
        
        elif choice == "2":
            # 运行阶段 1-4
            print("\n🚀 开始运行阶段 1-4（跳过菜谱对比）...")
            run_pipeline(folder_path, config_path, [5])
        
        elif choice == "3":
            # 仅运行阶段一
            print("\n🚀 开始仅运行阶段一（初步提取）...")
            run_pipeline(folder_path, config_path, [2, 3, 4, 5])
        
        elif choice == "4":
            # 仅运行阶段二
            print("\n🚀 开始仅运行阶段二（精细化分析）...")
            run_pipeline(folder_path, config_path, [1, 3, 4, 5])
        
        elif choice == "5":
            # 仅运行阶段三
            print("\n🚀 开始仅运行阶段三（视觉补充）...")
            run_pipeline(folder_path, config_path, [1, 2, 4, 5])
        
        elif choice == "6":
            # 仅运行阶段四
            print("\n🚀 开始仅运行阶段四（最终整合）...")
            run_pipeline(folder_path, config_path, [1, 2, 3, 5])
        
        elif choice == "7":
            # 仅运行阶段五
            print("\n🚀 开始仅运行阶段五（菜谱对比）...")
            run_pipeline(folder_path, config_path, [1, 2, 3, 4])
        
        elif choice == "8":
            # 自定义运行
            print("\n🎯 自定义选择阶段...")
            skip_stages = get_custom_stages()
            print("\n🚀 开始运行...")
            run_pipeline(folder_path, config_path, skip_stages)
        
        else:
            print("❌ 输入无效，请输入 0-8")
        
        # 询问是否继续
        continue_choice = input("\n是否继续？(y/n): ").strip().lower()
        if continue_choice not in ['y', 'yes']:
            print("\n👋 感谢使用，再见！")
            sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  程序已中断")
        sys.exit(0)
