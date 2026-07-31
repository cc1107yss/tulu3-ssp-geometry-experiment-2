import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


publisher = load_module("publisher", "ops/github-publisher/publisher.py")
archive = load_module("final_archive", "ops/github-publisher/final_archive.py")


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def init_fixture(tmp_path):
    root = tmp_path / "experiment"
    (root / "configs").mkdir(parents=True)
    write_json(root / "configs" / "study.json", {"study": "fixture"})
    write_json(
        root / "status" / "pipeline_status.json",
        {
            "status": "RUNNING",
            "current_stage": "train-A-seed42",
            "run_started_at": "2026-07-29T21:08:26+08:00",
            "updated_at": "2026-07-31T12:00:00+08:00",
            "stages": {
                "preflight": {"status": "COMPLETE", "completed_at": "2026-07-29T21:09:00+08:00"},
                "train-A-seed42": {"status": "RUNNING", "started_at": "2026-07-31T11:00:00+08:00"},
            },
        },
    )
    log = root / "logs" / "train-A-seed42.log"
    log.parent.mkdir(parents=True)
    log.write_text(
        "password=hunter2\n"
        "Authorization: Bearer ghp_abcdefghijklmnopqrstuvwxyz123456\n"
        'SSP_METRIC {"global_step": 100, "max_steps": 1107, "epoch": 0.27, '
        '"elapsed_wall_seconds": 1900, "ntp_loss": 0.9, "stp_loss": 0.01, '
        '"loss": 14.56, "grad_norm": 1.2}\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "fixture"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.com"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "configs/study.json"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
    return root


def test_snapshot_is_bounded_redacted_and_has_progress(tmp_path):
    root = init_fixture(tmp_path)
    export_root = tmp_path / "export"
    config = json.loads((ROOT / "ops/github-publisher/config.json").read_text())
    snapshot = publisher.build_snapshot(root, export_root, config)
    serialized = json.dumps(snapshot, ensure_ascii=False)
    assert len(serialized.encode("utf-8")) < 65536
    assert "hunter2" not in serialized
    assert "ghp_" not in serialized
    assert snapshot["pipeline"]["completed_count"] == 1
    assert snapshot["progress"]["global_step"] == 100
    assert snapshot["progress"]["eta_seconds"] > 0
    assert snapshot["integrity"]["study_config_sha256"]


def test_redaction_and_tail_limit(tmp_path):
    path = tmp_path / "long.log"
    path.write_text("\n".join(["line {} token=hf_{}".format(i, "x" * 25) for i in range(200)]), encoding="utf-8")
    lines = publisher.bounded_tail(path, 50, 2048)
    assert len(lines) <= 50
    assert len("\n".join(lines).encode("utf-8")) <= 2048
    assert "hf_" not in "\n".join(lines)


def test_archive_policy_keeps_final_adapter_and_excludes_rebuildable_bytes(tmp_path):
    root = tmp_path / "experiment"
    adapter = root / "outputs/training/A/seed-42/final_adapter/adapter_model.safetensors"
    checkpoint = root / "outputs/training/A/seed-42/checkpoints/checkpoint-10/optimizer.pt"
    merged = root / "outputs/merged/A/seed-42/model-00001-of-00004.safetensors"
    geometry = root / "outputs/geometry/grid/seed-42/A/reserved/shard-00001.pt"
    summary = root / "outputs/analysis/grid-seed42-reserved/summary.json"
    log = root / "logs/train-A-seed42.log"
    for path, data in [
        (adapter, b"adapter"),
        (checkpoint, b"optimizer"),
        (merged, b"merged"),
        (geometry, b"activation"),
        (summary, b"{}"),
        (log, b"complete log"),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (root / ".venv/bin").mkdir(parents=True)
    archive_root = tmp_path / "repo/archive/experiment-2"
    manifest = archive.build_archive(root, archive_root, 8 * 1024 ** 3)
    assert (archive_root / "outputs/training/A/seed-42/final_adapter/adapter_model.safetensors").exists()
    assert not (archive_root / "outputs/training/A/seed-42/checkpoints/checkpoint-10/optimizer.pt").exists()
    assert not (archive_root / "outputs/merged/A/seed-42/model-00001-of-00004.safetensors").exists()
    assert not (archive_root / "outputs/geometry/grid/seed-42/A/reserved/shard-00001.pt").exists()
    assert (archive_root / "logs/train-A-seed42.log.gz").exists()
    assert manifest["scientifically_reproducible"] is True
    assert manifest["byte_complete"] is False


def test_classification_is_explicit():
    assert archive.classify(Path("outputs/training/A/seed-42/checkpoints/checkpoint-1/optimizer.pt"))[0] == "exclude"
    assert archive.classify(Path("outputs/merged/A/seed-42/model.safetensors"))[0] == "exclude"
    assert archive.classify(Path("outputs/geometry/grid/A/shard.pt"))[0] == "exclude"
    decision, priority, _ = archive.classify(Path("outputs/training/A/seed-42/final_adapter/adapter_model.safetensors"))
    assert decision == "include"
    assert priority == 1
