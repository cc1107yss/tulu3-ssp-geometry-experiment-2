import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FINALIZER = ROOT / "ops/github-publisher/final_archive.py"


def git(*args, cwd=None):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.mark.skipif(shutil.which("git-lfs") is None, reason="git-lfs is required")
def test_complete_archive_push_and_idempotency(tmp_path):
    experiment = tmp_path / "experiment"
    write_json(
        experiment / "status/pipeline_status.json",
        {"status": "COMPLETE", "stages": {"final-report": {"status": "COMPLETE"}}},
    )
    write_json(experiment / "configs/study.json", {"study": "fixture"})
    write_json(experiment / "outputs/final/summary.json", {"complete": True})
    (experiment / "outputs/final/REPORT.md").parent.mkdir(parents=True, exist_ok=True)
    (experiment / "outputs/final/REPORT.md").write_text("# Fixture final report\n", encoding="utf-8")
    adapter = experiment / "outputs/training/A/seed-42/final_adapter/adapter_model.safetensors"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_bytes(b"adapter")
    write_json(experiment / "outputs/training/A/seed-42/run_manifest.json", {"condition": "A", "seed": 42})
    checkpoint = experiment / "outputs/training/A/seed-42/checkpoints/checkpoint-1/optimizer.pt"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_bytes(b"optimizer")
    merged = experiment / "outputs/merged/A/seed-42/model.safetensors"
    merged.parent.mkdir(parents=True, exist_ok=True)
    merged.write_bytes(b"merged")
    geometry = experiment / "outputs/geometry/grid/A/shard.pt"
    geometry.parent.mkdir(parents=True, exist_ok=True)
    geometry.write_bytes(b"activation")
    log = experiment / "logs/final-report.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("complete\n", encoding="utf-8")
    git("init", "-q", "-b", "main", str(experiment))
    git("config", "user.name", "fixture", cwd=experiment)
    git("config", "user.email", "fixture@example.com", cwd=experiment)
    git("add", "configs/study.json", cwd=experiment)
    git("commit", "-qm", "executed source", cwd=experiment)

    main_repo = tmp_path / "main"
    remote = tmp_path / "remote.git"
    git("init", "-q", "-b", "main", str(main_repo))
    git("config", "user.name", "fixture", cwd=main_repo)
    git("config", "user.email", "fixture@example.com", cwd=main_repo)
    (main_repo / ".gitattributes").write_text(
        "archive/experiment-2/**/*.safetensors filter=lfs diff=lfs merge=lfs -text\n"
        "archive/experiment-2/**/*.gz filter=lfs diff=lfs merge=lfs -text\n",
        encoding="utf-8",
    )
    (main_repo / "README.md").write_text("fixture\n", encoding="utf-8")
    git("add", ".", cwd=main_repo)
    git("commit", "-qm", "bootstrap", cwd=main_repo)
    git("init", "-q", "--bare", str(remote))
    git("remote", "add", "origin", str(remote), cwd=main_repo)
    git("push", "-u", "origin", "main", cwd=main_repo)

    export_root = tmp_path / "export"
    config = tmp_path / "config.json"
    write_json(config, {"lfs_budget_bytes": 8 * 1024 ** 3, "final_tag": "experiment-2-final-v1"})
    command = [
        sys.executable,
        str(FINALIZER),
        "--experiment-root",
        str(experiment),
        "--export-root",
        str(export_root),
        "--main-repo",
        str(main_repo),
        "--config",
        str(config),
    ]
    environment = os.environ.copy()
    subprocess.run(command, check=True, env=environment, capture_output=True, text=True)
    first_commit = subprocess.check_output(["git", "-C", str(main_repo), "rev-parse", "HEAD"], text=True).strip()
    subprocess.run(command, check=True, env=environment, capture_output=True, text=True)
    second_commit = subprocess.check_output(["git", "-C", str(main_repo), "rev-parse", "HEAD"], text=True).strip()
    assert first_commit == second_commit
    assert subprocess.run(["git", "-C", str(remote), "rev-parse", "refs/tags/experiment-2-final-v1"], capture_output=True).returncode == 0
    manifest = json.loads((main_repo / "archive/experiment-2/artifact_manifest.json").read_text())
    assert manifest["scientifically_reproducible"] is True
    assert (main_repo / "archive/experiment-2/outputs/training/A/seed-42/final_adapter/adapter_model.safetensors").exists()
    assert not (main_repo / "archive/experiment-2/outputs/merged/A/seed-42/model.safetensors").exists()
    assert not (main_repo / "archive/experiment-2/outputs/geometry/grid/A/shard.pt").exists()
    assert json.loads((export_root / "archive-state.json").read_text())["phase"] == "FINALIZED"


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
