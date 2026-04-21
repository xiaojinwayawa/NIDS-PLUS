import os
import csv
import uuid
import time
import threading
from collections import defaultdict
from logging_config import app_logger as logger

# 存储平衡任务进度
_balance_tasks = {}

def get_balance_progress(task_id: str):
    return _balance_tasks.get(task_id)

def _run_balance_task(task_id: str, input_files: list, output_file: str, max_samples: int, min_samples: int, db_callback=None):
    try:
        _balance_tasks[task_id] = {
            "stage": "scanning",
            "percent": 0,
            "message": "正在执行第一趟扫描（摸底各类别总数）...",
            "elapsed": 0
        }
        start_time = time.time()
        
        # ==========================================
        # 第一趟：摸底扫描 (Pass 1 - Discovery)
        # 仅读取各类别总数，极低内存占用
        # ==========================================
        label_counts = defaultdict(int)
        total_rows = 0
        header = None
        label_col_idx = -1
        
        for file_path in input_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                file_header = next(reader, None)
                if not file_header:
                    continue
                
                if header is None:
                    header = file_header
                    # 自动寻找 Label 列
                    for i, col in enumerate(header):
                        if col.strip().lower() in ['label', 'class', 'attack_cat']:
                            label_col_idx = i
                            break
                    if label_col_idx == -1:
                        label_col_idx = len(header) - 1 # 默认最后一列
                
                for row in reader:
                    if not row or len(row) <= label_col_idx:
                        continue
                    label = row[label_col_idx].strip()
                    label_counts[label] += 1
                    total_rows += 1
        
        if total_rows == 0:
            raise ValueError("选中的文件中没有读取到任何有效数据行")
            
        logger.info(f"[Balancer] Pass 1 completed. Total rows: {total_rows}. Label counts: {dict(label_counts)}")
        
        # ==========================================
        # 制定各类别策略
        # ==========================================
        strategy = {}
        for label, count in label_counts.items():
            if count > max_samples:
                strategy[label] = 'truncate' # 大类截断
            elif count < min_samples:
                strategy[label] = 'multiply' # 小类复制
            else:
                strategy[label] = 'keep'     # 中类保留
                
        # ==========================================
        # 第二趟：流式精准重组与写入 (Pass 2 - Construction)
        # ==========================================
        _balance_tasks[task_id]["stage"] = "balancing"
        _balance_tasks[task_id]["message"] = "正在执行第二趟流式重组（保证时序与防爆内存）..."
        
        written_counts = defaultdict(int)
        rows_processed = 0
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8', newline='') as out_f:
            writer = csv.writer(out_f)
            writer.writerow(header)
            
            for file_path in input_files:
                with open(file_path, 'r', encoding='utf-8') as in_f:
                    reader = csv.reader(in_f)
                    next(reader, None) # 跳过表头
                    
                    # 维护当前正在读取的“稀有类别块”
                    current_minority_block = []
                    current_minority_label = None
                    
                    def flush_minority_block():
                        """将缓冲的稀有类别块原位循环写入"""
                        nonlocal current_minority_block, current_minority_label
                        if not current_minority_block or not current_minority_label:
                            return
                            
                        label = current_minority_label
                        total_original = label_counts[label]
                        target = min_samples
                        block_size = len(current_minority_block)
                        
                        # 按该块在原数据集中的比例，计算本次该写入的目标数量
                        # (block_size / total_original) * target
                        target_for_block = int(round((block_size / total_original) * target))
                        
                        remaining_quota = target - written_counts[label]
                        if remaining_quota <= 0:
                            current_minority_block = []
                            current_minority_label = None
                            return
                            
                        to_write = min(target_for_block, remaining_quota)
                        
                        # 循环写入 (In-place Loop Padding)
                        writes_done = 0
                        while writes_done < to_write:
                            for row in current_minority_block:
                                if writes_done >= to_write:
                                    break
                                writer.writerow(row)
                                written_counts[label] += 1
                                writes_done += 1
                                
                        # 清空缓冲区
                        current_minority_block.clear()
                        current_minority_label = None

                    for row in reader:
                        if not row or len(row) <= label_col_idx:
                            continue
                            
                        rows_processed += 1
                        if rows_processed % 20000 == 0:
                            _balance_tasks[task_id]["percent"] = int((rows_processed / total_rows) * 100)
                            _balance_tasks[task_id]["elapsed"] = time.time() - start_time
                            
                        label = row[label_col_idx].strip()
                        strat = strategy[label]
                        
                        # 如果标签发生了切换，且缓冲区有数据，立刻将上一个稀有块触发【原位循环写入】
                        if label != current_minority_label:
                            flush_minority_block()
                            
                        if strat == 'truncate':
                            if written_counts[label] < max_samples:
                                writer.writerow(row)
                                written_counts[label] += 1
                        elif strat == 'keep':
                            writer.writerow(row)
                            written_counts[label] += 1
                        elif strat == 'multiply':
                            # 将属于这个稀有类的行暂存到当前块中
                            current_minority_label = label
                            current_minority_block.append(row)
                            
                    # 单个文件结束时，也要清空一次缓冲区
                    flush_minority_block()
                    
        # 记录到数据库
        if db_callback:
            db_callback(output_file)
            
        _balance_tasks[task_id] = {
            "stage": "complete",
            "percent": 100,
            "message": "类别平衡完成！",
            "elapsed": time.time() - start_time,
            "output_file": output_file,
            "final_counts": dict(written_counts)
        }
        logger.info(f"[Balancer] Finished. Final counts: {dict(written_counts)}")
        
    except Exception as e:
        import traceback
        logger.error(f"[Balancer] Error: {traceback.format_exc()}")
        _balance_tasks[task_id] = {
            "stage": "error",
            "percent": 0,
            "message": str(e),
            "elapsed": time.time() - start_time
        }

def start_balance_task(input_files: list, output_name: str, max_samples: int, min_samples: int, db_callback=None) -> str:
    """启动一个异步的流式数据平衡任务"""
    task_id = str(uuid.uuid4())
    
    # 确保输出目录存在
    from config import settings
    # _project_root is three levels up from ml dir to get to C:\SpaceB\nids-system
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # Output to the datasets/balanced directory in the project root
    output_dir = os.path.join(project_root, "data", "datasets", "balanced")
    os.makedirs(output_dir, exist_ok=True)
    
    if not output_name.endswith('.csv'):
        output_name += '.csv'
        
    output_file = os.path.join(output_dir, output_name)
    
    thread = threading.Thread(
        target=_run_balance_task, 
        args=(task_id, input_files, output_file, max_samples, min_samples, db_callback),
        daemon=True
    )
    thread.start()
    
    return task_id
