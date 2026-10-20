#!/usr/bin/env python3
"""Retry wrapper for benchmark_env_step long-running commands."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time


def _build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Run pysc2/bin/benchmark_env_step.py with no-capture/unbuffered "
            "settings and retry on transient failures."
        )
    )
    parser.add_argument(
        "--env-name",
        default=os.environ.get("SMACNT_ENV_NAME", "smacnt"),
        help="Conda env name (default: SMACNT_ENV_NAME or smacnt).",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=int(os.environ.get("BENCH_RETRY_ATTEMPTS", "2")),
        help="Max retry attempts (default: BENCH_RETRY_ATTEMPTS or 2).",
    )
    return parser


def main():
    parser = _build_parser()
    args, bench_args = parser.parse_known_args()
    if args.attempts < 1:
        parser.error("--attempts must be >= 1")

    project_root = Path(__file__).resolve().parents[2]
    benchmark_py = project_root / "pysc2" / "bin" / "benchmark_env_step.py"

    cmd = [
        "conda",
        "run",
        "--no-capture-output",
        "-n",
        args.env_name,
        "env",
        f"PYTHONPATH={project_root}",
        "PYTHONUNBUFFERED=1",
        "python",
        "-u",
        str(benchmark_py),
        *bench_args,
    ]

    for attempt in range(1, args.attempts + 1):
        print(f"[benchmark-retry] attempt {attempt}/{args.attempts}", flush=True)
        ret = subprocess.run(cmd).returncode
        if ret == 0:
            print(f"[benchmark-retry] succeeded on attempt {attempt}", flush=True)
            return 0
        if attempt == args.attempts:
            print(
                f"[benchmark-retry] failed after {args.attempts} attempts "
                f"(exit={ret})",
                file=sys.stderr,
                flush=True,
            )
            return ret
        sleep_seconds = attempt * 2
        print(
            f"[benchmark-retry] attempt {attempt} failed (exit={ret}), "
            f"retry in {sleep_seconds}s...",
            flush=True,
        )
        time.sleep(sleep_seconds)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
