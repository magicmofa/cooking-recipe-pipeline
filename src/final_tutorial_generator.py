"""
最终教程生成器
================
整合所有生成的文件（字幕、初步菜谱、精细化分析、视觉补充）生成完整的制作教程
"""

import json
import time
import requests
from pathlib import Path
from typing import Optional, Dict


class FinalTutorialGenerator:
    """最终教程生成器 - 整合所有资料生成完整教程"""
    
    def __init__(self, folder_path: str, config_path: str = "config.json"):
        """
        初始化生成器
        
        Args:
            folder_path: 工作文件夹路径
            config_path: 配置文件路径
        """
        self.folder_path = Path(folder_path)
        self.config = self._load_config(config_path)
        
        # 优先使用 final_tutorial 的独立配置，否则使用全局配置
        final_tutorial_config = self.config.get("final_tutorial", {})
        self.api_provider = final_tutorial_config.get("api_provider", self.config.get("api_provider", "ollama"))

        # 获取对应提供商的配置
        provider_config = self.config.get(self.api_provider, {})
        self.provider_config = provider_config

        self.model_name = final_tutorial_config.get("model", provider_config.get("model", "qwen3-vl:32b"))
        self.api_url = provider_config.get("base_url", "http://localhost:11434")
        self.api_key = provider_config.get("api_key")
        self.prompt_template = self.config.get("prompts", {}).get(
            "final_tutorial_generation",
            self._get_default_prompt()
        )
    
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
    
    def _get_default_prompt(self) -> str:
        """获取默认提示词"""
        return """你是一位专业的烹饪教学内容编辑。现在需要你整合多份资料，生成一份完整、详尽、易于理解的烹饪制作教程。

你将收到以下资料：
1. **视频字幕文本** - 原始的视频字幕内容
2. **初步菜谱** - 从字幕中提取的基础菜谱
3. **精细化分析** - 缺漏细节分析和完整性评估
4. **视觉补充内容** - 基于视频关键帧的详细分析和时间标注

你的任务是：

## 📋 输出要求

请生成一份结构完整的烹饪教程，包含以下部分：

### 1. 菜品名称和简介
- 菜品的正式名称
- 简短的背景介绍（如果有）
- 特点和风味描述

### 2. 准备工作
#### 2.1 食材清单
- 主料（包含精确的用量和规格）
- 辅料和调味料（包含精确的比例）
- 特殊说明（如食材的选择标准、替代方案）

#### 2.2 工具准备
- 所需的厨具和器具
- 温度计、计量工具等辅助工具

### 3. 详细制作步骤
将制作过程分解为清晰的步骤，每个步骤需包含：
- **步骤编号和标题**
- **具体操作** - 详细的操作说明
- **关键参数** - 温度、时间、火候等
- **视觉标准** - 描述应该看到的状态（颜色、质地、形态等）
- **技巧提示** - 操作的注意事项和技巧
- **参考时间点** - 标注视频中的时间（格式：MM:SS 或 HH:MM:SS）
- **📹 视频片段** - **重要：如果视觉补充内容中有对应的视频片段链接（如 clip_01.mp4），请在相关步骤中保留这些链接，格式为：[📹 查看视频演示](相对路径/clip_XX.mp4)**

### 4. 烹饪原理与技巧
- 关键操作背后的科学原理（如为什么要这样做）
- 重要的烹饪技巧总结
- 常见问题和解决方案
- **如有视频片段展示技巧，请保留链接**

### 5. 成品标准
- 完成品的外观描述
- 口感和味道特征
- 保存和食用建议

### 6. 难度评估和时间预估
- 难度等级（简单/中等/困难）
- 准备时间
- 制作时间
- 总计用时

## ✍️ 写作要求

1. **精确性** - 所有温度、时间、用量必须明确，不使用"适量"、"少许"等模糊词汇
2. **完整性** - 整合所有资料中的信息，不遗漏任何重要细节
3. **结构化** - 使用清晰的 Markdown 格式，层次分明
4. **可操作性** - 即使完全没有看过视频，读者也能按照教程成功制作
5. **专业性** - 使用准确的烹饪术语，解释关键原理
6. **易读性** - 语言简洁明了，适当使用emoji增强可读性
7. **视频链接保留** - **必须保留视觉补充内容中的所有视频片段链接（clip_*.mp4），并将它们放置在相应的步骤或技巧说明中**

## 📦 资料内容

{materials}

---

请基于以上资料，生成完整的烹饪制作教程。记住：一定要在相关步骤中保留视频片段的链接！
"""
    
    def find_video_materials(self, video_name: str) -> Optional[Dict[str, str]]:
        """
        查找某个视频的所有相关资料文件
        
        Args:
            video_name: 视频名称（不含扩展名）
            
        Returns:
            包含所有资料内容的字典，如果找不到则返回 None
        """
        materials = {}
        
        # 1. 查找字幕文件
        srt_file = self.folder_path / f"{video_name}.srt"
        if srt_file.exists():
            try:
                with open(srt_file, "r", encoding="utf-8") as f:
                    materials["subtitle"] = f.read()
            except Exception as e:
                print(f"⚠️  读取字幕文件失败: {e}")
        
        # 2. 查找初步菜谱
        recipe_file = self.folder_path / f"{video_name}_recipe.md"
        if recipe_file.exists():
            try:
                with open(recipe_file, "r", encoding="utf-8") as f:
                    materials["initial_recipe"] = f.read()
            except Exception as e:
                print(f"⚠️  读取初步菜谱失败: {e}")
        
        # 3. 查找精细化分析
        analysis_file = self.folder_path / f"{video_name}_analysis.md"
        if analysis_file.exists():
            try:
                with open(analysis_file, "r", encoding="utf-8") as f:
                    materials["refined_analysis"] = f.read()
            except Exception as e:
                print(f"⚠️  读取精细化分析失败: {e}")
        
        # 4. 查找视觉补充内容
        visual_file = self.folder_path / video_name / f"{video_name}_visual.md"
        if visual_file.exists():
            try:
                with open(visual_file, "r", encoding="utf-8") as f:
                    materials["visual_enhancement"] = f.read()
            except Exception as e:
                print(f"⚠️  读取视觉补充内容失败: {e}")
        
        if not materials:
            return None
        
        return materials
    
    def format_materials(self, materials: Dict[str, str]) -> str:
        """格式化资料内容为提示词"""
        sections = []
        
        if "subtitle" in materials:
            sections.append("### 📝 视频字幕文本\n\n```\n" + materials["subtitle"] + "\n```\n")
        
        if "initial_recipe" in materials:
            sections.append("### 📖 初步菜谱\n\n" + materials["initial_recipe"] + "\n")
        
        if "refined_analysis" in materials:
            sections.append("### 🔍 精细化分析\n\n" + materials["refined_analysis"] + "\n")
        
        if "visual_enhancement" in materials:
            sections.append("### 🎬 视觉补充内容（包含视频片段链接）\n\n" + materials["visual_enhancement"] + "\n")
        
        return "\n---\n\n".join(sections)
    
    def call_api(self, prompt: str) -> Optional[str]:
        """调用API生成最终教程"""
        if self.api_provider == "ollama":
            return self._call_ollama_api(prompt)
        else:
            # openai, deepseek, gemini 等都使用 OpenAI 兼容 API
            return self._call_openai_compatible_api(prompt)
    
    def _call_ollama_api(self, prompt: str) -> Optional[str]:
        """调用 Ollama API"""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }
        
        api_endpoint = f"{self.api_url}/api/generate"
        
        try:
            print(f"调用 Ollama API，模型: {self.model_name}")
            response = requests.post(
                api_endpoint,
                json=payload,
                timeout=900
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            else:
                print(f"API返回错误: {response.status_code}")
                print(f"错误信息: {response.text}")
                return None
                
        except Exception as e:
            print(f"调用 Ollama API 出错: {e}")
            return None
    
    def _call_openai_compatible_api(self, prompt: str) -> Optional[str]:
        """调用 OpenAI 兼容的 API (支持 OpenAI, DeepSeek, Gemini 等)"""
        provider_config = getattr(self, "provider_config", None) or self.config.get(self.api_provider, {})

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        reasoning_effort = provider_config.get("reasoning_effort")
        if isinstance(provider_config.get("reasoning"), dict):
            reasoning_effort = reasoning_effort or provider_config["reasoning"].get("effort")

        if reasoning_effort:
            reasoning_effort = str(reasoning_effort).lower()
            allowed_efforts = {"low", "medium", "high"}
            if reasoning_effort not in allowed_efforts:
                print(f"⚠️ 无效推理强度: {reasoning_effort}，已忽略（可选: low/medium/high）")
                reasoning_effort = None

        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
            print(f"推理强度: {reasoning_effort}")

        # 兼容部分提供商的 thinking 参数（如 deepseek-reasoner / 兼容代理）
        if isinstance(provider_config.get("thinking"), dict):
            payload["thinking"] = provider_config["thinking"]

        if "temperature" in provider_config:
            payload["temperature"] = provider_config["temperature"]
        else:
            payload["temperature"] = 1

        if "max_tokens" in provider_config:
            payload["max_tokens"] = provider_config["max_tokens"]
        else:
            payload["max_tokens"] = 16000

        timeout_seconds = provider_config.get("timeout_seconds", 120)
        max_retries = provider_config.get("max_retries", 0) or 0
        retry_backoff_seconds = provider_config.get("retry_backoff_seconds", 2)

        api_endpoint = f"{self.api_url}/chat/completions"

        for attempt in range(max_retries + 1):
            try:
                print(f"调用 {self.api_provider.upper()} API，模型: {self.model_name}（尝试 {attempt + 1}/{max_retries + 1}）")
                response = requests.post(
                    api_endpoint,
                    json=payload,
                    headers=headers,
                    timeout=(10, timeout_seconds)
                )

                if response.status_code == 200:
                    result = response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        choice = result["choices"][0]

                        if "thinking" in choice.get("message", {}):
                            thinking = choice["message"]["thinking"]
                            print(f"\n[推理过程]\n{thinking[:500]}...\n" if len(thinking) > 500 else f"\n[推理过程]\n{thinking}\n")

                        return choice["message"]["content"]
                    else:
                        print(f"API返回格式异常: {result}")
                        return None
                else:
                    print(f"API返回错误: {response.status_code}")
                    print(f"错误信息: {response.text}")
                    if response.status_code >= 500 and attempt < max_retries:
                        time.sleep(retry_backoff_seconds)
                        continue
                    return None

            except requests.exceptions.Timeout as e:
                print(f"调用 {self.api_provider.upper()} API 超时: {e}")
            except requests.exceptions.RequestException as e:
                print(f"调用 {self.api_provider.upper()} API 请求失败: {e}")

            if attempt < max_retries:
                time.sleep(retry_backoff_seconds)

        return None

    def generate_tutorial(self, video_name: str) -> Optional[Path]:
        """
        生成单个视频的最终教程

        Args:
            video_name: 视频名称（不含扩展名）
            
        Returns:
            生成的教程文件路径，如果失败则返回 None
        """
        print(f"\n{'='*70}")
        print(f"🎓 生成最终教程: {video_name}")
        print(f"{'='*70}")
        
        # 检查最终教程是否已存在
        output_file = self.folder_path / f"{video_name}_tutorial.md"
        if output_file.exists():
            print(f" 最终教程已存在，跳过: {output_file.name}")
            return output_file

        # 1. 收集资料
        print("📦 收集资料文件...")
        materials = self.find_video_materials(video_name)
        
        if not materials:
            print(f"❌ 未找到任何资料文件")
            return None
        
        print(f"✓ 找到 {len(materials)} 份资料:")
        for key in materials.keys():
            print(f"  - {key}")
        
        # 2. 格式化资料
        formatted_materials = self.format_materials(materials)
        
        # 3. 构建提示词
        prompt = self.prompt_template.format(materials=formatted_materials)
        
        print(f"\n📝 提示词长度: {len(prompt)} 字符")
        
        # 4. 调用API生成教程
        print(f"🤖 正在生成最终教程...")
        result = self.call_api(prompt)
        
        if not result:
            print(f"❌ 生成失败")
            return None
        
        # 5. 保存结果
        output_file = self.folder_path / f"{video_name}_tutorial.md"
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"✅ 最终教程已保存: {output_file.name}")
            return output_file
        except Exception as e:
            print(f"❌ 保存失败: {e}")
            return None
    
    def process_all(self) -> list:
        """
        处理文件夹中所有的视频（查找已有 _enriched_with_timestamps.md 的）
        
        Returns:
            生成的教程文件路径列表
        """
        print("\n" + "="*70)
        print("🎓 阶段四：生成最终教程 - 整合所有资料")
        print("="*70)
        
        # 查找所有已完成视觉补充的视频
        visual_files = sorted(self.folder_path.rglob("*_visual.md"))
        
        if not visual_files:
            print("⚠️  未找到任何已完成的视觉补充文件")
            return []
        
        video_names = set()
        for visual_file in visual_files:
            # 从文件名提取视频名称
            # 例如: 云南老昆明人正宗的（米浆粑粑）/云南老昆明人正宗的（米浆粑粑）_visual.md
            # 提取: 云南老昆明人正宗的（米浆粑粑）
            video_name = visual_file.stem.replace("_visual", "")
            video_names.add(video_name)
        
        print(f"找到 {len(video_names)} 个待处理视频\n")
        
        results = []
        for video_name in sorted(video_names):
            tutorial_path = self.generate_tutorial(video_name)
            if tutorial_path:
                results.append(tutorial_path)
        
        print(f"\n📊 阶段四统计：共生成 {len(results)} 份最终教程")
        return results


def main():
    """主函数"""
    folder_path = r"C:\Users\magic\Desktop\烹饪\米浆粑粑"
    config_path = "config.json"
    
    generator = FinalTutorialGenerator(folder_path, config_path)
    
    # 处理所有视频
    results = generator.process_all()
    
    # 或者单独处理某个视频
    # result = generator.generate_tutorial("云南老昆明人正宗的（米浆粑粑），云南人儿时的记忆，香甜松软")
    
    if results:
        print(f"\n✅ 完成！共生成 {len(results)} 份最终教程")
    else:
        print(f"\n⚠️  未生成任何教程")


if __name__ == "__main__":
    main()
