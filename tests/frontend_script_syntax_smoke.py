import re
import shutil
import subprocess
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_FILES = [
    PROJECT_ROOT / "frontend" / "index.html",
    PROJECT_ROOT / "frontend" / "logs.html",
    PROJECT_ROOT / "frontend" / "changes.html",
]


def extract_inline_scripts(html_text):
    """提取页面内联 JavaScript，交给 Node.js 做真正的语法检查。"""
    return re.findall(r"<script>([\s\S]*?)</script>", html_text, flags=re.IGNORECASE)


def main():
    # Node.js 只用于开发验收；代理服务器运行本身仍然只依赖 Python。
    node = shutil.which("node")
    if not node:
        print("frontend script syntax smoke test skipped: node command not found")
        return 0

    # 临时脚本放在项目内，避免 Windows 受限环境无法让 Node 读取系统临时目录。
    with tempfile.TemporaryDirectory(
        prefix="web_proxy_frontend_check_",
        dir=PROJECT_ROOT / "tests",
    ) as temp_dir:
        temp_root = Path(temp_dir)
        for html_path in FRONTEND_FILES:
            scripts = extract_inline_scripts(html_path.read_text(encoding="utf-8"))
            assert scripts, f"no inline script found: {html_path.name}"

            for index, script in enumerate(scripts, start=1):
                # 写入临时 .js 文件可以保留 UTF-8 内容，并让错误信息带准确行号。
                script_path = temp_root / f"{html_path.stem}_{index}.js"
                script_path.write_text(script, encoding="utf-8")
                completed = subprocess.run(
                    [node, "--check", str(script_path)],
                    cwd=str(PROJECT_ROOT),
                    text=True,
                    capture_output=True,
                    check=False,
                )
                assert completed.returncode == 0, (
                    f"JavaScript syntax error in {html_path.name}:\n"
                    f"{completed.stdout}{completed.stderr}"
                )

    print("frontend script syntax smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
