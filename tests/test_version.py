import datetime
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("version", ROOT / "scripts/version.py")
version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_build_version(case):
    if case == "normaal":
        assert version.build_version(datetime.date(2026, 10, 5), 27) == "2026.10.05.27"
    elif case == "boundary":
        assert version.build_version(datetime.date(2026, 1, 1), 1) == "2026.01.01.1"
        assert version.build_version(datetime.date(2026, 12, 31), 123456789) == "2026.12.31.123456789"
    else:
        for build in (0, -1, True, "27", 2.5, None):
            with pytest.raises(ValueError):
                version.build_version(datetime.date(2026, 10, 5), build)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_validate(case):
    if case == "normaal":
        assert version.validate("2026.10.05.27") == "2026.10.05.27"
    elif case == "boundary":
        assert version.validate("development") == "development"
        assert version.validate("2028.02.29.1") == "2028.02.29.1"  # leap day
    else:
        for invalid in ("0.4.0", "2026.10.5.27", "2026.10.05", "2026.10.05.0", "2026.13.01.1", "2026.02.30.1", "v2026.10.05.1", "2026.10.05.1-rc", "", None, "development "):
            with pytest.raises(ValueError):
                version.validate(invalid)


def test_cli_and_today_use_valid_format():
    assert version.validate(version.build_version(version.today(), 1))
    result = subprocess.run([sys.executable, str(ROOT / "scripts/version.py"), "--check", "0.4.0"], capture_output=True, text=True)
    assert result.returncode != 0
    printed = subprocess.run([sys.executable, str(ROOT / "scripts/version.py"), "--build", "5"], capture_output=True, text=True, check=True).stdout.strip()
    assert version.validate(printed).endswith(".5")


def test_repository_default_is_development():
    assert (ROOT / "VERSION").read_text().strip() == "development"


def test_package_rejects_invalid_version(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/package.py"), "--commit", "abc", "--version", "1.2.3"], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode != 0
    assert not (ROOT / "build-info.json").exists() or json.loads((ROOT / "build-info.json").read_text())["version"] != "1.2.3"
