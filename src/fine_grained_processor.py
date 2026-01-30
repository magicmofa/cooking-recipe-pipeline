import os
import re
import requests
import json
from pathlib import Path
from typing import List, Tuple, Optional


class FineGrainedProcessor:
    """精细化处理器 - 处理md和srt文件，调用API进行处理（支持ollama和deepseek）"""
    
    def __init__(
        self,
        folder_path: str,
        config_path: str = "config.json",
        model_name: Optional[str] = None,
        prompt_template: Optional[str] = None,
        api_provider: Optional[str] = None,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        初始化处理器
        
        Args:
            folder_path: 要遍历的文件夹路径
            config_path: config.json配置文件路径
            model_name: 模型名称，如果为None则从config读取
            prompt_template: 提示词模板，如果为None则从config读取
            api_provider: API提供商 ('ollama' 或 'deepseek')，如果为None则从config读取
            api_url: API地址，如果为None则从config读取
            api_key: API密钥（deepseek需要），如果为None则从config读取
        """
        self.folder_path = Path(folder_path)
        
        # 加载配置文件（返回完整配置）
        config = self._load_config(config_path)
        
        # 确定使用的API提供商
        self.api_provider = api_provider or config.get("api_provider", "ollama")
        
        # 优先使用传入的参数，否则使用配置文件中的值
        if self.api_provider == "deepseek":
            provider_config = config.get("deepseek", {})
            self.model_name = model_name or provider_config.get("model", "deepseek-reasoner")
            self.api_url = api_url or provider_config.get("base_url", "https://api.deepseek.com/v1")
            self.api_key = api_key or provider_config.get("api_key", "")
        else:  # ollama
            provider_config = config.get("ollama", {})
            self.model_name = model_name or provider_config.get("model", "qwen3-vl:32b")
            self.api_url = api_url or provider_config.get("base_url", "http://localhost:11434")
            self.api_key = None
        
        self.prompt_template = prompt_template or config.get("prompt_template", "请分析以下内容：")
        
        # 获取fine_grained_processor特定的提示词
        processor_config = config.get("fine_grained_processor", {})
        if "prompt_template" in processor_config:
            self.prompt_template = processor_config["prompt_template"]
    
    def _load_config(self, config_path: str) -> dict:
        """
        从config.json加载配置
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            配置字典
        """
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                print(f"警告: 配置文件 {config_path} 不存在，使用默认配置")
                return {}
            
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 兼容旧字段：若fine_grained_processor内缺少ollama_url，则补充
            processor_config = config.get("fine_grained_processor", {})
            ollama_config = config.get("ollama", {})
            if "base_url" in ollama_config and "ollama_url" not in processor_config:
                processor_config["ollama_url"] = ollama_config["base_url"]
                config["fine_grained_processor"] = processor_config
            
            return config

        except json.JSONDecodeError as e:
            print(f"错误: 配置文件格式错误 - {e}")
            return {}
        except Exception as e:
            print(f"错误: 读取配置文件失败 - {e}")
            return {}
        
    def find_marked_files(self) -> List[Path]:
        """
        查找初步菜谱文件（_recipe.md）
        
        Returns:
            md文件路径列表
        """
        marked_files = []
        
        for md_file in self.folder_path.glob("*_recipe.md"):
            marked_files.append(md_file)
        
        return sorted(marked_files)
    
    def find_matching_srt(self, md_file: Path) -> Optional[Path]:
        """
        根据md文件名找到对应的srt文件
        
        Args:
            md_file: md文件路径
            
        Returns:
            对应的srt文件路径，如果找不到则返回None
        """
        # 从md文件名去除后缀 _recipe
        md_name = md_file.stem  # 获取不包含后缀的文件名
        
        # 构造srt文件名（去除_recipe部分）
        srt_name_pattern = md_name.replace("_recipe", "")
        
        # 查找匹配的srt文件
        for srt_file in self.folder_path.glob("*.srt"):
            if srt_file.stem == srt_name_pattern:
                return srt_file
        
        return None
    
    def read_file_content(self, file_path: Path) -> str:
        """读取文件内容"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"读取文件 {file_path} 出错: {e}")
            return ""
    
    def call_ollama_api(self, md_content: str, srt_content: str) -> Optional[str]:
        """
        调用API进行处理（支持ollama和deepseek）
        
        Args:
            md_content: md文件内容
            srt_content: srt文件内容
            
        Returns:
            API返回的结果，如果失败则返回None
        """
        # 构造请求内容
        combined_input = f"Markdown内容:\n{md_content}\n\n字幕内容:\n{srt_content}"
        
        prompt = f"{self.prompt_template}\n\n{combined_input}"
        
        if self.api_provider == "deepseek":
            return self._call_deepseek_api(prompt)
        else:
            return self._call_ollama_api(prompt)
    
    def _call_ollama_api(self, prompt: str) -> Optional[str]:
        """调用ollama API"""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }
        
        api_endpoint = f"{self.api_url}/api/generate"
        
        try:
            print(f"调用ollama API，模型: {self.model_name}")
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
                
        except requests.exceptions.ConnectionError:
            print(f"无法连接到ollama服务 {self.api_url}，请确保ollama正在运行")
            return None
        except Exception as e:
            print(f"调用ollama API出错: {e}")
            return None
    
    def _call_deepseek_api(self, prompt: str) -> Optional[str]:
        """调用deepseek API（支持推理模型）"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 判断是否为推理模型（deepseek-reasoner系列）
        is_reasoning_model = "reasoner" in self.model_name.lower()
        
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        # 推理模型配置
        if is_reasoning_model:
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": 10000
            }
            print(f"使用推理模型: {self.model_name}（启用思考链）")
        else:
            payload["temperature"] = 1
            payload["max_tokens"] = 16000
        
        api_endpoint = f"{self.api_url}/chat/completions"
        
        try:
            print(f"调用deepseek API，模型: {self.model_name}")
            response = requests.post(
                api_endpoint,
                json=payload,
                headers=headers,
                timeout=900
            )
            
            if response.status_code == 200:
                result = response.json()
                # DeepSeek API返回格式
                if "choices" in result and len(result["choices"]) > 0:
                    choice = result["choices"][0]
                    
                    # 如果是推理模型，显示思考过程
                    if is_reasoning_model and "thinking" in choice.get("message", {}):
                        thinking = choice["message"]["thinking"]
                        print(f"\n[推理过程]\n{thinking[:500]}...\n" if len(thinking) > 500 else f"\n[推理过程]\n{thinking}\n")
                    
                    return choice["message"]["content"]
                else:
                    print(f"API返回格式异常: {result}")
                    return None
            else:
                print(f"API返回错误: {response.status_code}")
                print(f"错误信息: {response.text}")
                return None
                
        except requests.exceptions.ConnectionError:
            print(f"无法连接到deepseek服务 {self.api_url}")
            return None
        except Exception as e:
            print(f"调用deepseek API出错: {e}")
            return None
    
    def process_pairs(self) -> dict:
        """
        处理所有md和srt文件对，结果保存到md文件所在目录
        
        Returns:
            处理结果字典
        """
        marked_files = self.find_marked_files()
        
        if not marked_files:
            print("未找到带有[✓]标记的md文件")
            return {}
        
        print(f"找到 {len(marked_files)} 个带标记的md文件\n")
        
        results = {}
        
        for i, md_file in enumerate(marked_files, 1):
            srt_file = self.find_matching_srt(md_file)
            
            if srt_file is None:
                print(f"[{i}] ❌ 找不到对应的srt文件: {md_file.name}")
                continue

            # 检查是否已经存在分析文件
            analysis_file = md_file.parent / f"{md_file.stem.replace('_recipe', '')}_analysis.md"
            if analysis_file.exists():
                print(f"[{i}] ⏭️  已存在分析文件，跳过: {md_file.name}")
                continue
            
            print(f"[{i}] 处理文件对:")
            print(f"    MD文件: {md_file.name}")
            print(f"    SRT文件: {srt_file.name}")
            
            # 读取文件内容
            md_content = self.read_file_content(md_file)
            srt_content = self.read_file_content(srt_file)
            
            if not md_content or not srt_content:
                print(f"    ⚠️  文件读取失败，跳过\n")
                continue
            
            # 调用ollama API
            result = self.call_ollama_api(md_content, srt_content)
            
            if result:
                print(f"    ✓ 处理完成")
                results[md_file.name] = {
                    "md_file": str(md_file),
                    "srt_file": str(srt_file),
                    "result": result
                }
                
                # 保存结果到md文件所在目录
                self._save_result(md_file, result)
            else:
                print(f"    ✗ 处理失败")
            
            print()
        
        print(f"处理完成，共成功处理 {len(results)} 个文件对")
        return results
    
    def _save_result(self, md_file: Path, result: str):
        """保存处理结果到markdown文件（保存到md文件所在目录）"""
        # 保存到 md 文件所在的目录
        output_path = md_file.parent
        
        # 文件名：_analysis 表示精细化分析结果
        result_file = output_path / f"{md_file.stem.replace('_recipe', '')}_analysis.md"
        
        try:
            with open(result_file, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"    已保存到: {result_file}")
        except Exception as e:
            print(f"保存结果失败: {e}")


def main():
    """主函数 - 遍历所有markdown文件并处理"""
    
    # 配置文件路径
    config_path = "config.json"
    
    # 要遍历的根文件夹
    root_folder = r"C:\Users\magic\Desktop\烹饪"
    
    # ============ API 选择开关 ============
    # 使用 ollama（默认，从config.json读取）
    processor = FineGrainedProcessor(
        folder_path=root_folder,
        config_path=config_path
    )
    
    # 或使用 deepseek
    # processor = FineGrainedProcessor(
    #     folder_path=root_folder,
    #     config_path=config_path,
    #     api_provider="deepseek",
    #     api_key="sk-your-api-key-here"  # 需要提供deepseek API KEY
    # )
    
    # 或者直接修改config.json中的 "api_provider" 字段
    # ===================================
    
    print(f"使用的API: {processor.api_provider}")
    print(f"使用的模型: {processor.model_name}")
    print(f"遍历目录: {root_folder}\n")
    
    # 处理文件对，结果自动保存到md文件所在目录
    results = processor.process_pairs()
    
    if results:
        print(f"\n✅ 处理完成！共成功处理 {len(results)} 个文件")
    else:
        print(f"\n⚠️  未找到任何可处理的文件")


if __name__ == "__main__":
    main()

