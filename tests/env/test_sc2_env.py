#!/usr/bin/python
# Copyright 2019 Google Inc. All Rights Reserved.
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
"""Test for sc2_env."""

import contextlib
from unittest import mock

from absl.testing import absltest
from absl.testing import parameterized

from pysc2.env import environment
from pysc2.env import sc2_env


class TestNameCroppingAndDeduplication(parameterized.TestCase):

    @parameterized.named_parameters(
        ('empty', [], []),
        ('single_no_crop', ['agent_1'], ['agent_1']),
        ('single_cropped',
         ['very_long_agent_name_experimental_1'],
         ['very_long_agent_name_experimenta']),
        ('no_dupes_no_crop',
         ['agent_1', 'agent_2'],
         ['agent_1', 'agent_2']),
        ('no_dupes_cropped',
         ['a_very_long_agent_name_experimental',
          'b_very_long_agent_name_experimental'],
         ['a_very_long_agent_name_experimen',
          'b_very_long_agent_name_experimen']),
        ('dupes_no_crop',
         ['agent_1', 'agent_1'],
         ['(1) agent_1', '(2) agent_1']),
        ('dupes_cropped',
         ['very_long_agent_name_experimental_c123',
          'very_long_agent_name_experimental_c456'],
         ['(1) very_long_agent_name_experim',
          '(2) very_long_agent_name_experim']),
    )
    def test(self, names, expected_output):
        self.assertEqual(sc2_env.crop_and_deduplicate_names(names), expected_output)


class PipelineActionsAndStepTest(absltest.TestCase):

    def _make_env(self):
        env = sc2_env.SC2Env.__new__(sc2_env.SC2Env)
        env._pipeline_actions_and_step = True
        env._realtime = False
        env._controllers = [mock.Mock()]
        env._action_delay_fns = [None]
        env._delayed_actions = [[]]
        env._step_mul = 8
        return env

    def test_can_pipeline_when_single_controller_non_realtime(self):
        env = self._make_env()
        self.assertTrue(env._can_pipeline_actions_and_step(step_mul=None))

    def test_pipeline_guard_blocks_invalid_modes(self):
        env = self._make_env()
        env._pipeline_actions_and_step = False
        self.assertFalse(env._can_pipeline_actions_and_step(step_mul=None))

        env = self._make_env()
        env._realtime = True
        self.assertFalse(env._can_pipeline_actions_and_step(step_mul=None))

        env = self._make_env()
        env._controllers = [mock.Mock(), mock.Mock()]
        self.assertFalse(env._can_pipeline_actions_and_step(step_mul=None))

        env = self._make_env()
        env._action_delay_fns = [lambda: 1]
        self.assertFalse(env._can_pipeline_actions_and_step(step_mul=None))

        env = self._make_env()
        env._delayed_actions = [[mock.sentinel.pending]]
        self.assertFalse(env._can_pipeline_actions_and_step(step_mul=None))

        env = self._make_env()
        env._step_mul = 0
        self.assertFalse(env._can_pipeline_actions_and_step(step_mul=None))

    def test_step_uses_pipeline_path_when_enabled(self):
        env = sc2_env.SC2Env.__new__(sc2_env.SC2Env)
        env._state = environment.StepType.MID
        env._ensure_available_actions = True
        env._num_agents = 1
        env._realtime = False
        env._features = [mock.Mock()]
        env._features[0].transform_action.side_effect = (
            lambda obs, action, skip_available=False: action)
        env._obs = [mock.Mock(observation=mock.sentinel.observation_proto)]
        env._apply_action_delays = mock.Mock(side_effect=lambda actions: actions)
        env._can_pipeline_actions_and_step = mock.Mock(return_value=True)
        env._step_with_pipelined_actions = mock.Mock(return_value=mock.sentinel.result)

        result = env.step([mock.sentinel.action])

        self.assertIs(result, mock.sentinel.result)
        env._step_with_pipelined_actions.assert_called_once_with(
            [mock.sentinel.action], None)


class PipelineStepAndObserveTest(absltest.TestCase):

    def _make_env(self):
        env = sc2_env.SC2Env.__new__(sc2_env.SC2Env)
        env._pipeline_step_and_observe = True
        env._realtime = False
        env._controllers = [mock.Mock()]
        env._action_delay_fns = [None]
        env._delayed_actions = [[]]
        env._step_mul = 8
        return env

    def test_can_pipeline_when_single_controller_non_realtime(self):
        env = self._make_env()
        self.assertTrue(env._can_pipeline_step_and_observe(step_mul=8))

    def test_pipeline_guard_blocks_invalid_modes(self):
        env = self._make_env()
        env._pipeline_step_and_observe = False
        self.assertFalse(env._can_pipeline_step_and_observe(step_mul=8))

        env = self._make_env()
        env._realtime = True
        self.assertFalse(env._can_pipeline_step_and_observe(step_mul=8))

        env = self._make_env()
        env._controllers = [mock.Mock(), mock.Mock()]
        self.assertFalse(env._can_pipeline_step_and_observe(step_mul=8))

        env = self._make_env()
        env._action_delay_fns = [lambda: 1]
        self.assertFalse(env._can_pipeline_step_and_observe(step_mul=8))

        env = self._make_env()
        env._delayed_actions = [[mock.sentinel.pending]]
        self.assertFalse(env._can_pipeline_step_and_observe(step_mul=8))

        env = self._make_env()
        self.assertFalse(env._can_pipeline_step_and_observe(step_mul=0))

    def test_step_uses_step_observe_when_enabled(self):
        env = self._make_env()
        env._episode_steps = 10
        env._disable_fog = True
        env._metrics = mock.Mock()
        env._metrics.measure_step_time.return_value = contextlib.nullcontext()
        env._controllers[0].status_ended = False
        env._controllers[0].step_observe.return_value = mock.sentinel.prefetched_obs
        env._observe = mock.Mock(return_value=mock.sentinel.result)

        result = env._step(step_mul=None)

        self.assertIs(result, mock.sentinel.result)
        env._controllers[0].step_observe.assert_called_once_with(
            count=8, disable_fog=True, target_game_loop=18)
        env._observe.assert_called_once_with(
            target_game_loop=18, prefetched_obs=mock.sentinel.prefetched_obs)

    def test_step_observe_skipped_if_controller_already_ended(self):
        env = self._make_env()
        env._episode_steps = 4
        env._disable_fog = False
        env._metrics = mock.Mock()
        env._metrics.measure_step_time.return_value = contextlib.nullcontext()
        env._controllers[0].status_ended = True
        env._observe = mock.Mock(return_value=mock.sentinel.result)

        result = env._step(step_mul=6)

        self.assertIs(result, mock.sentinel.result)
        env._controllers[0].step_observe.assert_not_called()
        env._observe.assert_called_once_with(target_game_loop=10, prefetched_obs=None)


class ExperimentalScriptedFastResetTest(absltest.TestCase):

    class _ParallelStub:

        def run(self, calls):
            results = []
            for call in calls:
                if callable(call):
                    results.append(call())
                else:
                    fn, *args = call
                    results.append(fn(*args))
            return results

        def shutdown(self):
            return None

    @staticmethod
    def _raw_obs(*unit_specs, player_result=()):
        units = [
            mock.Mock(tag=tag, health=health)
            for tag, health in unit_specs
        ]
        return mock.Mock(
            player_result=list(player_result),
            observation=mock.Mock(raw_data=mock.Mock(units=units)),
        )

    def _make_fast_reset_env(self):
        env = sc2_env.SC2Env.__new__(sc2_env.SC2Env)
        env._experimental_scripted_fast_reset_mode = 'kill_and_observe'
        env._realtime = False
        env._episode_count = 1
        env._maps = [mock.sentinel.map_inst]
        env._controllers = [mock.Mock(), mock.Mock()]
        env._num_agents = 2
        env._players = [
            sc2_env.Agent(sc2_env.Race.random),
            sc2_env.Agent(sc2_env.Race.random),
        ]
        env._interface_options = [mock.Mock(raw=True), mock.Mock(raw=True)]
        env._disable_fog = True
        env._parallel = self._ParallelStub()
        env._obs = [
            self._raw_obs((1, 10.0), (2, 0.0)),
            self._raw_obs((3, 5.0)),
        ]
        for controller in env._controllers:
            controller.status_ended = False
        return env

    def test_try_experimental_restart_kills_units_and_prefetches_obs(self):
        env = self._make_fast_reset_env()
        next_obs0 = self._raw_obs((10, 9.0))
        next_obs1 = self._raw_obs((11, 9.0))
        env._controllers[0].step_observe.return_value = next_obs0
        env._controllers[1].step_observe.return_value = next_obs1

        prefetched_obs = env._try_experimental_scripted_fast_restart()

        self.assertEqual(prefetched_obs, [next_obs0, next_obs1])
        env._controllers[0].step_observe.assert_called_once_with(
            count=1,
            disable_fog=True,
            target_game_loop=0,
        )
        env._controllers[1].step_observe.assert_called_once_with(
            count=1,
            disable_fog=True,
            target_game_loop=0,
        )
        debug_commands = env._controllers[0].debug.call_args[0][0]
        self.assertLen(debug_commands, 1)
        self.assertEqual(
            list(debug_commands[0].kill_unit.tag),
            [1, 3],
        )

    def test_restart_falls_back_to_leave_join_when_prefetch_is_terminal(self):
        env = self._make_fast_reset_env()
        env._controllers[0].step_observe.return_value = self._raw_obs(
            (10, 9.0),
            player_result=[object()],
        )
        env._controllers[1].step_observe.return_value = self._raw_obs((11, 9.0))
        env._create_join = mock.Mock()

        prefetched_obs = env._restart()

        self.assertIsNone(prefetched_obs)
        env._create_join.assert_called_once_with()
        env._controllers[0].step_observe.assert_called_once()
        env._controllers[1].step_observe.assert_called_once()

    def test_reset_reuses_prefetched_observations_from_restart(self):
        env = sc2_env.SC2Env.__new__(sc2_env.SC2Env)
        env._episode_steps = 99
        env._episode_count = 2
        env._requested_races = {
            0: sc2_env.Race.random,
            1: sc2_env.Race.random,
        }
        env._map_name = '3m'
        env._metrics = mock.Mock()
        env._num_agents = 2
        env._realtime = False
        env._restart = mock.Mock(return_value=mock.sentinel.prefetched_obs)
        env._observe = mock.Mock(return_value=mock.sentinel.timesteps)

        timesteps = env.reset()

        self.assertIs(timesteps, mock.sentinel.timesteps)
        self.assertEqual(env._episode_steps, 0)
        self.assertEqual(env._episode_count, 3)
        self.assertEqual(env._last_score, [0, 0])
        self.assertEqual(env._state, environment.StepType.FIRST)
        env._restart.assert_called_once_with()
        env._observe.assert_called_once_with(
            target_game_loop=0,
            prefetched_obs=mock.sentinel.prefetched_obs,
        )
        env._metrics.increment_episode.assert_called_once_with()


class LaunchGameCleanupTest(absltest.TestCase):

    def test_launch_game_releases_partial_startup_resources_on_failure(self):
        env = sc2_env.SC2Env.__new__(sc2_env.SC2Env)
        env._num_agents = 2
        env._interface_options = [mock.Mock(), mock.Mock()]
        for interface in env._interface_options:
            interface.HasField.return_value = False
        env._run_config = mock.Mock()
        env._reuse_step_observe_requests = False
        env._battle_net_map = False
        env._ports = []
        env._sc2_procs = []
        env._controllers = []
        first_proc = mock.Mock(controller=mock.Mock())
        env._run_config.start.side_effect = [first_proc, RuntimeError('launch failed')]

        with mock.patch.object(
            sc2_env.portspicker,
            'pick_unused_ports',
            return_value=[1000, 1001, 1002, 1003],
        ), mock.patch.object(
            sc2_env.portspicker,
            'return_ports',
        ) as return_ports:
            with self.assertRaisesRegex(RuntimeError, 'launch failed'):
                env._launch_game()

        first_proc.close.assert_called_once_with()
        return_ports.assert_called_once_with([1000, 1001, 1002, 1003])
        self.assertEqual(env._ports, [])
        self.assertEqual(env._sc2_procs, [])
        self.assertEqual(env._controllers, [])


if __name__ == '__main__':
    absltest.main()
