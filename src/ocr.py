"""
视频字幕提取工具 - 面向对象版本
支持软字幕提取（ffmpeg）和硬字幕提取（Qwen3-VL OCR）

使用示例：
    # 方式1：使用主提取器
    extractor = SubtitleExtractor(ollama_model="qwen3-vl:8b")
    output_srt = extractor.extract("video.mp4", "output.srt")
    
    # 方式2：仅提取软字幕
    ok = SoftSubExtractor.extract("video.mp4", "output.srt")
    
    # 方式3：仅提取硬字幕
    hard_extractor = HardSubExtractor(model="qwen3-vl:8b")
    hard_extractor.extract("video.mp4", "output.srt", roi_str="0,1440,3840,720")
"""

import argparse
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
from tqdm import tqdm
import ollama


@dataclass
class Segment:
    """字幕片段"""
    start: float
    end: float
    text: str


class SRTUtils:
    """SRT文件工具类"""

    @staticmethod
    def format_srt_time(seconds: float) -> str:
        """将秒数格式化为SRT时间格式"""
        if seconds < 0:
            seconds = 0.0
        whole = int(seconds)
        ms = int(round((seconds - whole) * 1000.0))
        # handle rounding carry
        if ms >= 1000:
            whole += 1
            ms -= 1000
        s = whole % 60
        m = (whole // 60) % 60
        h = whole // 3600
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def normalize_text(t: str) -> str:
        """规范化文本"""
        t = t.strip()
        # unify whitespace
        t = re.sub(r"[ \t]+", " ", t)
        # collapse excessive blank lines
        t = re.sub(r"\n{3,}", "\n\n", t)
        return t

    @staticmethod
    def is_none_text(t: str) -> bool:
        """判断是否为无字幕文本"""
        if not t:
            return True
        tt = t.strip().upper()
        return tt in {"<NONE>", "NONE", "无", "没有字幕", "无字幕"}

    @staticmethod
    def merge_adjacent(segments: List[Segment], max_gap: float = 0.30) -> List[Segment]:
        """合并相邻的相同字幕"""
        if not segments:
            return []
        merged = [segments[0]]
        for seg in segments[1:]:
            last = merged[-1]
            if seg.text == last.text and (seg.start - last.end) <= max_gap:
                last.end = max(last.end, seg.end)
            else:
                merged.append(seg)
        return merged

    @staticmethod
    def write_srt(path: str, segments: List[Segment]) -> None:
        """写入SRT文件"""
        with open(path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, 1):
                start = SRTUtils.format_srt_time(seg.start)
                end = SRTUtils.format_srt_time(seg.end)
                f.write(f"{i}\n{start} --> {end}\n{seg.text}\n\n")


class SoftSubExtractor:
    """软字幕提取器 - 使用ffmpeg提取文本字幕"""

    TEXT_SUB_CODECS = {
        "subrip", "srt", "ass", "ssa", "mov_text", "text", "webvtt", "ttml"
    }

    @staticmethod
    def _run(cmd: List[str]) -> Tuple[int, str, str]:
        """运行命令"""
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return p.returncode, p.stdout, p.stderr

    @staticmethod
    def _ffprobe_subtitle_streams(video_path: str) -> List[dict]:
        """获取视频中的字幕流信息"""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "s",
            "-show_entries", "stream=index,codec_name:stream_tags=language,title",
            "-of", "json",
            video_path
        ]
        rc, out, err = SoftSubExtractor._run(cmd)
        if rc != 0:
            raise RuntimeError(f"ffprobe failed: {err.strip()}")
        data = json.loads(out)
        return data.get("streams", [])

    @staticmethod
    def extract(video_path: str, out_srt: str, preferred_stream: Optional[int] = None) -> bool:
        """
        尝试使用ffmpeg提取文本字幕流
        返回True表示成功，False表示失败
        """
        if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
            return False

        try:
            streams = SoftSubExtractor._ffprobe_subtitle_streams(video_path)
        except Exception:
            return False

        if not streams:
            return False

        # Choose a stream:
        chosen = None
        if preferred_stream is not None:
            # preferred_stream means absolute stream index (ffprobe stream.index)
            for s in streams:
                if int(s.get("index", -1)) == preferred_stream:
                    chosen = s
                    break
        else:
            # First text-based codec stream
            for s in streams:
                codec = (s.get("codec_name") or "").lower()
                if codec in SoftSubExtractor.TEXT_SUB_CODECS:
                    chosen = s
                    break

        if chosen is None:
            return False

        codec = (chosen.get("codec_name") or "").lower()
        if codec not in SoftSubExtractor.TEXT_SUB_CODECS:
            return False

        idx = int(chosen["index"])
        # Extract and convert to srt (style will be lost for ASS/SSA)
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-map", f"0:{idx}",
            "-c:s", "srt",
            out_srt
        ]
        rc, out, err = SoftSubExtractor._run(cmd)
        return rc == 0 and os.path.exists(out_srt) and os.path.getsize(out_srt) > 0


class HardSubExtractor:
    """硬字幕提取器 - 使用Qwen3-VL OCR提取图像中的字幕"""

    def __init__(self, model: str = "qwen3-vl:8b", host: str = "http://localhost:11434"):
        """
        初始化硬字幕提取器

        Args:
            model: Ollama模型名称
            host: Ollama服务地址
        """
        self.model = model
        self.host = host
        self.client = ollama.Client(host=host)

    @staticmethod
    def _preprocess_roi(roi_bgr: np.ndarray, scale: int = 2) -> np.ndarray:
        """预处理ROI区域"""
        # upscale
        h, w = roi_bgr.shape[:2]
        roi = cv2.resize(roi_bgr, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # light denoise
        gray = cv2.bilateralFilter(gray, 7, 40, 40)
        # adaptive threshold often helps subtitle contrast
        thr = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,
            31, 7
        )
        return thr

    @staticmethod
    def _mean_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
        """计算两个矩阵的平均绝对差"""
        if a.shape != b.shape:
            return 1e9
        return float(np.mean(cv2.absdiff(a, b)))

    def _extract_text_from_image(self, image_bytes: bytes) -> str:
        """使用Qwen3-VL从图像提取文本"""
        prompt = (
            "你是一名字幕提取器。请只输出这张画面里'字幕区域'的文字内容。\n"
            "要求：\n"
            "1) 如果画面没有字幕，输出 <NONE>\n"
            "2) 只输出字幕文字本身，不要解释、不要加引号、不要加前后缀\n"
            "3) 保留原本的换行（若字幕是两行就输出两行）\n"
        )
        resp = self.client.chat(
            model=self.model,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [image_bytes],
            }],
            options={"temperature": 0}
        )
        text = resp["message"]["content"]
        return SRTUtils.normalize_text(text)

    @staticmethod
    def _parse_roi(roi_str: str, frame_w: int, frame_h: int) -> Tuple[int, int, int, int]:
        """
        解析ROI字符串为坐标值
        roi_str: "x,y,w,h" 像素值
        """
        parts = [p.strip() for p in roi_str.split(",")]
        if len(parts) != 4:
            raise ValueError("ROI must be 'x,y,w,h' in pixels, e.g. 0,720,1920,360")
        x, y, w, h = map(int, parts)
        x = max(0, min(x, frame_w - 1))
        y = max(0, min(y, frame_h - 1))
        w = max(1, min(w, frame_w - x))
        h = max(1, min(h, frame_h - y))
        return x, y, w, h

    def extract(
        self,
        video_path: str,
        out_srt: str,
        interval_ms: int = 500,
        stability: int = 2,
        diff_thresh: float = 2.5,
        roi_str: Optional[str] = None,
        min_duration: float = 0.40,
    ) -> None:
        """
        从视频中提取硬字幕并保存为SRT文件

        Args:
            video_path: 输入视频路径
            out_srt: 输出SRT文件路径
            interval_ms: OCR采样间隔（毫秒）
            stability: 稳定性参数，需要N次连续相同的识别结果才切换
            diff_thresh: ROI变化检测阈值
            roi_str: ROI区域，格式为 "x,y,w,h"，默认为底部30%
            min_duration: 最小字幕段长度（秒）
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 1e-6:
            fps = 25.0

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        # read one frame for ROI sizing
        ok, frame0 = cap.read()
        if not ok:
            raise RuntimeError("Failed to read first frame.")
        frame_h, frame_w = frame0.shape[:2]

        if roi_str:
            x, y, w, h = self._parse_roi(roi_str, frame_w, frame_h)
        else:
            # default: bottom 30% of frame (common subtitle location)
            x, y, w, h = 0, int(frame_h * 0.70), frame_w, int(frame_h * 0.30)

        # reset to beginning
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        step_frames = max(1, int(round(fps * interval_ms / 1000.0)))
        interval_sec = step_frames / fps

        segments: List[Segment] = []

        stable_text = "<NONE>"
        candidate_text = None
        candidate_count = 0
        open_start: Optional[float] = None

        last_thr = None  # for diff-based skip
        last_observed = "<NONE>"

        # progress length
        if total_frames > 0:
            iterator = range(0, total_frames, step_frames)
            pbar_total = len(list(iterator))
            iterator = range(0, total_frames, step_frames)
        else:
            # unknown frame count
            iterator = None
            pbar_total = None

        def commit_change(new_text: str, change_time: float):
            nonlocal stable_text, open_start, segments
            # close old
            if not SRTUtils.is_none_text(stable_text) and open_start is not None:
                end_time = max(change_time, open_start + min_duration)
                segments.append(Segment(start=open_start, end=end_time, text=stable_text))
            # open new
            if SRTUtils.is_none_text(new_text):
                open_start = None
            else:
                open_start = change_time
            stable_text = new_text

        if iterator is None:
            # fallback loop reading sequentially and skipping
            frame_idx = 0
            pbar = tqdm(total=None, desc="OCR frames")
            while True:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ok, frame = cap.read()
                if not ok:
                    break
                t = frame_idx / fps
                roi = frame[y:y+h, x:x+w]
                thr = self._preprocess_roi(roi)

                do_infer = True
                if last_thr is not None:
                    if self._mean_abs_diff(thr, last_thr) < diff_thresh:
                        do_infer = False

                if do_infer:
                    ok_enc, buf = cv2.imencode(".jpg", thr, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                    if not ok_enc:
                        observed = "<NONE>"
                    else:
                        observed = self._extract_text_from_image(buf.tobytes())
                    last_thr = thr
                    last_observed = observed
                else:
                    observed = last_observed

                observed = "<NONE>" if SRTUtils.is_none_text(observed) else observed

                if observed == stable_text:
                    candidate_text = None
                    candidate_count = 0
                else:
                    if candidate_text == observed:
                        candidate_count += 1
                    else:
                        candidate_text = observed
                        candidate_count = 1
                    if candidate_count >= stability:
                        change_time = max(0.0, t - (stability - 1) * interval_sec)
                        commit_change(observed, change_time)
                        candidate_text = None
                        candidate_count = 0

                frame_idx += step_frames
                pbar.update(1)
            pbar.close()
            video_end = frame_idx / fps
        else:
            pbar = tqdm(total=pbar_total, desc="OCR frames")
            for frame_idx in iterator:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ok, frame = cap.read()
                if not ok:
                    break
                t = frame_idx / fps

                roi = frame[y:y+h, x:x+w]
                thr = self._preprocess_roi(roi)

                do_infer = True
                if last_thr is not None:
                    if self._mean_abs_diff(thr, last_thr) < diff_thresh:
                        do_infer = False

                if do_infer:
                    ok_enc, buf = cv2.imencode(".jpg", thr, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                    if not ok_enc:
                        observed = "<NONE>"
                    else:
                        observed = self._extract_text_from_image(buf.tobytes())
                    last_thr = thr
                    last_observed = observed
                else:
                    observed = last_observed

                observed = "<NONE>" if SRTUtils.is_none_text(observed) else observed

                if observed == stable_text:
                    candidate_text = None
                    candidate_count = 0
                else:
                    if candidate_text == observed:
                        candidate_count += 1
                    else:
                        candidate_text = observed
                        candidate_count = 1
                    if candidate_count >= stability:
                        change_time = max(0.0, t - (stability - 1) * interval_sec)
                        commit_change(observed, change_time)
                        candidate_text = None
                        candidate_count = 0

                pbar.update(1)

            pbar.close()
            video_end = (total_frames / fps) if total_frames > 0 else 0.0

        cap.release()

        # close last open segment
        if not SRTUtils.is_none_text(stable_text) and open_start is not None:
            segments.append(Segment(start=open_start, end=max(video_end, open_start + min_duration), text=stable_text))

        segments = SRTUtils.merge_adjacent(segments, max_gap=0.30)

        # ensure monotonic & minimal durations
        cleaned: List[Segment] = []
        for seg in segments:
            if seg.end <= seg.start:
                seg.end = seg.start + min_duration
            if (seg.end - seg.start) < min_duration:
                seg.end = seg.start + min_duration
            cleaned.append(seg)

        SRTUtils.write_srt(out_srt, cleaned)


class SubtitleExtractor:
    """主字幕提取器 - 组合软字幕和硬字幕提取"""

    def __init__(
        self,
        ollama_model: str = "qwen3-vl:8b",
        ollama_host: str = "http://localhost:11434"
    ):
        """
        初始化字幕提取器

        Args:
            ollama_model: Ollama模型名称
            ollama_host: Ollama服务地址
        """
        self.hard_extractor = HardSubExtractor(model=ollama_model, host=ollama_host)

    def extract(
        self,
        video_path: str,
        out_srt: Optional[str] = None,
        force_ocr: bool = False,
        subtitle_stream: Optional[int] = None,
        interval_ms: int = 500,
        stability: int = 2,
        diff_thresh: float = 2.5,
        roi_str: Optional[str] = None,
        min_duration: float = 0.40,
    ) -> str:
        """
        提取字幕并保存为SRT文件

        Args:
            video_path: 输入视频路径
            out_srt: 输出SRT文件路径（默认为video_path去扩展名+.srt）
            force_ocr: 是否强制使用OCR，跳过软字幕提取
            subtitle_stream: 偏好的字幕流索引
            interval_ms: OCR采样间隔（毫秒）
            stability: 稳定性参数
            diff_thresh: ROI变化检测阈值
            roi_str: ROI区域字符串
            min_duration: 最小字幕段长度（秒）

        Returns:
            生成的SRT文件路径
        """
        if out_srt is None:
            out_srt = os.path.splitext(video_path)[0] + ".srt"

        # First try soft subtitle extraction
        if not force_ocr:
            ok = SoftSubExtractor.extract(video_path, out_srt, preferred_stream=subtitle_stream)
            if ok:
                print(f"[OK] Extracted soft subtitle track to: {out_srt}")
                return out_srt
            else:
                print("[INFO] No extractable text subtitle track found. Falling back to OCR...")

        # OCR fallback
        self.hard_extractor.extract(
            video_path=video_path,
            out_srt=out_srt,
            interval_ms=interval_ms,
            stability=max(1, stability),
            diff_thresh=diff_thresh,
            roi_str=roi_str,
            min_duration=max(0.05, min_duration),
        )
        print(f"[OK] OCR-generated SRT saved to: {out_srt}")
        return out_srt


# ---------------------------
# CLI
# ---------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Generate SRT by extracting embedded subtitles: softsub via ffmpeg, or hardsub via Qwen3-VL on Ollama."
    )
    ap.add_argument("video", help="Input video path")
    ap.add_argument("-o", "--out", default=None, help="Output .srt path (default: <video>.srt)")
    ap.add_argument("--model", default="qwen3-vl:8b", help="Ollama model name (default: qwen3-vl:8b)")
    ap.add_argument("--host", default=os.getenv("OLLAMA_HOST", "http://localhost:11434"), help="Ollama host URL")
    ap.add_argument("--force-ocr", action="store_true", help="Skip ffmpeg subtitle-track extraction; always use OCR")
    ap.add_argument("--subtitle-stream", type=int, default=None,
                    help="Preferred subtitle stream absolute index (ffprobe stream.index). Only for softsub extraction.")
    ap.add_argument("--interval-ms", type=int, default=500, help="OCR sampling interval in ms (default: 500)")
    ap.add_argument("--stability", type=int, default=2, help="Require N consecutive same readings before switching (default: 2)")
    ap.add_argument("--diff-thresh", type=float, default=2.5,
                    help="Mean abs diff threshold for ROI change; below this will skip inference (default: 2.5)")
    ap.add_argument("--roi", type=str, default=None,
                    help="ROI crop in pixels: x,y,w,h. Default: bottom 30%% of frame. Example: 0,720,1920,360")
    ap.add_argument("--min-duration", type=float, default=0.40,
                    help="Minimum subtitle segment duration seconds (default: 0.40)")
    args = ap.parse_args()

    video_path = args.video
    out_srt = args.out or (os.path.splitext(video_path)[0] + ".srt")

    # 使用新的面向对象API
    extractor = SubtitleExtractor(
        ollama_model=args.model,
        ollama_host=args.host
    )
    extractor.extract(
        video_path=video_path,
        out_srt=out_srt,
        force_ocr=args.force_ocr,
        subtitle_stream=args.subtitle_stream,
        interval_ms=args.interval_ms,
        stability=max(1, args.stability),
        diff_thresh=args.diff_thresh,
        roi_str=args.roi,
        min_duration=max(0.05, args.min_duration),
    )


if __name__ == "__main__":
    main()
