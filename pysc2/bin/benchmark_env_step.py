#!/usr/bin/python
# Copyright 2024 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Benchmark environment step latency.

This benchmark now supports deterministic runs, repeated measurements, and
structured JSON/CSV outputs for easier historical comparisons.
"""

import csv
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pysc2 as _pysc2_pkg

from pysc2 import maps
from pysc2.agents import random_agent
from pysc2.env import sc2_env
from pysc2.lib import app
from pysc2.lib import flags
from pysc2.lib import stopwatch

FLAGS = flags.FLAGS
flags.DEFINE_string("map", "Simple64", "Name of a map to use.")
flags.DEFINE_integer("steps", 2000, "Measured steps per run.")
flags.DEFINE_integer("step_mul", 8, "Game steps per observation.")
flags.DEFINE_string("resolution", "64", "Resolution for screen/minimap.")
flags.DEFINE_integer("warmup_steps", 0, "Warmup env.step calls before measuring.")
flags.DEFINE_integer("repeats", 1, "How many benchmark runs to execute.")
flags.DEFINE_integer("seed", 12345, "Base random seed. Per-run seed is seed + run_id.")
flags.DEFINE_string(
    "agent_race", "random", "Agent race: random/protoss/terran/zerg.")
flags.DEFINE_string(
    "bot_race", "random", "Bot race for 2P maps: random/protoss/terran/zerg.")
flags.DEFINE_string(
    "output_prefix",
    "",
    "If set, writes <output_prefix>.json and <output_prefix>.csv.",
)
flags.DEFINE_string(
    "output_dir",
    "",
    "If set, auto-writes timestamped JSON/CSV under this directory.",
)
flags.DEFINE_bool(
    "obs_include_ui_data",
    True,
    "Whether to include UI-derived observation fields (single_select, etc.).",
)
flags.DEFINE_bool(
    "obs_include_score_details",
    True,
    "Whether to include score_by_category and score_by_vital observations.",
)
flags.DEFINE_bool(
    "obs_include_last_actions",
    True,
    "Whether to include last_actions observation.",
)


def _parse_race(value):
    try:
        return getattr(sc2_env.Race, value.lower())
    except AttributeError as exc:
        raise ValueError(
            "Unknown race '%s'. Use one of: random/protoss/terran/zerg." % value
        ) from exc


def _build_players(map_name, agent_race, bot_race):
    map_inst = maps.get(map_name)
    if map_inst.players == 1:
        return [sc2_env.Agent(agent_race)]
    return [
        sc2_env.Agent(agent_race),
        sc2_env.Bot(bot_race, sc2_env.Difficulty.very_easy),
    ]


def _set_global_seed(seed):
    random.seed(seed)
    np.random.seed(seed)


def _step_once(env, agent, timesteps):
    step_actions = [agent.step(timesteps[0])]
    return env.step(step_actions)


def _serialize_stopwatch(sw):
    total_top_level = sum(v.sum for k, v in sw.times.items() if "." not in k)
    rows = {}
    for name, stat in sorted(sw.times.items()):
        if stat.num <= 0:
            continue
        rows[name] = {
            "pct_total": (100.0 * stat.sum / (total_top_level or 1.0)),
            "sum_s": stat.sum,
            "avg_s": stat.avg,
            "dev_s": stat.dev,
            "min_s": stat.min,
            "max_s": stat.max,
            "num": stat.num,
        }
    return {
        "total_top_level_s": total_top_level,
        "rows": rows,
    }


def _run_once(run_id, res, players):
    run_seed = FLAGS.seed + run_id
    _set_global_seed(run_seed)
    stopwatch.sw.clear()

    agent = random_agent.RandomAgent()
    with sc2_env.SC2Env(
        map_name=FLAGS.map,
        players=players,
        step_mul=FLAGS.step_mul,
        random_seed=run_seed,
        visualize=False,
        agent_interface_format=sc2_env.AgentInterfaceFormat(
            feature_dimensions=sc2_env.Dimensions(screen=res, minimap=res),
            use_feature_units=True,
            include_ui_data=FLAGS.obs_include_ui_data,
            include_score_details=FLAGS.obs_include_score_details,
            include_last_actions=FLAGS.obs_include_last_actions,
        ),
    ) as env:
        agent.setup(env.observation_spec()[0], env.action_spec()[0])
        timesteps = env.reset()
        agent.reset()

        warmup_resets = 0
        for _ in range(FLAGS.warmup_steps):
            timesteps = _step_once(env, agent, timesteps)
            if timesteps[0].last():
                timesteps = env.reset()
                agent.reset()
                warmup_resets += 1

        step_times_ms = []
        measured_resets = 0
        start_global = time.perf_counter()
        for _ in range(FLAGS.steps):
            t0 = time.perf_counter_ns()
            timesteps = _step_once(env, agent, timesteps)
            t1 = time.perf_counter_ns()
            step_times_ms.append((t1 - t0) / 1e6)
            if timesteps[0].last():
                timesteps = env.reset()
                agent.reset()
                measured_resets += 1
        total_time_s = time.perf_counter() - start_global

    lat = np.asarray(step_times_ms, dtype=np.float64)
    return {
        "run_id": run_id,
        "seed": run_seed,
        "warmup_steps": FLAGS.warmup_steps,
        "measured_steps": FLAGS.steps,
        "warmup_resets": warmup_resets,
        "measured_resets": measured_resets,
        "total_time_s": float(total_time_s),
        "sps": float(FLAGS.steps / total_time_s),
        "latency_mean_ms": float(np.mean(lat)),
        "latency_p50_ms": float(np.median(lat)),
        "latency_p99_ms": float(np.percentile(lat, 99)),
        "stopwatch": _serialize_stopwatch(stopwatch.sw),
    }


def _aggregate_runs(runs):
    keys = [
        "total_time_s",
        "sps",
        "latency_mean_ms",
        "latency_p50_ms",
        "latency_p99_ms",
    ]
    agg = {"num_runs": len(runs)}
    for key in keys:
        vals = np.asarray([r[key] for r in runs], dtype=np.float64)
        agg[key] = {
            "mean": float(np.mean(vals)),
            "median": float(np.median(vals)),
            "min": float(np.min(vals)),
            "max": float(np.max(vals)),
            "std": float(np.std(vals)),
        }
    return agg


def _resolve_output_paths():
    if FLAGS.output_prefix and FLAGS.output_dir:
        raise ValueError("Only one of --output_prefix or --output_dir can be set.")
    if FLAGS.output_prefix:
        prefix = Path(FLAGS.output_prefix).expanduser()
    elif FLAGS.output_dir:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        prefix = Path(FLAGS.output_dir).expanduser() / (
            "profile_env_step_%s" % stamp)
    else:
        return None, None
    return Path(str(prefix) + ".json"), Path(str(prefix) + ".csv")


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _write_csv(path, runs):
    path.parent.mkdir(parents=True, exist_ok=True)
    hotspot_keys = [
        "step_env",
        "step_env.observe.read.read_response",
        "step_env.observe.read.parse_response",
        "step_env.transform_obs",
        "step_env.actions",
        "step_env.step",
    ]
    base_fields = [
        "run_id",
        "seed",
        "warmup_steps",
        "measured_steps",
        "warmup_resets",
        "measured_resets",
        "total_time_s",
        "sps",
        "latency_mean_ms",
        "latency_p50_ms",
        "latency_p99_ms",
    ]
    fieldnames = base_fields + hotspot_keys
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for run in runs:
            row = {k: run[k] for k in base_fields}
            rows = run["stopwatch"]["rows"]
            for key in hotspot_keys:
                row[key] = rows.get(key, {}).get("sum_s", 0.0)
            writer.writerow(row)


def _get_protobuf_info():
    try:
        import google.protobuf as pb
        from google.protobuf.internal import api_implementation
        return pb.__version__, api_implementation.Type()
    except Exception:
        return None, None


def main(unused_argv):
    stopwatch.sw.enable()
    if FLAGS.repeats < 1:
        raise ValueError("--repeats must be >= 1")
    if FLAGS.steps < 1:
        raise ValueError("--steps must be >= 1")
    if FLAGS.warmup_steps < 0:
        raise ValueError("--warmup_steps must be >= 0")

    res = int(FLAGS.resolution)
    agent_race = _parse_race(FLAGS.agent_race)
    bot_race = _parse_race(FLAGS.bot_race)
    players = _build_players(FLAGS.map, agent_race, bot_race)

    print(
        "Starting benchmark on %s with resolution %s (%d players), "
        "repeats=%d, warmup=%d, steps=%d."
        % (
            FLAGS.map,
            res,
            len(players),
            FLAGS.repeats,
            FLAGS.warmup_steps,
            FLAGS.steps,
        )
    )

    runs = []
    for run_id in range(FLAGS.repeats):
        print("\n" + "-" * 50)
        print("Run %d/%d (seed=%d)" % (run_id + 1, FLAGS.repeats, FLAGS.seed + run_id))
        print("-" * 50)
        run = _run_once(run_id, res, players)
        runs.append(run)
        print("Total Time:    %.4f s" % run["total_time_s"])
        print("Average SPS:   %.2f steps/s" % run["sps"])
        print("Latency Mean:  %.4f ms" % run["latency_mean_ms"])
        print("Latency P50:   %.4f ms" % run["latency_p50_ms"])
        print("Latency P99:   %.4f ms" % run["latency_p99_ms"])
        print("Internal Stopwatch:")
        print(stopwatch.sw)

    agg = _aggregate_runs(runs)
    print("\n" + "=" * 50)
    print("AGGREGATED RESULTS (%d runs)" % agg["num_runs"])
    print("=" * 50)
    print("Total Time mean/median: %.4f / %.4f s" % (
        agg["total_time_s"]["mean"], agg["total_time_s"]["median"]))
    print("SPS mean/median: %.2f / %.2f" % (
        agg["sps"]["mean"], agg["sps"]["median"]))
    print("Latency Mean mean/median: %.4f / %.4f ms" % (
        agg["latency_mean_ms"]["mean"], agg["latency_mean_ms"]["median"]))
    print("Latency P50 mean/median: %.4f / %.4f ms" % (
        agg["latency_p50_ms"]["mean"], agg["latency_p50_ms"]["median"]))
    print("Latency P99 mean/median: %.4f / %.4f ms" % (
        agg["latency_p99_ms"]["mean"], agg["latency_p99_ms"]["median"]))
    print("=" * 50)

    pb_version, pb_backend = _get_protobuf_info()
    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark": "pysc2.bin.benchmark_env_step",
        "config": {
            "map": FLAGS.map,
            "resolution": res,
            "step_mul": FLAGS.step_mul,
            "warmup_steps": FLAGS.warmup_steps,
            "steps": FLAGS.steps,
            "repeats": FLAGS.repeats,
            "seed": FLAGS.seed,
            "agent_race": FLAGS.agent_race,
            "bot_race": FLAGS.bot_race,
            "obs_include_ui_data": FLAGS.obs_include_ui_data,
            "obs_include_score_details": FLAGS.obs_include_score_details,
            "obs_include_last_actions": FLAGS.obs_include_last_actions,
        },
        "environment": {
            "python_version": sys.version.split()[0],
            "python_executable": sys.executable,
            "pysc2_path": getattr(_pysc2_pkg, "__file__", None),
            "protobuf_version": pb_version,
            "protobuf_backend": pb_backend,
        },
        "aggregate": agg,
        "runs": runs,
    }

    json_path, csv_path = _resolve_output_paths()
    if json_path and csv_path:
        _write_json(json_path, payload)
        _write_csv(csv_path, runs)
        print("Wrote JSON summary to: %s" % json_path)
        print("Wrote CSV summary to:  %s" % csv_path)

if __name__ == "__main__":
    app.run(main)
