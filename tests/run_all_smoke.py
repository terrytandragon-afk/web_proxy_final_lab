import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 总测试只编排两个职责明确的批量脚本，失败时可以快速判断问题类别。
BATCH_TESTS = [
    "run_web_features_smoke.py",
    "run_rule_management_smoke.py",
]


def main():
    for batch_script in BATCH_TESTS:
        print(f"\n######## running batch script: {batch_script} ########", flush=True)
        completed = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tests" / batch_script)],
            cwd=str(PROJECT_ROOT),
            check=False,
        )
        if completed.returncode != 0:
            print(f"FAILED batch script: {batch_script}", flush=True)
            return completed.returncode

    print("\nall test batches passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
