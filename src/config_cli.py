#!/usr/bin/env python3
"""配置管理 CLI 工具"""

from pathlib import Path
from file_processor import ConfigManager
import sys


def print_menu():
    """打印菜单"""
    print("\n" + "="*60)
    print("⚙️  文件处理器配置工具")
    print("="*60)
    print("\n选项:")
    print("  1. 显示当前配置")
    print("  2. 切换模型")
    print("  3. 修改 Ollama 地址")
    print("  4. 修改图片识别提示词")
    print("  5. 修改 Markdown 优化提示词")
    print("  6. 重置为默认配置")
    print("  0. 退出")
    print("\n" + "="*60)


def show_config(config_manager):
    """显示配置"""
    config_manager.show_config()


def switch_model(config_manager):
    """切换模型"""
    print("\n当前模型:", config_manager.get_model())
    model = input("请输入新的模型名称: ").strip()
    if model:
        config_manager.set_model(model)
    else:
        print("❌ 模型名称不能为空")


def modify_base_url(config_manager):
    """修改 Ollama 地址"""
    print("\n当前地址:", config_manager.get_base_url())
    url = input("请输入新的 Ollama 地址 (如 http://localhost:11434): ").strip()
    if url:
        config_manager.set_base_url(url)
    else:
        print("❌ 地址不能为空")


def modify_image_prompt(config_manager):
    """修改图片识别提示词"""
    print("\n当前图片识别提示词:")
    print("-" * 60)
    print(config_manager.get_prompt("image_recognition"))
    print("-" * 60)
    print("\n请输入新的提示词（输入 'EOF' 单独一行结束）:")
    
    lines = []
    while True:
        line = input()
        if line == "EOF":
            break
        lines.append(line)
    
    prompt = "\n".join(lines)
    if prompt:
        config_manager.set_prompt("image_recognition", prompt)
    else:
        print("❌ 提示词不能为空")


def modify_markdown_prompt(config_manager):
    """修改 Markdown 优化提示词"""
    print("\n当前 Markdown 优化提示词:")
    print("-" * 60)
    print(config_manager.get_prompt("markdown_optimize"))
    print("-" * 60)
    print("\n请输入新的提示词（输入 'EOF' 单独一行结束）:")
    print("注意：使用 {content} 占位符表示文件内容")
    
    lines = []
    while True:
        line = input()
        if line == "EOF":
            break
        lines.append(line)
    
    prompt = "\n".join(lines)
    if prompt:
        config_manager.set_prompt("markdown_optimize", prompt)
    else:
        print("❌ 提示词不能为空")


def reset_config(config_manager):
    """重置为默认配置"""
    confirm = input("确认重置为默认配置? (y/n): ").strip().lower()
    if confirm == 'y':
        # 删除配置文件
        if config_manager.config_path.exists():
            config_manager.config_path.unlink()
            print("✅ 配置文件已删除，已使用默认配置")
        else:
            print("✅ 已使用默认配置")
    else:
        print("❌ 已取消")


def main():
    """主函数"""
    config_manager = ConfigManager()
    
    while True:
        print_menu()
        choice = input("请选择操作 (0-6): ").strip()
        
        if choice == "1":
            show_config(config_manager)
        elif choice == "2":
            switch_model(config_manager)
        elif choice == "3":
            modify_base_url(config_manager)
        elif choice == "4":
            modify_image_prompt(config_manager)
        elif choice == "5":
            modify_markdown_prompt(config_manager)
        elif choice == "6":
            reset_config(config_manager)
            config_manager = ConfigManager()  # 重新加载
        elif choice == "0":
            print("\n👋 再见!")
            break
        else:
            print("\n❌ 无效的选择，请重试")


if __name__ == "__main__":
    main()
