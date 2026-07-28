import subprocess
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
from tabulate import tabulate
import time
import os
import datetime
import sys
import shutil
from pathlib import Path

# Progress bar imports
try:
    from tqdm import tqdm

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

try:
    from rich.progress import (
        Progress,
        BarColumn,
        TextColumn,
        TimeRemainingColumn,
        TimeElapsedColumn,
    )
    from rich.console import Console

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def run_script(task):
    """
    调用auto_solve.py 脚本运行单个任务，创建golden文件
    """
    cmd = [
        sys.executable,
        "solve/auto_solve.py",
        "-p",
        task["path"],
        "-i",
        str(task["id"]),
        "-o",
        task["output_dir"],
        "-m",
        task["mode"],
        "-M",
        task["model"],
        "--with_answer",  # 添加with_answer参数来创建golden文件
    ]

    cmd_str = " ".join(cmd)
    print(cmd_str)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    task_name = "_".join(task["path"].split("/")[3:]).replace("data.json", "")
    log_filename = f"logs/{task_name}_{task['id']}_golden_{timestamp}.log"
    os.makedirs("logs", exist_ok=True)
    try:
        # 将 stdout 和 stderr 重定向到 日志文件
        print(f"Golden creation started: {cmd_str}")
        start_time = time.time()
        with open(log_filename, "w", encoding="utf-8") as log_file:
            subprocess.run(cmd, check=True, stdout=log_file, stderr=log_file)
        end_time = time.time()
        print(
            f"Golden creation finished: {cmd_str} (Duration: {end_time - start_time:.2f}s)"
        )
        return f"Golden creation succeeded: {cmd_str}"  # ✅ 修复拼写错误
    except subprocess.CalledProcessError as e:
        error_message = f"Golden creation failed: {cmd_str}"
        print(error_message)
        return error_message


def main(tasks_file, mode, model, start=0, end=10, linear=True, workers=4):
    # 加载任务配置
    with open(tasks_file, "r", encoding="utf-8") as t:
        tasks = json.load(t)
    tasks = tasks[start:end]

    # 为golden文件创建专门的输出目录结构
    golden_tasks = []
    for task in tasks:
        golden_task = task.copy()
        # 添加mode和model信息
        golden_task["mode"] = mode
        golden_task["model"] = model
        # 修改输出目录为golden文件专用目录
        # 构建golden文件路径: golden/{dataset}/{mode}_{model}/{id}/
        task_name_parts = task["path"].split("/")
        task_name_parts = task_name_parts[:-1]  # 去掉最后的data.json
        dataset = (
            "/".join(task_name_parts[3:5])
            if len(task_name_parts) > 4
            else task_name_parts[3]
        )

        golden_task["golden_output_dir"] = (
            f"golden/{dataset}/{mode}_{model}/{task['id']}/"
        )
        golden_tasks.append(golden_task)

    # 使用线程池运行任务
    results = []
    table_data = []
    start_time = time.time()

    # 显示进度可视化状态
    progress_status = []
    if RICH_AVAILABLE:
        progress_status.append("Rich ✓")
    if TQDM_AVAILABLE:
        progress_status.append("tqdm ✓")
    if not RICH_AVAILABLE and not TQDM_AVAILABLE:
        progress_status.append("Text mode")

    print(
        f"Starting golden file creation from index {start} to {end}, linear={linear}, workers={workers}"
    )
    print(f"Progress visualization: {' | '.join(progress_status)}")

    if linear:
        # Progress bar for linear execution
        if RICH_AVAILABLE:
            console = Console()
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task_progress = progress.add_task(
                    f"[gold]Golden file creation", total=len(golden_tasks)
                )

                for task in golden_tasks:
                    # 修改任务的输出目录为golden目录
                    task_copy = task.copy()
                    task_copy["output_dir"] = task["golden_output_dir"]
                    result = run_script(task_copy)
                    results.append(result)
                    table_data.append(
                        [
                            task["path"],
                            task["id"],
                            task["model"],
                            task["mode"],
                            (
                                "success" if "succeeded" in result else "failed"
                            ),  # ✅ 修复拼写错误
                        ]
                    )
                    progress.update(
                        task_progress,
                        advance=1,
                        description=f"[gold]Golden file creation",
                    )
        elif TQDM_AVAILABLE:
            pbar = tqdm(golden_tasks, desc="Golden file creation", unit="file")
            for task in pbar:
                # 修改任务的输出目录为golden目录
                task_copy = task.copy()
                task_copy["output_dir"] = task["golden_output_dir"]
                result = run_script(task_copy)
                results.append(result)
                table_data.append(
                    [
                        task["path"],
                        task["id"],
                        task["model"],
                        task["mode"],
                        (
                            "success" if "succeeded" in result else "failed"
                        ),  # ✅ 修复拼写错误
                    ]
                )
                pbar.set_postfix(status="✓" if "succeeded" in result else "✗")
            pbar.close()
        else:
            # Fallback: simple text progress
            for i, task in enumerate(golden_tasks):
                # 修改任务的输出目录为golden目录
                task_copy = task.copy()
                task_copy["output_dir"] = task["golden_output_dir"]
                result = run_script(task_copy)
                results.append(result)
                table_data.append(
                    [
                        task["path"],
                        task["id"],
                        task["model"],
                        task["mode"],
                        (
                            "success" if "succeeded" in result else "failed"
                        ),  # ✅ 修复拼写错误
                    ]
                )
                print(
                    f"Progress: {i+1}/{len(golden_tasks)} ({((i+1)/len(golden_tasks)*100):.1f}%) - {'✓' if 'succeeded' in result else '✗'}"
                )
    else:
        # Progress bar for parallel execution
        if RICH_AVAILABLE:
            console = Console()
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("[gold]Completed: {task.completed}/{task.total}"),
                console=console,
            ) as progress:
                task_progress = progress.add_task(
                    f"[gold]Golden file creation (parallel)", total=len(golden_tasks)
                )

                with ThreadPoolExecutor(max_workers=workers) as executor:
                    future_to_task = {}
                    for task in golden_tasks:
                        # 修改任务的输出目录为golden目录
                        task_copy = task.copy()
                        task_copy["output_dir"] = task["golden_output_dir"]
                        future = executor.submit(run_script, task_copy)
                        future_to_task[future] = task

                    for future in as_completed(future_to_task):
                        task = future_to_task[future]
                        try:
                            result = future.result()
                            results.append(result)
                            table_data.append(
                                [
                                    task["path"],
                                    task["id"],
                                    task["model"],
                                    task["mode"],
                                    (
                                        "success" if "succeeded" in result else "failed"
                                    ),  # ✅ 修复拼写错误
                                ]
                            )
                        except Exception as e:
                            print(f"Unexpected error: {e}")
                            results.append(
                                f"Golden creation failed: {task['path']} id={task['id']} ({e})"
                            )
                            table_data.append(
                                [
                                    task["path"],
                                    task["id"],
                                    task["model"],
                                    task["mode"],
                                    "failed",
                                ]
                            )
                        progress.update(task_progress, advance=1)
        elif TQDM_AVAILABLE:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_task = {}
                for task in golden_tasks:
                    # 修改任务的输出目录为golden目录
                    task_copy = task.copy()
                    task_copy["output_dir"] = task["golden_output_dir"]
                    future = executor.submit(run_script, task_copy)
                    future_to_task[future] = task

                with tqdm(
                    total=len(golden_tasks),
                    desc="Golden file creation (parallel)",
                    unit="file",
                ) as pbar:
                    for future in as_completed(future_to_task):
                        task = future_to_task[future]
                        try:
                            result = future.result()
                            results.append(result)
                            table_data.append(
                                [
                                    task["path"],
                                    task["id"],
                                    task["model"],
                                    task["mode"],
                                    (
                                        "success" if "succeeded" in result else "failed"
                                    ),  # ✅ 修复拼写错误
                                ]
                            )
                            pbar.set_postfix(
                                status="✓" if "succeeded" in result else "✗"
                            )
                        except Exception as e:
                            print(f"Unexpected error: {e}")
                            results.append(
                                f"Golden creation failed: {task['path']} id={task['id']} ({e})"
                            )
                            table_data.append(
                                [
                                    task["path"],
                                    task["id"],
                                    task["model"],
                                    task["mode"],
                                    "failed",
                                ]
                            )
                        pbar.update(1)
        else:
            # Fallback: simple text progress for parallel execution
            completed_count = 0
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_task = {}
                for task in golden_tasks:
                    # 修改任务的输出目录为golden目录
                    task_copy = task.copy()
                    task_copy["output_dir"] = task["golden_output_dir"]
                    future = executor.submit(run_script, task_copy)
                    future_to_task[future] = task

                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        result = future.result()
                        results.append(result)
                        table_data.append(
                            [
                                task["path"],
                                task["id"],
                                task["model"],
                                task["mode"],
                                (
                                    "success" if "succeeded" in result else "failed"
                                ),  # ✅ 修复拼写错误
                            ]
                        )
                        completed_count += 1
                        print(
                            f"Progress: {completed_count}/{len(golden_tasks)} ({(completed_count/len(golden_tasks)*100):.1f}%) - {'✓' if 'succeeded' in result else '✗'}"
                        )
                    except Exception as e:
                        print(f"Unexpected error: {e}")
                        results.append(
                            f"Golden creation failed: {task['path']} id={task['id']} ({e})"
                        )
                        table_data.append(
                            [
                                task["path"],
                                task["id"],
                                task["model"],
                                task["mode"],
                                "failed",
                            ]
                        )
                        completed_count += 1
                        print(
                            f"Progress: {completed_count}/{len(golden_tasks)} ({(completed_count/len(golden_tasks)*100):.1f}%) - error"
                        )

    end_time = time.time()

    # ✅ 添加最终完成确认
    success_count = sum(1 for row in table_data if row[-1] == "success")
    failed_count = sum(1 for row in table_data if row[-1] == "failed")
    total_count = len(table_data)

    print(f"\n=== FINAL SUMMARY ===")
    print(f"Total golden files created: {total_count}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failed_count}")
    print(f"Completion rate: {success_count/total_count*100:.1f}%")

    if success_count + failed_count == total_count:
        print("✅ All golden files have been processed!")
    else:
        print(
            f"❌ Missing {total_count - (success_count + failed_count)} golden files!"
        )

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_log = f"logs/golden_summary_{timestamp}.log"
    consume_time_str = (
        f"All golden files created in {end_time - start_time:.2f} seconds."
    )
    table_str = tabulate(
        table_data,
        headers=["Path", "ID", "Model", "Mode", "Status"],
        tablefmt="simple_grid",
    )

    # ✅ 记录详细的进度日志
    progress_log = f"logs/golden_progress_{timestamp}.log"
    os.makedirs("logs", exist_ok=True)
    with open(progress_log, "w", encoding="utf-8") as progress_file:
        progress_file.write("Detailed golden file creation progress:\n")
        for i, row in enumerate(table_data):
            progress_file.write(f"{i+1}/{total_count}: {row}\n")
        progress_file.write(f"\n{consume_time_str}\n")
        progress_file.write(
            f"Success: {success_count}, Failed: {failed_count}, Total: {total_count}\n"
        )

    with open(summary_log, "w", encoding="utf-8") as f:
        for res in results:
            f.write(res + "\n")
        f.write(f"\n{consume_time_str}\n")
        f.write(table_str)

    print(f"Golden summary log written to {summary_log}")
    print(f"Golden progress log written to {progress_log}")
    print(consume_time_str)


if __name__ == "__main__":
    """
    examples:
    python3 create_golden.py --tasks tasks/math_tasks.json --mode code --model gemini-2.5-pro --workers 5 --start 0 --end 10
    python3 create_golden.py --tasks tasks/m3cot_tasks.json --mode banana --model gpt-4o
    """
    parser = argparse.ArgumentParser(description="Create golden files for tasks")
    parser.add_argument("--tasks", help="任务文件json的路径", required=True)
    parser.add_argument(
        "--mode",
        type=str,
        choices=["code", "banana"],
        help="解题模式, code | banana",
        required=True,
    )
    parser.add_argument(
        "--model",
        type=str,
        help="使用的大语言模型, gpt-4o | gemini-2.5-pro | ...",
        required=True,
    )
    parser.add_argument(
        "--linear", help="是否线性执行", action="store_true", required=False
    )
    parser.add_argument(
        "--workers", type=int, default=4, help="并行执行时的最大线程数", required=False
    )
    parser.add_argument(
        "--start", type=int, default=0, help="任务开始索引", required=False
    )
    parser.add_argument(
        "--end",
        type=int,
        default=10,
        help="任务结束索引，list slice的结束索引",
        required=False,
    )
    args = parser.parse_args()
    main(
        args.tasks,
        args.mode,
        args.model,
        args.start,
        args.end,
        args.linear,
        args.workers,
    )
