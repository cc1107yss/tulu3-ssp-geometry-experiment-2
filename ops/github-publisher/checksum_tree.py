#!/usr/bin/env python3
"""Write a deterministic SHA-256 manifest for an exported directory tree."""

import argparse
import hashlib
import os
import tempfile
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("output")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.resolve() != output:
            rows.append("{}  {}".format(digest(path), path.relative_to(root).as_posix()))
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=output.name + ".", dir=str(output.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write("\n".join(rows) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


if __name__ == "__main__":
    main()
