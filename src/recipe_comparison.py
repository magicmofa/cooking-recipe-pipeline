"""
菜谱对比整合模块
================
检测多个最终整合结果，通过 deepseek 进行对比
对比各个菜谱，总结出有差异的部分并输出为新的 md 文件
"""

import json
import re
import time
import requests
from pathlib import Path
from typing import Optional, Dict, List, Tuple


class RecipeComparison:
    """菜谱对比整合模块"""

    def __init__(self, folder_path: str, config_path: str = "config.json"):
        """
        初始化对比整合模块

        Args:
            folder_path: 工作文件夹路径
            config_path: 配置文件路径
        """
        self.folder_path = Path(folder_path)
        self.config = self._load_config(config_path)

        # 获取 API 配置
        comparison_config = self.config.get("recipe_comparison", {})
        self.api_provider = comparison_config.get("api_provider", self.config.get("api_provider", "deepseek"))

        # 获取对应提供商的配置
        provider_config = self.config.get(self.api_provider, {})
        self.provider_config = provider_config

        self.model_name = comparison_config.get("model", provider_config.get("model", "deepseek-chat"))
        self.api_url = provider_config.get("base_url", "https://api.deepseek.com/v1/chat/completions")
        self.api_key = provider_config.get("api_key")

        if not self.api_key and self.api_provider == "deepseek":
            raise ValueError("❌ 未配置 Deepseek API 密钥，请在 config.json 中设置 'deepseek.api_key'")

    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                print(f"警告: 配置文件 {config_path} 不存在，使用默认配置")
                return {}

            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"错误: 读取配置文件失败 - {e}")
            return {}

    def find_final_tutorials(self) -> List[Path]:
        """
        查找所有最终整合结果文件
        查找名称为 *_tutorial.md 的文件
        
        Returns:
            最终整合文件路径列表
        """
        tutorial_files = sorted(self.folder_path.rglob("*_tutorial.md"))
        return tutorial_files

    def detect_multiple_results(self) -> Tuple[bool, List[Path]]:
        """
        检测目标目录中是否存在多个最终整合结果

        Returns:
            (是否存在多个结果, 结果文件列表)
        """
        tutorial_files = self.find_final_tutorials()

        if len(tutorial_files) < 2:
            return False, tutorial_files

        return True, tutorial_files

    def ask_user_comparison(self, tutorial_files: List[Path]) -> bool:
        """
        询问用户是否需要进行对比整合

        Args:
            tutorial_files: 整合结果文件列表

        Returns:
            用户是否同意进行对比
        """
        print("\n" + "="*70)
        print("🔍 检测到多个最终整合结果")
        print("="*70)
        print(f"\n找到 {len(tutorial_files)} 个最终整合文件：")
        for i, file in enumerate(tutorial_files, 1):
            print(f"  {i}. {file.name}")

        print("\n这些文件可能包含对同一菜品的不同整合结果。")
        print("是否需要对比这些整合结果，提取有差异的部分？")

        while True:
            user_input = input("\n请选择 (y/n): ").strip().lower()
            if user_input in ['y', 'yes', '是']:
                return True
            elif user_input in ['n', 'no', '否']:
                return False
            else:
                print("❌ 输入无效，请输入 y/n")

    def read_file_content(self, file_path: Path) -> str:
        """
        读取文件内容

        Args:
            file_path: 文件路径

        Returns:
            文件内容
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"❌ 读取文件失败 {file_path}: {e}")
            return ""

    def call_deepseek_api(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """
        调用 Deepseek API 进行对比分析

        Args:
            prompt: 提示词
            max_retries: 最大重试次数

        Returns:
            API 返回的内容
        """
        for attempt in range(max_retries):
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                data = {
                    "model": self.model_name,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 8000
                }

                print(f"\n📡 调用 Deepseek API (尝试 {attempt + 1}/{max_retries})...")
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=data,
                    timeout=60
                )

                if response.status_code == 200:
                    result = response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        content = result["choices"][0]["message"]["content"]
                        print(f"✅ API 调用成功")
                        return content
                    else:
                        print(f"❌ API 返回格式错误")
                        return None
                else:
                    print(f"❌ API 错误 (状态码: {response.status_code})")
                    print(f"响应: {response.text[:200]}")
                    if attempt < max_retries - 1:
                        wait_time = 5 * (attempt + 1)
                        print(f"⏳ {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    continue

            except Exception as e:
                print(f"❌ API 调用异常: {e}")
                if attempt < max_retries - 1:
                    wait_time = 5 * (attempt + 1)
                    print(f"⏳ {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                continue

        return None

    def generate_comparison_prompt(self, tutorial_files: List[Path], contents: List[str]) -> str:
        """
        生成对比分析提示词

        Args:
            tutorial_files: 整合结果文件列表
            contents: 各文件的内容列表

        Returns:
            生成的提示词
        """
        file_list = "\n".join([f"{i+1}. {file.name}" for i, file in enumerate(tutorial_files)])

        prompt = f"""你是一位资深的烹饪专家和菜谱编辑。现在需要你对比分析多份烹饪教程，提取其中有差异的部分。

## 任务说明

我需要你对以下 {len(tutorial_files)} 份烹饪教程进行对比：
{file_list}

## 对比分析步骤

1. **仔细阅读所有教程内容**
2. **识别差异部分** - 找出各份教程中不同的地方，包括：
   - 食材用量或配方的差异
   - 烹饪步骤的差异
   - 烹饪时间和温度的差异
   - 技巧和提示的差异
   - 烹饪原理和科学解释的差异

3. **保留原始说明** - 对于每一个差异部分，如果原文中有说明原因和科学原理，一定要保留原样

4. **生成对比报告** - 按照下面的格式输出

## 输出格式

请使用以下 Markdown 格式生成对比报告：

### 菜品名称
{len(tutorial_files)} 份教程均为同一菜品，菜品名称为：[菜品名称]

### 概览
- 教程数量：{len(tutorial_files)}
- 发现的差异部分数量：[数量]

### 详细对比

#### [差异部分标题 1]
**出现在的教程：** [列出出现在哪些教程中]

**差异内容：**

[以表格或列表形式展示差异]

例如，如果涉及食材用量：
| 教程 | 食材 | 用量 | 说明 |
|-----|------|------|------|
| {tutorial_files[0].name} | ... | ... | ... |
| {tutorial_files[1].name} | ... | ... | ... |

**原理说明：** [保留原文中的原因和科学原理说明]

#### [差异部分标题 2]
[重复上述格式...]

### 相同部分总结
列出各份教程中相同或基本相同的关键部分

### 建议

根据对比结果，提供整合建议

---

## 这是你需要对比的教程内容：

"""

        for i, (file, content) in enumerate(zip(tutorial_files, contents), 1):
            prompt += f"\n### 教程 {i}: {file.name}\n\n"
            prompt += content[:3000]  # 限制长度，防止超出 token 限制
            prompt += "\n\n---\n"

        return prompt

    def compare_recipes(self, tutorial_files: List[Path]) -> Optional[str]:
        """
        对比多份菜谱

        Args:
            tutorial_files: 整合结果文件列表

        Returns:
            对比分析结果
        """
        print(f"\n📖 读取 {len(tutorial_files)} 份教程内容...")

        # 读取所有文件内容
        contents = []
        for file in tutorial_files:
            print(f"  - 读取: {file.name}")
            content = self.read_file_content(file)
            contents.append(content)

        if not all(contents):
            print("❌ 某些文件读取失败")
            return None

        # 生成对比提示词
        print(f"\n🔨 生成对比分析提示词...")
        prompt = self.generate_comparison_prompt(tutorial_files, contents)

        # 调用 API 进行对比
        result = self.call_deepseek_api(prompt)

        return result

    def save_comparison_result(self, result: str, output_filename: str = "recipe_comparison.md") -> Optional[Path]:
        """
        保存对比结果

        Args:
            result: 对比分析结果
            output_filename: 输出文件名

        Returns:
            输出文件路径
        """
        try:
            output_path = self.folder_path / output_filename

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result)

            print(f"\n✅ 对比结果已保存: {output_path}")
            return output_path

        except Exception as e:
            print(f"❌ 保存对比结果失败: {e}")
            return None

    def run_comparison_workflow(self) -> Optional[Path]:
        """
        运行完整的对比整合工作流

        Returns:
            生成的对比结果文件路径
        """
        print("\n" + "="*70)
        print("🔄 启动菜谱对比整合工作流")
        print("="*70)

        # 第一步：检测是否存在多个结果
        has_multiple, tutorial_files = self.detect_multiple_results()

        if not has_multiple:
            print(f"\n⚠️  仅找到 {len(tutorial_files)} 个最终整合文件，需要至少 2 个才能进行对比")
            return None

        # 第二步：询问用户是否进行对比
        if not self.ask_user_comparison(tutorial_files):
            print("\n✖️  用户取消对比整合")
            return None

        # 第三步：对比菜谱
        result = self.compare_recipes(tutorial_files)

        if not result:
            print("\n❌ 对比分析失败")
            return None

        # 第四步：保存结果
        output_path = self.save_comparison_result(result)

        if output_path:
            print("\n" + "="*70)
            print("🎉 菜谱对比整合完成！")
            print("="*70)
            print(f"📄 对比结果文件: {output_path}")

        return output_path


def run_recipe_comparison(folder_path: str, config_path: str = "config.json") -> Optional[Path]:
    """
    运行菜谱对比整合

    Args:
        folder_path: 工作文件夹路径
        config_path: 配置文件路径

    Returns:
        生成的对比结果文件路径
    """
    try:
        comparison = RecipeComparison(folder_path, config_path)
        return comparison.run_comparison_workflow()
    except Exception as e:
        print(f"❌ 菜谱对比整合出错: {e}")
        import traceback
        traceback.print_exc()
        return None
