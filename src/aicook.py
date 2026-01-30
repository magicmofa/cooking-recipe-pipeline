import cv2
import ollama
import math

# --- 配置区 ---
VIDEO_PATH = r"云南老昆明人正宗的（米浆粑粑），云南人儿时的记忆，香甜松软.mp4"
MODEL_NAME = "qwen3-vl:8b"
CHUNK_DURATION = 40  
FRAMES_PER_CHUNK = 6 

def main():
    # ================= 第一阶段：视频分析 (和之前一样) =================
    cap = cv2.VideoCapture(VIDEO_PATH)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    
    print(f"1. 正在扫描视频提取数据 (时长: {duration/60:.2f} 分钟)...")
    
    current_data_sheet = "【提取到的原始数据】：(空)"
    num_chunks = math.ceil(duration / CHUNK_DURATION)
    
    for i in range(num_chunks):
        print(f"   -> 正在分析第 {i+1}/{num_chunks} 片段...")
        
        # 抽帧逻辑
        images_batch = []
        start_frame = int(i * CHUNK_DURATION * fps)
        end_frame = int(min((i + 1) * CHUNK_DURATION * fps, total_frames))
        step = (end_frame - start_frame) // FRAMES_PER_CHUNK
        
        for j in range(FRAMES_PER_CHUNK):
            current_pos = start_frame + j * step
            if current_pos >= total_frames: break
            cap.set(cv2.CAP_PROP_POS_FRAMES, current_pos)
            success, frame = cap.read()
            if success:
                _, buffer = cv2.imencode('.jpg', frame)
                images_batch.append(buffer.tobytes())
        
        if not images_batch: continue

        # 提取数据的 Prompt
        prompt = f"""
        任务：建立精准烹饪配料表。
        【已知数据】：{current_data_sheet}
        【当前任务】：观察截图，寻找“食材”、“调料”、“用量”、“比例”。
        规则：
        1. 忽略动作，只抓取数据（字幕数字、量具单位）。
        2. 发现新数据则更新，未发现则保持。
        请输出更新后的配料数据表。
        """

        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{'role': 'user', 'content': prompt, 'images': images_batch}]
        )
        current_data_sheet = response['message']['content']

    cap.release()
    print("\n" + "="*40)
    print("视频分析完成！已获取配料数据。")
    print("="*40)

    # ================= 第二阶段：交互式追问 (新增功能) =================
    
    # 1. 先定义“系统记忆”，让它记住刚才扒下来的数据
    chat_history = [
        {
            'role': 'system', 
            'content': f"""
            你现在是一个基于视频数据的【配方问答助手】。
            以下是你刚才从视频中提取到的【完整配料数据】：
            
            {current_data_sheet}
            
            请基于以上数据回答用户的问题。
            如果用户问的问题在数据里找不到（比如视频没说煮多久），请如实回答“视频中未提及”。
            """
        }
    ]

    print("\n>>> 现在你可以对结果进行追问了 (输入 'exit' 退出) <<<")
    
    while True:
        # 获取你的输入
        user_input = input("\n你: ")
        
        if user_input.lower() in ['exit', 'quit', '退出']:
            print("再见！")
            break
            
        # 把你的问题加入历史记录
        chat_history.append({'role': 'user', 'content': user_input})
        
        print("AI 正在思考...")
        
        # 发送给 Ollama (不带图片了，只带文字记忆，速度极快)
        response = ollama.chat(model=MODEL_NAME, messages=chat_history)
        
        ai_reply = response['message']['content']
        print(f"AI: {ai_reply}")
        
        # 把 AI 的回答也加入历史，这样它能记住上下文
        chat_history.append({'role': 'assistant', 'content': ai_reply})

if __name__ == "__main__":
    main()