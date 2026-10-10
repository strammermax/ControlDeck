import importlib.util
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("agent_proxy", ROOT / "scripts/controldeck-agent-proxy.py")
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)
from backend import agent_client  # noqa: E402

AGENT_SPEC = importlib.util.spec_from_file_location("controldeck_agent", ROOT / "scripts/controldeck-agent.py")
agent = importlib.util.module_from_spec(AGENT_SPEC)
AGENT_SPEC.loader.exec_module(agent)


def host_key_line(address="192.168.1.98"):
    key = ed25519.Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH).decode()
    return f"{address} {key}"


@pytest.fixture
def proxy_state(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTROLDECK_PROXY_STATE", str(tmp_path))
    (tmp_path / "id_ed25519").write_text("PRIVATE")
    (tmp_path / "id_ed25519.pub").write_text("ssh-ed25519 AAAA controldeck-agent")
    return tmp_path


class FakeRun:
    """Stands in for ssh/ssh-keyscan; records the command and stdin."""
    def __init__(self, key_line):
        self.key_line, self.calls, self.answer, self.stderr, self.code = key_line, [], {"ok": True, "data": {"agentVersion": 1}}, b"", 0

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs.get("input")))
        if "keyscan" in command[0]:
            return SimpleNamespace(stdout=f"# comment\n{self.key_line}\n", stderr="", returncode=0)
        stdout = (json.dumps(self.answer) + "\n").encode() if self.answer is not None else b""
        return SimpleNamespace(stdout=stdout, stderr=self.stderr, returncode=self.code)


def test_proxy_and_agent_agree_on_actions():
    assert proxy.AGENT_ACTIONS == set(agent.ACTIONS)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_fingerprint(case):
    line = host_key_line()
    if case == "normaal":
        value = proxy.fingerprint(line)
        assert proxy.FINGERPRINT.fullmatch(value)
        if shutil.which("ssh-keygen"):
            result = subprocess.run(["ssh-keygen", "-lf", "-"], input=line, capture_output=True, text=True)
            assert value in result.stdout  # same as what the admin sees on the node
    elif case == "boundary":
        assert proxy.fingerprint(line + " extra-comment") == proxy.fingerprint(line)
    else:
        for invalid in ("", "host ssh-rsa AAAA", "host ssh-ed25519 !!!notbase64"):
            with pytest.raises(proxy.ProxyError):
                proxy.fingerprint(invalid)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_enroll_and_call(proxy_state, monkeypatch, case):
    fake = FakeRun(host_key_line())
    monkeypatch.setattr(proxy.subprocess, "run", fake)
    scanned = proxy.handle({"op": "scan", "address": "192.168.1.98"})["data"]["fingerprint"]
    if case == "faal":
        # A different (e.g. spoofed) host key than the one the admin confirmed is never trusted.
        fake.key_line = host_key_line()
        result = proxy.handle({"op": "trust", "node": "pve-amd", "address": "192.168.1.98", "fingerprint": scanned})
        assert result["error"] == "fingerprint_mismatch" and not (proxy_state / "known_hosts").exists()
        assert proxy.handle({"op": "call", "node": "pve-amd", "action": "info"})["error"] == "unknown_node"
        assert proxy.handle({"op": "call", "node": "pve-amd", "action": "shell"})["error"] == "unknown_action"
        return
    assert proxy.handle({"op": "trust", "node": "pve-amd", "address": "192.168.1.98", "fingerprint": scanned})["ok"]
    assert (proxy_state / "known_hosts").read_text().startswith("192.168.1.98 ssh-ed25519 ")
    status = proxy.handle({"op": "status"})["data"]
    assert status["keyExists"] and status["nodes"][0]["node"] == "pve-amd" and "key" not in status["nodes"][0]
    result = proxy.handle({"op": "call", "node": "pve-amd", "action": "cron.list", "payload": {}, "actor": "admin@example.test"})
    assert result == {"ok": True, "data": {"ok": True, "data": {"agentVersion": 1}}}
    command, body = fake.calls[-1]
    assert command[-2:] == ["root@192.168.1.98", "cron.list"] and "StrictHostKeyChecking=yes" in command and "BatchMode=yes" in command
    assert json.loads(body) == {"actor": "admin@example.test"}
    audit = [json.loads(line) for line in (proxy_state / "audit.log").read_text().splitlines()]
    assert audit[-1] == {**audit[-1], "op": "call", "node": "pve-amd", "action": "cron.list", "result": "ok"}
    if case == "boundary":
        proxy.handle({"op": "trust", "node": "pve-intel", "address": "192.168.1.99", "fingerprint": proxy.fingerprint(fake.key_line)})
        assert proxy.handle({"op": "forget", "node": "pve-amd"})["ok"]
        assert [n["node"] for n in proxy.handle({"op": "status"})["data"]["nodes"]] == ["pve-intel"]
        assert "192.168.1.98" not in (proxy_state / "known_hosts").read_text()


@pytest.mark.parametrize("stderr,code", [(b"@@@ WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED! @@@", "hostkey_changed"),
                                         (b"root@192.168.1.98: Permission denied (publickey).", "not_authorized"),
                                         (b"ssh: connect to host 192.168.1.98 port 22: No route to host", "ssh_failed")])
def test_ssh_failures_are_explained_without_details(proxy_state, monkeypatch, stderr, code):
    fake = FakeRun(host_key_line())
    monkeypatch.setattr(proxy.subprocess, "run", fake)
    proxy.handle({"op": "trust", "node": "pve-amd", "address": "192.168.1.98", "fingerprint": proxy.fingerprint(fake.key_line)})
    fake.answer, fake.stderr, fake.code = None, stderr, 255
    result = proxy.handle({"op": "call", "node": "pve-amd", "action": "info"})
    assert result["error"] == code and "192.168.1.98" not in result["message"]


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_validate_requests(case):
    if case == "normaal":
        assert proxy.validate({"op": "call", "node": "pve-amd", "action": "cron.put", "payload": {"id": "x"}, "actor": "a"}) == "call"
    elif case == "boundary":
        assert proxy.validate({"op": "scan", "address": "fe80::1"}) == "scan"
        assert proxy.validate({"op": "scan", "address": "pve-amd.home"}) == "scan"
    else:
        for invalid in (None, {}, {"op": "exec"}, {"op": "status", "x": 1}, {"op": "scan", "address": "a b"}, {"op": "scan", "address": "-oProxyCommand=x"},
                        {"op": "forget", "node": "../x"}, {"op": "trust", "node": "a", "address": "1.2.3.4", "fingerprint": "MD5:aa"},
                        {"op": "call", "node": "a", "action": "cron.put", "payload": []}):
            with pytest.raises(proxy.ProxyError):
                proxy.validate(invalid)


@pytest.mark.skipif(os.name != "posix", reason="Unix sockets; covered on Linux in CI")
def test_socket_server_and_client(proxy_state, monkeypatch, tmp_path):
    socket_path = tmp_path / "agent.sock"
    thread = threading.Thread(target=proxy.serve, args=(str(socket_path),), daemon=True)
    thread.start()
    # serve() binds first and chmods right after; wait for both to avoid a race.
    for _ in range(100):
        if socket_path.exists() and socket_path.stat().st_mode & 0o777 == 0o660:
            break
        time.sleep(0.02)
    assert oct(socket_path.stat().st_mode & 0o777) == "0o660"
    # Regression: serve() once set the process umask to 0117, so every directory the process created afterwards
    # lacked the execute bit and 217 unrelated tests failed with "Permission denied" in CI.
    probe = tmp_path / "probe-dir"
    probe.mkdir()
    (probe / "file").write_text("ok")
    assert (probe / "file").read_text() == "ok"
    current = os.umask(0o022)
    os.umask(current)
    assert current & 0o100 == 0
    monkeypatch.setenv("CONTROLDECK_AGENT_SOCKET", str(socket_path))
    assert agent_client.proxy_request({"op": "status"})["data"]["keyExists"] is True
    assert agent_client.proxy_request({"op": "nope"})["error"] == "invalid_request"


def test_client_reports_missing_proxy(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTROLDECK_AGENT_SOCKET", str(tmp_path / "missing.sock"))
    with pytest.raises(agent_client.AgentUnavailable):
        agent_client.proxy_request({"op": "status"})


def test_bootstrap_installs_proxy_without_root_access_to_key():
    """The proxy runs as its own user; the web app joins its group for the socket but the key stays 0600."""
    script = (ROOT / "scripts/install-wizard.sh").read_text()
    unit = (ROOT / "deploy/controldeck-agent-proxy.service").read_text()
    assert "useradd --system --home /var/lib/controldeck-ssh" in script and "usermod -aG controldeck-ssh controldeck" in script
    assert "-m 0700 /var/lib/controldeck-ssh" in script and "systemctl restart controldeck-agent-proxy.service" in script
    assert "User=controldeck-ssh" in unit and "NoNewPrivileges=yes" in unit and "ProtectSystem=strict" in unit
    assert "User=root" not in unit and "ReadWritePaths=/var/lib/controldeck-ssh" in unit
