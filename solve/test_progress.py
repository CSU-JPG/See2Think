#!/usr/bin/env python3
"""
Smoke test script for progress visualization in run_tasks.py

This script creates a mock version of run_tasks.py to test the progress visualization
without actually running any real tasks.
"""

import json
import time
import os
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse

# Mock the imports for progress visualization
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

try:
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, TimeElapsedColumn
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

def mock_run_script(task, experiment_type=None, golden_path=None):
    """
    Mock version of run_script that simulates task execution with variable duration
    """
    task_id = task["id"]
    exp_type = experiment_type if experiment_type else "baseline"

    # Simulate variable processing time (1-3 seconds)
    processing_time = 1 + (task_id % 3)
    time.sleep(processing_time)

    # Simulate some failures (20% failure rate for testing)
    if task_id % 5 == 0:
        return f"Task failed: mock task {task_id} ({exp_type})"
    else:
        return f"Task succeded: mock task {task_id} ({exp_type})"

def create_mock_tasks(count=10):
    """Create mock task configurations"""
    tasks = []
    for i in range(count):
        task = {
            "id": i,
            "path": f"annotation/dataset/data/mock/data.json",
            "output_dir": f"mock_output/{i}/",
            "mode": "code",
            "model": "test-model"
        }
        tasks.append(task)
    return tasks

def test_progress_linear(tasks, experiment_types):
    """Test linear execution with progress visualization"""
    print("\n" + "="*60)
    print("TESTING LINEAR EXECUTION WITH PROGRESS")
    print("="*60)

    for exp_type in experiment_types:
        exp_name = exp_type if exp_type else "baseline"
        print(f"\nStarting {exp_name} linear execution test...")

        if RICH_AVAILABLE:
            console = Console()
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                task_progress = progress.add_task(
                    f"[cyan]{exp_name} tasks",
                    total=len(tasks)
                )

                for task in tasks:
                    result = mock_run_script(task, exp_type if exp_type else None)
                    progress.update(task_progress, advance=1, description=f"[cyan]{exp_name} tasks")

        elif TQDM_AVAILABLE:
            pbar = tqdm(tasks, desc=f"{exp_name} tasks", unit="task")
            for task in pbar:
                result = mock_run_script(task, exp_type if exp_type else None)
                pbar.set_postfix(status="✓" if "succeded" in result else "✗")
            pbar.close()

        else:
            # Fallback: simple text progress
            for i, task in enumerate(tasks):
                result = mock_run_script(task, exp_type if exp_type else None)
                print(f"Progress: {i+1}/{len(tasks)} ({((i+1)/len(tasks)*100):.1f}%) - {'✓' if 'succeded' in result else '✗'}")

def test_progress_parallel(tasks, experiment_types, workers=3):
    """Test parallel execution with progress visualization"""
    print("\n" + "="*60)
    print("TESTING PARALLEL EXECUTION WITH PROGRESS")
    print("="*60)

    for exp_type in experiment_types:
        exp_name = exp_type if exp_type else "baseline"
        print(f"\nStarting {exp_name} parallel execution test (workers={workers})...")

        if RICH_AVAILABLE:
            console = Console()
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("[cyan]Completed: {task.completed}/{task.total}"),
                console=console
            ) as progress:
                task_progress = progress.add_task(
                    f"[cyan]{exp_name} tasks (parallel)",
                    total=len(tasks)
                )

                with ThreadPoolExecutor(max_workers=workers) as executor:
                    future_to_task = {}
                    for task in tasks:
                        future = executor.submit(mock_run_script, task, exp_type if exp_type else None)
                        future_to_task[future] = task

                    for future in as_completed(future_to_task):
                        try:
                            result = future.result()
                            progress.update(task_progress, advance=1)
                        except Exception as e:
                            print(f"Unexpected error: {e}")
                            progress.update(task_progress, advance=1)

        elif TQDM_AVAILABLE:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_task = {}
                for task in tasks:
                    future = executor.submit(mock_run_script, task, exp_type if exp_type else None)
                    future_to_task[future] = task

                with tqdm(total=len(tasks), desc=f"{exp_name} tasks (parallel)", unit="task") as pbar:
                    for future in as_completed(future_to_task):
                        try:
                            result = future.result()
                            pbar.update(1)
                            pbar.set_postfix(status="✓" if "succeded" in result else "✗")
                        except Exception as e:
                            print(f"Unexpected error: {e}")
                            pbar.update(1)

        else:
            # Fallback: simple text progress for parallel execution
            completed_count = 0
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_task = {}
                for task in tasks:
                    future = executor.submit(mock_run_script, task, exp_type if exp_type else None)
                    future_to_task[future] = task

                for future in as_completed(future_to_task):
                    try:
                        result = future.result()
                        completed_count += 1
                        print(f"Progress: {completed_count}/{len(tasks)} ({(completed_count/len(tasks)*100):.1f}%) - {'✓' if 'succeded' in result else '✗'}")
                    except Exception as e:
                        print(f"Unexpected error: {e}")
                        completed_count += 1

def test_with_mock_tasks_file():
    """Test using a temporary tasks file (simulating real usage)"""
    print("\n" + "="*60)
    print("TESTING WITH MOCK TASKS FILE")
    print("="*60)

    # Create temporary tasks file
    mock_tasks = create_mock_tasks(5)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(mock_tasks, f, indent=2)
        tasks_file = f.name

    try:
        # Load tasks from file (simulate real usage)
        with open(tasks_file, 'r') as f:
            loaded_tasks = json.load(f)

        experiment_types = ["baseline", "text_only"]

        print(f"Loaded {len(loaded_tasks)} tasks from temporary file")
        test_progress_linear(loaded_tasks[:3], experiment_types[:1])  # Test with subset
        test_progress_parallel(loaded_tasks[:3], experiment_types[:1], workers=2)  # Test with subset

    finally:
        # Clean up temporary file
        os.unlink(tasks_file)
        print(f"\nCleaned up temporary file: {tasks_file}")

def main():
    parser = argparse.ArgumentParser(description="Test progress visualization for run_tasks.py")
    parser.add_argument("--tasks", type=int, default=8, help="Number of mock tasks to create")
    parser.add_argument("--workers", type=int, default=3, help="Number of parallel workers")
    parser.add_argument("--skip-linear", action="store_true", help="Skip linear execution tests")
    parser.add_argument("--skip-parallel", action="store_true", help="Skip parallel execution tests")
    parser.add_argument("--skip-file-test", action="store_true", help="Skip file-based tests")

    args = parser.parse_args()

    print("PROGRESS VISUALIZATION SMOKE TEST")
    print("="*60)
    print(f"Testing with {args.tasks} mock tasks")
    print(f"Available libraries:")
    print(f"  - Rich: {'✓' if RICH_AVAILABLE else '✗'}")
    print(f"  - tqdm: {'✓' if TQDM_AVAILABLE else '✗'}")

    # Create mock tasks
    mock_tasks = create_mock_tasks(args.tasks)
    experiment_types = ["baseline", "text_only", "interference_key", "interference_non_key"]

    # Run tests
    try:
        if not args.skip_linear:
            test_progress_linear(mock_tasks[:5], experiment_types[:2])  # Test with subset

        if not args.skip_parallel:
            test_progress_parallel(mock_tasks[:5], experiment_types[:2], args.workers)  # Test with subset

        if not args.skip_file_test:
            test_with_mock_tasks_file()

        print("\n" + "="*60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("Progress visualization is working correctly.")
        print("="*60)

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()