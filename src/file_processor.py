import os
import json
import base64
from pathlib import Path
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass
import requests
from datetime import datetime


class ConfigManager:
    """配置管理器 - 处理模型和提示词配置"""
    
    def __init__(self, config_path: str = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为 config.json
        """
        if config_path is None:
            config_path = Path(__file__).parent / "config.json"
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  无法读取配置文件: {e}，使用默认配置")
        
        # 默认配置
        return {
            "ollama": {
                "base_url": "http://localhost:11434",
                "model": "qwen3-vl:8b"
            },
            "prompts": {
                "image_recognition": "请分析这张图片中的菜品，用Markdown格式输出一份易读的菜谱。\n\n要求：\n- 保留所有的烹饪细节、材料比例、温度、时间等信息\n- 使用便于教学的清晰排版格式\n- 可以自由调整结构，只要易于阅读即可\n- 保持中文输出\n\n输出为Markdown格式即可。",
                "markdown_optimize": "请优化以下Markdown文档，使其成为易于阅读的菜谱。\n\n要求：\n- 完整保留所有烹饪细节、配料比例、温度、时间、技巧等信息，一个都不能少\n- 调整排版格式使其易于教学和查阅\n- 保持Markdown格式，自由调整结构即可\n- 强调清晰易读，方便按步骤操作\n\n原文档：\n{content}\n\n请输出调整后的Markdown文档：",
                "subtitle_recipe_extraction": "请从以下视频字幕中提取菜谱内容，用Markdown格式组织。\n\n要求：\n- 完整保留所有烹饪细节、材料比例、温度、时间等信息\n- 使用便于教学的清晰排版格式\n- 组织为：菜名、材料清单、烹饪步骤、烹饪技巧等结构\n- 如果字幕中没有完整的菜谱信息，请根据文字进行合理补充\n- 保持中文输出，易于阅读和操作\n\n字幕内容如下：\n{content}\n\n请输出提取后的Markdown格式菜谱："
            }
        }
    
    def _save_config(self) -> None:
        """保存配置文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            print(f"✅ 配置已保存: {self.config_path}")
        except Exception as e:
            print(f"❌ 无法保存配置: {e}")
    
    def get_model(self) -> str:
        """获取当前模型"""
        return self.config.get("ollama", {}).get("model", "qwen3-vl:8b")
    
    def set_model(self, model: str) -> None:
        """设置模型"""
        if "ollama" not in self.config:
            self.config["ollama"] = {}
        self.config["ollama"]["model"] = model
        self._save_config()
        print(f"✅ 模型已切换: {model}")
    
    def get_base_url(self) -> str:
        """获取 Ollama 基础 URL"""
        return self.config.get("ollama", {}).get("base_url", "http://localhost:11434")
    
    def set_base_url(self, base_url: str) -> None:
        """设置 Ollama 基础 URL"""
        if "ollama" not in self.config:
            self.config["ollama"] = {}
        self.config["ollama"]["base_url"] = base_url
        self._save_config()
    
    def get_prompt(self, prompt_key: str) -> str:
        """获取指定的提示词"""
        return self.config.get("prompts", {}).get(prompt_key, "")
    
    def set_prompt(self, prompt_key: str, prompt_text: str) -> None:
        """设置指定的提示词"""
        if "prompts" not in self.config:
            self.config["prompts"] = {}
        self.config["prompts"][prompt_key] = prompt_text
        self._save_config()
        print(f"✅ 提示词已更新: {prompt_key}")
    
    def list_prompts(self) -> List[str]:
        """列出所有提示词键"""
        return list(self.config.get("prompts", {}).keys())
    
    def show_config(self) -> None:
        """显示当前配置"""
        print("\n" + "="*60)
        print("📋 当前配置")
        print("="*60)
        print(f"\n🤖 Ollama 配置:")
        print(f"  - 地址: {self.get_base_url()}")
        print(f"  - 模型: {self.get_model()}")
        print(f"\n💬 提示词:")
        for key in self.list_prompts():
            prompt_text = self.get_prompt(key)
            preview = prompt_text[:50] + "..." if len(prompt_text) > 50 else prompt_text
            print(f"  - {key}: {preview}")
        print("\n" + "="*60 + "\n")


class OllamaClient:
    """Ollama HTTP API 客户端"""
    
    def __init__(self, config_manager: ConfigManager = None):
        """
        初始化 Ollama 客户端
        
        Args:
            config_manager: 配置管理器实例
        """
        if config_manager is None:
            config_manager = ConfigManager()
        
        self.config_manager = config_manager
        self.model = config_manager.get_model()
        self.base_url = config_manager.get_base_url()
        self.generate_url = f"{self.base_url}/api/generate"
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为 base64"""
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
                return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            print(f"❌ 图片编码失败: {e}")
            return ""
    
    def generate(self, prompt: str, image_path: Optional[str] = None) -> str:
        """
        调用 Ollama HTTP API 生成响应
        
        Args:
            prompt: 提示词
            image_path: 可选的图片路径 (用于视觉模型)
            
        Returns:
            生成的文本
        """
        try:
            # 构建请求数据
            data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
            
            # 如果提供了图片路径，将其编码并添加到请求中
            if image_path and os.path.exists(image_path):
                image_base64 = self._encode_image_to_base64(image_path)
                if image_base64:
                    # 对于视觉模型，将 base64 图片信息传入 prompt
                    data["prompt"] = f"[image: {image_base64}]\n\n{prompt}"
            
            # 发送 HTTP 请求
            response = requests.post(
                self.generate_url,
                json=data,
                timeout=300  # 5分钟超时
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                print(f"❌ Ollama API 错误 ({response.status_code}): {response.text}")
                return ""
        
        except requests.exceptions.ConnectionError:
            print(f"❌ 无法连接到 Ollama 服务 ({self.base_url})")
            return ""
        except requests.exceptions.Timeout:
            print(f"❌ Ollama 请求超时")
            return ""
        except Exception as e:
            print(f"❌ 调用 Ollama 失败: {e}")
            return ""


class SRTParser:
    """SRT 字幕文件解析器"""
    
    @staticmethod
    def parse(srt_path: str) -> List[Dict]:
        """解析 SRT 文件"""
        segments = []
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 简单的 SRT 解析
            blocks = content.strip().split('\n\n')
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    segments.append({
                        'index': lines[0],
                        'time': lines[1],
                        'text': '\n'.join(lines[2:])
                    })
            return segments
        except Exception as e:
            print(f"❌ 解析 SRT 失败: {e}")
            return []
    
    @staticmethod
    def exists(video_path: Path) -> bool:
        """检查对应的 SRT 字幕是否存在"""
        srt_path = video_path.with_suffix('.srt')
        return srt_path.exists()
    
    @staticmethod
    def get_path(video_path: Path) -> Path:
        """获取对应的 SRT 文件路径"""
        return video_path.with_suffix('.srt')


@dataclass
class FileInfo:
    """文件信息类"""
    path: str
    name: str
    extension: str
    size: int
    category: str


class FileProcessor:
    """文件处理器 - 遍历文件夹并根据类型处理"""
    
    # 文件类型映射
    FILE_TYPES = {
        'markdown': {'.md', '.markdown'},
        'video': {'.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.webm', '.m4v'},
        'image': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.tiff'}
    }
    
    def __init__(self, folder_path: str):
        """初始化处理器
        
        Args:
            folder_path: 要遍历的文件夹路径
        """
        self.folder_path = Path(folder_path)
        if not self.folder_path.exists():
            raise ValueError(f"文件夹不存在: {folder_path}")
        
        # 存储各类型处理函数
        self.handlers: Dict[str, List[Callable]] = {
            'markdown': [],
            'video': [],
            'image': []
        }
    
    def categorize_file(self, extension: str) -> str:
        """根据扩展名分类文件"""
        ext_lower = extension.lower()
        for category, extensions in self.FILE_TYPES.items():
            if ext_lower in extensions:
                return category
        return 'other'
    
    def register_handler(self, category: str, handler: Callable) -> None:
        """注册处理函数
        
        Args:
            category: 文件类别 ('markdown', 'video', 'image')
            handler: 处理函数，接收 FileInfo 对象
        """
        if category in self.handlers:
            self.handlers[category].append(handler)
        else:
            raise ValueError(f"未知的文件类别: {category}")
    
    def scan_files(self, recursive: bool = True) -> Dict[str, List[FileInfo]]:
        """扫描文件夹
        
        Args:
            recursive: 是否递归扫描子文件夹
            
        Returns:
            按类别分类的文件信息字典
        """
        files_by_category = {
            'markdown': [],
            'video': [],
            'image': [],
            'other': []
        }
        
        pattern = '**/*' if recursive else '*'
        
        for file_path in self.folder_path.glob(pattern):
            if not file_path.is_file():
                continue
            
            file_info = FileInfo(
                path=str(file_path),
                name=file_path.name,
                extension=file_path.suffix,
                size=file_path.stat().st_size,
                category=self.categorize_file(file_path.suffix)
            )
            
            category = file_info.category
            if category in files_by_category:
                files_by_category[category].append(file_info)
        
        return files_by_category
    
    def process(self, recursive: bool = True) -> Dict[str, int]:
        """扫描并处理文件
        
        Args:
            recursive: 是否递归扫描子文件夹
            
        Returns:
            处理统计信息
        """
        files_by_category = self.scan_files(recursive)
        stats = {'total': 0, 'processed': 0}
        
        # 处理 markdown 文件
        for file_info in files_by_category['markdown']:
            stats['total'] += 1
            for handler in self.handlers['markdown']:
                try:
                    result = handler(file_info)
                    # 只有在handler返回True时才算处理过
                    if result:
                        stats['processed'] += 1
                except Exception as e:
                    print(f"处理 {file_info.name} 失败: {e}")
        
        # 处理视频文件
        for file_info in files_by_category['video']:
            stats['total'] += 1
            for handler in self.handlers['video']:
                try:
                    result = handler(file_info)
                    # 只有在handler返回True时才算处理过
                    if result:
                        stats['processed'] += 1
                except Exception as e:
                    print(f"处理 {file_info.name} 失败: {e}")
        
        # 处理图片文件
        for file_info in files_by_category['image']:
            stats['total'] += 1
            for handler in self.handlers['image']:
                try:
                    result = handler(file_info)
                    # 只有在handler返回True时才算处理过
                    if result:
                        stats['processed'] += 1
                except Exception as e:
                    print(f"处理 {file_info.name} 失败: {e}")
        
        return stats, files_by_category
    
    def print_summary(self, files_by_category: Dict[str, List[FileInfo]]) -> None:
        """打印文件扫描摘要"""
        print("\n" + "="*60)
        print("📁 文件扫描结果")
        print("="*60)
        
        for category, files in files_by_category.items():
            if category == 'other':
                continue
            if files:
                print(f"\n📋 {category.upper()} 文件 ({len(files)} 个):")
                for file_info in files:
                    size_mb = file_info.size / (1024 * 1024)
                    print(f"  - {file_info.name} ({size_mb:.2f} MB)")
        
        if files_by_category['other']:
            print(f"\n❓ 其他文件 ({len(files_by_category['other'])} 个):")
            for file_info in files_by_category['other'][:5]:
                print(f"  - {file_info.name}")
            if len(files_by_category['other']) > 5:
                print(f"  ... 还有 {len(files_by_category['other']) - 5} 个文件")
        
        print("\n" + "="*60)


# ============ 实际处理函数 ============

# 需要导入 fur.py 中的 SpeechRecognizer
try:
    from fur import SpeechRecognizer
    SPEECH_RECOGNIZER = SpeechRecognizer()
except Exception as e:
    print(f"⚠️  警告：无法加载 SpeechRecognizer: {e}")
    SPEECH_RECOGNIZER = None

# 全局配置管理器
CONFIG_MANAGER = ConfigManager()


def process_video_file(file_info: FileInfo) -> bool:
    """
    处理视频文件：检查字幕，如果没有则通过 ASR 识别生成；如果有字幕，则用 Qwen 提取菜谱
    返回 True 表示实际进行了处理，False 表示跳过
    """
    video_path = Path(file_info.path)
    srt_path = SRTParser.get_path(video_path)
    
    if SRTParser.exists(video_path):
        print(f"✅ [Video] {file_info.name} - 字幕已存在: {srt_path.name}")
        # 从字幕提取菜谱
        return extract_recipe_from_subtitle(video_path, srt_path)
    else:
        if SPEECH_RECOGNIZER is None:
            print(f"❌ [Video] {file_info.name} - 无法处理（SpeechRecognizer 未加载）")
            return False
        
        try:
            print(f"🎙️  [Video] {file_info.name} - 正在识别字幕...")
            # 调用 fur.py 的 transcribe 方法生成字幕
            SPEECH_RECOGNIZER.transcribe(str(video_path), output_srt=True)
            print(f"✅ [Video] {file_info.name} - 字幕生成完成")
            return True
        except Exception as e:
            print(f"❌ [Video] {file_info.name} - 字幕识别失败: {e}")
            return False


def extract_recipe_from_subtitle(video_path: Path, srt_path: Path) -> bool:
    """
    从视频字幕中提取菜谱内容，用 Qwen 生成 Markdown 格式的菜谱
    返回 True 表示实际进行了处理，False 表示跳过
    
    Args:
        video_path: 视频文件路径
        srt_path: 字幕文件路径
    """
    # 检查对应的菜谱 Markdown 是否已存在
    md_filename = video_path.stem + "_recipe.md"
    md_path = video_path.parent / md_filename
    
    if md_path.exists():
        print(f"⏭️  [Subtitle] {video_path.name} - 菜谱已提取，跳过")
        return False
    
    try:
        # 解析字幕文件
        segments = SRTParser.parse(str(srt_path))
        
        if not segments:
            print(f"❌ [Subtitle] {video_path.name} - 字幕解析失败或为空")
            return False
        
        # 合并所有字幕文本
        subtitle_text = '\n'.join([segment['text'] for segment in segments])
        
        # 初始化 Ollama 客户端
        ollama_client = OllamaClient(CONFIG_MANAGER)
        
        # 从配置获取提示词模板
        prompt_template = CONFIG_MANAGER.get_prompt("subtitle_recipe_extraction")
        prompt = prompt_template.format(content=subtitle_text)
        
        print(f"👨‍🍳 [Subtitle] {video_path.name} - 正在提取菜谱...")
        
        # 调用 Ollama/Qwen 提取菜谱
        response = ollama_client.generate(prompt)
        
        if response:
            # 保存为 Markdown 文件
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(response)
            
            print(f"✅ [Subtitle] {video_path.name} - 菜谱已提取: {md_filename}")
            return True
        else:
            print(f"❌ [Subtitle] {video_path.name} - 菜谱提取失败或无响应")
            return False
    
    except Exception as e:
        print(f"❌ [Subtitle] {video_path.name} - 提取失败: {e}")
        return False


def process_image_file(file_info: FileInfo) -> bool:
    """
    处理图片文件：通过 Ollama 识别内容并保存为 Markdown
    返回 True 表示实际进行了处理，False 表示跳过
    """
    image_path = Path(file_info.path)
    
    # 检查对应的 Markdown 是否已存在
    md_filename = image_path.stem + "_recipe.md"
    md_path = image_path.parent / md_filename
    
    if md_path.exists():
        print(f"⏭️  [Image] {file_info.name} - 已处理过，跳过")
        return False
    
    ollama_client = OllamaClient(CONFIG_MANAGER)
    
    # 从配置获取提示词
    prompt = CONFIG_MANAGER.get_prompt("image_recognition")
    
    print(f"🔍 [Image] {image_path.name} - 正在识别内容...")
    
    try:
        # 调用 Ollama 识别
        response = ollama_client.generate(prompt, str(image_path))
        
        if response:
            # 保存为 Markdown 文件（带处理标记）
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(response)
            
            print(f"✅ [Image] {image_path.name} - Markdown 已保存: {md_filename}")
            return True
        else:
            print(f"❌ [Image] {image_path.name} - 识别失败或无响应")
            return False
    
    except Exception as e:
        print(f"❌ [Image] {image_path.name} - 处理失败: {e}")
        return False


def process_markdown_file(file_info: FileInfo) -> bool:
    """
    处理 Markdown 文件：通过 Ollama 优化格式为菜谱格式
    返回 True 表示实际进行了处理，False 表示跳过
    """
    md_path = Path(file_info.path)
    
    # 检查文件名是否为生成的文件（跳过 _recipe, _analysis, _visual, _tutorial 等）
    if any(suffix in md_path.stem for suffix in ['_recipe', '_analysis', '_visual', '_tutorial']):
        print(f"⏭️  [Markdown] {file_info.name} - 已是生成文件，跳过")
        return False
    
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ [Markdown] {file_info.name} - 读取失败: {e}")
        return False
    
    ollama_client = OllamaClient(CONFIG_MANAGER)
    
    # 从配置获取提示词模板
    prompt_template = CONFIG_MANAGER.get_prompt("markdown_optimize")
    prompt = prompt_template.format(content=content)
    
    print(f"📝 [Markdown] {file_info.name} - 正在优化格式...")
    
    try:
        response = ollama_client.generate(prompt)
        
        if response:
            # 保存优化后的内容
            backup_path = md_path.with_stem(md_path.stem + "_backup")
            
            # 备份原文件
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 保存优化后的文件
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(response)
            
            # 重命名文件，添加处理标记
            new_name = md_path.stem + " [✓].md"
            new_path = md_path.parent / new_name
            md_path.rename(new_path)
            
            print(f"✅ [Markdown] {file_info.name} - 格式优化完成，已重命名: {new_name}")
            return True
        else:
            print(f"❌ [Markdown] {file_info.name} - 优化失败或无响应")
            return False
    
    except Exception as e:
        print(f"❌ [Markdown] {file_info.name} - 处理失败: {e}")
        return False


def main():
    """主函数 - 循环处理直到没有新的符合条件的文件"""
    # 指定要处理的文件夹（改为你的文件夹路径）
    folder_path = r"C:\Users\magic\Desktop\烹饪\蒸蛋"
    
    print(f"🚀 开始扫描文件夹: {folder_path}\n")
    
    round_num = 1
    total_processed = 0
    
    # 循环处理直到没有新文件被处理
    while True:
        print("\n" + "="*60)
        print(f"📍 处理轮次: {round_num}")
        print("="*60)
        
        # 创建处理器
        processor = FileProcessor(folder_path)
        
        # 注册处理函数
        processor.register_handler('markdown', process_markdown_file)
        processor.register_handler('video', process_video_file)
        processor.register_handler('image', process_image_file)
        
        # 处理文件（recursive=True 表示递归扫描子文件夹）
        stats, files_by_category = processor.process(recursive=True)
        
        # 打印摘要
        processor.print_summary(files_by_category)
        
        # 打印本轮处理统计
        print(f"\n📊 本轮处理统计:")
        print(f"   总文件数: {stats['total']}")
        print(f"   已处理: {stats['processed']}")
        
        total_processed += stats['processed']
        
        # 如果本轮没有处理任何文件，说明已完成所有待处理的文件
        if stats['processed'] == 0:
            print(f"\n✅ 所有符合条件的文件已处理完成!")
            print(f"   总轮次: {round_num}")
            print(f"   总处理数: {total_processed}")
            break
        
        round_num += 1


if __name__ == "__main__":
    main()
