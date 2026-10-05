import importlib.util
import json
from pathlib import Path

import pytest

from backend import root_components
from backend.agent_client import AgentUnavailable

ROOT = Path(__file__).resolve().parent.parent


def test_proxy_version_matches_backend_requirement():
    spec = importlib.util.spec_from_file_location("agent_proxy", ROOT / "scripts/controldeck-agent-proxy.py")
    proxy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proxy)
    assert proxy.PROXY_VERSION == root_components.REQUIRED_PROXY


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_bootstrap_info_and_command(tmp_path, case):
    record = tmp_path / "bootstrap.json"
    if case == "normaal":
        record.write_text(json.dumps({"checkout": "/home/llmuser/controldeck-bootstrap", "owner": "llmuser", "commit": "a" * 40}))
        info = root_components.bootstrap_info(tmp_path)
        assert info == {"checkout": "/home/llmuser/controldeck-bootstrap", "owner": "llmuser", "commit": "a" * 40}
        # git refuses root on another user's repository ("dubious ownership"), so pull runs as the owner.
        assert root_components.update_command(info) == "sudo -u llmuser git -C /home/llmuser/controldeck-bootstrap pull && bash /home/llmuser/controldeck-bootstrap/scripts/install-wizard.sh"
    elif case == "boundary":
        assert root_components.bootstrap_info(tmp_path) is None  # never bootstrapped with this version
        assert root_components.update_command(None) == "git -C /root/controldeck-bootstrap pull && bash /root/controldeck-bootstrap/scripts/install-wizard.sh"
        record.write_text(json.dumps({"checkout": "/srv/cd", "owner": "root"}))
        assert root_components.update_command(root_components.bootstrap_info(tmp_path)).startswith("git -C /srv/cd pull")
    else:
        for bad in ("not json", json.dumps([1]), json.dumps({"checkout": "relative/path"}), json.dumps({"checkout": "/x; rm -rf /"})):
            record.write_text(bad)
            assert root_components.bootstrap_info(tmp_path) is None
        record.write_text(json.dumps({"checkout": "/srv/cd", "owner": "a b; id", "commit": "zz"}))
        info = root_components.bootstrap_info(tmp_path)
        assert info["owner"] == "root" and info["commit"] is None


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_root_components_issues(tmp_path, monkeypatch, case):
    def proxy(version=None, error=False):
        def fake(request, timeout=75):
            if error:
                raise AgentUnavailable("De agent-proxy draait niet.")
            return {"ok": True, "data": {"proxyVersion": version} if version is not None else {}}
        return fake
    if case == "normaal":
        monkeypatch.setattr(root_components, "proxy_request", proxy(root_components.REQUIRED_PROXY))
        assert root_components.root_components(tmp_path, {"workerOutdated": False})["issues"] == []
    elif case == "boundary":
        monkeypatch.setattr(root_components, "proxy_request", proxy())  # proxy from before versioning
        status = root_components.root_components(tmp_path, {"workerOutdated": True})
        assert status["issues"] == ["installatieworker", "agent-proxy"] and status["proxy"]["outdated"] is True
    else:
        monkeypatch.setattr(root_components, "proxy_request", proxy(error=True))
        status = root_components.root_components(tmp_path, {"workerOutdated": False})
        assert status["issues"] == ["agent-proxy (niet geïnstalleerd)"] and "install-wizard.sh" in status["command"]


def test_catalog_reports_root_components(tmp_path, monkeypatch):
    from backend.app import create_app
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([{"email": "admin@example.test", "role": "admin"}]))
    monkeypatch.setattr(root_components, "proxy_request", lambda request, timeout=75: (_ for _ in ()).throw(AgentUnavailable("x")))
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    client = app.test_client()
    with client.session_transaction() as session:
        session["identity"] = {"email": "admin@example.test", "sub": "admin"}
        session["csrf"] = "csrf"
    status = client.get("/api/installations").json["rootComponents"]
    assert "agent-proxy (niet geïnstalleerd)" in status["issues"] and status["command"].endswith("scripts/install-wizard.sh")


def test_bootstrap_records_checkout_for_the_app():
    script = (ROOT / "scripts/install-wizard.sh").read_text()
    assert '/var/lib/controldeck/bootstrap.json' in script and "chown root:controldeck /var/lib/controldeck/bootstrap.json" in script
    assert 'stat -c %U "$source_root"' in script
