import subprocess
import sys
import hashlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 总测试只编排两个职责明确的批量脚本，失败时可以快速判断问题类别。
BATCH_TESTS = [
    "run_web_features_smoke.py",
    "run_rule_management_smoke.py",
]

WEB_EVIDENCE_FILES = [
    PROJECT_ROOT / "tests" / "evidence" / "web" / "proxy.log",
    PROJECT_ROOT / "tests" / "evidence" / "web" / "blocked.log",
    PROJECT_ROOT / "tests" / "evidence" / "web" / "error.log",
    PROJECT_ROOT / "tests" / "evidence" / "web" / "acceptance_config.json",
]


def evidence_digests(paths):
    """Hash Web evidence so the following rule batch cannot silently modify it."""
    return {
        str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
        if path.exists()
    }


def main():
    web_evidence_after_batch = None
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
        if batch_script == "run_web_features_smoke.py":
            web_evidence_after_batch = evidence_digests(WEB_EVIDENCE_FILES)

    if web_evidence_after_batch != evidence_digests(WEB_EVIDENCE_FILES):
        print("\nFAILED: rule batch modified Web/proxy evidence files", flush=True)
        return 1

    print("\nWeb/proxy evidence isolation verified", flush=True)
    print("\nall test batches passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
