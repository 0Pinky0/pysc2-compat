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
from pysc2.agents import base_agent
from pysc2.agents import random_agent
from pysc2.env import sc2_env
from pysc2.lib import app
from pysc2.lib import flags
from pysc2.lib import stopwatch

FLAGS = flags.FLAGS
flags.DEFINE_string("map", "Simple64", "Name of a map to use.")
flags.DEFINE_string(
    "agent_type",
    "random",
    "Agent policy for benchmark: random|noop.",
)
flags.DEFINE_integer("steps", 2000, "Measured steps per run.")
flags.DEFINE_integer("step_mul", 8, "Game steps per observation.")
flags.DEFINE_bool(
    "ensure_available_actions",
    True,
    "Whether to validate availability in transform_action.",
)
flags.DEFINE_bool(
    "pipeline_actions_and_step",
    False,
    "Whether to pipeline action and step RPC for single-controller runs.",
)
flags.DEFINE_bool(
    "pipeline_step_and_observe",
    False,
    "Whether to pipeline step and observe RPC for single-controller runs.",
)
flags.DEFINE_bool(
    "reuse_step_observe_requests",
    False,
    "Whether to reuse step/observe request containers across env steps.",
)
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
flags.DEFINE_bool(
    "obs_include_available_actions",
    True,
    "Whether to include available_actions observation.",
)
flags.DEFINE_bool(
    "obs_reuse_available_actions_result",
    False,
    "Whether to reuse available_actions result between transform_obs and "
    "transform_action for the same observation.",
)
flags.DEFINE_integer(
    "obs_available_actions_cache_size",
    0,
    "Cache size for available_actions ability mapping (0 disables cache).",
)
flags.DEFINE_string(
    "obs_available_actions_cache_size_ab",
    "",
    "Optional A/B cache sizes as 'A,B' (e.g. '0,256'). When set, runs are "
    "scheduled by --ab_pattern and this overrides --obs_available_actions_cache_size.",
)
flags.DEFINE_string(
    "obs_include_available_actions_ab",
    "",
    "Optional A/B include flag values as 'true,false'. When set, runs are "
    "scheduled by --ab_pattern and this overrides --obs_include_available_actions.",
)
flags.DEFINE_string(
    "obs_reuse_available_actions_result_ab",
    "",
    "Optional A/B reuse flag values as 'true,false'. When set, runs are "
    "scheduled by --ab_pattern and this overrides "
    "--obs_reuse_available_actions_result.",
)
flags.DEFINE_string(
    "pipeline_actions_and_step_ab",
    "",
    "Optional A/B pipeline flag values as 'true,false'. When set, runs are "
    "scheduled by --ab_pattern and this overrides --pipeline_actions_and_step.",
)
flags.DEFINE_string(
    "pipeline_step_and_observe_ab",
    "",
    "Optional A/B pipeline flag values as 'true,false'. When set, runs are "
    "scheduled by --ab_pattern and this overrides --pipeline_step_and_observe.",
)
flags.DEFINE_string(
    "reuse_step_observe_requests_ab",
    "",
    "Optional A/B request-reuse values as 'true,false'. When set, runs are "
    "scheduled by --ab_pattern and this overrides --reuse_step_observe_requests.",
)
flags.DEFINE_string(
    "ab_pattern",
    "abab",
    "A/B run order pattern when any *_ab flag is set. "
    "Supported: abab, abba.",
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


def _safe_delta_pct(new_value, base_value):
    if base_value == 0:
        return None
    return float((new_value - base_value) * 100.0 / base_value)


def _parse_ab_cache_sizes(spec):
    if not spec:
        return None
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    if len(parts) != 2:
        raise ValueError(
            "--obs_available_actions_cache_size_ab must have exactly 2 integers, "
            "e.g. '0,256'.")
    try:
        a_size, b_size = (int(parts[0]), int(parts[1]))
    except ValueError as exc:
        raise ValueError(
            "--obs_available_actions_cache_size_ab must be two integers, "
            "e.g. '0,256'.") from exc
    if a_size < 0 or b_size < 0:
        raise ValueError(
            "--obs_available_actions_cache_size_ab values must be >= 0.")
    return a_size, b_size


def _parse_bool_token(token):
    normalized = token.strip().lower()
    if normalized in ("1", "true", "t", "yes", "y", "on"):
        return True
    if normalized in ("0", "false", "f", "no", "n", "off"):
        return False
    raise ValueError("Invalid bool token: %s" % token)


def _parse_ab_bools(spec, flag_name):
    if not spec:
        return None
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    if len(parts) != 2:
        raise ValueError(
            "--%s must have exactly 2 bool values, e.g. 'true,false'."
            % flag_name)
    try:
        a_value, b_value = (_parse_bool_token(parts[0]), _parse_bool_token(parts[1]))
    except ValueError as exc:
        raise ValueError(
            "--%s must be bool,bool, e.g. 'true,false'." % flag_name) from exc
    return a_value, b_value


def _build_ab_schedule(repeats, cache_sizes, pattern):
    if repeats < 2:
        raise ValueError("--repeats must be >= 2 when A/B mode is enabled.")
    pattern = pattern.lower()
    if pattern == "abab":
        seq = [cache_sizes[0], cache_sizes[1]]
    elif pattern == "abba":
        seq = [cache_sizes[0], cache_sizes[1], cache_sizes[1], cache_sizes[0]]
    else:
        raise ValueError("--ab_pattern must be one of: abab, abba.")
    return [seq[i % len(seq)] for i in range(repeats)]


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


def _run_once(
        run_id,
        res,
        players,
        available_actions_cache_size,
        include_available_actions,
        reuse_available_actions_result,
        pipeline_actions_and_step,
        pipeline_step_and_observe,
        reuse_step_observe_requests,
        agent_type):
    run_seed = FLAGS.seed + run_id
    _set_global_seed(run_seed)
    stopwatch.sw.clear()

    if agent_type == "random":
        agent = random_agent.RandomAgent()
    else:
        agent = base_agent.BaseAgent()
    with sc2_env.SC2Env(
        map_name=FLAGS.map,
        players=players,
        step_mul=FLAGS.step_mul,
        random_seed=run_seed,
        visualize=False,
        ensure_available_actions=FLAGS.ensure_available_actions,
        pipeline_actions_and_step=pipeline_actions_and_step,
        pipeline_step_and_observe=pipeline_step_and_observe,
        reuse_step_observe_requests=reuse_step_observe_requests,
        agent_interface_format=sc2_env.AgentInterfaceFormat(
            feature_dimensions=sc2_env.Dimensions(screen=res, minimap=res),
            use_feature_units=True,
            include_ui_data=FLAGS.obs_include_ui_data,
            include_score_details=FLAGS.obs_include_score_details,
            include_last_actions=FLAGS.obs_include_last_actions,
            include_available_actions=include_available_actions,
            reuse_available_actions_result=reuse_available_actions_result,
            available_actions_cache_size=available_actions_cache_size,
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
        "agent_type": agent_type,
        "obs_include_available_actions": include_available_actions,
        "obs_reuse_available_actions_result": reuse_available_actions_result,
        "pipeline_actions_and_step": pipeline_actions_and_step,
        "pipeline_step_and_observe": pipeline_step_and_observe,
        "reuse_step_observe_requests": reuse_step_observe_requests,
        "obs_available_actions_cache_size": available_actions_cache_size,
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


def _stopwatch_mean_sum(runs, key):
    values = []
    for run in runs:
        row = run["stopwatch"]["rows"].get(key)
        if row:
            values.append(row["sum_s"])
    if not values:
        return None
    return float(np.mean(np.asarray(values, dtype=np.float64)))


def _build_ab_summary(runs, group_key, value_a, value_b, pattern, label):
    runs_a = [r for r in runs if r[group_key] == value_a]
    runs_b = [r for r in runs if r[group_key] == value_b]
    if not runs_a or not runs_b:
        raise ValueError(
            "A/B summary requires both groups to have at least one run. "
            "Got A=%d, B=%d." % (len(runs_a), len(runs_b)))

    agg_a = _aggregate_runs(runs_a)
    agg_b = _aggregate_runs(runs_b)
    metrics = [
        "total_time_s",
        "sps",
        "latency_mean_ms",
        "latency_p50_ms",
        "latency_p99_ms",
    ]
    delta_metrics = {}
    for metric in metrics:
        delta_metrics[metric] = {
            "mean_pct_b_vs_a": _safe_delta_pct(
                agg_b[metric]["mean"], agg_a[metric]["mean"]),
            "median_pct_b_vs_a": _safe_delta_pct(
                agg_b[metric]["median"], agg_a[metric]["median"]),
        }

    hotspot_keys = [
        "step_env",
        "step_env.observe.read.read_response",
        "step_env.transform_obs",
        "step_env.transform_obs.available_actions",
        "step_env.transform_action.available_actions",
        "step_env.actions",
    ]
    hotspot_mean_s = {}
    for key in hotspot_keys:
        mean_a = _stopwatch_mean_sum(runs_a, key)
        mean_b = _stopwatch_mean_sum(runs_b, key)
        hotspot_mean_s[key] = {
            "a": mean_a,
            "b": mean_b,
            "delta_pct_b_vs_a": (
                _safe_delta_pct(mean_b, mean_a)
                if mean_a is not None and mean_b is not None
                else None
            ),
        }

    return {
        "enabled": True,
        "label": label,
        "group_key": group_key,
        "value_a": value_a,
        "value_b": value_b,
        "pattern": pattern,
        "runs_a": len(runs_a),
        "runs_b": len(runs_b),
        "aggregate_a": agg_a,
        "aggregate_b": agg_b,
        "delta_pct_b_vs_a": delta_metrics,
        "stopwatch_mean_s": hotspot_mean_s,
    }


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
        "agent_type",
        "obs_include_available_actions",
        "obs_reuse_available_actions_result",
        "pipeline_actions_and_step",
        "pipeline_step_and_observe",
        "reuse_step_observe_requests",
        "obs_available_actions_cache_size",
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
    agent_type = FLAGS.agent_type.lower()
    if agent_type not in ("random", "noop"):
        raise ValueError("--agent_type must be one of: random, noop")
    if FLAGS.repeats < 1:
        raise ValueError("--repeats must be >= 1")
    if FLAGS.steps < 1:
        raise ValueError("--steps must be >= 1")
    if FLAGS.warmup_steps < 0:
        raise ValueError("--warmup_steps must be >= 0")

    ab_cache_sizes = _parse_ab_cache_sizes(FLAGS.obs_available_actions_cache_size_ab)
    ab_include_available_actions = _parse_ab_bools(
        FLAGS.obs_include_available_actions_ab,
        "obs_include_available_actions_ab")
    ab_reuse_available_actions_result = _parse_ab_bools(
        FLAGS.obs_reuse_available_actions_result_ab,
        "obs_reuse_available_actions_result_ab")
    ab_pipeline_actions_and_step = _parse_ab_bools(
        FLAGS.pipeline_actions_and_step_ab,
        "pipeline_actions_and_step_ab")
    ab_pipeline_step_and_observe = _parse_ab_bools(
        FLAGS.pipeline_step_and_observe_ab,
        "pipeline_step_and_observe_ab")
    ab_reuse_step_observe_requests = _parse_ab_bools(
        FLAGS.reuse_step_observe_requests_ab,
        "reuse_step_observe_requests_ab")
    ab_target_count = sum([
        ab_cache_sizes is not None,
        ab_include_available_actions is not None,
        ab_reuse_available_actions_result is not None,
        ab_pipeline_actions_and_step is not None,
        ab_pipeline_step_and_observe is not None,
        ab_reuse_step_observe_requests is not None,
    ])
    if ab_target_count > 1:
        raise ValueError(
            "Only one A/B target is supported per run. Use either "
            "--obs_available_actions_cache_size_ab or "
            "--obs_include_available_actions_ab or "
            "--obs_reuse_available_actions_result_ab or "
            "--pipeline_actions_and_step_ab or "
            "--pipeline_step_and_observe_ab or "
            "--reuse_step_observe_requests_ab."
        )

    if FLAGS.obs_available_actions_cache_size < 0:
        raise ValueError("--obs_available_actions_cache_size must be >= 0")

    if ab_cache_sizes is None:
        run_cache_sizes = [FLAGS.obs_available_actions_cache_size] * FLAGS.repeats
    else:
        run_cache_sizes = _build_ab_schedule(
            FLAGS.repeats, ab_cache_sizes, FLAGS.ab_pattern)

    if ab_include_available_actions is None:
        run_include_available_actions = [FLAGS.obs_include_available_actions] * FLAGS.repeats
    else:
        run_include_available_actions = _build_ab_schedule(
            FLAGS.repeats, ab_include_available_actions, FLAGS.ab_pattern)

    if ab_reuse_available_actions_result is None:
        run_reuse_available_actions_result = [
            FLAGS.obs_reuse_available_actions_result] * FLAGS.repeats
    else:
        run_reuse_available_actions_result = _build_ab_schedule(
            FLAGS.repeats, ab_reuse_available_actions_result, FLAGS.ab_pattern)

    if ab_pipeline_actions_and_step is None:
        run_pipeline_actions_and_step = [FLAGS.pipeline_actions_and_step] * FLAGS.repeats
    else:
        run_pipeline_actions_and_step = _build_ab_schedule(
            FLAGS.repeats, ab_pipeline_actions_and_step, FLAGS.ab_pattern)

    if ab_pipeline_step_and_observe is None:
        run_pipeline_step_and_observe = [FLAGS.pipeline_step_and_observe] * FLAGS.repeats
    else:
        run_pipeline_step_and_observe = _build_ab_schedule(
            FLAGS.repeats, ab_pipeline_step_and_observe, FLAGS.ab_pattern)

    if ab_reuse_step_observe_requests is None:
        run_reuse_step_observe_requests = [
            FLAGS.reuse_step_observe_requests] * FLAGS.repeats
    else:
        run_reuse_step_observe_requests = _build_ab_schedule(
            FLAGS.repeats, ab_reuse_step_observe_requests, FLAGS.ab_pattern)

    if agent_type == "random" and not all(run_include_available_actions):
        raise ValueError(
            "random agent requires available_actions. Disable random agent or keep "
            "include_available_actions=true for all scheduled runs."
        )

    ab_group_key = None
    ab_value_a = None
    ab_value_b = None
    ab_label = None
    if ab_cache_sizes is not None:
        ab_group_key = "obs_available_actions_cache_size"
        ab_value_a, ab_value_b = ab_cache_sizes
        ab_label = "available_actions_cache_size"
    elif ab_include_available_actions is not None:
        ab_group_key = "obs_include_available_actions"
        ab_value_a, ab_value_b = ab_include_available_actions
        ab_label = "include_available_actions"
    elif ab_reuse_available_actions_result is not None:
        ab_group_key = "obs_reuse_available_actions_result"
        ab_value_a, ab_value_b = ab_reuse_available_actions_result
        ab_label = "reuse_available_actions_result"
    elif ab_pipeline_actions_and_step is not None:
        ab_group_key = "pipeline_actions_and_step"
        ab_value_a, ab_value_b = ab_pipeline_actions_and_step
        ab_label = "pipeline_actions_and_step"
    elif ab_pipeline_step_and_observe is not None:
        ab_group_key = "pipeline_step_and_observe"
        ab_value_a, ab_value_b = ab_pipeline_step_and_observe
        ab_label = "pipeline_step_and_observe"
    elif ab_reuse_step_observe_requests is not None:
        ab_group_key = "reuse_step_observe_requests"
        ab_value_a, ab_value_b = ab_reuse_step_observe_requests
        ab_label = "reuse_step_observe_requests"

    res = int(FLAGS.resolution)
    agent_race = _parse_race(FLAGS.agent_race)
    bot_race = _parse_race(FLAGS.bot_race)
    players = _build_players(FLAGS.map, agent_race, bot_race)

    print(
        "Starting benchmark on %s with resolution %s (%d players), "
        "agent=%s, repeats=%d, warmup=%d, steps=%d."
        % (
            FLAGS.map,
            res,
            len(players),
            agent_type,
            FLAGS.repeats,
            FLAGS.warmup_steps,
            FLAGS.steps,
        )
    )
    if ab_group_key is None:
        print(
            "available_actions_cache_size=%d, include_available_actions=%s, "
            "reuse_available_actions_result=%s, pipeline_actions_and_step=%s, "
            "pipeline_step_and_observe=%s, reuse_step_observe_requests=%s."
            % (
                run_cache_sizes[0],
                str(run_include_available_actions[0]).lower(),
                str(run_reuse_available_actions_result[0]).lower(),
                str(run_pipeline_actions_and_step[0]).lower(),
                str(run_pipeline_step_and_observe[0]).lower(),
                str(run_reuse_step_observe_requests[0]).lower(),
            )
        )
    else:
        if ab_group_key == "obs_available_actions_cache_size":
            ab_values = run_cache_sizes
        elif ab_group_key == "obs_include_available_actions":
            ab_values = run_include_available_actions
        elif ab_group_key == "obs_reuse_available_actions_result":
            ab_values = run_reuse_available_actions_result
        elif ab_group_key == "pipeline_actions_and_step":
            ab_values = run_pipeline_actions_and_step
        elif ab_group_key == "pipeline_step_and_observe":
            ab_values = run_pipeline_step_and_observe
        else:
            ab_values = run_reuse_step_observe_requests
        preview = ",".join(str(v).lower() for v in ab_values[:8])
        if len(ab_values) > 8:
            preview += ",..."
        print(
            "A/B mode enabled: %s A=%s, B=%s, pattern=%s, schedule=%s"
            % (
                ab_label,
                str(ab_value_a).lower(),
                str(ab_value_b).lower(),
                FLAGS.ab_pattern.lower(),
                preview,
            )
        )

    runs = []
    for run_id, (
            cache_size,
            include_available_actions,
            reuse_available_actions_result,
            pipeline_actions_and_step,
            pipeline_step_and_observe,
            reuse_step_observe_requests) in enumerate(
            zip(
                run_cache_sizes,
                run_include_available_actions,
                run_reuse_available_actions_result,
                run_pipeline_actions_and_step,
                run_pipeline_step_and_observe,
                run_reuse_step_observe_requests)):
        print("\n" + "-" * 50)
        print(
            "Run %d/%d (seed=%d, cache_size=%d, include_available_actions=%s, "
            "reuse_available_actions_result=%s, pipeline_actions_and_step=%s, "
            "pipeline_step_and_observe=%s, reuse_step_observe_requests=%s)"
            % (
                run_id + 1,
                FLAGS.repeats,
                FLAGS.seed + run_id,
                cache_size,
                str(include_available_actions).lower(),
                str(reuse_available_actions_result).lower(),
                str(pipeline_actions_and_step).lower(),
                str(pipeline_step_and_observe).lower(),
                str(reuse_step_observe_requests).lower(),
            )
        )
        print("-" * 50)
        run = _run_once(
            run_id,
            res,
            players,
            cache_size,
            include_available_actions,
            reuse_available_actions_result,
            pipeline_actions_and_step,
            pipeline_step_and_observe,
            reuse_step_observe_requests,
            agent_type)
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

    ab_summary = None
    if ab_group_key is not None:
        ab_summary = _build_ab_summary(
            runs,
            group_key=ab_group_key,
            value_a=ab_value_a,
            value_b=ab_value_b,
            pattern=FLAGS.ab_pattern.lower(),
            label=ab_label,
        )
        print("\n" + "=" * 50)
        print(
            "AB SUMMARY (%s, B=%s vs A=%s, pattern=%s)"
            % (
                ab_summary["label"],
                str(ab_summary["value_b"]).lower(),
                str(ab_summary["value_a"]).lower(),
                ab_summary["pattern"],
            )
        )
        print("=" * 50)
        for metric in ("total_time_s", "sps", "latency_mean_ms", "latency_p99_ms"):
            delta = ab_summary["delta_pct_b_vs_a"][metric]
            print(
                "%s delta mean/median: %+0.2f%% / %+0.2f%%"
                % (
                    metric,
                    delta["mean_pct_b_vs_a"],
                    delta["median_pct_b_vs_a"],
                )
            )
        print("=" * 50)

    pb_version, pb_backend = _get_protobuf_info()
    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark": "pysc2.bin.benchmark_env_step",
        "config": {
            "map": FLAGS.map,
            "agent_type": agent_type,
            "resolution": res,
            "step_mul": FLAGS.step_mul,
            "ensure_available_actions": FLAGS.ensure_available_actions,
            "pipeline_actions_and_step": FLAGS.pipeline_actions_and_step,
            "pipeline_actions_and_step_ab": FLAGS.pipeline_actions_and_step_ab,
            "pipeline_step_and_observe": FLAGS.pipeline_step_and_observe,
            "pipeline_step_and_observe_ab": FLAGS.pipeline_step_and_observe_ab,
            "reuse_step_observe_requests": FLAGS.reuse_step_observe_requests,
            "reuse_step_observe_requests_ab": FLAGS.reuse_step_observe_requests_ab,
            "warmup_steps": FLAGS.warmup_steps,
            "steps": FLAGS.steps,
            "repeats": FLAGS.repeats,
            "seed": FLAGS.seed,
            "agent_race": FLAGS.agent_race,
            "bot_race": FLAGS.bot_race,
            "obs_include_ui_data": FLAGS.obs_include_ui_data,
            "obs_include_score_details": FLAGS.obs_include_score_details,
            "obs_include_last_actions": FLAGS.obs_include_last_actions,
            "obs_include_available_actions": FLAGS.obs_include_available_actions,
            "obs_include_available_actions_ab": FLAGS.obs_include_available_actions_ab,
            "obs_reuse_available_actions_result": FLAGS.obs_reuse_available_actions_result,
            "obs_reuse_available_actions_result_ab": FLAGS.obs_reuse_available_actions_result_ab,
            "obs_available_actions_cache_size": FLAGS.obs_available_actions_cache_size,
            "obs_available_actions_cache_size_ab": FLAGS.obs_available_actions_cache_size_ab,
            "ab_pattern": FLAGS.ab_pattern.lower(),
            "run_cache_size_schedule": run_cache_sizes,
            "run_include_available_actions_schedule": run_include_available_actions,
            "run_reuse_available_actions_result_schedule": run_reuse_available_actions_result,
            "run_pipeline_actions_and_step_schedule": run_pipeline_actions_and_step,
            "run_pipeline_step_and_observe_schedule": run_pipeline_step_and_observe,
            "run_reuse_step_observe_requests_schedule": run_reuse_step_observe_requests,
            "ab_test_target": ab_label,
        },
        "environment": {
            "python_version": sys.version.split()[0],
            "python_executable": sys.executable,
            "pysc2_path": getattr(_pysc2_pkg, "__file__", None),
            "protobuf_version": pb_version,
            "protobuf_backend": pb_backend,
        },
        "aggregate": agg,
        "ab_test": ab_summary,
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
