from ocr import SubtitleExtractor

video_file = "云南的早餐多着呢~米浆粑粑看招！.mp4"

# 创建OCR字幕提取器
extractor = SubtitleExtractor()

# 提取字幕
extractor.extract(
    video_path=video_file,
    force_ocr=True,
    interval_ms=500,
    stability=2,
)