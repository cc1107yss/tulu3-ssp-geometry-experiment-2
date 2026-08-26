# GitHub publisher (retired)

This utility was used during the live experiment to export read-only status snapshots from the server project into a separate GitHub branch. It is retained for provenance, but it is not part of the public results pipeline.

## Current archive policy

- The `run-status` branch has been deleted.
- The user-level publisher timer and service are stopped and disabled.
- The public `main` branch is the curated archive; it is not an automatically updating live dashboard.
- No credentials or private deployment material belong in this repository.

## Historical command

```bash
python3 ops/github-publisher/publisher.py --dry-run
```

The publisher never modified experiment parameters or resumed failed jobs. Its `PAUSED`/`FAILED` behavior was observation-only. This documentation is preserved to explain repository history, not to suggest that the publisher is currently active.
