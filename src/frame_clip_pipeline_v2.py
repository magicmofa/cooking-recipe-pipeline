import base64
import os
import re
import math
from io import BytesIO
from pathlib import Path
from typing import List, Dict, Any

import requests
from moviepy import VideoFileClip
from PIL import Image

# --------- Config ---------
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3-vl:32b"
DEFAULT_CONTEXT_WINDOW = 5  # 秒：截取时间戳前后各5秒
DEFAULT_MIN_FRAMES = 5      # 每段最少帧数
DEFAULT_MAX_FRAMES = 20     # 每段最多帧数
DEFAULT_SECONDS_PER_FRAME = 1.5  # 按片段时长自适应抽帧间隔（秒）
DEFAULT_IMAGE_MAX_SIDE = 1280    # 图像最长边等比缩放到该尺寸以内，None 表示不缩放
DEFAULT_IMAGE_QUALITY = 90       # JPEG 质量（1-100，数值越大质量越高体积越大）
DEFAULT_IMAGE_FORMAT = "JPEG"    # 发送给模型的图片格式（JPEG 推荐，若需无损可改 PNG）
DEFAULT_CLIP_MARGIN = 2.0        # 剪辑时前后各扩展的秒数，用以包含完整上下文

VISION_PROMPT_TEMPLATE = (
    "你是烹饪视频视觉助手。下面给你一段视频片段的多张截图（均来自同一片段，截图对应的相对时间已标注）。\n\n"
    "【问题】\n{question}\n\n"
    "【截图时间标注】\n{frame_timestamps}\n\n"
    "【任务】\n"
    "1. 根据截图内容回答上述问题。\n"
    "2. 请返回时间段相对于本片段起点的时间（片段起点为 0s），格式 MM:SS 或 HH:MM:SS。\n"
    "3. 同时给出关键画面的时间段（相对片段起点）。\n\n"
    "【回答格式】\n"
    "ANSWER: [你的详细回答，包含关键时间说明]\n"
    "KEY_FRAMES: [关键时间段，格式 MM:SS-MM:SS，相对片段起点]\n"
)

# --------- Parsing markdown ---------

def load_frame_tasks_from_markdown(md_path: Path) -> List[Dict[str, Any]]:
    """Parse FRAME_EXTRACTION_TABLE from refined markdown."""
    text = md_path.read_text(encoding="utf-8")
    if "FRAME_EXTRACTION_TABLE" not in text:
        raise ValueError("未找到 FRAME_EXTRACTION_TABLE 标记")
    
    lines = text.splitlines()
    table_started = False
    rows = []
    for line in lines:
        if "FRAME_EXTRACTION_TABLE" in line:
            table_started = True
            continue
        if table_started:
            if line.strip().startswith("TABLE_END"):
                break
            if line.strip().startswith("|"):
                rows.append(line.strip())
    
    data_rows = [r for r in rows if not re.match(r"\|[- ]+\|", r)]
    tasks = []
    for row in data_rows:
        cols = [c.strip() for c in row.strip("|").split("|")]
        if len(cols) < 5:
            continue
        try:
            index = int(cols[0])
        except ValueError:
            continue
        ts = cols[1]
        use = cols[2]
        missing = cols[3]
        priority = cols[4]
        tasks.append({
            "index": index,
            "timestamp": ts,
            "use": use,
            "missing": missing,
            "priority": priority
        })
    return tasks

# --------- Time helpers ---------

def ts_to_seconds(ts: str) -> float:
    """支持 MM:SS 或 HH:MM:SS 格式"""
    parts = ts.split(":")
    if len(parts) == 2:
        m, s = [float(p) for p in parts]
        return m * 60 + s
    elif len(parts) == 3:
        h, m, s = [float(p) for p in parts]
        return h * 3600 + m * 60 + s
    else:
        raise ValueError(f"时间戳格式错误: {ts}")


def seconds_to_ts(sec: float) -> str:
    sec = max(sec, 0.0)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:05.2f}"
    else:
        return f"{m:02d}:{s:05.2f}"

# --------- Video & frame operations ---------

def calc_num_frames(duration: float, seconds_per_frame: float, min_frames: int, max_frames: int) -> int:
    """根据片段时长自适应计算帧数"""
    if duration <= 0:
        return min_frames
    n = math.ceil(duration / seconds_per_frame)
    return max(min_frames, min(max_frames, n))


def extract_frames_from_clip(video_path: Path, start: float, end: float, output_dir: Path, num_frames: int) -> List[tuple]:
    """从视频片段中等间距抽取多帧，返回 [(frame_path, timestamp_abs), ...]"""
    video = VideoFileClip(str(video_path))
    duration = end - start
    output_dir.mkdir(parents=True, exist_ok=True)
    
    frame_list = []
    if num_frames <= 1:
        num_frames = 1
    for i in range(num_frames):
        # 等间距抽帧（绝对时间戳）
        t_abs = start + (i / (num_frames - 1)) * duration if num_frames > 1 else start + duration / 2
        frame_path = output_dir / f"frame_{i:02d}.png"
        video.save_frame(str(frame_path), t=t_abs)
        frame_list.append((frame_path, t_abs))
    
    video.close()
    return frame_list


def cut_clip(video_path: Path, start: float, end: float, out_path: Path) -> None:
    """剪出视频片段"""
    video = VideoFileClip(str(video_path))
    clip = video.subclipped(start, end)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"正在生成剪辑: {out_path.name}")
    clip.write_videofile(str(out_path), codec="libx264", audio_codec="aac")
    clip.close()
    video.close()

# --------- Vision API ---------

def encode_image_to_base64(
    img_path: Path,
    max_side: int | None = DEFAULT_IMAGE_MAX_SIDE,
    quality: int = DEFAULT_IMAGE_QUALITY,
    fmt: str = DEFAULT_IMAGE_FORMAT,
) -> str:
    """加载图片，按需等比缩放并以指定格式编码 base64"""
    with Image.open(img_path) as im:
        if max_side and (im.width > max_side or im.height > max_side):
            scale = max(im.width, im.height) / max_side
            new_w = int(im.width / scale)
            new_h = int(im.height / scale)
            im = im.resize((new_w, new_h), Image.LANCZOS)

        buf = BytesIO()
        save_kwargs = {}
        if fmt.upper() == "JPEG":
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
        im.save(buf, format=fmt, **save_kwargs)
        data = buf.getvalue()
    return base64.b64encode(data).decode("utf-8")


def ask_qwen_vision_multiframe(
    prompt: str,
    frame_paths: List[Path],
    base_url: str,
    model: str,
    max_side: int | None = DEFAULT_IMAGE_MAX_SIDE,
    quality: int = DEFAULT_IMAGE_QUALITY,
    fmt: str = DEFAULT_IMAGE_FORMAT,
) -> str:
    """一次性传入多张图片，获取答案"""
    images_b64 = [encode_image_to_base64(p, max_side=max_side, quality=quality, fmt=fmt) for p in frame_paths]
    
    url = f"{base_url}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "images": images_b64,
        "stream": False,
        "keep_alive": "1m"  # 推理完1分钟后自动卸载模型释放显存（可改 0 立即释放）
    }
    
    print(f"调用 {model}，传入 {len(frame_paths)} 张图片...")
    resp = requests.post(url, json=payload, timeout=600)
    resp.raise_for_status()
    return resp.json().get("response", "")

# --------- Main pipeline ---------

def run_pipeline_v2(
    video_path: str,
    refined_md_path: str,
    output_dir: str = "vision_pipeline_v2",
    ollama_url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_MODEL,
    context_window: float = DEFAULT_CONTEXT_WINDOW,
    seconds_per_frame: float = DEFAULT_SECONDS_PER_FRAME,
    min_frames: int = DEFAULT_MIN_FRAMES,
    max_frames: int = DEFAULT_MAX_FRAMES,
    clip_margin: float = DEFAULT_CLIP_MARGIN,
    image_max_side: int | None = DEFAULT_IMAGE_MAX_SIDE,
    image_quality: int = DEFAULT_IMAGE_QUALITY,
    image_format: str = DEFAULT_IMAGE_FORMAT,
    prompt_template: str = VISION_PROMPT_TEMPLATE,
    video_name: str | None = None
) -> Path:
    video_path = Path(video_path)
    refined_md_path = Path(refined_md_path)
    out_dir = Path(output_dir)
    frames_dir = out_dir / "frames"
    clips_dir = out_dir / "clips"
    
    # 使用视频名称作为 markdown 文件名，若未提供则使用默认名称
    if video_name:
        result_md = out_dir / f"{video_name}_visual.md"
    else:
        result_md = out_dir / "visual.md"

    # 检查结果文件是否已存在
    if result_md.exists():
        print(f" 结果文件已存在，跳过处理: {result_md}")
        return result_md
    
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    clips_dir.mkdir(parents=True, exist_ok=True)

    # 加载任务表
    tasks = load_frame_tasks_from_markdown(refined_md_path)
    qa_blocks = []

    video = VideoFileClip(str(video_path))
    video_duration = video.duration
    video.close()

    for task in tasks:
        print(f"\n{'='*60}")
        print(f"处理任务 {task['index']}: {task['missing'][:50]}...")
        print(f"{'='*60}")
        
        # 1. 解析时间戳，确定片段范围
        center_ts = ts_to_seconds(task["timestamp"])
        start_ts = max(center_ts - context_window, 0)
        end_ts = min(center_ts + context_window, video_duration)
        
        print(f"时间戳: {task['timestamp']} → 秒数: {center_ts:.1f}s")
        print(f"片段范围: {seconds_to_ts(start_ts)} - {seconds_to_ts(end_ts)}")
        
        # 2. 计算帧数并抽取多帧
        task_frames_dir = frames_dir / f"task_{task['index']:02d}"
        num_frames = calc_num_frames(end_ts - start_ts, seconds_per_frame, min_frames, max_frames)
        frame_list = extract_frames_from_clip(video_path, start_ts, end_ts, task_frames_dir, num_frames)
        
        # 3. 组装提示词（拼接缺漏细节 + 问题）
        rel_ts_lines = []
        for i, (_, t_abs) in enumerate(frame_list):
            t_rel = t_abs - start_ts
            rel_ts_lines.append(f"帧{i+1}: t={seconds_to_ts(t_rel)} (片段内相对时间)")
        frame_ts_text = "\n".join(rel_ts_lines)

        question = (
            f"缺漏细节：{task['missing']}\n"
            f"截图用途：{task['use']}\n"
            f"片段范围：{seconds_to_ts(start_ts)} - {seconds_to_ts(end_ts)} (相对原视频)\n"
            f"请基于这段视频回答上述问题，时间戳请使用片段内相对时间（0s 为片段开始）。"
        )
        full_prompt = prompt_template.format(question=question, frame_timestamps=frame_ts_text)
        
        # 4. 调用视觉模型（传入所有帧）
        frame_paths = [p for p, _ in frame_list]
        answer = ask_qwen_vision_multiframe(
            full_prompt,
            frame_paths,
            ollama_url,
            model,
            max_side=image_max_side,
            quality=image_quality,
            fmt=image_format,
        )
        
        print(f"模型回答:\n{answer[:300]}...\n")
        
        # 5. 解析答案中的时间戳（先尝试按相对片段时间解析，如超出片段长度则视为原视频绝对时间）
        key_frames_match = re.search(r"KEY_FRAMES:\s*([0-9:.\-]+)", answer)
        if key_frames_match:
            key_span = key_frames_match.group(1).strip()
            try:
                if "-" in key_span:
                    start_str, end_str = key_span.split("-")
                    rel_start = ts_to_seconds(start_str)
                    rel_end = ts_to_seconds(end_str)
                else:
                    rel_start = ts_to_seconds(key_span)
                    rel_end = rel_start + 5

                clip_duration = end_ts - start_ts
                # 如果解析出的时间在片段长度内，认为是片段内相对时间；否则认为是全局绝对时间
                if rel_end <= clip_duration + 1.0:
                    clip_start = start_ts + rel_start
                    clip_end = start_ts + rel_end
                    key_span_display = f"{seconds_to_ts(rel_start)}-{seconds_to_ts(rel_end)} (片段内相对时间)"
                else:
                    clip_start = rel_start
                    clip_end = rel_end
                    key_span_display = f"{seconds_to_ts(clip_start)}-{seconds_to_ts(clip_end)} (原视频绝对时间)"
            except Exception as e:
                print(f"时间戳解析失败: {e}，使用默认范围")
                clip_start = start_ts
                clip_end = end_ts
                key_span_display = f"{seconds_to_ts(clip_start-start_ts)}-{seconds_to_ts(clip_end-start_ts)} (片段内)"
        else:
            # 若模型未给出，使用整个片段
            clip_start = start_ts
            clip_end = end_ts
            key_span_display = f"{seconds_to_ts(0)}-{seconds_to_ts(clip_end-start_ts)} (片段内默认)"
        
        # 5.5. 应用 margin 扩展（前后各扩展 clip_margin 秒）
        clip_start = max(clip_start - clip_margin, 0)
        clip_end = min(clip_end + clip_margin, video_duration)
        
        # 6. 剪辑视频
        clip_path = clips_dir / f"clip_{task['index']:02d}.mp4"
        cut_clip(video_path, clip_start, clip_end, clip_path)
        
        qa_blocks.append({
            "index": task["index"],
            "missing": task["missing"],
            "use": task["use"],
            "priority": task["priority"],
            "question": question,
            "answer": answer,
            "time_span": key_span_display,
            "clip_path": clip_path
        })

    # 7. 生成最终 markdown
    lines = ["# 视觉问答与时间戳标注\n"]
    for qa in qa_blocks:
        lines.append(f"## 问题 {qa['index']} - {qa['priority']}")
        lines.append(f"**缺漏细节**: {qa['missing']}")
        lines.append(f"**截图用途**: {qa['use']}\n")
        lines.append(f"### 模型回答")
        lines.append(qa['answer'])
        lines.append(f"\n**建议时间段**: {qa['time_span']}")
        lines.append(f"**剪辑文件**: [{qa['clip_path'].name}]({qa['clip_path'].as_posix()})\n")
        lines.append("---\n")
    
    result_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ 完成！结果已保存到: {result_md}")
    return result_md


if __name__ == "__main__":
    # 单一输入目录，程序自动遍历并处理所有符合的 markdown 文件
    input_dir = r"c:\Users\magic\Desktop\烹饪"
    
    input_path = Path(input_dir)
    
    # 查找所有 _analysis.md 文件
    refined_files = sorted(input_path.rglob("*_analysis.md"))
    
    if not refined_files:
        print(f"未在 {input_dir} 中找到任何 _recipe [✓]_refined.md 文件")
        exit(1)
    
    print(f"找到 {len(refined_files)} 个任务文件\n")
    
    for refined_md_path in refined_files:
        print(f"{'#'*70}")
        print(f"处理: {refined_md_path.name}")
        print(f"{'#'*70}")
        
        # 从 markdown 文件名推断视频名称
        # 例如: 【我保证！...】_analysis.md -> 【我保证！...】
        md_name = refined_md_path.stem  # 去掉 .md
        video_name = md_name.replace("_analysis", "")  # 得到视频名称
        
        # 在目录树中查找对应的 mp4 文件
        video_candidates = sorted(input_path.rglob(f"{video_name}.mp4"))
        
        if not video_candidates:
            print(f"⚠️  未找到 {video_name}.mp4，跳过此任务")
            continue
        
        video_path = video_candidates[0]
        print(f"✓ 视频: {video_path.name}")
        print(f"✓ Markdown: {refined_md_path.name}")
        
        # 创建输出目录：在 markdown 所在目录下创建与视频同名的文件夹
        output_dir = refined_md_path.parent / video_name
        print(f"✓ 输出目录: {output_dir}")
        
        # 运行 pipeline
        run_pipeline_v2(
            video_path=str(video_path),
            refined_md_path=str(refined_md_path),
            output_dir=str(output_dir),
            ollama_url=DEFAULT_OLLAMA_URL,
            model=DEFAULT_MODEL,
            context_window=DEFAULT_CONTEXT_WINDOW,
            seconds_per_frame=DEFAULT_SECONDS_PER_FRAME,
            min_frames=DEFAULT_MIN_FRAMES,
            max_frames=DEFAULT_MAX_FRAMES,
            clip_margin=DEFAULT_CLIP_MARGIN,
            image_max_side=DEFAULT_IMAGE_MAX_SIDE,
            image_quality=DEFAULT_IMAGE_QUALITY,
            image_format=DEFAULT_IMAGE_FORMAT,
            video_name=video_name,
        )
    
    print(f"\n✅ 全部任务完成！")
