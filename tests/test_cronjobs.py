import json

import pytest

from backend import cronjobs
from backend.agent_client import AgentUnavailable
from backend.app import create_app

H = {"X-CSRF-Token": "csrf"}
PUBLIC_KEY = "ssh-ed25519 " + "A" * 68 + " controldeck-agent"
FINGERPRINT = "SHA256:" + "a" * 43


class FakeProxy:
    def __init__(self):
        self.calls, self.nodes, self.available, self.info = [], [], True, {}

    def __call__(self, request, timeout=75):
        self.calls.append(request)
        if not self.available:
            raise AgentUnavailable("De agent-proxy draait niet.")
        op = request["op"]
        if op == "status":
            return {"ok": True, "data": {"keyExists": True, "publicKey": PUBLIC_KEY, "nodes": [{"node": n, "address": a, "fingerprint": FINGERPRINT} for n, a in self.nodes]}}
        if op == "keygen":
            return {"ok": True, "data": {"keyExists": True, "publicKey": PUBLIC_KEY, "nodes": []}}
        if op == "scan":
            return {"ok": True, "data": {"address": request["address"], "fingerprint": FINGERPRINT}}
        if op == "trust":
            if request["fingerprint"] != FINGERPRINT:
                return {"ok": False, "error": "fingerprint_mismatch", "message": "De hostsleutel komt niet overeen."}
            self.nodes.append((request["node"], request["address"]))
            return {"ok": True, "data": {"node": request["node"]}}
        if op == "forget":
            self.nodes = [(n, a) for n, a in self.nodes if n != request["node"]]
            return {"ok": True, "data": {"forgotten": True}}
        if op == "call":
            return self.info.get(request["node"], {"ok": True, "data": {"ok": True, "data": {"agentVersion": 1, "hostname": request["node"]}}})
        raise AssertionError(op)


@pytest.fixture
def env(tmp_path, monkeypatch):
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps([{"email": "admin@example.test", "role": "admin"}, {"email": "viewer@example.test", "role": "user", "modules": ["proxmox"]}]))
    fake = FakeProxy()
    monkeypatch.setattr(cronjobs, "proxy_request", fake)
    monkeypatch.setattr(cronjobs, "source_address", lambda address: "192.168.1.164")
    app = create_app(data_dir=tmp_path / "data", accounts_path=accounts)
    app.config["TESTING"] = True
    def client(email="admin@example.test"):
        test_client = app.test_client()
        with test_client.session_transaction() as session:
            session["identity"] = {"email": email, "sub": email}
            session["csrf"] = "csrf"
        return test_client
    return client, fake, tmp_path / "data/cronjobs/connection.json"


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_install_command(case):
    if case == "normaal":
        command = cronjobs.install_command(PUBLIC_KEY, "192.168.1.164", "a" * 40)
        assert f"https://raw.githubusercontent.com/strammermax/ControlDeck/{'a' * 40}/scripts/controldeck-agent.py" in command
        assert f"echo '{cronjobs.agent_checksum()}  /tmp/controldeck-agent' | sha256sum -c -" in command
        assert f'restrict,from="192.168.1.164",command="/usr/local/sbin/controldeck-agent" {PUBLIC_KEY}' in command
        # Idempotent: the key line is only added when the key is not present yet (shared cluster authorized_keys).
        assert f"grep -qF '{'A' * 68}' /root/.ssh/authorized_keys" in command
        # The checksum is verified before anything is installed.
        assert command.index("sha256sum -c") < command.index("install -m 0755")
    elif case == "boundary":
        assert "/ControlDeck/main/scripts/" in cronjobs.install_command(PUBLIC_KEY, "10.0.0.1", "development")
    else:
        for key, source in ((None, "1.2.3.4"), ("ssh-rsa AAAA x", "1.2.3.4"), (PUBLIC_KEY + "'; rm -rf / #", "1.2.3.4"), (PUBLIC_KEY, "1.2.3.4'; id #"), (PUBLIC_KEY, "host.example")):
            with pytest.raises(ValueError):
                cronjobs.install_command(key, source, "a" * 40)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_node_state(case):
    ok = lambda version: {"ok": True, "data": {"ok": True, "data": {"agentVersion": version}}}
    if case == "normaal":
        assert cronjobs.node_state(ok(cronjobs.required_agent_version())) == "ready"
    elif case == "boundary":
        assert cronjobs.node_state(ok(cronjobs.required_agent_version() + 1)) == "ready"
        assert cronjobs.node_state(ok(0)) == "outdated"
    else:
        assert cronjobs.node_state({"ok": False, "error": "not_authorized"}) == "not_installed"
        assert cronjobs.node_state({"ok": False, "error": "hostkey_changed"}) == "hostkey_changed"
        assert cronjobs.node_state({"ok": False, "error": "timeout"}) == "unreachable"
        assert cronjobs.node_state({"ok": True, "data": {"ok": False}}) == "unreachable"
        assert cronjobs.node_state(ok("1")) == "outdated"


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_enrol_flow(env, case):
    client, fake, marker = env
    admin = client()
    if case == "faal":
        assert admin.post("/api/cronjobs/agent/trust", headers=H, json={"node": "pve-amd", "address": "192.168.1.98", "fingerprint": "SHA256:" + "b" * 43}).status_code == 400
        assert admin.post("/api/cronjobs/agent/scan", headers=H, json={"node": "pve-amd", "address": "192.168.1.98; id"}).status_code == 400
        assert admin.post("/api/cronjobs/agent/scan", headers=H, json={"node": "../x", "address": "192.168.1.98"}).status_code == 400
        fake.available = False
        overview = admin.get("/api/cronjobs/agent").json
        assert overview["proxy"] is False and "draait niet" in overview["error"]
        assert admin.post("/api/cronjobs/agent/key", headers=H).status_code == 503
        return
    assert admin.post("/api/cronjobs/agent/key", headers=H).json["publicKey"] == PUBLIC_KEY
    assert admin.post("/api/cronjobs/agent/scan", headers=H, json={"node": "pve-amd", "address": "192.168.1.98"}).json["fingerprint"] == FINGERPRINT
    assert admin.post("/api/cronjobs/agent/trust", headers=H, json={"node": "pve-amd", "address": "192.168.1.98", "fingerprint": FINGERPRINT}).status_code == 200
    command = admin.post("/api/cronjobs/agent/install-command", headers=H, json={"node": "pve-amd", "address": "192.168.1.98"}).json["command"]
    assert 'from="192.168.1.164"' in command
    test = admin.post("/api/cronjobs/agent/test", headers=H, json={"node": "pve-amd"}).json
    assert test["state"] == "ready" and test["hostname"] == "pve-amd"
    assert fake.calls[-1]["actor"] == "admin@example.test"
    overview = admin.get("/api/cronjobs/agent").json
    assert overview["nodes"][0]["state"] == "ready" and json.loads(marker.read_text())["nodes"] == ["pve-amd"]
    assert next(m for m in admin.get("/api/installations").json["modules"] if m["id"] == "cronjobs")["installed"] is True
    if case == "boundary":
        # Agent not installed yet on a second node: enrolled, but not counted as installed.
        fake.nodes.append(("pve-intel", "192.168.1.99"))
        fake.info["pve-intel"] = {"ok": False, "error": "not_authorized", "message": "x"}
        states = {n["node"]: n["state"] for n in admin.get("/api/cronjobs/agent").json["nodes"]}
        assert states == {"pve-amd": "ready", "pve-intel": "not_installed"} and json.loads(marker.read_text())["nodes"] == ["pve-amd"]
        assert admin.delete("/api/cronjobs/connection", headers=H).json == {"connected": False}
        assert fake.nodes == [] and not marker.exists()


def test_admin_only_and_csrf(env):
    client, fake, marker = env
    assert client("nobody@example.test").get("/api/cronjobs/agent").status_code == 401
    viewer = client("viewer@example.test")
    assert viewer.get("/api/cronjobs/agent").status_code == 403
    assert viewer.post("/api/cronjobs/agent/key", headers=H).status_code == 403
    assert viewer.delete("/api/cronjobs/connection", headers=H).status_code == 403
    assert client().post("/api/cronjobs/agent/key").status_code == 403  # missing CSRF token
    assert fake.calls == []


def test_bundle_and_image_ship_the_agent():
    """The install command's checksum is computed from this file, so the release must contain it."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    assert '"scripts/controldeck-agent.py"' in (root / "scripts/package.py").read_text()
    assert "COPY scripts/controldeck-agent.py scripts/controldeck-agent.py" in (root / "Dockerfile").read_text()


def test_removal_command_keeps_the_cluster_authorized_keys_symlink():
    """Regression: on Proxmox /root/.ssh/authorized_keys is a symlink to the cluster-wide /etc/pve/priv/authorized_keys.
    `sed -i` would replace that symlink with a plain file; the removal command must write through the symlink."""
    from pathlib import Path
    source = (Path(__file__).resolve().parent.parent / "frontend/components/module-remove.tsx").read_text(encoding="utf-8")
    cronjobs_entry = source[source.index("cronjobs:{"):source.index("termix:{")]
    assert "sed -i" not in cronjobs_entry.replace("Gebruik geen sed -i", "")
    assert "cat /tmp/authorized_keys.new > /root/.ssh/authorized_keys" in cronjobs_entry
    # The install command appends (>>), which also writes through the symlink.
    assert ">> /root/.ssh/authorized_keys" in cronjobs.install_command(PUBLIC_KEY, "192.168.1.164", "a" * 40)
