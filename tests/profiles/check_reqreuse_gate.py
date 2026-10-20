#!/usr/bin/env python3
"""Gate checker for `reuse_step_observe_requests` manual enablement."""

import argparse
import json
from pathlib import Path
import sys


def _safe_delta(new_value, base_value):
    if base_value == 0:
        return None
    return (new_value - base_value) * 100.0 / base_value


def _load_ab_payload(path):
    with path.open() as f:
        data = json.load(f)
    ab = data.get("ab_test")
    if not ab:
        raise ValueError(f"{path}: missing `ab_test` payload")
    if ab.get("label") != "reuse_step_observe_requests":
        raise ValueError(
            f"{path}: unexpected ab_test label `{ab.get('label')}`, "
            "expected `reuse_step_observe_requests`"
        )
    value_a = ab.get("value_a")
    value_b = ab.get("value_b")
    if not isinstance(value_a, bool) or not isinstance(value_b, bool):
        raise ValueError(
            f"{path}: expected boolean value_a/value_b, got "
            f"{value_a!r}/{value_b!r}"
        )
    agg_a = ab.get("aggregate_a")
    agg_b = ab.get("aggregate_b")
    if not agg_a or not agg_b:
        raise ValueError(f"{path}: missing aggregate_a/aggregate_b")
    return {
        "path": str(path),
        "value_a": value_a,
        "value_b": value_b,
        "agg_a": agg_a,
        "agg_b": agg_b,
    }


def _disabled_vs_enabled_delta(payload, metric, stat_key):
    """Compute delta_pct(disabled=false vs enabled=true) for one stat.

    Positive means disabled is slower than enabled (enabled is better).
    Negative means disabled is faster than enabled.
    """
    value_a = payload["value_a"]
    value_b = payload["value_b"]
    agg_a = payload["agg_a"][metric][stat_key]
    agg_b = payload["agg_b"][metric][stat_key]

    if value_a is True and value_b is False:
        # A=enabled, B=disabled.
        return _safe_delta(agg_b, agg_a)
    if value_a is False and value_b is True:
        # A=disabled, B=enabled.
        return _safe_delta(agg_a, agg_b)
    raise ValueError(
        f"{payload['path']}: invalid value_a/value_b pair "
        f"{value_a!r}/{value_b!r}, expected one true and one false"
    )


def _check(name, actual, threshold, op):
    if actual is None:
        return False, f"{name}: metric unavailable"
    if op == ">=":
        ok = actual >= threshold
        rule = f">= {threshold:+.2f}%"
    else:
        raise ValueError(f"Unsupported op: {op}")
    verdict = "PASS" if ok else "FAIL"
    msg = f"[{verdict}] {name}: {actual:+.2f}% (required {rule})"
    return ok, msg


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Check whether `reuse_step_observe_requests` can be manually "
            "enabled based on AB benchmark JSON outputs."
        )
    )
    parser.add_argument("--fixed8-random", required=True, type=Path)
    parser.add_argument("--fixed8-noop", required=True, type=Path)
    parser.add_argument("--long8-random", required=True, type=Path)
    args = parser.parse_args()

    fixed8_random = _load_ab_payload(args.fixed8_random)
    fixed8_noop = _load_ab_payload(args.fixed8_noop)
    long8_random = _load_ab_payload(args.long8_random)

    checks = []
    # Enable-gate thresholds (delta of disabled vs enabled).
    checks.append(
        _check(
            "fixed8 random total_time mean",
            _disabled_vs_enabled_delta(fixed8_random, "total_time_s", "mean"),
            +1.0,
            ">=",
        )
    )
    checks.append(
        _check(
            "fixed8 random total_time median",
            _disabled_vs_enabled_delta(fixed8_random, "total_time_s", "median"),
            +1.0,
            ">=",
        )
    )
    checks.append(
        _check(
            "fixed8 noop total_time mean",
            _disabled_vs_enabled_delta(fixed8_noop, "total_time_s", "mean"),
            -0.5,
            ">=",
        )
    )
    checks.append(
        _check(
            "long8 random total_time mean",
            _disabled_vs_enabled_delta(long8_random, "total_time_s", "mean"),
            +0.5,
            ">=",
        )
    )
    checks.append(
        _check(
            "long8 random latency_p99 mean",
            _disabled_vs_enabled_delta(long8_random, "latency_p99_ms", "mean"),
            -2.0,
            ">=",
        )
    )

    all_ok = True
    print("reuse_step_observe_requests gate check")
    for ok, msg in checks:
        print(msg)
        all_ok = all_ok and ok

    if all_ok:
        print("FINAL: PASS (manual enablement gate satisfied)")
        return 0
    print("FINAL: FAIL (keep default OFF)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
