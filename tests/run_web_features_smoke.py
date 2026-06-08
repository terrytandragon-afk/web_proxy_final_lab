from batch_runner import run_smoke_batch


# 基础 Web/代理功能批量测试：验证转发、过滤、HTTPS、缓存、前端、认证和限流。
WEB_FEATURE_TESTS = [
    "stage4_smoke.py",
    "stage5_smoke.py",
    "stage6_smoke.py",
    "stage7_policy_smoke.py",
    "stage9_connect_smoke.py",
    "stage10_cache_smoke.py",
    "stage12_frontend_display_smoke.py",
    "stage13_auth_smoke.py",
    "stage14_rate_limit_smoke.py",
    "acceptance_web_evidence_smoke.py",
]


def main():
    result = run_smoke_batch("web/proxy features", WEB_FEATURE_TESTS)
    if result == 0:
        print("Web evidence: tests/evidence/proxy.log and tests/evidence/blocked.log", flush=True)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
