import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = PROJECT_ROOT / "tools" / "start_proxy_browser.ps1"


def main():
    """Verify that the acceptance browser launcher forces loopback through the proxy."""
    script = LAUNCHER.read_text(encoding="utf-8")
    assert script.isascii()
    assert "--proxy-server=$ProxyServer" in script
    assert "--proxy-bypass-list=<-loopback>" in script
    assert "--disable-background-networking" in script
    assert "--disable-features=HttpsUpgrades,HttpsFirstModeV2,AutomaticHttps" in script
    assert "--disk-cache-size=1" in script
    assert "--user-data-dir=$profileDir" in script
    assert "127.0.0.1.nip.io:9000/game/index.html" in script
    assert "127.0.0.1.nip.io:9000/content-test.html" in script
    assert "127.0.0.1:8080" in script

    powershell = shutil.which("powershell.exe")
    if powershell:
        completed = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(LAUNCHER),
                "-ValidateOnly",
            ],
            cwd=str(PROJECT_ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "Launcher validation passed." in completed.stdout
    print("browser proxy launcher smoke test passed")


if __name__ == "__main__":
    main()
