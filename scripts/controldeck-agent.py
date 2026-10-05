#!/usr/bin/env python3
"""ControlDeck node agent: a fixed set of actions on a Proxmox node, nothing else.

Two entry points:

* SSH (forced command). ``authorized_keys`` starts this script for ControlDeck's key, whatever the
  client asked. The requested action is the single word in ``SSH_ORIGINAL_COMMAND``; its input is a JSON
  object on stdin (max 64 KiB). The answer is one JSON object on stdout.
* Cron. ``/etc/cron.d/controldeck`` runs ``controldeck-agent run <id>`` for every ControlDeck job; the
  agent executes the stored command and records start, end, duration, exit code and output per run.

Only ControlDeck's own jobs (``/etc/cron.d/controldeck``) are changed. Other cron entries are read-only,
except an explicit adopt/release, which comments a line out (with a backup) or restores it.
Design: docs/NODE-AGENT.md. Standard library only; Python 3.9+.
"""
import datetime
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

AGENT_VERSION = 1
MAX_INPUT = 64 * 1024
MAX_OUTPUT_PER_RUN = 256 * 1024
KEEP_RUNS = 20
KEEP_DAYS = 14
JOB_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
RUN_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{6}")
REF = re.compile(r"[0-9a-f]{16}")
SPECIAL_SCHEDULES = {"@hourly", "@daily", "@weekly", "@monthly", "@yearly", "@annually", "@midnight"}
MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
DAYS = "sun mon tue wed thu fri sat".split()
FIELD_RANGES = [(0, 59, []), (0, 23, []), (1, 31, []), (1, 12, MONTHS), (0, 7, DAYS)]
CRON_HEADER = "# Managed by ControlDeck (controldeck-agent). Do not edit: changes are overwritten.\n"
ADOPT_MARK = "# disabled by ControlDeck"


class AgentError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


# --- paths (a different root keeps tests away from the real system) -------------------------------------

def root():
    return Path(os.environ.get("CONTROLDECK_AGENT_ROOT", "/"))


def paths():
    base = root()
    return {
        "jobs": base / "etc/controldeck-agent/jobs",
        "cron": base / "etc/cron.d/controldeck",
        "cron_d": base / "etc/cron.d",
        "crontab": base / "etc/crontab",
        "runs": base / "var/lib/controldeck-agent/runs",
        "backups": base / "var/lib/controldeck-agent/backups",
        "audit": base / "var/log/controldeck-agent.log",
    }


def agent_command():
    return os.environ.get("CONTROLDECK_AGENT_PATH", "/usr/local/sbin/controldeck-agent")


def now():
    return time.time()


def write_atomic(path, text, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".controldeck-")
    try:
        os.chmod(temporary, mode)
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def audit(action, payload, result):
    entry = {"at": int(now()), "action": action, "actor": str(payload.get("actor", ""))[:120], "result": result}
    if "id" in payload:
        entry["id"] = str(payload["id"])[:40]
    log = paths()["audit"]
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as output:
        output.write(json.dumps(entry) + "\n")
    try:
        os.chmod(log, 0o600)
    except OSError:
        pass


# --- validation -----------------------------------------------------------------------------------------

def validate_field(value, low, high, names):
    for part in value.split(","):
        base, _, step = part.partition("/")
        if step and (not step.isdigit() or not 1 <= int(step) <= high):
            return False
        if base == "*":
            continue
        start, _, end = base.partition("-")
        for item in (start, end) if end else (start,):
            item = item.lower()
            if item in names:
                continue
            if not item.isdigit() or not low <= int(item) <= high:
                return False
    return bool(value)


def validate_schedule(value):
    if not isinstance(value, str) or len(value) > 100:
        raise AgentError("invalid_schedule", "Ongeldig schema.")
    value = " ".join(value.split())
    if value in SPECIAL_SCHEDULES:
        return value
    fields = value.split(" ")
    if len(fields) != 5 or not all(validate_field(field, *spec) for field, spec in zip(fields, FIELD_RANGES)):
        raise AgentError("invalid_schedule", "Ongeldig schema: gebruik vijf cronvelden of @hourly/@daily/@weekly/@monthly.")
    return value


def user_exists(name):
    try:
        import pwd
        pwd.getpwnam(name)
        return True
    except (ImportError, KeyError):
        return False


def validate_job(payload, existing=None):
    if not isinstance(payload, dict):
        raise AgentError("invalid_input", "Ongeldige invoer.")
    allowed = {"id", "description", "schedule", "user", "command", "enabled", "logs", "timeoutMinutes", "actor"}
    if not set(payload) <= allowed:
        raise AgentError("invalid_input", "Onbekende velden.")
    job_id = payload.get("id")
    if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
        raise AgentError("invalid_id", "Ongeldige naam: kleine letters, cijfers en '-', maximaal 40 tekens.")
    command = payload.get("command")
    if not isinstance(command, str) or not command.strip() or len(command) > 1000 or any(c in command for c in "\n\r\0"):
        raise AgentError("invalid_command", "Ongeldig commando: één regel, maximaal 1000 tekens.")
    user = payload.get("user", "root")
    if not isinstance(user, str) or not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user) or not user_exists(user):
        raise AgentError("invalid_user", "Onbekende gebruiker.")
    description = payload.get("description", "")
    if not isinstance(description, str) or len(description) > 200 or any(c in description for c in "\n\r\0"):
        raise AgentError("invalid_input", "Ongeldige omschrijving.")
    timeout = payload.get("timeoutMinutes")
    if timeout is not None and (not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 1440):
        raise AgentError("invalid_input", "Time-out moet tussen 1 en 1440 minuten liggen.")
    for flag in ("enabled", "logs"):
        if flag in payload and not isinstance(payload[flag], bool):
            raise AgentError("invalid_input", f"{flag} moet waar of onwaar zijn.")
    stamp = int(now())
    job = {
        "id": job_id, "description": description, "schedule": validate_schedule(payload.get("schedule")),
        "user": user, "command": command, "enabled": payload.get("enabled", True), "logs": payload.get("logs", True),
        "timeoutMinutes": timeout, "createdAt": (existing or {}).get("createdAt", stamp), "updatedAt": stamp,
    }
    if existing and existing.get("adopted"):
        job["adopted"] = existing["adopted"]
    return job


# --- jobs and the managed cron file ---------------------------------------------------------------------

def load_jobs():
    directory = paths()["jobs"]
    jobs = {}
    if directory.is_dir():
        for file in sorted(directory.glob("*.json")):
            try:
                job = json.loads(file.read_text(encoding="utf-8"))
                if isinstance(job, dict) and JOB_ID.fullmatch(str(job.get("id", ""))) and job["id"] == file.stem:
                    jobs[job["id"]] = job
            except (OSError, ValueError):
                continue
    return jobs


def save_job(job):
    directory = paths()["jobs"]
    directory.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass
    write_atomic(directory / f"{job['id']}.json", json.dumps(job, indent=2) + "\n", 0o600)


def render_cron(jobs):
    """All jobs run through the agent as root; the agent switches to the job user itself."""
    lines = [CRON_HEADER, "SHELL=/bin/sh\n", "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n"]
    for job in sorted(jobs.values(), key=lambda item: item["id"]):
        entry = f"{job['schedule']} root {agent_command()} run {job['id']}\n"
        lines.append(f"# {job['id']}: {job.get('description', '')}".rstrip() + "\n")
        lines.append(entry if job.get("enabled", True) else f"# paused: {entry}")
    return "".join(lines)


def write_cron(jobs):
    write_atomic(paths()["cron"], render_cron(jobs), 0o644)


# --- runs -----------------------------------------------------------------------------------------------

def run_dir(job_id):
    return paths()["runs"] / job_id


def read_run(job_id, run_id):
    try:
        record = json.loads((run_dir(job_id) / f"{run_id}.json").read_text(encoding="utf-8"))
        return record if isinstance(record, dict) else None
    except (OSError, ValueError):
        return None


def list_runs(job_id, limit):
    directory = run_dir(job_id)
    if not directory.is_dir():
        return []
    records = [read_run(job_id, file.stem) for file in sorted(directory.glob("*.json"), reverse=True)[:limit]]
    return [record for record in records if record]


def rotate(job_id):
    directory = run_dir(job_id)
    if not directory.is_dir():
        return
    cutoff = now() - KEEP_DAYS * 86400
    for index, file in enumerate(sorted(directory.glob("*.json"), reverse=True)):
        record = read_run(job_id, file.stem) or {}
        if index >= KEEP_RUNS or (record.get("start") or 0) < cutoff:
            for suffix in (".json", ".log"):
                (directory / f"{file.stem}{suffix}").unlink(missing_ok=True)


def new_run_id():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


def execute(job_id, run_id=None, trigger="schedule"):
    """Runs one job: lock, record, execute (as the job user), capture output, record result, rotate."""
    jobs = load_jobs()
    job = jobs.get(job_id)
    if job is None:
        raise AgentError("not_found", "Onbekende job.")
    run_id = run_id or new_run_id()
    directory = run_dir(job_id)
    directory.mkdir(parents=True, exist_ok=True)
    record_path, log_path = directory / f"{run_id}.json", directory / f"{run_id}.log"
    record = {"runId": run_id, "jobId": job_id, "trigger": trigger, "start": now(), "end": None, "duration": None, "exitCode": None, "status": "running"}
    lock_path = directory / ".lock"
    lock = open(lock_path, "a")
    try:
        import fcntl
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            record.update(end=now(), duration=0, status="skipped", message="Vorige run was nog bezig.")
            write_atomic(record_path, json.dumps(record), 0o600)
            lock.close()
            return record
    except ImportError:
        pass
    try:
        write_atomic(record_path, json.dumps(record), 0o600)
        command = ["/bin/sh", "-c", job["command"]]
        if job["user"] != current_user():
            command = ["runuser", "-u", job["user"], "--"] + command
        timeout = (job.get("timeoutMinutes") or 0) * 60 or None
        written = 0
        with open(log_path, "wb") as log:
            os.chmod(log_path, 0o600)
            try:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            except OSError as error:
                log.write(f"Kan niet starten: {error}\n".encode())
                record.update(end=now(), exitCode=127, status="failed")
                return record
            started = time.monotonic()
            while True:
                chunk = process.stdout.read1(8192) if hasattr(process.stdout, "read1") else process.stdout.read(8192)
                if not chunk:
                    break
                if job.get("logs", True) and written < MAX_OUTPUT_PER_RUN:
                    part = chunk[: MAX_OUTPUT_PER_RUN - written]
                    log.write(part)
                    log.flush()
                    written += len(part)
                if timeout and time.monotonic() - started > timeout:
                    process.kill()
                    record["message"] = "Gestopt na de time-out."
                    break
            code = process.wait()
            if written >= MAX_OUTPUT_PER_RUN:
                log.write(b"\n[... uitvoer ingekort ...]\n")
        end = now()
        record.update(end=end, duration=round(end - record["start"], 3), exitCode=code, status="succeeded" if code == 0 and "message" not in record else "failed")
        return record
    finally:
        write_atomic(record_path, json.dumps(record), 0o600)
        lock.close()
        rotate(job_id)


def current_user():
    try:
        import pwd
        return pwd.getpwuid(os.geteuid()).pw_name
    except (ImportError, KeyError, AttributeError):
        return "root"


# --- system (non-ControlDeck) cron entries --------------------------------------------------------------

def entry_ref(source, line):
    return hashlib.sha256(f"{source}\n{line}".encode()).hexdigest()[:16]


def parse_cron_lines(text, source, with_user):
    entries = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or re.match(r"[A-Za-z_][A-Za-z0-9_]*\s*=", line):
            continue
        parts = line.split(None, 1 if line.startswith("@") else 5)
        count = 1 if line.startswith("@") else 5
        if len(parts) <= count:
            continue
        schedule = " ".join(parts[:count])
        rest = parts[count]
        user = "root"
        if with_user:
            user, _, rest = rest.partition(" ")
            rest = rest.strip()
        if not rest:
            continue
        entries.append({"ref": entry_ref(source, raw), "source": source, "schedule": schedule, "user": user, "command": rest, "line": raw})
    return entries


def root_crontab():
    try:
        result = subprocess.run(["crontab", "-l", "-u", "root"], capture_output=True, text=True, timeout=10)
        return result.stdout if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def system_entries():
    p = paths()
    entries = []
    if p["crontab"].is_file():
        entries += parse_cron_lines(p["crontab"].read_text(encoding="utf-8", errors="replace"), "/etc/crontab", True)
    if p["cron_d"].is_dir():
        for file in sorted(p["cron_d"].iterdir()):
            if file.name == "controldeck" or not file.is_file() or file.name.startswith(".") or "~" in file.name:
                continue
            entries += parse_cron_lines(file.read_text(encoding="utf-8", errors="replace"), f"/etc/cron.d/{file.name}", True)
    if os.environ.get("CONTROLDECK_AGENT_ROOT") is None:
        entries += parse_cron_lines(root_crontab(), "crontab:root", False)
    return entries


def system_timers():
    if os.environ.get("CONTROLDECK_AGENT_ROOT") is not None:
        return []
    try:
        result = subprocess.run(["systemctl", "list-timers", "--all", "--output=json"], capture_output=True, text=True, timeout=10)
        timers = json.loads(result.stdout) if result.returncode == 0 else []
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    def stamp(value):
        return value / 1_000_000 if isinstance(value, (int, float)) and value > 0 else None
    return [{"unit": str(item.get("unit", "")), "activates": str(item.get("activates", "")), "next": stamp(item.get("next")), "last": stamp(item.get("last"))}
            for item in timers if isinstance(item, dict)][:200]


# --- adopt / release ------------------------------------------------------------------------------------

def source_path(source):
    if source == "/etc/crontab":
        return paths()["crontab"]
    if source.startswith("/etc/cron.d/") and "/" not in source[len("/etc/cron.d/"):]:
        return paths()["cron_d"] / source[len("/etc/cron.d/"):]
    raise AgentError("unsupported", "Alleen regels uit /etc/crontab en /etc/cron.d kunnen worden overgenomen.")


def replace_line(path, old, new):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.rstrip("\n") == old:
            lines[index] = new + "\n"
            write_atomic(path, "".join(lines), os.stat(path).st_mode & 0o777)
            return
    raise AgentError("not_found", "De cronregel is niet (meer) gevonden.")


def adopt(payload):
    ref, job_id = payload.get("ref"), payload.get("id")
    if not isinstance(ref, str) or not REF.fullmatch(ref):
        raise AgentError("invalid_input", "Ongeldige verwijzing.")
    entry = next((item for item in system_entries() if item["ref"] == ref), None)
    if entry is None:
        raise AgentError("not_found", "De cronregel is niet (meer) gevonden.")
    if job_id in load_jobs():
        raise AgentError("exists", "Er bestaat al een job met deze naam.")
    path = source_path(entry["source"])
    job = validate_job({"id": job_id, "schedule": entry["schedule"], "user": entry["user"], "command": entry["command"], "description": f"Overgenomen uit {entry['source']}"})
    backups = paths()["backups"]
    backups.mkdir(parents=True, exist_ok=True)
    backup = backups / f"{path.name}.{int(now())}.bak"
    shutil.copy2(path, backup)
    marker = f"{ADOPT_MARK} {datetime.date.today().isoformat()} (job {job_id}): {entry['line']}"
    job["adopted"] = {"source": entry["source"], "line": entry["line"], "marker": marker, "backup": str(backup)}
    replace_line(path, entry["line"], marker)
    save_job(job)
    jobs = load_jobs()
    write_cron(jobs)
    return job


def release(job_id):
    jobs = load_jobs()
    job = jobs.get(job_id)
    if job is None or not job.get("adopted"):
        raise AgentError("not_found", "Geen overgenomen job met deze naam.")
    info = job["adopted"]
    replace_line(source_path(info["source"]), info["marker"], info["line"])
    remove_job(job_id)
    return {"id": job_id, "restored": info["source"]}


def remove_job(job_id):
    (paths()["jobs"] / f"{job_id}.json").unlink(missing_ok=True)
    jobs = load_jobs()
    write_cron(jobs)
    shutil.rmtree(run_dir(job_id), ignore_errors=True)


# --- journal (which non-ControlDeck cron jobs started) --------------------------------------------------

def journal_cron_starts(since, limit):
    if os.environ.get("CONTROLDECK_AGENT_ROOT") is not None:
        return []
    try:
        result = subprocess.run(["journalctl", "-u", "cron", "--since", f"@{int(since)}", "-o", "json", "--no-pager", "-n", str(limit * 4)],
                                capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return []
    starts = []
    for line in result.stdout.splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        match = re.search(r"\((\S+)\) CMD \((.*)\)$", str(item.get("MESSAGE", "")))
        if not match or f"{agent_command()} run " in match.group(2):
            continue
        stamp = int(item.get("__REALTIME_TIMESTAMP", 0)) / 1_000_000
        starts.append({"source": "system", "user": match.group(1), "command": match.group(2)[:300], "start": stamp, "status": "started"})
    return starts[-limit:]


# --- actions --------------------------------------------------------------------------------------------

def action_info(payload):
    version = ""
    try:
        version = subprocess.run(["pveversion"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return {"agentVersion": AGENT_VERSION, "hostname": socket.gethostname(), "pveVersion": version[:120], "python": sys.version.split()[0]}


def summary(job):
    last = list_runs(job["id"], 1)
    return {**{key: job.get(key) for key in ("id", "description", "schedule", "user", "command", "enabled", "logs", "timeoutMinutes", "createdAt", "updatedAt")},
            "adopted": bool(job.get("adopted")), "adoptedFrom": (job.get("adopted") or {}).get("source"), "lastRun": last[0] if last else None}


def action_list(payload):
    return {"jobs": [summary(job) for job in load_jobs().values()], "system": system_entries(), "timers": system_timers()}


def action_put(payload):
    existing = load_jobs().get(payload.get("id"))
    job = validate_job(payload, existing)
    save_job(job)
    write_cron(load_jobs())
    return summary(job)


def require_job(payload):
    job_id = payload.get("id")
    if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id) or job_id not in load_jobs():
        raise AgentError("not_found", "Onbekende job.")
    return job_id


def action_delete(payload):
    job_id = require_job(payload)
    if load_jobs()[job_id].get("adopted"):
        raise AgentError("adopted", "Deze job is overgenomen; geef hem terug of verwijder hem na teruggeven.")
    remove_job(job_id)
    return {"id": job_id, "deleted": True}


def action_run(payload):
    """Starts the job in the background and returns the run id for live log polling."""
    job_id = require_job(payload)
    run_id = new_run_id()
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "run", job_id, "--run-id", run_id, "--trigger", "manual"],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"id": job_id, "runId": run_id}


def action_history(payload):
    job_id = require_job(payload)
    limit = payload.get("limit", KEEP_RUNS)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise AgentError("invalid_input", "limit moet tussen 1 en 100 liggen.")
    return {"id": job_id, "runs": list_runs(job_id, limit)}


def action_log(payload):
    job_id = require_job(payload)
    run_id, offset = payload.get("runId"), payload.get("offset", 0)
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id) or not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise AgentError("invalid_input", "Ongeldige run of offset.")
    record = read_run(job_id, run_id)
    path = run_dir(job_id) / f"{run_id}.log"
    content = b""
    if path.is_file():
        with open(path, "rb") as log:
            log.seek(offset)
            content = log.read(MAX_INPUT)
    return {"id": job_id, "runId": run_id, "status": (record or {}).get("status", "pending"), "exitCode": (record or {}).get("exitCode"),
            "offset": offset + len(content), "content": content.decode("utf-8", errors="replace")}


def action_runs(payload):
    since, limit = payload.get("since", now() - 86400), payload.get("limit", 200)
    if not isinstance(since, (int, float)) or isinstance(since, bool) or not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500:
        raise AgentError("invalid_input", "Ongeldige periode of limiet.")
    runs = []
    for job in load_jobs().values():
        runs += [{"source": "controldeck", "jobId": job["id"], "description": job.get("description", ""), **record}
                 for record in list_runs(job["id"], KEEP_RUNS) if (record.get("start") or 0) >= since]
    runs += journal_cron_starts(since, limit)
    return {"runs": sorted(runs, key=lambda item: item.get("start") or 0, reverse=True)[:limit]}


def action_adopt(payload):
    return summary(adopt(payload))


def action_release(payload):
    return release(require_job(payload))


ACTIONS = {
    "info": (action_info, False), "cron.list": (action_list, False), "cron.put": (action_put, True), "cron.delete": (action_delete, True),
    "cron.run": (action_run, True), "cron.history": (action_history, False), "cron.log": (action_log, False), "cron.runs": (action_runs, False),
    "cron.adopt": (action_adopt, True), "cron.release": (action_release, True),
}


def handle(action, raw):
    """One request: validated action name and JSON input in, one result object out. Never raises."""
    if action not in ACTIONS:
        return {"ok": False, "error": "unknown_action", "message": "Onbekende actie."}
    if len(raw) > MAX_INPUT:
        return {"ok": False, "error": "too_large", "message": "Invoer te groot."}
    try:
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            raise ValueError
    except ValueError:
        return {"ok": False, "error": "invalid_json", "message": "Ongeldige JSON."}
    function, mutating = ACTIONS[action]
    try:
        data = function(payload)
        if mutating:
            audit(action, payload, "ok")
        return {"ok": True, "data": data}
    except AgentError as error:
        if mutating:
            audit(action, payload, error.code)
        return {"ok": False, "error": error.code, "message": error.message}
    except OSError:
        if mutating:
            audit(action, payload, "io_error")
        return {"ok": False, "error": "io_error", "message": "Bestandsfout op de node."}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    requested = os.environ.get("SSH_ORIGINAL_COMMAND")
    if requested is not None:
        # Forced command: ignore argv, accept exactly one action word.
        action = requested.strip()
        raw = sys.stdin.buffer.read(MAX_INPUT + 1).decode("utf-8", errors="replace")
        result = handle(action if re.fullmatch(r"[a-z.]{1,20}", action) else "", raw)
        sys.stdout.write(json.dumps(result) + "\n")
        return 0 if result["ok"] else 1
    if len(argv) >= 2 and argv[0] == "run" and JOB_ID.fullmatch(argv[1]):
        options = dict(zip(argv[2::2], argv[3::2]))
        run_id = options.get("--run-id")
        trigger = options.get("--trigger", "schedule")
        if (run_id and not RUN_ID.fullmatch(run_id)) or trigger not in ("schedule", "manual"):
            return 2
        try:
            record = execute(argv[1], run_id, trigger)
        except AgentError:
            return 2
        return 0 if record["status"] == "succeeded" else 1
    sys.stderr.write("Usage: controldeck-agent run <job-id>  (other actions only via ControlDeck over SSH)\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
