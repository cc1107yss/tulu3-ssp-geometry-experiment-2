#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ssp_tulu.io import atomic_json, read_json, sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/study.json")
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def find_endpoint(summary: dict, left: str, right: str, horizon: int) -> dict | None:
    for row in summary.get("primary_endpoints", []):
        if (
            row["left"] == left
            and row["right"] == right
            and row["layer"] == 32
            and row["metric"] == "normalized_mse"
            and row["horizon"] == horizon
        ):
            return row
    return None


def main() -> None:
    args = parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    frozen = read_json("outputs/analysis/frozen/summary.json")
    grid = read_json("outputs/analysis/grid-seed42-reserved/summary.json")
    behavior = {}
    for condition in ["B1", "B2", "C", "A2", "A", "A1", "C-match", "A2-match"]:
        behavior[condition] = {}
        for mode in ["greedy", "pass4"]:
            path = Path(f"outputs/behavior/{condition}/{mode}/summary.json")
            if path.exists():
                behavior[condition][mode] = read_json(path)
    dpo_rlvr = find_endpoint(frozen, "dpo", "rlvr", 3)
    c_a = find_endpoint(grid, "C", "A", 1)
    b2_accuracy = behavior["B2"]["greedy"]["observed_pass"]["1"]
    a_accuracy = behavior["A"]["greedy"]["observed_pass"]["1"]
    behavior_delta_pp = 100 * (a_accuracy - b2_accuracy)
    payload = {
        "primary_endpoints": {
            "dpo_vs_rlvr_final_layer_mse3": dpo_rlvr,
            "A_vs_C_final_layer_mse1": c_a,
        },
        "behavior": behavior,
        "A_minus_B2_accuracy_pp": behavior_delta_pp,
        "behavior_non_degradation_pass": behavior_delta_pp >= -2.0,
    }
    atomic_json(output / "summary.json", payload)

    lines = [
        "# Tulu-3-8B SSP 复现与四阶段轨迹重组：最终报告",
        "",
        "## 主要终点",
        "",
    ]
    if dpo_rlvr:
        lines.extend(
            [
                f"- DPO→RLVR，末层 MSE@3：{dpo_rlvr['left_mean']:.6g} → "
                f"{dpo_rlvr['right_mean']:.6g}；差值 "
                f"{dpo_rlvr['mean_difference']:.6g}，95% CI "
                f"[{dpo_rlvr['ci95_low']:.6g}, {dpo_rlvr['ci95_high']:.6g}]。",
            ]
        )
    if c_a:
        lines.extend(
            [
                f"- C→A，末层 MSE@1：{c_a['left_mean']:.6g} → "
                f"{c_a['right_mean']:.6g}；改善倍数 "
                f"{c_a['improvement_ratio_left_over_right']:.3g}×。",
            ]
        )
    lines.extend(
        [
            "",
            "## 行为保持",
            "",
            f"- B2 greedy MATH-500：{100*b2_accuracy:.2f}%。",
            f"- A greedy MATH-500：{100*a_accuracy:.2f}%。",
            f"- A−B2：{behavior_delta_pp:+.2f} pp；"
            f"{'通过' if behavior_delta_pp >= -2 else '未通过'} −2 pp 非退化界。",
            "",
            "## 可复现性",
            "",
            "- 所有逐题几何量、bootstrap 汇总、训练日志、adapter、BF16 合并模型、"
            "量化敏感性、行为生成和 MLP probe 均保存在 `outputs/`。",
            "- `data/processed/*manifest.json` 记录数据排除与哈希；"
            "`artifacts/preflight.json` 记录 tokenizer、模型与运行环境契约。",
            "- 科学阴性结果未触发停止；任何技术失败均由流水线失败标记保留现场。",
            "",
        ]
    )
    (output / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    files = [
        Path("configs/study.json"),
        Path("data/processed/math_train_manifest.json"),
        Path("data/processed/math500_trace_bank_manifest.json"),
        Path("artifacts/preflight.json"),
        output / "summary.json",
        output / "REPORT.md",
    ]
    atomic_json(
        output / "artifact_hashes.json",
        {str(path): sha256_file(path) for path in files if path.exists()},
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

