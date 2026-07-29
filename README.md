# Tulu-3-8B SSP 复现与四阶段轨迹重组

本目录是独立、可审计的实验实现。旧模型、旧 MATH-500 生成结果和
`/home/ai/limit-of-RLVR` 只作为只读输入；新产物统一写到
`/home/ai/projects/ssp-tulu-repro`。

## 研究终点

- SSP 端口：A 相对 C 的末层 normalized MSE@1。
- 四阶段机制：RLVR 相对 DPO 的题目配对末层 normalized MSE@3。
- 行为非退化：A 的 MATH-500 greedy 准确率相对 B2 不低于 2 pp。

论文设置、原始 STP 继承项、RTX 3090 工程适配和本研究新增项全部固化在
[`configs/study.json`](configs/study.json) 及各阶段 manifest 中。

## 执行

服务器初始化与正式启动由以下命令完成：

```bash
bash scripts/bootstrap_remote.sh
bash scripts/launch_tmux.sh
```

正式 tmux 会话名为 `ssp-tulu-runner`。流水线单 GPU 串行执行，每阶段有独立
日志、完成/失败标记和状态 JSON；技术失败停止且不自动重试。

查看一次结构化状态：

```bash
source scripts/env.sh
python scripts/monitor_snapshot.py
```

## 关键实现约定

- 训练使用保留 token `<|reserved_special_token_247|>`（ID 128255）。
- 激活由 decoder layer forward hook 提取，位置在最终 RMSNorm 之前。
- A 使用全部连续步骤三元组；C/A2 每轨迹一个固定随机三元组；
  `C-match`/`A2-match` 将三元组数量匹配到 A。
- 几何主评测按题目聚合并 bootstrap；DPO/RLVR 使用同题同轨迹配对。
- ProcessBench 和 Qwen 均不在本轮范围。

