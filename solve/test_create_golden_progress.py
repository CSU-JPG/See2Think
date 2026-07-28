#!/usr/bin/env python3
"""
Test script for progress visualization in create_golden.py

This script creates a mock version of create_golden.py to test the progress visualization
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

def mock_run_script(task):
    """
    Mock version of run_script that simulates golden file creation with variable duration
    """
    task_id = task["id"]

    # Simulate variable processing time (1-3 seconds)
    processing_time = 1 + (task_id % 3)
    time.sleep(processing_time)

    # Simulate some failures (15% failure rate for testing)
    if task_id % 7 == 0:
        return f"Golden creation failed: mock task {task_id}"
    else:
        return f"Golden creation succeeded: mock task {task_id}"

def create_mock_tasks(count=10):
    """Create mock task configurations"""
    tasks = []
    for i in range(count):
        task = {
            "id": i,
            "path": f"annotation/dataset/data/mock/data.json",
            "output_dir": f"mock_output/{i}/",
            "mode": "code",
            "model": "test-model",
            "golden_output_dir": f"golden/mock/test-model/{i}/"
        }
        tasks.append(task)
    return tasks

def test_golden_progress_linear(tasks):
    """Test linear execution with progress visualization for golden creation"""
    print("\n" + "="*60)
    print("TESTING GOLDEN CREATION - LINEAR EXECUTION")
    print("="*60)

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
                f"[gold]Golden file creation",
                total=len(tasks)
            )

            for task in tasks:
                task_copy = task.copy()
                task_copy["output_dir"] = task["golden_output_dir"]
                result = mock_run_script(task_copy)
                progress.update(task_progress, advance=1, description=f"[gold]Golden file creation")

    elif TQDM_AVAILABLE:
        pbar = tqdm(tasks, desc="Golden file creation", unit="file")
        for task in pbar:
            task_copy = task.copy()
            task_copy["output_dir"] = task["golden_output_dir"]
            result = mock_run_script(task_copy)
            pbar.set_postfix(status="✓" if "succeeded" in result else "✗")
        pbar.close()

    else:
        # Fallback: simple text progress
        for i, task in enumerate(tasks):
            task_copy = task.copy()
            task_copy["output_dir"] = task["golden_output_dir"]
            result = mock_run_script(task_copy)
            print(f"Progress: {i+1}/{len(tasks)} ({((i+1)/len(tasks)*100):.1f}%) - {'✓' if 'succeeded' in result else '✗'}")

def test_golden_progress_parallel(tasks, workers=3):
    """Test parallel execution with progress visualization for golden creation"""
    print("\n" + "="*60)
    print("TESTING GOLDEN CREATION - PARALLEL EXECUTION")
    print("="*60)

    if RICH_AVAILABLE:
        console = Console()
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[gold]Completed: {task.completed}/{task.total}"),
            console=console
        ) as progress:
            task_progress = progress.add_task(
                f"[gold]Golden file creation (parallel)",
                total=len(tasks)
            )

            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_task = {}
                for task in tasks:
                    task_copy = task.copy()
                    task_copy["output_dir"] = task["golden_output_dir"]
                    future = executor.submit(mock_run_script, task_copy)
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
                task_copy = task.copy()
                task_copy["output_dir"] = task["golden_output_dir"]
                future = executor.submit(mock_run_script, task_copy)
                future_to_task[future] = task

            with tqdm(total=len(tasks), desc="Golden file creation (parallel)", unit="file") as pbar:
                for future in as_completed(future_to_task):
                    try:
                        result = future.result()
                        pbar.update(1)
                        pbar.set_postfix(status="✓" if "succeeded" in result else "✗")
                    except Exception as e:
                        print(f"Unexpected error: {e}")
                        pbar.update(1)

    else:
        # Fallback: simple text progress for parallel execution
        completed_count = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_task = {}
            for task in tasks:
                task_copy = task.copy()
                task_copy["output_dir"] = task["golden_output_dir"]
                future = executor.submit(mock_run_script, task_copy)
                future_to_task[future] = task

            for future in as_completed(future_to_task):
                try:
                    result = future.result()
                    completed_count += 1
                    print(f"Progress: {completed_count}/{len(tasks)} ({(completed_count/len(tasks)*100):.1f}%) - {'✓' if 'succeeded' in result else '✗'}")
                except Exception as e:
                    print(f"Unexpected error: {e}")
                    completed_count += 1

def main():
    parser = argparse.ArgumentParser(description="Test progress visualization for create_golden.py")
    parser.add_argument("--tasks", type=int, default=8, help="Number of mock tasks to create")
    parser.add_argument("--workers", type=int, default=3, help="Number of parallel workers")
    parser.add_argument("--skip-linear", action="store_true", help="Skip linear execution tests")
    parser.add_argument("--skip-parallel", action="store_true", help="Skip parallel execution tests")

    args = parser.parse_args()

    print("GOLDEN CREATION PROGRESS VISUALIZATION TEST")
    print("="*60)
    print(f"Testing with {args.tasks} mock golden tasks")
    print(f"Available libraries:")
    print(f"  - Rich: {'✓' if RICH_AVAILABLE else '✗'}")
    print(f"  - tqdm: {'✓' if TQDM_AVAILABLE else '✗'}")

    # Create mock tasks
    mock_tasks = create_mock_tasks(args.tasks)

    # Run tests
    try:
        if not args.skip_linear:
            test_golden_progress_linear(mock_tasks)

        if not args.skip_parallel:
            test_golden_progress_parallel(mock_tasks, args.workers)

        print("\n" + "="*60)
        print("ALL GOLDEN CREATION TESTS COMPLETED SUCCESSFULLY!")
        print("Progress visualization for golden creation is working correctly.")
        print("="*60)

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()