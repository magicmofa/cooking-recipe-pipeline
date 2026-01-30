# fine_grained_processor.py 补丁文件
# 在 process_pairs 方法中，处理每个 md 文件之前添加检查

在 process_pairs 方法的循环中，找到这段代码：

```python
for i, md_file in enumerate(marked_files, 1):
    srt_file = self.find_matching_srt(md_file)
    
    if srt_file is None:
        print(f"[{i}] ❌ 找不到对应的srt文件: {md_file.name}")
        continue
```

在这之后、读取文件内容之前，添加检查：

```python
    # 检查是否已经存在 refined 文件
    refined_file = md_file.parent / f"{md_file.stem}_refined.md"
    if refined_file.exists():
        print(f"[{i}] ⏭️  已存在 refined 文件，跳过: {md_file.name}")
        continue
    
    print(f"[{i}] 处理文件对:")
    print(f"    MD文件: {md_file.name}")
    print(f"    SRT文件: {srt_file.name}")
```

完整的修改后的循环应该是：

```python
for i, md_file in enumerate(marked_files, 1):
    srt_file = self.find_matching_srt(md_file)
    
    if srt_file is None:
        print(f"[{i}] ❌ 找不到对应的srt文件: {md_file.name}")
        continue
    
    # 检查是否已经存在 refined 文件
    refined_file = md_file.parent / f"{md_file.stem}_refined.md"
    if refined_file.exists():
        print(f"[{i}] ⏭️  已存在 refined 文件，跳过: {md_file.name}")
        continue
    
    print(f"[{i}] 处理文件对:")
    print(f"    MD文件: {md_file.name}")
    print(f"    SRT文件: {srt_file.name}")
    
    # 读取文件内容
    md_content = self.read_file_content(md_file)
    srt_content = self.read_file_content(srt_file)
    
    # ... 后续处理
```
