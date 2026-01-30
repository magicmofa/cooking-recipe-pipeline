import os
import json
import logging
from pathlib import Path
from funasr import AutoModel

class SpeechRecognizer:
    def __init__(self):
        """
        初始化 ASR 模型。
        """
        self.config = self._load_config()
        self._prepare_modelscope_env()
        print("正在加载 FunASR 模型...")
        self.model = AutoModel(
            model="iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
            vad_model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
            punc_model="iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
            trust_remote_code=False,
            disable_update=True,
        )
        print("✅ FunASR 模型加载完成")

    def _load_config(self) -> dict:
        config_path = Path("config.json")
        if not config_path.exists():
            return {}
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _prepare_modelscope_env(self):
        funasr_cfg = self.config.get("funasr", {})
        offline_when_cached = funasr_cfg.get("offline_when_cached", True)
        quiet = funasr_cfg.get("quiet", True)

        if quiet:
            os.environ.setdefault("MODELSCOPE_LOG_LEVEL", "ERROR")
            logging.getLogger().setLevel(logging.ERROR)
            logging.getLogger("modelscope").setLevel(logging.ERROR)
            logging.getLogger("modelscope.utils").setLevel(logging.ERROR)

        if offline_when_cached:
            cache_root = Path.home() / ".cache" / "modelscope" / "hub" / "models" / "iic"
            model_dirs = [
                "speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
                "speech_fsmn_vad_zh-cn-16k-common-pytorch",
                "punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
            ]
            all_cached = all((cache_root / name).exists() for name in model_dirs)
            if all_cached:
                os.environ["MODELSCOPE_OFFLINE"] = "1"

    def _extract_audio_if_needed(self, video_path: Path) -> Path:
        """
        内部逻辑：判断并提取音频。
        返回生成的（或已存在的）音频文件路径。
        """
        audio_path = video_path.with_suffix(".wav")

        # 1. 如果音频已经存在，直接返回
        if audio_path.exists():
            # print(f"🔍 发现已有音频，跳过提取: {audio_path.name}")
            return audio_path

        # 2. 如果不存在，调用 ffmpeg 提取
        print(f"🔨 正在提取音频: {video_path.name} -> {audio_path.name}")
        
        # 这里的 ffmpeg 命令：
        # -vn: 去掉视频流
        # -ac 1: 单声道 (ASR 只需要单声道)
        # -ar 16000: 16k 采样率 (模型要求)
        cmd = f'ffmpeg -i "{video_path}" -ac 1 -ar 16000 -vn "{audio_path}" -y -v quiet'
        exit_code = os.system(cmd)
        
        if exit_code != 0:
            raise RuntimeError(f"❌ ffmpeg 提取失败，请检查视频路径或是否安装了 ffmpeg。")
            
        return audio_path

    def transcribe(self, video_file: str, output_srt: bool = False):
        """
        主入口：传入视频路径，返回识别结果列表。
        自动处理音频提取逻辑。
        
        参数：
            video_file: 视频文件路径
            output_srt: 可选，是否生成 SRT 字幕文件。
                       如果为 True，则在项目根目录生成与视频文件同名的 .srt 文件。
                       默认为 False。
        """
        video_path = Path(video_file)
        
        if not video_path.exists():
            print(f"❌ 错误：找不到视频文件 {video_path}")
            return []

        # Step 1: 自动获取/生成音频
        try:
            audio_path = self._extract_audio_if_needed(video_path)
        except Exception as e:
            print(e)
            return []

        # Step 2: 执行识别
        print(f"🎙️ 正在识别: {video_path.name} ...")
        
        # FunASR 推理
        res = self.model.generate(
            input=str(audio_path),            
            batch_size_s=300,            
            sentence_timestamp=True,      
            return_timestamps=True,       
            disable_pbar=False,
            trust_remote_code=False            
        )

        segments = []
        if res and len(res) > 0:
            # 优先读取 VAD 切分后的 sentence_info
            if "sentence_info" in res[0]:
                for item in res[0]["sentence_info"]:
                    text_clean = item["text"].replace(" ", "")
                    segments.append({
                        "text": text_clean,
                        "start": item["start"] / 1000.0, # 毫秒转秒
                        "end": item["end"] / 1000.0,
                    })
            # 兜底：如果没有切分信息（极短语音）
            elif "text" in res[0]:
                 segments.append({
                    "text": res[0]["text"].replace(" ", ""),
                    "start": 0.0,
                    "end": 0.0,
                })
        
        # Step 3: 如果需要生成 SRT 文件
        if output_srt:
            # 根据视频文件名生成对应的 SRT 文件名，保存在视频所在目录
            srt_filename = video_path.stem + ".srt"
            srt_path = video_path.parent / srt_filename
            self.generate_srt(segments, str(srt_path))
        
        return segments

    def generate_srt(self, segments, output_srt_path: str):
        """
        辅助工具：生成 SRT 文件（可选）
        """
        def _fmt(seconds):
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(s*1000)%1000:03d}"

        with open(output_srt_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments):
                start = _fmt(seg['start'])
                end = _fmt(seg['end'])
                f.write(f"{i+1}\n{start} --> {end}\n{seg['text']}\n\n")
        print(f"📄 SRT 字幕已生成: {output_srt_path}")

# ==========================================
# 调用示例
# ==========================================
if __name__ == "__main__":
    # 1. 初始化
    recognizer = SpeechRecognizer()

    # 2. 直接丢视频路径进去 (不管有没有音频，它自己会处理)
    video_file = "云南的早餐多着呢~米浆粑粑看招！.mp4"
    
    # 3. 获取结果 List[Dict]
    # 方式 A：不生成 SRT 文件
    # results = recognizer.transcribe(video_file)
    
    # 方式 B：生成 SRT 文件（自动根据视频名生成，保存到项目根目录）
    # 生成的文件名为：云南的早餐多着呢~米浆粑粑看招！.srt
    results = recognizer.transcribe(video_file, output_srt=True)

    # 4. 打印看看
    print(f"识别完成，共 {len(results)} 句。")
    if len(results) > 0:
        print(f"第一句: {results[0]}")