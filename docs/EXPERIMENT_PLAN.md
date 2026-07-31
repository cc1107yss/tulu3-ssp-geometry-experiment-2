# Experiment 2: Tulu-3-8B SSP 复现与四阶段轨迹重组

## 研究问题

Base→SFT→DPO→RLVR 是否表现为推理轨迹预测几何的系统重组，尤其是
DPO 与 RLVR 之间的变化；同时在 Tulu-3-8B 上复现 Semantic Step
Prediction (SSP) 论文的六条件因果消融。

## 主要终点

- SSP 方法端口：A（连续步骤 STP）对 C（随机 token STP）末层 MSE@1。
- 四阶段机制：DPO 对 RLVR 的题目内配对末层 MSE@3。
- 行为保持：A 相对 B2 的 MATH-500 greedy 准确率下降不超过 2 pp。

## 数据与测量契约

- 冻结四阶段基线使用现有 MATH-500 多采样轨迹，DPO/RLVR 建立
  source-balanced trace bank，主配对单位为题目。
- SSP 训练使用官方 MATH train，内容哈希排除测试重叠，截断只能发生在完整步骤边界。
- 主几何分析使用自然段落边界；保留 token 和 semantic-clean 边界作敏感性分析。
- 所有模型以 BF16、非量化形式测量 pre-final-RMSNorm hidden state。

## SSP 条件

| 条件 | NTP | STP 目标 | 采样 |
|---|---:|---|---|
| B1 | 否 | 无 | 冻结 Base |
| B2 | 是 | 无 | — |
| C | 是 | 随机 token | token 随机 |
| A2 | 是 | 随机步骤 | 步骤随机 |
| A | 是 | 下一连续步骤 | 连续步骤 |
| A1 | 否 | 下一连续步骤 | 连续步骤 |

另运行 C-match/A2-match 样本数匹配控制。Seed 42 跑完整网格，B2/C/A2/A
追加 seed 43、44。

## 统一训练设置

- Meta-Llama-3.1-8B Base，QLoRA NF4 + double quant，BF16 compute。
- LoRA rank 16、alpha 32、dropout 0.1，仅 q/k/v/o projection。
- AdamW，LR `2e-5`，linear schedule，无 warmup，weight decay 0。
- micro-batch 1，gradient accumulation 16，3 epochs，STP `beta=1`。
- gradient checkpointing、SDPA、关闭 KV cache。
- 步骤 token：`<|reserved_special_token_247|>`，ID 128255。

## 评测与统计

- 几何：MSE@1/2/3/5、cosine/perpendicular 分解、层间平滑性和 decode。
- 行为：六个核心条件 greedy；B1/B2/C/A2/A 追加 pass@4。
- pass@4：temperature 0.6、top-p 0.95、最大生成 16k token。
- 主效应报告点估计、题目级 bootstrap 95% CI 及跨 seed 离散度。
- MLP 使用 problem-level split，增加 DPO→RLVR 和 RLVR→DPO 迁移。

## 执行与停止规则

- RTX 3090 24GB，单 GPU 串行 tmux `ssp-tulu-runner`。
- 科学阴性结果不停止；技术失败保留现场并停在当前单元。
- 核心网格预计超过 14 天时才暂停；实测时间审计已判定继续。
- ProcessBench 和 Qwen 本轮延期。
