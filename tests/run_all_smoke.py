import subprocess
import sys
from pathlib import Path


# 一键验收脚本：按顺序运行所有功能模块的 smoke test。
PROJECT_ROOT = Path(__file__).resolve().parents[1]

TESTS = [
    "stage4_smoke.py",
    "stage5_smoke.py",
    "stage6_smoke.py",
    "stage7_policy_smoke.py",
    "stage8_admin_smoke.py",
    "stage9_connect_smoke.py",
    "stage10_cache_smoke.py",
    "stage11_whitelist_smoke.py",
    "stage12_frontend_display_smoke.py",
    "stage13_auth_smoke.py",
    "stage14_rate_limit_smoke.py",
    "stage15_rule_management_smoke.py",
    "stage16_rule_cli_smoke.py",
    "stage17_runtime_settings_smoke.py",
]


def main():
    for test_name in TESTS:
        print(f"\n===== running {test_name} =====", flush=True)
        completed = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tests" / test_name)],
            cwd=str(PROJECT_ROOT),
            check=False,
        )
        if completed.returncode != 0:
            print(f"FAILED: {test_name}", flush=True)
            return completed.returncode

    print("\nall smoke tests passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
