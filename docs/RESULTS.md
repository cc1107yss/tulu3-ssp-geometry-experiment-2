# Completed results and archive scope

## Status

The formal run started on 2026-07-29 and stopped on 2026-08-02 at
`behavior-B1-greedy`. The failure was technical:

```text
ModuleNotFoundError: No module named 'latex2sympy2'
```

The run is not presented as behaviorally complete. No behavior accuracy or
pass@4 number is claimed in this archive.

## Completed stages

- Data and trace-bank construction, including hash-based test-overlap checks.
- Frozen Base/SFT/DPO/RLVR geometry and paired statistical analysis.
- Frozen decode diagnostics.
- Seed-42 SSP training for B2, C, A2, A, A1, C-match, and A2-match.
- Seed-43 and seed-44 training for B2, C, A2, and A.
- Adapter merging and quantization-sensitivity validation for the completed
  seed-42 conditions.
- Reserved-boundary grid geometry and natural-boundary sensitivity analyses.
- Grid decode diagnostics.

## Frozen geometry endpoint

The primary four-stage endpoint is final-layer normalized MSE@3 on natural
step boundaries. DPO is 12.010713 and RLVR is 11.976006. The paired difference
RLVR-DPO is -0.034707 with a 95% bootstrap interval of
[-0.056219, -0.014215], n=486.

## Reproducibility boundary

The archive contains source code, configuration, manifests, checksums, compact
logs, and completed analysis outputs. It does not contain private credentials,
model weights, merged model directories, optimizer state, or every raw
activation shard. Those can be regenerated from the server-side paths recorded
in the manifests by an authorized operator.

## Honest interpretation

The data support a cumulative final-layer geometry change from Base through SFT
and DPO. RLVR is very close to DPO and differs by a small, boundary-sensitive
correction. Step-level SSP targets are easy to optimize, while random-token STP
is harder and increases NTP loss. The archive deliberately separates completed
scientific results from the incomplete behavioral endpoint.
