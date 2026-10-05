import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AGENT = ROOT / "scripts/controldeck-agent.py"
spec = importlib.util.spec_from_file_location("controldeck_agent", AGENT)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)
posix = pytest.mark.skipif(os.name != "posix", reason="Runs jobs with /bin/sh and fcntl; covered on Linux in CI")


@pytest.fixture
def node(tmp_path, monkeypatch):
    """A fake node file system; every user exists except 'ghost'."""
    monkeypatch.setenv("CONTROLDECK_AGENT_ROOT", str(tmp_path))
    monkeypatch.setenv("CONTROLDECK_AGENT_PATH", "/usr/local/sbin/controldeck-agent")
    monkeypatch.setattr(agent, "user_exists", lambda name: name != "ghost")
    (tmp_path / "etc/cron.d").mkdir(parents=True)
    return tmp_path


def call(action, payload=None):
    return agent.handle(action, json.dumps(payload or {}))


JOB = {"id": "backup-db", "schedule": "30 2 * * *", "command": "/usr/local/bin/backup.sh --full", "description": "Nachtelijke backup", "actor": "admin@example.test"}


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_validate_schedule(case):
    if case == "normaal":
        assert agent.validate_schedule("30 2 * * *") == "30 2 * * *"
        assert agent.validate_schedule("*/15 8-18 * * mon-fri") == "*/15 8-18 * * mon-fri"
    elif case == "boundary":
        assert agent.validate_schedule("@daily") == "@daily"
        assert agent.validate_schedule("59 23 31 12 7") == "59 23 31 12 7"
        assert agent.validate_schedule("  0   0 1,15 JAN,jul *  ") == "0 0 1,15 JAN,jul *"
    else:
        for invalid in ("60 * * * *", "* 24 * * *", "* * 0 * *", "* * * 13 *", "* * * * 8", "* * * *", "* * * * * *", "@reboot", "*/0 * * * *",
                        "1-x * * * *", "", None, "0 0 * * * ; rm -rf /", "x" * 101):
            with pytest.raises(agent.AgentError):
                agent.validate_schedule(invalid)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_put_list_and_cron_file(node, case):
    if case == "normaal":
        result = call("cron.put", JOB)
        assert result["ok"] and result["data"]["user"] == "root" and result["data"]["enabled"] is True
        cron = (node / "etc/cron.d/controldeck").read_text()
        assert "30 2 * * * root /usr/local/sbin/controldeck-agent run backup-db\n" in cron
        # The command itself never appears in the cron file; it stays in the root-only job definition.
        assert "backup.sh" not in cron
        listed = call("cron.list")["data"]["jobs"]
        assert [job["id"] for job in listed] == ["backup-db"] and listed[0]["lastRun"] is None
    elif case == "boundary":
        call("cron.put", JOB)
        created = json.loads((node / "etc/controldeck-agent/jobs/backup-db.json").read_text())["createdAt"]
        paused = call("cron.put", {**JOB, "enabled": False, "user": "www-data", "timeoutMinutes": 1440, "command": "x" * 1000})
        assert paused["ok"] and paused["data"]["createdAt"] == created
        assert "# paused: 30 2 * * * root" in (node / "etc/cron.d/controldeck").read_text()
    else:
        for invalid in ({**JOB, "id": "Backup"}, {**JOB, "id": "a" * 41}, {**JOB, "user": "ghost"}, {**JOB, "user": "root;id"},
                        {**JOB, "command": "echo a\necho b"}, {**JOB, "command": " "}, {**JOB, "command": "x" * 1001},
                        {**JOB, "schedule": "bad"}, {**JOB, "extra": 1}, {**JOB, "enabled": "yes"}, {**JOB, "timeoutMinutes": 0}):
            assert call("cron.put", invalid)["ok"] is False
        assert not (node / "etc/cron.d/controldeck").exists()


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_delete_and_audit(node, case):
    call("cron.put", JOB)
    if case == "normaal":
        assert call("cron.delete", {"id": "backup-db", "actor": "admin@example.test"})["data"]["deleted"] is True
        assert "backup-db" not in (node / "etc/cron.d/controldeck").read_text()
        entries = [json.loads(line) for line in (node / "var/log/controldeck-agent.log").read_text().splitlines()]
        assert [(e["action"], e["result"], e["actor"]) for e in entries] == [("cron.put", "ok", "admin@example.test"), ("cron.delete", "ok", "admin@example.test")]
    elif case == "boundary":
        call("cron.delete", {"id": "backup-db"})
        assert (node / "etc/cron.d/controldeck").read_text().startswith(agent.CRON_HEADER)
    else:
        assert call("cron.delete", {"id": "unknown"})["error"] == "not_found"
        assert call("cron.delete", {"id": "../../etc/passwd"})["error"] == "not_found"


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_handle_rejects_unknown_input(node, case):
    if case == "normaal":
        assert call("info")["data"]["agentVersion"] == agent.AGENT_VERSION
    elif case == "boundary":
        assert agent.handle("cron.list", "")["ok"] is True  # empty input is an empty object
        assert agent.handle("cron.list", "x" * agent.MAX_INPUT)["error"] == "invalid_json"
    else:
        assert agent.handle("shell", "{}")["error"] == "unknown_action"
        assert agent.handle("cron.list", "[1]")["error"] == "invalid_json"
        assert agent.handle("cron.put", "x" * (agent.MAX_INPUT + 1))["error"] == "too_large"


def write_run(node, job_id, run_id, start, status="succeeded", code=0, log=b""):
    directory = node / "var/lib/controldeck-agent/runs" / job_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{run_id}.json").write_text(json.dumps({"runId": run_id, "jobId": job_id, "start": start, "end": start + 2, "duration": 2, "exitCode": code, "status": status}))
    (directory / f"{run_id}.log").write_bytes(log)


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_history_log_runs_and_rotation(node, case):
    call("cron.put", JOB)
    now = time.time()
    if case == "normaal":
        write_run(node, "backup-db", "20261005T010000Z-aaaaaa", now - 7200, log=b"started\ndone\n")
        write_run(node, "backup-db", "20261005T020000Z-bbbbbb", now - 3600, "failed", 3)
        history = call("cron.history", {"id": "backup-db"})["data"]["runs"]
        assert [run["status"] for run in history] == ["failed", "succeeded"]
        assert call("cron.list")["data"]["jobs"][0]["lastRun"]["exitCode"] == 3
        log = call("cron.log", {"id": "backup-db", "runId": "20261005T010000Z-aaaaaa", "offset": 8})["data"]
        assert log["content"] == "done\n" and log["offset"] == 13
        runs = call("cron.runs", {"since": now - 5400})["data"]["runs"]
        assert [(run["source"], run["status"]) for run in runs] == [("controldeck", "failed")]
    elif case == "boundary":
        for index in range(25):
            write_run(node, "backup-db", f"202610{index + 1:02d}T000000Z-{index:06x}", now - 100 + index)
        write_run(node, "backup-db", "20261001T000000Z-ffffff", now - 15 * 86400)  # older than 14 days
        agent.rotate("backup-db")
        remaining = sorted(path.stem for path in (node / "var/lib/controldeck-agent/runs/backup-db").glob("*.json"))
        assert len(remaining) == agent.KEEP_RUNS and "20261001T000000Z-ffffff" not in remaining
    else:
        assert call("cron.log", {"id": "backup-db", "runId": "../../etc/shadow"})["error"] == "invalid_input"
        assert call("cron.log", {"id": "backup-db", "runId": "20261005T010000Z-aaaaaa", "offset": -1})["error"] == "invalid_input"
        assert call("cron.history", {"id": "backup-db", "limit": 101})["error"] == "invalid_input"
        assert call("cron.runs", {"limit": 501})["error"] == "invalid_input"


SYSTEM_CRONTAB = "SHELL=/bin/sh\n# m h dom mon dow user command\n17 * * * * root cd / && run-parts --report /etc/cron.hourly\n@reboot root /opt/start.sh\n"


@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_system_entries_adopt_and_release(node, case):
    (node / "etc/crontab").write_text(SYSTEM_CRONTAB)
    (node / "etc/cron.d/pve-backup").write_text("PATH=/usr/bin\n0 3 * * sun root /usr/bin/vzdump --all\n")
    (node / "etc/cron.d/controldeck").write_text(agent.CRON_HEADER)
    entries = call("cron.list")["data"]["system"]
    assert {(e["source"], e["schedule"], e["user"]) for e in entries} == {("/etc/crontab", "17 * * * *", "root"), ("/etc/crontab", "@reboot", "root"), ("/etc/cron.d/pve-backup", "0 3 * * sun", "root")}
    vzdump = next(e for e in entries if "vzdump" in e["command"])
    if case == "normaal":
        adopted = call("cron.adopt", {"ref": vzdump["ref"], "id": "weekly-vzdump"})["data"]
        assert adopted["adopted"] is True and adopted["adoptedFrom"] == "/etc/cron.d/pve-backup"
        original = (node / "etc/cron.d/pve-backup").read_text()
        assert "# disabled by ControlDeck" in original and "(job weekly-vzdump): 0 3 * * sun root /usr/bin/vzdump --all" in original
        assert "run weekly-vzdump" in (node / "etc/cron.d/controldeck").read_text()
        assert list((node / "var/lib/controldeck-agent/backups").glob("pve-backup.*.bak"))
        # Released: original line back, job gone.
        assert call("cron.release", {"id": "weekly-vzdump"})["ok"]
        assert (node / "etc/cron.d/pve-backup").read_text() == "PATH=/usr/bin\n0 3 * * sun root /usr/bin/vzdump --all\n"
        assert "weekly-vzdump" not in (node / "etc/cron.d/controldeck").read_text()
    elif case == "boundary":
        call("cron.adopt", {"ref": vzdump["ref"], "id": "weekly-vzdump"})
        assert all("vzdump" not in e["command"] for e in call("cron.list")["data"]["system"])  # the disabled line is no longer an active entry
        assert call("cron.delete", {"id": "weekly-vzdump"})["error"] == "adopted"
    else:
        reboot = next(e for e in entries if e["schedule"] == "@reboot")
        assert call("cron.adopt", {"ref": reboot["ref"], "id": "start"})["error"] == "invalid_schedule"
        assert call("cron.adopt", {"ref": "0" * 16, "id": "x"})["error"] == "not_found"
        assert call("cron.adopt", {"ref": "../etc", "id": "x"})["error"] == "invalid_input"
        assert call("cron.release", {"id": "backup-db"})["error"] == "not_found"
        assert (node / "etc/cron.d/pve-backup").read_text().count("#") == 0


@posix
@pytest.mark.parametrize("case", ["normaal", "boundary", "faal"])
def test_execute_records_runs(node, case):
    user = agent.current_user()
    if case == "normaal":
        call("cron.put", {**JOB, "user": user, "command": "echo hallo; echo fout >&2"})
        record = agent.execute("backup-db")
        assert record["status"] == "succeeded" and record["exitCode"] == 0 and record["duration"] >= 0
        log = (node / "var/lib/controldeck-agent/runs/backup-db" / f"{record['runId']}.log").read_text()
        assert "hallo" in log and "fout" in log
    elif case == "boundary":
        call("cron.put", {**JOB, "user": user, "command": "head -c 300000 /dev/zero"})
        record = agent.execute("backup-db")
        log = (node / "var/lib/controldeck-agent/runs/backup-db" / f"{record['runId']}.log").read_bytes()
        assert record["status"] == "succeeded" and log.endswith(b"[... uitvoer ingekort ...]\n") and len(log) < agent.MAX_OUTPUT_PER_RUN + 100
        # A run that is still busy (lock held) makes the next start skip instead of running twice.
        import fcntl
        with open(node / "var/lib/controldeck-agent/runs/backup-db/.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            assert agent.execute("backup-db")["status"] == "skipped"
    else:
        call("cron.put", {**JOB, "user": user, "command": "exit 3"})
        record = agent.execute("backup-db")
        assert record["status"] == "failed" and record["exitCode"] == 3
        with pytest.raises(agent.AgentError):
            agent.execute("unknown")


@posix
def test_ssh_forced_command_entry(node):
    env = {**os.environ, "SSH_ORIGINAL_COMMAND": "cron.list"}
    result = subprocess.run([sys.executable, str(AGENT)], input=b"{}", capture_output=True, env=env, timeout=30)
    assert result.returncode == 0 and json.loads(result.stdout)["ok"] is True
    # Arguments are ignored when called over SSH; only the single action word counts.
    env["SSH_ORIGINAL_COMMAND"] = "cron.list; rm -rf /"
    result = subprocess.run([sys.executable, str(AGENT), "run", "x"], input=b"{}", capture_output=True, env=env, timeout=30)
    assert result.returncode == 1 and json.loads(result.stdout)["error"] == "unknown_action"


def test_cli_without_ssh_only_runs_jobs():
    assert agent.main(["cron.put"]) == 2
    assert agent.main(["run", "../x"]) == 2
