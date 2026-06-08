from batch_runner import run_smoke_batch


# 规则与模式批量测试：验证管理 API、白名单切换、规则组增删改查和运行时热更新。
RULE_MANAGEMENT_TESTS = [
    "stage8_admin_smoke.py",
    "stage11_whitelist_smoke.py",
    "stage15_rule_management_smoke.py",
    "stage16_rule_cli_smoke.py",
    "stage17_runtime_settings_smoke.py",
    "acceptance_rule_evidence_smoke.py",
]


def main():
    result = run_smoke_batch("rule groups and runtime modes", RULE_MANAGEMENT_TESTS)
    if result == 0:
        print("Rule evidence: tests/evidence/changes.jsonl", flush=True)
        print(
            "Evidence dashboard: python src\\proxy.py --config tests\\evidence\\acceptance_config.json",
            flush=True,
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
