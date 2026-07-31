#!/usr/bin/env python3
"""Publish a bounded, redacted Experiment 2 status snapshot to GitHub."""

from __future__ import print_function

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ANSI_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
ERROR_RE = re.compile(
    r"Traceback|CUDA out of memory|OutOfMemoryError|\bnan\b|\binf\b|Killed|No space left",
    re.IGNORECASE,
)
REDACTIONS = [
    (re.compile(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:token|password|passwd|secret|api[_-]?key)\s*[:=]\s*)\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,})"), "[REDACTED_TOKEN]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL), "[REDACTED_PRIVATE_KEY]"),
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-root", default=os.environ.get("EXPERIMENT_ROOT", "/home/ai/projects/ssp-tulu-repro"))
    parser.add_argument("--export-root", default=os.environ.get("EXPORT_ROOT", "/home/ai/projects/ssp-tulu-github-export"))
    parser.add_argument("--status-repo", default=os.environ.get("STATUS_REPO"))
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
    parser.add_argument("--output")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-finalize", action="store_true")
    return parser.parse_args()


def now_iso():
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat()


def run(command, cwd=None, timeout=30, check=False, env=None):
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except OSError as exc:
        completed = subprocess.CompletedProcess(command, 127, "", str(exc))
    if check and completed.returncode != 0:
        raise RuntimeError(
            "command failed ({}): {}\n{}".format(
                completed.returncode, " ".join(command), completed.stderr.strip()
            )
        )
    return completed


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sanitize(text):
    clean = ANSI_RE.sub("", text.replace("\x00", ""))
    for pattern, replacement in REDACTIONS:
        clean = pattern.sub(replacement, clean)
    return clean


def bounded_tail(path, max_lines, max_bytes):
    path = Path(path)
    if not path.exists():
        return []
    size = path.stat().st_size
    read_bytes = min(size, max(max_bytes * 4, 65536))
    with path.open("rb") as stream:
        stream.seek(max(0, size - read_bytes))
        data = stream.read(read_bytes)
    text = sanitize(data.decode("utf-8", errors="replace"))
    lines = text.splitlines()[-max_lines:]
    while lines and len("\n".join(lines).encode("utf-8")) > max_bytes:
        lines.pop(0)
    return lines


def parse_metrics(lines):
    parsed = []
    for line in lines:
        marker = "SSP_METRIC "
        if marker not in line:
            continue
        try:
            item = json.loads(line.split(marker, 1)[1])
        except (json.JSONDecodeError, IndexError):
            continue
        parsed.append(item)
    return parsed[-5:]


def gpu_status():
    result = run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits",
        ],
        timeout=10,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return {"available": False, "error": sanitize(result.stderr.strip())[:500]}
    fields = [field.strip() for field in result.stdout.strip().splitlines()[0].split(",")]
    if len(fields) != 5:
        return {"available": True, "raw": result.stdout.strip()[:500]}
    return {
        "available": True,
        "name": fields[0],
        "memory_used_mib": number(fields[1]),
        "memory_total_mib": number(fields[2]),
        "utilization_percent": number(fields[3]),
        "temperature_c": number(fields[4]),
    }


def number(value):
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def source_integrity(root):
    commit = run(["git", "-C", str(root), "rev-parse", "HEAD"], timeout=10)
    dirty = run(["git", "-C", str(root), "status", "--porcelain=v1"], timeout=10)
    config_path = root / "configs" / "study.json"
    manifest_hashes = {}
    for path in sorted((root / "data" / "processed").glob("*manifest*.json")):
        manifest_hashes[str(path.relative_to(root))] = sha256_file(path)
    return {
        "source_commit": commit.stdout.strip() if commit.returncode == 0 else None,
        "source_worktree_clean": dirty.returncode == 0 and not dirty.stdout.strip(),
        "study_config_sha256": sha256_file(config_path) if config_path.exists() else None,
        "data_manifest_sha256": manifest_hashes,
    }


def completed_training_runs(root):
    rows = []
    training_root = root / "outputs" / "training"
    if not training_root.exists():
        return rows
    for manifest in sorted(training_root.glob("*/seed-*/run_manifest.json")):
        payload = read_json(manifest, {}) or {}
        metrics = payload.get("metrics", {})
        rows.append(
            {
                "condition": payload.get("condition"),
                "seed": payload.get("seed"),
                "global_step": metrics.get("global_step"),
                "max_steps": metrics.get("max_steps"),
                "epoch": metrics.get("epoch"),
                "elapsed_wall_seconds": metrics.get("elapsed_wall_seconds"),
                "ntp_loss": metrics.get("ntp_loss"),
                "stp_loss": metrics.get("stp_loss"),
                "train_loss": metrics.get("train_loss"),
                "manifest": str(manifest.relative_to(root)),
            }
        )
    return rows


def scientific_summaries(root):
    summaries = {}
    candidates = {
        "frozen": root / "outputs" / "analysis" / "frozen" / "summary.json",
        "grid_seed42_reserved": root / "outputs" / "analysis" / "grid-seed42-reserved" / "summary.json",
        "grid_seed42_natural": root / "outputs" / "analysis" / "grid-seed42-natural" / "summary.json",
        "final": root / "outputs" / "final" / "summary.json",
    }
    for label, path in candidates.items():
        payload = read_json(path)
        if not isinstance(payload, dict):
            continue
        if label == "final":
            summaries[label] = payload
        else:
            summaries[label] = {
                "primary_endpoints": payload.get("primary_endpoints", []),
                "source": str(path.relative_to(root)),
            }
    return summaries


def archive_state(export_root):
    state = read_json(export_root / "archive-state.json", {}) or {}
    if not state:
        return {"phase": "NOT_STARTED"}
    allowed = {
        "phase",
        "updated_at",
        "error",
        "final_commit",
        "final_tag",
        "manifest_sha256",
        "included_bytes",
        "lfs_bytes",
        "byte_complete",
    }
    return {key: value for key, value in state.items() if key in allowed}


def build_snapshot(root, export_root, config):
    status = read_json(root / "status" / "pipeline_status.json", {}) or {}
    stages = status.get("stages", {}) or {}
    current_stage = status.get("current_stage")
    current_log_path = root / "logs" / (str(current_stage) + ".log") if current_stage else None
    log_lines = bounded_tail(
        current_log_path,
        int(config["log_tail_lines"]),
        int(config["log_tail_bytes"]),
    ) if current_log_path else []
    metrics = parse_metrics(log_lines)
    latest = metrics[-1] if metrics else {}
    max_steps = latest.get("max_steps")
    global_step = latest.get("global_step")
    elapsed = latest.get("elapsed_wall_seconds")
    seconds_per_step = None
    eta_seconds = None
    if global_step and elapsed:
        seconds_per_step = elapsed / global_step
        if max_steps and max_steps >= global_step:
            eta_seconds = (max_steps - global_step) * seconds_per_step
    tmux_binary = os.environ.get("TMUX_BINARY") or shutil.which("tmux")
    tmux_candidates = [
        root / ".deps" / "tmux" / "bin" / "tmux",
        Path.home() / ".local" / "opt" / "tmux-3.0a" / "usr" / "bin" / "tmux",
    ]
    if not tmux_binary:
        tmux_binary = next((str(path) for path in tmux_candidates if path.exists()), None)
    tmux = run([tmux_binary or "tmux", "has-session", "-t", "ssp-tulu-runner"], timeout=10)
    usage = shutil.disk_usage(str(root))
    log_age = None
    if current_log_path and current_log_path.exists():
        log_age = max(0, dt.datetime.now().timestamp() - current_log_path.stat().st_mtime)
    errors = sorted(set(match.group(0) for match in ERROR_RE.finditer("\n".join(log_lines))))
    compact_stages = {}
    for name, value in stages.items():
        compact_stages[name] = {
            key: value.get(key)
            for key in ("status", "started_at", "completed_at", "failed_at", "exit_code")
            if value.get(key) is not None
        }
    completed_count = sum(1 for value in stages.values() if value.get("status") == "COMPLETE")
    payload = {
        "schema_version": int(config["schema_version"]),
        "experiment_id": config["experiment_id"],
        "study_name": config["study_name"],
        "repository": config["repository"],
        "observed_at": now_iso(),
        "pipeline": {
            "status": status.get("status", "UNKNOWN"),
            "current_stage": current_stage,
            "run_started_at": status.get("run_started_at"),
            "pipeline_updated_at": status.get("updated_at"),
            "completed_count": completed_count,
            "planned_count": int(config["planned_count"]),
            "started_count": len(stages),
            "stages": compact_stages,
        },
        "progress": {
            "epoch": latest.get("epoch"),
            "global_step": global_step,
            "max_steps": max_steps,
            "elapsed_wall_seconds": elapsed,
            "seconds_per_step": seconds_per_step,
            "eta_seconds": eta_seconds,
            "latest_metrics": latest,
            "recent_metrics": metrics,
        },
        "integrity": source_integrity(root),
        "health": {
            "tmux_session": "ssp-tulu-runner",
            "tmux_alive": tmux.returncode == 0,
            "gpu": gpu_status(),
            "disk_free_gib": usage.free / 1024 ** 3,
            "disk_used_percent": 100 * usage.used / usage.total,
            "error_signatures": errors,
        },
        "completed_training_runs": completed_training_runs(root),
        "scientific_summaries": scientific_summaries(root),
        "current_log": {
            "path": str(current_log_path) if current_log_path else None,
            "age_seconds": log_age,
            "tail_line_count": len(log_lines),
            "tail": log_lines,
        },
        "archive": archive_state(export_root),
    }
    return enforce_size(payload, int(config["status_max_bytes"]))


def encoded_size(payload):
    return len(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")) + 1


def enforce_size(payload, limit):
    if encoded_size(payload) <= limit:
        payload["status_size_bytes"] = encoded_size(payload)
        return payload
    payload["current_log"]["tail"] = payload["current_log"]["tail"][-10:]
    payload["current_log"]["tail_line_count"] = len(payload["current_log"]["tail"])
    payload.setdefault("truncated_fields", []).append("current_log.tail")
    if encoded_size(payload) > limit:
        payload["pipeline"]["stages"] = {
            name: {"status": value.get("status")}
            for name, value in payload["pipeline"]["stages"].items()
        }
        payload["truncated_fields"].append("pipeline.stages.timestamps")
    if encoded_size(payload) > limit:
        payload["scientific_summaries"] = {
            "note": "See main branch and final archive; detailed summaries omitted from bounded live status."
        }
        payload["truncated_fields"].append("scientific_summaries")
    if encoded_size(payload) > limit:
        raise RuntimeError("status payload exceeds {} bytes after compaction".format(limit))
    payload["status_size_bytes"] = encoded_size(payload)
    return payload


def sync_status_branch(repo):
    fetch = run(["git", "fetch", "origin", "run-status"], cwd=repo, timeout=60)
    if fetch.returncode != 0:
        return
    ancestor = run(["git", "merge-base", "--is-ancestor", "HEAD", "origin/run-status"], cwd=repo)
    reverse = run(["git", "merge-base", "--is-ancestor", "origin/run-status", "HEAD"], cwd=repo)
    if ancestor.returncode == 0 and reverse.returncode != 0:
        run(["git", "merge", "--ff-only", "origin/run-status"], cwd=repo, check=True)
    elif ancestor.returncode != 0 and reverse.returncode != 0:
        raise RuntimeError("run-status branch diverged; refusing force-push")


def publish_snapshot(payload, status_repo, config):
    status_repo = Path(status_repo)
    sync_status_branch(status_repo)
    target = status_repo / config["status_filename"]
    atomic_json(target, payload)
    run(["git", "add", "--", config["status_filename"]], cwd=status_repo, check=True)
    stage = payload.get("pipeline", {}).get("current_stage") or payload.get("pipeline", {}).get("status")
    message = "status: {} {}".format(payload["observed_at"], stage)
    run(["git", "commit", "-m", message], cwd=status_repo, check=True)
    pushed = run(["git", "push", "origin", "run-status"], cwd=status_repo, timeout=180)
    if pushed.returncode != 0:
        raise RuntimeError("status push failed; local commit retained: {}".format(sanitize(pushed.stderr.strip())[:1000]))


def write_publisher_state(export_root, phase, error=None):
    state = {"phase": phase, "updated_at": now_iso()}
    if error:
        state["error"] = sanitize(str(error))[:2000]
    atomic_json(export_root / "publisher-state.json", state)


def maybe_finalize(args, config, snapshot):
    if args.no_finalize or snapshot.get("pipeline", {}).get("status") != "COMPLETE":
        return False
    archive = archive_state(Path(args.export_root))
    if archive.get("phase") == "FINALIZED":
        return True
    script = Path(__file__).with_name("final_archive.py")
    command = [
        sys.executable,
        str(script),
        "--experiment-root",
        args.experiment_root,
        "--export-root",
        args.export_root,
        "--main-repo",
        os.environ.get("MAIN_REPO", str(Path(args.export_root) / "main")),
        "--config",
        args.config,
    ]
    result = run(command, timeout=24 * 60 * 60)
    if result.returncode != 0:
        raise RuntimeError("final archive failed: {}".format(sanitize(result.stderr.strip())[-2000:]))
    return archive_state(Path(args.export_root)).get("phase") == "FINALIZED"


def main():
    args = parse_args()
    root = Path(args.experiment_root).resolve()
    export_root = Path(args.export_root).resolve()
    status_repo = Path(args.status_repo or (export_root / "run-status")).resolve()
    config = read_json(args.config)
    if not isinstance(config, dict):
        raise SystemExit("invalid publisher config")
    snapshot = build_snapshot(root, export_root, config)
    if args.output:
        atomic_json(args.output, snapshot)
    if args.dry_run:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True))
        return
    try:
        write_publisher_state(export_root, "PUBLISHING")
        publish_snapshot(snapshot, status_repo, config)
        finalized = maybe_finalize(args, config, snapshot)
        if finalized:
            final_snapshot = build_snapshot(root, export_root, config)
            publish_snapshot(final_snapshot, status_repo, config)
            write_publisher_state(export_root, "FINALIZED")
            if os.environ.get("DISABLE_TIMER_ON_COMPLETE", "1") == "1":
                run(["systemctl", "--user", "disable", "--now", "ssp-tulu-github-publisher.timer"], timeout=30)
        else:
            write_publisher_state(export_root, "OK")
    except Exception as exc:
        write_publisher_state(export_root, "ERROR", exc)
        raise


if __name__ == "__main__":
    main()
