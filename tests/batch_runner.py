import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_smoke_batch(batch_name, test_names):
    """按顺序运行一组独立 smoke test，并输出便于验收查看的汇总。"""
    passed = []
    print(f"\n{'=' * 68}", flush=True)
    print(f"Starting batch: {batch_name}", flush=True)
    print(f"{'=' * 68}", flush=True)

    for test_name in test_names:
        print(f"\n===== running {test_name} =====", flush=True)
        completed = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tests" / test_name)],
            cwd=str(PROJECT_ROOT),
            check=False,
        )
        if completed.returncode != 0:
            print(f"\nFAILED batch: {batch_name}", flush=True)
            print(f"FAILED test: {test_name}", flush=True)
            print(f"Passed before failure: {len(passed)}/{len(test_names)}", flush=True)
            return completed.returncode
        passed.append(test_name)

    print(f"\nPASSED batch: {batch_name}", flush=True)
    print(f"Passed tests: {len(passed)}/{len(test_names)}", flush=True)
    return 0
