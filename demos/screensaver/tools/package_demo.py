"""Build a portable zipapp from an explicit list of approved runtime files."""

import argparse
import shutil
import tempfile
import zipapp
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "dist"
RUNTIME_FILES = (
    Path("__init__.py"),
    Path("__main__.py"),
    Path("app.py"),
    Path("art.py"),
    Path("lettering.py"),
    Path("terminal.py"),
    Path("assets", "copilot.json"),
    Path("assets", "copilot.svg"),
    Path("assets", "LICENSE-Octicons.txt"),
)

LAUNCHER = r"""@echo off
setlocal
where py.exe >nul 2>nul
if not errorlevel 1 goto run_py
where python.exe >nul 2>nul
if not errorlevel 1 goto run_python
echo Python 3.10 or newer is required. Install Python, then launch this file again. 1>&2
exit /b 1

:run_py
py -3 "%~dp0copilot-screensaver.pyz" %*
exit /b %errorlevel%

:run_python
python "%~dp0copilot-screensaver.pyz" %*
exit /b %errorlevel%
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Output directory (default: this demo's dist directory).")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hackathon-screensaver-") as staging:
        stage = Path(staging)
        for relative in RUNTIME_FILES:
            target = stage / "copilot_showcase" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "copilot_showcase" / relative, target)
        shutil.copy2(ROOT / "screensaver.py", stage / "__main__.py")
        zipapp.create_archive(
            stage, args.output / "copilot-screensaver.pyz",
            compressed=True,
        )
    (args.output / "Start-Screensaver.cmd").write_text(LAUNCHER, encoding="ascii")
    shutil.copy2(ROOT / "README.md", args.output / "README.md")
    shutil.copy2(
        ROOT / "copilot_showcase" / "assets" / "LICENSE-Octicons.txt",
        args.output / "LICENSE-Octicons.txt",
    )
    print(args.output / "Start-Screensaver.cmd")
    print(f"Standalone archive: {(args.output / 'copilot-screensaver.pyz').stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
