"""
Cooking Recipe Pipeline - 烹饪视频菜谱提取系统

一个完整的四阶段处理流程，用于从烹饪视频或图片中自动提取和生成详细的菜谱。
"""

__version__ = "1.0.0"
__author__ = "Magic"
__description__ = "AI-powered cooking recipe extraction pipeline from videos and images"

from src.main_pipeline import CookingRecipePipeline

__all__ = ["CookingRecipePipeline"]
