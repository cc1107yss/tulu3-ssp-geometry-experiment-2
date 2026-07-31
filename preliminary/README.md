# Preliminary server snapshot

- Captured from `/home/ai/projects/ssp-tulu-repro` while the formal pipeline was
  RUNNING on 2026-07-31.
- Executed source commit: `afdf19bdfb24c445cc757ea1878914d64fa8a6e9`.
- The snapshot contains processed training/trace data and manifests, preflight
  and time-governor artifacts, complete stage/status records, compressed logs,
  frozen analysis except the 599 MB point-level JSONL, frozen decode results,
  and compact training run metadata.
- It deliberately excludes adapters, optimizer/intermediate checkpoints, raw
  activation shards, merged BF16 models and the large point-level file while
  training is active. The automatic COMPLETE archive handles canonical final
  adapters and compressed high-granularity results.
- Every result here is preliminary. The immutable source of formal conclusions
  will be tag `experiment-2-final-v1`.

The nested paths mirror the server paths relative to the experiment root so
that settings and outputs can be inspected without SSH access.
