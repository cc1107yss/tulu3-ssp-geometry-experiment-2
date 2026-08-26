# Archived server snapshot

This directory is a bounded, privacy-conscious snapshot of the formal run from
`/home/ai/projects/ssp-tulu-repro`. It is included so that the protocol,
manifests, frozen analysis, decode diagnostics, compact run metadata, and
compressed logs can be inspected without server access.

The snapshot was captured while the extended seed runs were still in progress;
the final server state later reached `behavior-B1-greedy` and failed because
the evaluation environment lacked `latex2sympy2`. The authoritative completed
geometry results are unchanged and are summarized in `docs/PRELIMINARY_RESULTS.md`.

Large private or regenerable artifacts are intentionally excluded: model
weights, adapters, optimizer checkpoints, raw activation shards, private
credentials, and oversized point-level tables. The nested paths mirror the
server experiment root. SHA-256 checksums are provided in `SHA256SUMS`.
