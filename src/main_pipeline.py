"""
烹饪视频菜谱提取完整流程
======================

这是一个完整的五阶段处理流程:
1. 阶段一: 初步提取 - 从视频/图片生成初步菜谱
2. 阶段二: 精细化分析 - 分析缺漏，生成截图时间表
3. 阶段三: 视觉补充 - 提取关键帧，生成完整菜谱
4. 阶段四: 最终整合 - 整合所有资料生成完整教程
5. 阶段五: 菜谱对比 - 对比多份整合结果，提取差异部分
"""

import sys
from pathlib import Path
from typing import Optional
import json

# 导入各个模块
from file_processor import (
    FileProcessor, 
    process_video_file,
    process_image_file,
    process_markdown_file,
    CONFIG_MANAGER
)
from fine_grained_processor import FineGrainedProcessor
from frame_clip_pipeline_v2 import run_pipeline_v2, DEFAULT_OLLAMA_URL, DEFAULT_MODEL
from final_tutorial_generator import FinalTutorialGenerator
from recipe_comparison import RecipeComparison


class CookingRecipePipeline:
    """烹饪菜谱提取完整流程控制器"""

    def __init__(self, folder_path: str, config_path: str = "config.json"):
        """
        初始化流程控制器

        Args:
            folder_path: 要处理的文件夹路径
            config_path: 配置文件路径
        """
        self.folder_path = Path(folder_path)
        self.config_path = Path(config_path)

        if not self.folder_path.exists():
            raise ValueError(f"文件夹不存在: {folder_path}")

        # 加载配置
        self.config = self._load_config()

        print(f"🎯 流程控制器初始化完成")
        print(f"📁 工作目录: {self.folder_path}")
        print(f"⚙️  配置文件: {self.config_path}")
        print(f"🤖 API 提供商: {self.config.get('api_provider', 'ollama')}")

    def _load_config(self) -> dict:
        """加载配置文件"""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def stage_1_initial_extraction(self, recursive: bool = True) -> dict:
        """
        阶段一：初步提取
        - 处理视频文件：ASR 生成字幕 → 提取菜谱
        - 处理图片文件：识别内容 → 生成菜谱
        - 处理 Markdown：优化格式

        Args:
            recursive: 是否递归处理子文件夹

        Returns:
            处理统计信息
        """
        print("\n" + "="*70)
        print("🚀 阶段一：初步提取 - 从原始文件生成初步菜谱")
        print("="*70)

        processor = FileProcessor(str(self.folder_path))

        # 注册处理函数
        processor.register_handler('video', process_video_file)
        processor.register_handler('image', process_image_file)
        processor.register_handler('markdown', process_markdown_file)

        # 循环处理直到没有新文件
        round_num = 1
        total_processed = 0
        files_processed_this_round = 0

        while True:
            print(f"\n--- 第 {round_num} 轮扫描 ---")

            # 扫描文件
            files_by_category = processor.scan_files(recursive=recursive)
            files_processed_this_round = 0

            # 处理 markdown 文件（跳过生成的文件）
            for file_info in files_by_category['markdown']:
                # 跳过生成的文档（recipe、analysis、visual、tutorial）
                if any(keyword in file_info.name for keyword in ['_recipe', '_analysis', '_visual', '_tutorial', '_optimized']):
                    continue

                stats = {'total': 0, 'processed': 0}
                for handler in processor.handlers['markdown']:
                    try:
                        if handler(file_info):
                            files_processed_this_round += 1
                    except Exception as e:
                        print(f"处理 {file_info.name} 时出错: {e}")

            # 处理视频文件（跳过生成的片段）
            for file_info in files_by_category['video']:
                # 跳过 clips 目录中的视频片段和 clip_*.mp4 文件
                file_path = Path(file_info.path)
                if 'clips' in file_path.parts or file_info.name.startswith('clip_'):
                    continue

                stats = {'total': 0, 'processed': 0}
                for handler in processor.handlers['video']:
                    try:
                        if handler(file_info):
                            files_processed_this_round += 1
                    except Exception as e:
                        print(f"处理 {file_info.name} 时出错: {e}")

            # 处理图片文件（跳过生成的截图）
            for file_info in files_by_category['image']:
                # 跳过 frames 目录中的截图
                file_path = Path(file_info.path)
                if 'frames' in file_path.parts or file_info.name.startswith('frame_'):
                    continue

                stats = {'total': 0, 'processed': 0}
                for handler in processor.handlers['image']:
                    try:
                        if handler(file_info):
                            files_processed_this_round += 1
                    except Exception as e:
                        print(f"处理 {file_info.name} 时出错: {e}")

            if files_processed_this_round == 0:
                print(f"\n✅ 阶段一完成！本轮无新文件需要处理")
                break

            total_processed += files_processed_this_round
            print(f"\n本轮处理: {files_processed_this_round} 个文件")
            round_num += 1

            # 安全机制：最多10轮
            if round_num > 10:
                print(f"\n⚠️  已达到最大处理轮数 (10)，停止处理")
                break

        result = {
            'rounds': round_num - 1,
            'total_processed': total_processed
        }

        print(f"\n📊 阶段一统计：共处理 {total_processed} 个文件，用了 {round_num - 1} 轮")
        return result

    def stage_2_fine_grained_analysis(self) -> dict:
        """
        阶段二：精细化分析
        - 查找初步菜谱文件（_recipe.md）
        - 对比字幕和菜谱内容
        - 评估完整性，生成缺漏细节
        - 生成视频截图时间表

        Returns:
            处理结果字典
        """
        print("\n" + "="*70)
        print("🔍 阶段二：精细化分析 - 评估完整性并生成截图时间表")
        print("="*70)

        processor = FineGrainedProcessor(
            folder_path=str(self.folder_path),
            config_path=str(self.config_path)
        )

        results = processor.process_pairs()

        print(f"\n📊 阶段二统计：共分析 {len(results)} 个文件对")
        return results

    def stage_3_visual_enhancement(self) -> list:
        """
        阶段三：视觉补充与剪辑
        - 读取 _refined.md 中的时间表
        - 从视频提取关键帧
        - 调用视觉模型分析
        - 生成视频片段
        - 输出最终完整菜谱

        Returns:
            生成的结果文件路径列表
        """
        print("\n" + "="*70)
        print("🎬 阶段三：视觉补充 - 提取关键帧并生成完整菜谱")
        print("="*70)

        # 查找所有 _analysis.md 文件
        analysis_files = sorted(self.folder_path.rglob("*_analysis.md"))

        if not analysis_files:
            print(f"⚠️  未找到任何 _analysis.md 文件，跳过阶段三")
            return []

        print(f"找到 {len(analysis_files)} 个待处理文件\n")

        results = []

        for analysis_md_path in analysis_files:
            print(f"\n{'#'*70}")
            print(f"处理: {analysis_md_path.name}")
            print(f"{'#'*70}")

            # 推断视频名称
            md_name = analysis_md_path.stem
            video_name = md_name.replace("_analysis", "")

            # 查找对应的视频文件
            video_candidates = sorted(self.folder_path.rglob(f"{video_name}.mp4"))

            if not video_candidates:
                print(f"❌ 未找到对应的视频文件: {video_name}.mp4")
                continue

            video_path = video_candidates[0]
            print(f"✓ 视频: {video_path.name}")
            print(f"✓ Markdown: {analysis_md_path.name}")

            # 创建输出目录
            output_dir = analysis_md_path.parent / video_name
            print(f"✓ 输出目录: {output_dir}")

            # 获取 Ollama 配置
            ollama_config = self.config.get("ollama", {})
            ollama_url = ollama_config.get("base_url", DEFAULT_OLLAMA_URL)
            model = ollama_config.get("model", DEFAULT_MODEL)

            # 运行视觉处理流程
            try:
                result_md = run_pipeline_v2(
                    video_path=str(video_path),
                    refined_md_path=str(analysis_md_path),
                    output_dir=str(output_dir),
                    ollama_url=ollama_url,
                    model=model,
                    video_name=video_name,
                )
                results.append(result_md)
                print(f"✅ 成功生成: {result_md}")
            except Exception as e:
                print(f"❌ 处理失败: {e}")
                continue

        print(f"\n📊 阶段三统计：共生成 {len(results)} 个完整菜谱文档")
        return results

    def stage_4_final_tutorial(self) -> list:
        """
        阶段四：生成最终教程
        - 整合字幕、初步菜谱、精细化分析、视觉补充
        - 生成完整的制作教程

        Returns:
            生成的教程文件路径列表
        """
        print("\n" + "="*70)
        print("🎓 阶段四：生成最终教程 - 整合所有资料")
        print("="*70)

        generator = FinalTutorialGenerator(
            folder_path=str(self.folder_path),
            config_path=str(self.config_path)
        )

        results = generator.process_all()

        print(f"\n📊 阶段四统计：共生成 {len(results)} 份最终教程")
        return results

    def stage_5_recipe_comparison(self) -> Optional[Path]:
        """
        阶段五：菜谱对比整合（可选）
        - 检测是否存在多个最终整合结果
        - 询问用户是否需要进行对比整合
        - 通过 Deepseek 对比各菜谱
        - 总结出有差异的部分
        - 输出为新的 md 文件

        Returns:
            对比结果文件路径，如果不进行对比则返回 None
        """
        print("\n" + "="*70)
        print("🔍 阶段五（可选）：菜谱对比整合 - 对比多份整合结果")
        print("="*70)

        try:
            comparison = RecipeComparison(
                folder_path=str(self.folder_path),
                config_path=str(self.config_path)
            )

            result_path = comparison.run_comparison_workflow()

            if result_path:
                print(f"\n✅ 阶段五完成：对比结果已保存到 {result_path}")
            else:
                print(f"\n⏭️  阶段五跳过：未进行对比整合或不存在多个整合结果")

            return result_path

        except Exception as e:
            print(f"\n❌ 阶段五出错: {e}")
            import traceback
            traceback.print_exc()
            return None

    def run_full_pipeline(self, recursive: bool = True, skip_stages: list = None) -> dict:
        """
        运行完整的五阶段流程

        Args:
            recursive: 是否递归处理子文件夹
            skip_stages: 要跳过的阶段列表，例如 [1, 2, 3] 表示跳过阶段一、二、三

        Returns:
            完整流程的统计信息
        """
        skip_stages = skip_stages or []

        print("\n" + "="*70)
        print("🎯 开始运行完整的烹饪菜谱提取流程")
        print("="*70)
        print(f"📁 工作目录: {self.folder_path}")
        print(f"🔄 递归处理: {'是' if recursive else '否'}")

        results = {}

        # 阶段一
        if 1 not in skip_stages:
            results['stage_1'] = self.stage_1_initial_extraction(recursive)
        else:
            print("\n⏭️  跳过阶段一")

        # 阶段二
        if 2 not in skip_stages:
            results['stage_2'] = self.stage_2_fine_grained_analysis()
        else:
            print("\n⏭️  跳过阶段二")

        # 阶段三
        if 3 not in skip_stages:
            results['stage_3'] = self.stage_3_visual_enhancement()
        else:
            print("\n⏭️  跳过阶段三")

        # 阶段四
        if 4 not in skip_stages:
            results['stage_4'] = self.stage_4_final_tutorial()
        else:
            print("\n⏭️  跳过阶段四")

        # 阶段五（可选对比整合）- 自动运行（除非用户在交互中取消）
        if 5 not in skip_stages:
            results['stage_5'] = self.stage_5_recipe_comparison()
        else:
            print("\n⏭️  跳过阶段五（菜谱对比整合）")

        # 最终统计
        print("\n" + "="*70)
        print("🎉 完整流程执行完毕！")
        print("="*70)

        if 'stage_1' in results:
            print(f"阶段一：处理 {results['stage_1']['total_processed']} 个文件")
        if 'stage_2' in results:
            print(f"阶段二：分析 {len(results['stage_2'])} 个文件对")
        if 'stage_3' in results:
            print(f"阶段三：生成 {len(results['stage_3'])} 个完整菜谱")
        if 'stage_4' in results:
            print(f"阶段四：生成 {len(results['stage_4'])} 份最终教程")
        if 'stage_5' in results and results['stage_5']:
            print(f"阶段五：生成菜谱对比报告")

        print("\n✅ 全部完成！")
        return results


def main():
    """主函数 - 运行完整流程"""

    # ============ 配置区 ============
    # 要处理的文件夹路径
    folder_path = r"C:\Users\magic\Desktop\烹饪\蒸蛋"

    # 配置文件路径
    config_path = "config.json"

    # 是否递归处理子文件夹
    recursive = True

    # 要跳过的阶段（例如 [1] 表示跳过阶段一，[] 表示全部执行，[5] 表示跳过菜谱对比）
    skip_stages = []
    # ================================

    try:
        # 创建流程控制器
        pipeline = CookingRecipePipeline(folder_path, config_path)

        # 运行完整流程
        results = pipeline.run_full_pipeline(recursive=recursive, skip_stages=skip_stages)

        # 可以单独运行某个阶段：
        # pipeline.stage_1_initial_extraction()
        # pipeline.stage_2_fine_grained_analysis()
        # pipeline.stage_3_visual_enhancement()
        # pipeline.stage_4_final_tutorial()
        # pipeline.stage_5_recipe_comparison()

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断操作")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 流程执行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
