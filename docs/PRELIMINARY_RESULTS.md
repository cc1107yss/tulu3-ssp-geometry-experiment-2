# Preliminary results

> 本文档是 GitHub 初始快照。流水线完成前所有结论均为 preliminary，
> 正式结果以 `experiment-2-final-v1` 标签为准。

## 冻结四阶段几何

- 自然段落边界末层 MSE@3：DPO 12.010713，RLVR 11.976006。
- RLVR−DPO = -0.034707，题目配对 bootstrap 95% CI
  [-0.056219, -0.014215]，n=486。
- 方向上 RLVR 误差更低，但效应仅约 0.29%，实质量级很小。
- literal marker 和 semantic-clean 敏感性分析的置信区间均跨 0。

## Seed 42 训练观察

- B2：NTP 0.902279。
- C：NTP 1.016235，STP 1.105469。
- A2：NTP 0.936236，STP 0.008188。
- A：NTP 0.935629，STP 0.008254。
- A1：NTP 0，STP 0.000380。
- C-match：NTP 1.021317，STP 1.088869。
- A2-match：NTP 0.935591，STP 0.008166。

匹配控制与原条件的训练终点几乎一致，但是否复现 SSP 的因果排序仍须等待
合并 BF16 后的统一几何与行为评测。
