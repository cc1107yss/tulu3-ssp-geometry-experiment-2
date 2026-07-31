# Experiment 2 GitHub publisher

该 publisher 从正式实验目录只读采集状态，在独立 export root 中提交并推送。

## 服务器布局

- 实验：`/home/ai/projects/ssp-tulu-repro`（只读）
- 导出：`/home/ai/projects/ssp-tulu-github-export`
- main clone：`$EXPORT_ROOT/main`
- run-status clone：`$EXPORT_ROOT/run-status`
- deploy key：`$EXPORT_ROOT/credentials/deploy_key`

## 运行

```bash
python3 ops/github-publisher/publisher.py --dry-run
systemctl --user status ssp-tulu-github-publisher.timer
journalctl --user -u ssp-tulu-github-publisher.service
```

publisher 每小时更新 `run-status/experiment-2.json`。实验 `COMPLETE` 后，
`final_archive.py` 会将规范结果冻结至 main，推送 tag，再写入最后一份状态。

## 故障约定

- GitHub 不可达：本地状态提交继续保留，下次恢复后补推。
- 分支分叉：拒绝 force-push，在 publisher state 中报错。
- `PAUSED/FAILED`：只更新状态，不自动恢复或冻结。
- 归档失败：保留已构建 staging，后续只重试未完成的 Git/LFS 传输。
