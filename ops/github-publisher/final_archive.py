#!/usr/bin/env python3
"""Build and push the reproducibility-complete Experiment 2 archive."""

from __future__ import print_function

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


LFS_THRESHOLD = 50 * 1024 * 1024
SCIENTIFIC_ROOTS = ("data/processed", "artifacts", "logs", "status", "outputs")
WEIGHT_SUFFIXES = {".safetensors", ".bin", ".pth", ".pt"}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-root", required=True)
    parser.add_argument("--export-root", required=True)
    parser.add_argument("--main-repo", required=True)
    parser.add_argument("--config", required=True)
    return parser.parse_args()


def now_iso():
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat()


def run(command, cwd=None, timeout=300, check=False):
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
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
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def update_state(path, phase, **values):
    current = read_json(path, {}) or {}
    current.update(values)
    current["phase"] = phase
    current["updated_at"] = now_iso()
    atomic_json(path, current)
    return current


def classify(relative):
    parts = relative.parts
    suffix = relative.suffix.lower()
    text = relative.as_posix()
    if any(part in {"__pycache__", ".pytest_cache"} for part in parts):
        return "exclude", 9, "runtime cache"
    if "checkpoints" in parts:
        return "exclude", 9, "optimizer/intermediate checkpoint; final adapter retained"
    if len(parts) >= 2 and parts[0] == "outputs" and parts[1] == "geometry" and suffix == ".pt":
        return "exclude", 9, "raw activation shard; reconstruct from trace bank and model"
    if len(parts) >= 2 and parts[0] == "outputs" and parts[1] == "merged" and suffix in WEIGHT_SUFFIXES:
        return "exclude", 9, "merged BF16 weight; reconstruct from Base and final adapter"
    if "/final_adapter/" in "/" + text:
        return "include", 1, "final LoRA adapter"
    if suffix in {".jsonl", ".csv", ".json", ".md", ".txt", ".yaml", ".yml", ".tsv", ".png", ".pdf", ".svg"}:
        return "include", 0, "canonical scientific evidence"
    if parts and parts[0] in {"logs", "status", "artifacts", "data"}:
        return "include", 0, "provenance or execution record"
    return "include", 2, "canonical output required for reproducibility"


def destination_for(relative, size):
    destination = relative
    compress = False
    if relative.parts and relative.parts[0] == "logs":
        destination = Path("logs") / ("/".join(relative.parts[1:]) + ".gz")
        compress = True
    elif relative.suffix.lower() == ".jsonl" and size >= 5 * 1024 * 1024:
        destination = Path(str(relative) + ".gz")
        compress = True
    return destination, compress


def copy_or_compress(source, target, compress):
    target.parent.mkdir(parents=True, exist_ok=True)
    if compress:
        with source.open("rb") as src, gzip.open(str(target), "wb", compresslevel=6) as dst:
            shutil.copyfileobj(src, dst, length=4 * 1024 * 1024)
    else:
        shutil.copy2(str(source), str(target))


def iter_scientific_files(root):
    for relative_root in SCIENTIFIC_ROOTS:
        base = root / relative_root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            yield path, path.relative_to(root)


def write_environment(root, archive_root):
    provenance = archive_root / "provenance"
    provenance.mkdir(parents=True, exist_ok=True)
    sections = []
    commands = [
        ["uname", "-a"],
        ["nvidia-smi"],
        [str(root / ".venv" / "bin" / "python"), "--version"],
        [str(root / ".venv" / "bin" / "python"), "-m", "pip", "freeze"],
    ]
    for command in commands:
        if not Path(command[0]).exists() and "/" in command[0]:
            continue
        result = run(command, timeout=120)
        sections.append("$ {}\n{}{}".format(
            " ".join(command), result.stdout, result.stderr
        ))
    (provenance / "environment.txt").write_text("\n\n".join(sections), encoding="utf-8")
    commit = run(["git", "-C", str(root), "rev-parse", "HEAD"], timeout=30)
    (provenance / "executed-source-commit.txt").write_text(commit.stdout.strip() + "\n", encoding="utf-8")


def rebuilding_text():
    return """# Rebuilding excluded artifacts

The archive is scientifically and operationally reproducible, but it is not a
byte-for-byte mirror of the server. The following generated objects are
intentionally represented by SHA-256 inventory entries:

- `outputs/merged/**` model weights: rerun `scripts/merge_adapter.py` using the
  recorded Meta-Llama-3.1-8B Base path and the archived `final_adapter`.
- `outputs/training/**/checkpoints/**`: optimizer/intermediate checkpoints are
  not needed after a successful three-epoch run; final adapters, run manifests,
  configuration, seeds, data hashes and complete logs are archived.
- `outputs/geometry/**/*.pt`: rerun `scripts/extract_geometry.py` with the
  archived trace bank, model/adapter, boundary mode and `configs/study.json`.

`artifact-inventory.jsonl.gz` contains the source-relative path, byte size,
SHA-256, inclusion decision and rebuild reason for every scientific artifact.
"""


def build_archive(root, archive_root, budget):
    if archive_root.exists():
        resolved = archive_root.resolve()
        if resolved.name != "experiment-2" or resolved.parent.name != "archive":
            raise RuntimeError("refusing to replace unexpected archive path: {}".format(resolved))
        shutil.rmtree(str(archive_root))
    archive_root.mkdir(parents=True)
    inventory = []
    included = []
    for source, relative in iter_scientific_files(root):
        size = source.stat().st_size
        decision, priority, reason = classify(relative)
        row = {
            "path": relative.as_posix(),
            "size_bytes": size,
            "sha256": sha256_file(source),
            "decision": decision,
            "reason": reason,
            "priority": priority,
        }
        if decision == "include":
            destination, compress = destination_for(relative, size)
            target = archive_root / destination
            copy_or_compress(source, target, compress)
            row["archive_path"] = destination.as_posix()
            row["archive_size_bytes"] = target.stat().st_size
            row["archive_sha256"] = sha256_file(target)
            row["lfs_candidate"] = target.suffix.lower() in {".gz", ".safetensors", ".bin"} or target.stat().st_size >= LFS_THRESHOLD
            included.append((row, target))
        inventory.append(row)

    lfs_total = sum(row["archive_size_bytes"] for row, _ in included if row.get("lfs_candidate"))
    if lfs_total > budget:
        removable = sorted(
            [(row, path) for row, path in included if row.get("lfs_candidate") and row["priority"] >= 2],
            key=lambda item: (item[0]["priority"], item[0]["archive_size_bytes"]),
            reverse=True,
        )
        for row, path in removable:
            if lfs_total <= budget:
                break
            lfs_total -= row["archive_size_bytes"]
            path.unlink()
            row["decision"] = "excluded_lfs_budget"
            row["reason"] = "omitted by deterministic 8 GiB LFS budget after higher-priority evidence"
            row.pop("archive_sha256", None)
            row.pop("archive_size_bytes", None)
            row.pop("archive_path", None)
            row["lfs_candidate"] = False
    if lfs_total > budget:
        raise RuntimeError("mandatory final adapters and core archive exceed LFS budget")

    write_environment(root, archive_root)
    (archive_root / "REBUILDING.md").write_text(rebuilding_text(), encoding="utf-8")
    inventory_path = archive_root / "artifact-inventory.jsonl.gz"
    with gzip.open(str(inventory_path), "wt", encoding="utf-8", compresslevel=6) as stream:
        for row in inventory:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    included_rows = [row for row in inventory if row["decision"] == "include"]
    manifest = {
        "schema_version": 1,
        "experiment_id": "experiment-2",
        "created_at": now_iso(),
        "archive_policy": "reproducibility-complete",
        "byte_complete": False,
        "scientifically_reproducible": True,
        "included_file_count": len(included_rows),
        "excluded_file_count": len(inventory) - len(included_rows),
        "source_bytes_included": sum(row["size_bytes"] for row in included_rows),
        "archive_bytes_included": sum(row.get("archive_size_bytes", 0) for row in included_rows),
        "lfs_bytes": lfs_total,
        "lfs_budget_bytes": budget,
        "inventory": "artifact-inventory.jsonl.gz",
        "inventory_sha256": sha256_file(inventory_path),
        "rebuilding": "REBUILDING.md",
    }
    atomic_json(archive_root / "artifact_manifest.json", manifest)
    return manifest


def ensure_lfs_tracking(main_repo, archive_root):
    run(["git", "lfs", "install", "--local"], cwd=main_repo, check=True)
    for path in sorted(archive_root.rglob("*")):
        if not path.is_file() or path.stat().st_size < LFS_THRESHOLD:
            continue
        relative = path.relative_to(main_repo).as_posix()
        attribute = run(["git", "check-attr", "filter", "--", relative], cwd=main_repo, check=True)
        if "filter: lfs" not in attribute.stdout:
            run(["git", "lfs", "track", "--", relative], cwd=main_repo, check=True)


def main():
    args = parse_args()
    root = Path(args.experiment_root).resolve()
    export_root = Path(args.export_root).resolve()
    main_repo = Path(args.main_repo).resolve()
    config = read_json(args.config)
    if not isinstance(config, dict):
        raise SystemExit("invalid archive config")
    status = read_json(root / "status" / "pipeline_status.json", {}) or {}
    if status.get("status") != "COMPLETE":
        raise SystemExit("refusing final archive because pipeline is not COMPLETE")
    state_path = export_root / "archive-state.json"
    state = read_json(state_path, {}) or {}
    if state.get("phase") == "FINALIZED":
        print(json.dumps(state, indent=2))
        return
    branch = run(["git", "branch", "--show-current"], cwd=main_repo, check=True).stdout.strip()
    if branch != "main":
        raise RuntimeError("main archive clone is on unexpected branch {}".format(branch))

    archive_root = main_repo / "archive" / "experiment-2"
    if state.get("phase") not in {"BUILT", "COMMITTED"}:
        dirty = run(["git", "status", "--porcelain=v1"], cwd=main_repo, check=True).stdout.strip()
        if dirty:
            raise RuntimeError("main archive clone is dirty before build")
        run(["git", "pull", "--ff-only", "origin", "main"], cwd=main_repo, timeout=180, check=True)
        update_state(state_path, "BUILDING")
        try:
            manifest = build_archive(root, archive_root, int(config["lfs_budget_bytes"]))
            ensure_lfs_tracking(main_repo, archive_root)
            update_state(
                state_path,
                "BUILT",
                manifest_sha256=sha256_file(archive_root / "artifact_manifest.json"),
                included_bytes=manifest["archive_bytes_included"],
                lfs_bytes=manifest["lfs_bytes"],
                byte_complete=manifest["byte_complete"],
            )
        except Exception as exc:
            update_state(state_path, "ERROR", error=str(exc), build_ready=False)
            raise
        state = read_json(state_path, {}) or {}

    if state.get("phase") == "BUILT":
        run(["git", "add", "--", ".gitattributes", "archive/experiment-2"], cwd=main_repo, check=True)
        run(["git", "commit", "-m", "Freeze Experiment 2 results"], cwd=main_repo, check=True)
        commit = run(["git", "rev-parse", "HEAD"], cwd=main_repo, check=True).stdout.strip()
        update_state(state_path, "COMMITTED", final_commit=commit)
        state = read_json(state_path, {}) or {}

    if state.get("phase") == "COMMITTED":
        run(["git", "push", "origin", "main"], cwd=main_repo, timeout=24 * 60 * 60, check=True)
        tag = config["final_tag"]
        tag_exists = run(["git", "rev-parse", "--verify", "refs/tags/{}".format(tag)], cwd=main_repo)
        if tag_exists.returncode != 0:
            run(["git", "tag", "-a", tag, "-m", "Freeze Experiment 2 formal results"], cwd=main_repo, check=True)
        run(["git", "push", "origin", "refs/tags/{}".format(tag)], cwd=main_repo, timeout=3600, check=True)
        final_commit = run(["git", "rev-parse", "HEAD"], cwd=main_repo, check=True).stdout.strip()
        final_state = update_state(
            state_path,
            "FINALIZED",
            final_commit=final_commit,
            final_tag=tag,
            error=None,
        )
        print(json.dumps(final_state, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
