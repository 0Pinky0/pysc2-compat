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
"""Benchmark environment step latency."""

import time
import numpy as np
from pysc2 import maps
from pysc2.lib import app
from pysc2.lib import flags
from pysc2.env import sc2_env
from pysc2.agents import random_agent
from pysc2.lib import stopwatch

FLAGS = flags.FLAGS
flags.DEFINE_string("map", "Simple64", "Name of a map to use.")
flags.DEFINE_integer("steps", 2000, "Total steps to run.")
flags.DEFINE_integer("step_mul", 8, "Game steps per observation.")
flags.DEFINE_string("resolution", "64", "Resolution for screen/minimap.")


def _build_players(map_name):
    map_inst = maps.get(map_name)
    if map_inst.players == 1:
        return [sc2_env.Agent(sc2_env.Race.random)]
    return [
        sc2_env.Agent(sc2_env.Race.random),
        sc2_env.Bot(sc2_env.Race.random, sc2_env.Difficulty.very_easy),
    ]


def main(unused_argv):
    stopwatch.sw.enable()
    
    # 解析分辨率
    res = int(FLAGS.resolution)
    agent = random_agent.RandomAgent()
    players = _build_players(FLAGS.map)
    
    print(
        f"Starting benchmark on {FLAGS.map} with resolution {res} "
        f"({len(players)} players)..."
    )
    
    with sc2_env.SC2Env(
        map_name=FLAGS.map,
        players=players,
        step_mul=FLAGS.step_mul,
        visualize=False,
        agent_interface_format=sc2_env.AgentInterfaceFormat(
            feature_dimensions=sc2_env.Dimensions(screen=res, minimap=res),
            use_feature_units=True
        )
    ) as env:
        
        agent.setup(env.observation_spec()[0], env.action_spec()[0])
        timesteps = env.reset()
        agent.reset()
        
        step_times = []  # 记录 env.step 的耗时
        
        start_global = time.perf_counter()
        
        for i in range(FLAGS.steps):
            # 1. Agent 决策 (理论上很快，忽略不计)
            step_actions = [agent.step(timesteps[0])]
            
            # 2. 环境步进 (主要测试目标)
            t0 = time.perf_counter_ns()
            timesteps = env.step(step_actions)
            t1 = time.perf_counter_ns()
            
            step_times.append((t1 - t0) / 1e6)  # 转为毫秒
            
            if timesteps[0].last():
                timesteps = env.reset()
                agent.reset()

        total_time = time.perf_counter() - start_global
        
        step_times = np.array(step_times)
        print("\n" + "="*30)
        print(f"RESULTS ({FLAGS.steps} steps)")
        print("="*30)
        print(f"Total Time:    {total_time:.4f} s")
        print(f"Average SPS:   {FLAGS.steps / total_time:.2f} steps/s")
        print(f"Latency Mean:  {np.mean(step_times):.4f} ms")
        print(f"Latency P50:   {np.median(step_times):.4f} ms")
        print(f"Latency P99:   {np.percentile(step_times, 99):.4f} ms")
        print("="*30)
        
        # 打印详细的各组件耗时 (features, protocol, etc.)
        print("\nInternal Stopwatch:")
        print(stopwatch.sw)

if __name__ == "__main__":
    app.run(main)
