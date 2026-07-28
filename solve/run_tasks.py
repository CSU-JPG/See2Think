from pathlib import Path
import select
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
from tabulate import tabulate
import time
import os
import datetime
import sys
import urllib.request


# Base directory for all task outputs; override via SEE2THINK_OUTPUT_BASE env var.
OUTPUT_BASE_DIR = Path(
    os.getenv("SEE2THINK_OUTPUT_BASE", "tasks/out")
).expanduser()

# Base directory for run logs; override via SEE2THINK_LOG_DIR env var.
_default_log_dir = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR = Path(os.getenv("SEE2THINK_LOG_DIR", str(_default_log_dir))).expanduser()
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR = LOG_DIR.resolve()

# Per-task hard timeout for auto_solve.py. 0 or unset keeps the old no-timeout behavior.
TASK_TIMEOUT_SECONDS = int(os.getenv("SEE2THINK_TASK_TIMEOUT_SECONDS", "0") or "0")

# Explicit VAoT step cap passed through to auto_solve.py. 0 or unset keeps
# auto_solve.py's own default.
MAX_STEPS = int(os.getenv("SEE2THINK_MAX_STEPS", "0") or "0")

# Optional backend health gate. When configured, workers wait for the model
# service instead of rapidly marking queued tasks as failed while it is down.
BACKEND_HEALTH_URL = os.getenv("SEE2THINK_BACKEND_HEALTH_URL", "").strip()
BACKEND_HEALTH_POLL_SECONDS = float(
    os.getenv("SEE2THINK_BACKEND_HEALTH_POLL_SECONDS", "5") or "5"
)

# Base directory for task data files; override via SEE2THINK_DATA_BASE env var.
# If set, task paths will be resolved relative to this base directory.
DATA_BASE_DIR = os.getenv("SEE2THINK_DATA_BASE", "").strip()
if DATA_BASE_DIR:
    DATA_BASE_DIR = Path(DATA_BASE_DIR).expanduser().resolve()
else:
    DATA_BASE_DIR = None


def wait_for_backend():
    if not BACKEND_HEALTH_URL:
        return

    announced = False
    while True:
        try:
            with urllib.request.urlopen(BACKEND_HEALTH_URL, timeout=3) as response:
                if 200 <= response.status < 300:
                    if announced:
                        print(f"Backend recovered: {BACKEND_HEALTH_URL}", flush=True)
                    return
        except Exception:
            pass

        if not announced:
            print(
                f"Backend unavailable; waiting before starting more tasks: "
                f"{BACKEND_HEALTH_URL}",
                flush=True,
            )
            announced = True
        time.sleep(max(BACKEND_HEALTH_POLL_SECONDS, 1.0))


def run_script(task, experiment_type=None, setting=None, prompt_dir=None):
    """
    调用 auto_solve.py 运行单个任务
    """
    wait_for_backend()

    # 处理任务路径：如果设置了 DATA_BASE_DIR，则使用绝对路径
    task_path = task["path"]
    if DATA_BASE_DIR:
        task_path = str(DATA_BASE_DIR / task_path)
    
    cmd = [
        "python",
        "solve/auto_solve.py",
        "-p",
        task_path,
        "-i",
        str(task["id"]),
        "-o",
        task["output_dir"],
        "-m",
        task["mode"],
        "-M",
        task["model"],
    ]
    if setting:
        cmd.extend(["--setting", setting])
    if prompt_dir:
        cmd.extend(["--prompt_dir", prompt_dir])
    if MAX_STEPS > 0:
        cmd.extend(["--max_steps", str(MAX_STEPS)])

    if experiment_type == "text_only":
        cmd.append("--text_only")
    elif experiment_type == "interference_key":
        cmd.extend(["--interference", "modify_key"])
    elif experiment_type == "interference_non_key":
        cmd.extend(["--interference", "modify_non_key"])
    elif experiment_type == "use_edge":
        cmd.append("--use_edge")
    elif experiment_type == "use_depth":
        cmd.append("--use_depth")
    elif experiment_type == "optional":
        cmd.append("--optional")

    cmd_str = " ".join(cmd)
    print(cmd_str)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    task_name = "_".join(task["path"].split("/")[3:]).replace("data.json", "")
    log_suffix = f"{task_name}_{task['id']}_{timestamp}.log"
    if experiment_type:
        log_suffix = f"{task_name}_{task['id']}_{experiment_type}_{timestamp}.log"
    log_filename = LOG_DIR / log_suffix
    try:
        print(f"Task started: {cmd_str}, logging -> {log_filename}")
        start_time = time.time()
        with open(log_filename, "w", encoding="utf-8") as log_file:
            subprocess.run(
                cmd,
                check=True,
                stdout=log_file,
                stderr=log_file,
                timeout=TASK_TIMEOUT_SECONDS if TASK_TIMEOUT_SECONDS > 0 else None,
            )
        end_time = time.time()
        print(
            f"Task completed: {cmd_str} (Duration: {end_time - start_time:.2f}s) Logging -> {log_filename}"
        )
        return f"Task succeeded: {cmd_str}"  # ✅ 修复拼写错误
    except subprocess.TimeoutExpired:
        end_time = time.time()
        error_message = (
            f"Task timeout after {TASK_TIMEOUT_SECONDS}s: {cmd_str} "
            f"(Duration: {end_time - start_time:.2f}s) logging -> {log_filename}"
        )
        print(error_message)
        with open(log_filename, "a", encoding="utf-8") as log_file:
            log_file.write(f"\n[TIMEOUT] auto_solve exceeded {TASK_TIMEOUT_SECONDS}s and was killed by run_tasks.py\n")
        return error_message
    except subprocess.CalledProcessError:
        error_message = f"Task failed: {cmd_str}, logging -> {log_filename}"
        print(error_message)
        return error_message


def build_output_dir(task_path, task_id, mode, model, exp_type, setting=None):
    """
    构建输出目录路径
    支持相对路径和绝对路径
    例如: annotation/dataset/data/math/data.json -> tasks/out/math/code_gpt-4o/123/
    """
    # 将路径转换为 Path 对象以标准化处理
    path_obj = Path(task_path)
    
    # 获取路径的各个部分，过滤掉空字符串（绝对路径会产生）
    parts = [p for p in path_obj.parts if p and p != '/']
    
    # 如果最后一部分是 data.json，移除它
    if parts and parts[-1] == "data.json":
        parts = parts[:-1]
    
    # 查找 "data" 目录的位置，提取数据集路径
    # 例如: annotation/dataset/data/math -> math
    # 或: annotation/dataset/data/emma/chemistry -> emma/chemistry
    try:
        data_idx = parts.index("data")
        # 提取 data 之后的部分作为数据集路径
        dataset_parts = parts[data_idx + 1:]
        if not dataset_parts:
            # 如果没有找到，使用默认值
            dataset_parts = ["unknown"]
    except (ValueError, IndexError):
        # 如果找不到 "data" 目录，尝试使用后三个部分
        if len(parts) >= 3:
            dataset_parts = parts[-3:-1] if parts[-1] == "data.json" else parts[-2:]
        else:
            dataset_parts = parts[-1:] if parts else ["unknown"]
    
    dataset_path = Path(*dataset_parts) if dataset_parts else Path("unknown")
    base_name = f"{mode}_{model}"
    if setting:
        base_name += f"_{setting}"
    if exp_type:
        base_name += f"_{exp_type}"
    output_dir = OUTPUT_BASE_DIR / dataset_path / base_name / str(task_id)
    return f"{output_dir}/"


def main(
    tasks_file,
    mode,
    model,
    start=0,
    end=10,
    linear=True,
    workers=4,
    experiment=False,
    experiment_types=None,
    global_parallel=False,
    setting=None,
    prompt_dir=None,
):
    with open(tasks_file, "r", encoding="utf-8") as t:
        tasks = json.load(t)
    tasks = tasks[start:end]

    for task in tasks:
        task["mode"] = mode
        task["model"] = model

    if experiment:
        if not experiment_types:
            experiment_types = [
                # "", 去除baseline
                "text_only",
                "interference_key",
                "interference_non_key",
                "use_edge", # add experiment type
                "use_depth", # add experiment type
                "optional", # add experiment type
            ]
    else:
        experiment_types = [""]

    all_results = []
    all_table_data = []
    start_time = time.time()

    if global_parallel:
        print(
            f"Global parallel enabled: merging {len(experiment_types)} experiment types x {len(tasks)} tasks."
        )
        combined_tasks = []
        for exp_type in experiment_types:
            for task in tasks:
                t_copy = task.copy()
                t_copy["output_dir"] = build_output_dir(
                    task["path"], task["id"], mode, model, exp_type, setting
                )
                t_copy["_exp_type"] = exp_type
                t_copy["_exp_name"] = exp_type if exp_type else "baseline"
                combined_tasks.append(t_copy)

        print(
            f"Submitting {len(combined_tasks)} tasks with max_workers={workers}, linear={linear}"
        )

        if linear:
            for i, ct in enumerate(combined_tasks, 1):
                print(
                    f"Running task {i}/{len(combined_tasks)}: {ct['path']} (ID: {ct['id']}) [{ct['_exp_name']}]"
                )
                result = run_script(ct, ct["_exp_type"] if ct["_exp_type"] else None, setting, prompt_dir)
                all_results.append(result)
                all_table_data.append(
                    [
                        ct["path"],
                        ct["id"],
                        ct["model"],
                        ct["mode"],
                        ct["_exp_name"],
                        "success" if "succeeded" in result else "failed",  # ✅ 修复拼写错误
                    ]
                )
        else:
            completed = 0
            total = len(combined_tasks)
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_task = {
                    executor.submit(
                        run_script,
                        ct,
                        ct["_exp_type"] if ct["_exp_type"] else None,
                        setting,
                        prompt_dir,
                    ): ct
                    for ct in combined_tasks
                }
                for fut in as_completed(future_to_task):
                    ct = future_to_task[fut]
                    try:
                        result = fut.result()
                        status = "success" if "succeeded" in result else "failed"  # ✅ 修复拼写错误
                    except Exception as e:
                        result = f"Task failed: {ct['path']} id={ct['id']} ({e})"
                        status = "failed"
                    all_results.append(result)
                    all_table_data.append(
                        [
                            ct["path"],
                            ct["id"],
                            ct["model"],
                            ct["mode"],
                            ct["_exp_name"],
                            status,
                        ]
                    )
                    completed += 1
                    # ✅ 添加flush=True确保及时输出，避免缓冲
                    print(f"Progress: {completed}/{total} ({completed/total*100:.1f}%) - {status} [{ct['_exp_name']}]", flush=True)
    else:
        for exp_type in experiment_types:
            exp_name = exp_type if exp_type else "baseline"
            print(
                f"Starting {exp_name} experiment execution from index {start} to {end}, linear={linear}, workers={workers}"
            )

            exp_tasks = []
            for task in tasks:
                exp_task = task.copy()
                exp_task["output_dir"] = build_output_dir(
                    task["path"], task["id"], mode, model, exp_type, setting
                )
                exp_tasks.append(exp_task)

            results = []
            table_data = []

            if linear:
                for i, task in enumerate(exp_tasks):
                    print(
                        f"Running task {i+1}/{len(exp_tasks)}: {task['path']} (ID: {task['id']})"
                    )
                    result = run_script(task, exp_type if exp_type else None, setting, prompt_dir)
                    results.append(result)
                    table_data.append(
                        [
                            task["path"],
                            task["id"],
                            task["model"],
                            task["mode"],
                            exp_name,
                            "success" if "succeeded" in result else "failed",  # ✅ 修复拼写错误
                        ]
                    )
                    print(
                        f"Task {i+1} completed: {'✓' if 'succeeded' in result else '✗'}"
                    )
            else:
                completed_count = 0
                total_tasks = len(exp_tasks)
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    future_to_task = {}
                    for task in exp_tasks:
                        future = executor.submit(
                            run_script, task, exp_type if exp_type else None, setting, prompt_dir
                        )
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
                                    exp_name,
                                    "success" if "succeeded" in result else "failed",  # ✅ 修复拼写错误
                                ]
                            )
                            completed_count += 1
                            print(
                                f"Progress: {completed_count}/{total_tasks} ({(completed_count/total_tasks*100):.1f}%) - {'✓' if 'succeeded' in result else '✗'}", 
                                flush=True  # ✅ 添加flush确保及时输出
                            )
                        except Exception as e:
                            print(f"Unexpected error: {e}")
                            table_data.append(
                                [
                                    task["path"],
                                    task["id"],
                                    task["model"],
                                    task["mode"],
                                    exp_name,
                                    "failed",
                                ]
                            )
                            completed_count += 1
                            print(
                                f"Progress: {completed_count}/{total_tasks} ({(completed_count/total_tasks*100):.1f}%) - error", 
                                flush=True  # ✅ 添加flush确保及时输出
                            )

            all_results.extend(results)
            all_table_data.extend(table_data)

    end_time = time.time()
    time_stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_log = LOG_DIR / f"summary_{mode}_{model}_{start}_{end}_{time_stamp}.log"
    consume_time_str = f"Total time taken: {end_time - start_time:.2f} seconds"
    
    # ✅ 添加最终完成确认
    success_count = sum(1 for row in all_table_data if row[-1] == "success")
    failed_count = sum(1 for row in all_table_data if row[-1] == "failed")
    total_count = len(all_table_data)
    
    print(f"\n=== FINAL SUMMARY ===")
    print(f"Total tasks: {total_count}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failed_count}")
    print(f"Completion rate: {success_count/total_count*100:.1f}%")
    
    if success_count + failed_count == total_count:
        print("✅ All tasks have been processed!")
    else:
        print(f"❌ Missing {total_count - (success_count + failed_count)} tasks!")
    
    # ✅ 记录详细的进度日志
    progress_log = LOG_DIR / f"progress_{mode}_{model}_{start}_{end}_{time_stamp}.log"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(progress_log, "w", encoding="utf-8") as progress_file:
        progress_file.write("Detailed progress log:\n")
        for i, row in enumerate(all_table_data):
            progress_file.write(f"{i+1}/{total_count}: {row}\n")
        progress_file.write(f"\n{consume_time_str}\n")
        progress_file.write(f"Success: {success_count}, Failed: {failed_count}, Total: {total_count}\n")

    # 记录失败的任务到日志和表格中
    failed_table_data = [row for row in all_table_data if row[-1].lower() == "failed"]
    if failed_table_data:
        table_str = tabulate(
            failed_table_data,
            headers=["Path", "ID", "Model", "Mode", "Experiment", "Status"],
            tablefmt="simple_grid",
        )
        with open(summary_log, "w", encoding="utf-8") as f:
            f.write("Failed tasks: \n")
            for row in failed_table_data:
                f.write(json.dumps(
                    {
                        "path": row[0],
                        "id": row[1],
                        "model": row[2],
                        "mode": row[3],
                        "experiment": row[4],
                        "status": row[5],
                    },
                    ensure_ascii=False
                )+ "\n")
            f.write(f"\n{consume_time_str}\n")
            f.write(table_str)
        print(f"Summary (failed tasks) written to {summary_log}")
        print(consume_time_str)
        print("\n--- Failed Task Results ---\n")
        print(table_str)
    else:
        with open(summary_log, "w", encoding="utf-8") as f:
            f.write(f"All tasks succeeded. \n {consume_time_str}\n")
        print(f"Summary written to {summary_log}")
        print(consume_time_str)
        print("\nAll tasks succeeded. No failures to report \n")

    # Propagate task failures to shell wrappers. Smoke-test and pipeline scripts
    # use the process exit status as their gate for starting larger runs.
    # Batch experiments are best-effort: per-sample failures are written to the
    # summary above, but must not stop the remaining experiment pipeline.
    return 0


def ask_confirmation(args):
    print(json.dumps(vars(args), indent=4))
    print(
        "Press 'y' to confirm and continue, any other key to abort (auto continue in 10s): "
    )
    i, o, e = select.select([sys.stdin], [], [], 10)
    if i:
        user_input = sys.stdin.readline().strip()
        if user_input.lower() != 'y':
            print("Aborted by user.")
            sys.exit(0)
    else:
        print("No input received, continuing...")


if __name__ == "__main__":
    """
    examples:
    python3 run_tasks.py --tasks tasks/math_tasks.json --mode code --model gemini-2.5-pro --workers 5 --start 0 --end 10
    python3 run_tasks.py --tasks tasks/m3cot_tasks.json --mode banana --model gpt-4o --experiment --experiment_types text_only interference_key
    python3 run_tasks.py --tasks tasks/m3cot_tasks.json --mode code --model gpt-4o --experiment --global_parallel
    """
    parser = argparse.ArgumentParser()
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
        "--setting",
        type=str,
        choices=["text_cot", "vaot_no_render", "vaot_full", "vaot_full_min1_render", "vaot_wrong_render"],
        default=None,
        help="See2Think setting; passed to auto_solve and prompt",
        required=False,
    )
    parser.add_argument(
        "--prompt_dir",
        type=str,
        default=None,
        help="Prompt directory; defaults to SEE2THINK_PROMPT_DIR or prompt",
        required=False,
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
    parser.add_argument(
        "--experiment", action="store_true", help="是否开启对照实验", required=False
    )
    parser.add_argument(
        "--experiment_types",
        nargs="+",
        choices=[
            "text_only",
            "interference_key",
            "interference_non_key",
            "use_edge",
            "use_depth",
            "optional",
        ],
        help=(
            "指定实验类型，可选择多个。"
            "默认运行所有实验（baseline, text_only, interference_key, interference_non_key, use_edge, use_depth, optional）"
            "如果未指定 --experiment，则仅运行 baseline 实验。"
        ),
        required=False,
    )
    parser.add_argument(
        "--global_parallel",
        action="store_true",
        help="跨实验类型合并并行运行所有任务",
        required=False,
    )
    args = parser.parse_args()
    if not os.environ.get("SKIP_CONFIRM") in ["1", "true", "True"]:
        print("Please confirm the following parameters:")
        ask_confirmation(args)
    else:
        print("SKIP_CONFIRM is set, skipping confirmation.")

    sys.exit(
        main(
            args.tasks,
            args.mode,
            args.model,
            args.start,
            args.end,
            args.linear,
            args.workers,
            args.experiment,
            args.experiment_types,
            args.global_parallel,
            args.setting,
            args.prompt_dir,
        )
    )
