#!/usr/bin/python
# Copyright 2026 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for RemoteController pipeline action-step helper."""

from absl.testing import absltest
from s2clientprotocol import sc2api_pb2 as sc_pb

from pysc2.lib import protocol
from pysc2.lib import remote_controller


class _FakeClient(object):

    def __init__(self):
        self.status = protocol.Status.in_game
        self.multi_calls = []
        self.send_calls = []
        self.prebuilt_calls = []

    def send_multi(self, named_requests):
        named_requests = list(named_requests)
        self.multi_calls.append(named_requests)
        responses = []
        for name, _ in named_requests:
            if name == "action":
                responses.append(sc_pb.ResponseAction())
            elif name == "step":
                responses.append(sc_pb.ResponseStep())
            elif name == "observation":
                obs = sc_pb.ResponseObservation()
                obs.observation.game_loop = 10
                responses.append(obs)
            else:
                raise AssertionError("Unexpected request name: %s" % name)
        return responses

    def send(self, **kwargs):
        self.send_calls.append(kwargs)
        if "step" in kwargs:
            return sc_pb.ResponseStep()
        if "observation" in kwargs:
            obs = sc_pb.ResponseObservation()
            obs.observation.game_loop = 10
            return obs
        raise AssertionError("Unexpected send kwargs: %s" % kwargs)

    def send_prebuilt(self, name, req):
        self.prebuilt_calls.append((name, req))
        if name == "step":
            return sc_pb.ResponseStep()
        if name == "observation":
            obs = sc_pb.ResponseObservation()
            obs.observation.game_loop = req.observation.game_loop
            return obs
        raise AssertionError("Unexpected prebuilt name: %s" % name)


class RemoteControllerPipelineTest(absltest.TestCase):

    def setUp(self):
        super(RemoteControllerPipelineTest, self).setUp()
        self.client = _FakeClient()
        self.controller = remote_controller.RemoteController.__new__(
            remote_controller.RemoteController)
        self.controller._client = self.client
        self.controller._last_obs = None
        self.controller._reuse_step_observe_requests = False
        self.controller._step_request = sc_pb.Request(step=sc_pb.RequestStep())
        self.controller._observation_request = sc_pb.Request(
            observation=sc_pb.RequestObservation())

    def test_actions_step_uses_send_multi_when_actions_present(self):
        req = sc_pb.RequestAction(actions=[sc_pb.Action()])

        out = self.controller.actions_step(req, count=7)

        self.assertIsInstance(out, sc_pb.ResponseStep)
        self.assertLen(self.client.multi_calls, 1)
        sent = self.client.multi_calls[0]
        self.assertLen(sent, 2)
        self.assertEqual(sent[0][0], "action")
        self.assertEqual(sent[1][0], "step")
        self.assertEqual(sent[1][1].count, 7)
        self.assertEmpty(self.client.send_calls)

    def test_actions_step_falls_back_to_step_when_no_actions(self):
        req = sc_pb.RequestAction()

        out = self.controller.actions_step(req, count=3)

        self.assertIsInstance(out, sc_pb.ResponseStep)
        self.assertEmpty(self.client.multi_calls)
        self.assertLen(self.client.send_calls, 1)
        sent = self.client.send_calls[0]
        self.assertIn("step", sent)
        self.assertEqual(sent["step"].count, 3)

    def test_step_observe_uses_send_multi(self):
        out = self.controller.step_observe(
            count=5, disable_fog=True, target_game_loop=123)

        self.assertIsInstance(out, sc_pb.ResponseObservation)
        self.assertLen(self.client.multi_calls, 1)
        sent = self.client.multi_calls[0]
        self.assertLen(sent, 2)
        self.assertEqual(sent[0][0], "step")
        self.assertEqual(sent[0][1].count, 5)
        self.assertEqual(sent[1][0], "observation")
        self.assertEqual(sent[1][1].game_loop, 123)
        self.assertTrue(sent[1][1].disable_fog)
        self.assertEmpty(self.client.send_calls)
        self.assertEmpty(self.client.prebuilt_calls)

    def test_step_uses_send_prebuilt_when_request_reuse_enabled(self):
        self.controller.set_reuse_step_observe_requests(True)

        out = self.controller.step(count=11)

        self.assertIsInstance(out, sc_pb.ResponseStep)
        self.assertEmpty(self.client.send_calls)
        self.assertLen(self.client.prebuilt_calls, 1)
        name, req = self.client.prebuilt_calls[0]
        self.assertEqual(name, "step")
        self.assertEqual(req.step.count, 11)

    def test_step_observe_uses_prebuilt_requests_when_enabled(self):
        self.controller.set_reuse_step_observe_requests(True)

        out = self.controller.step_observe(
            count=6, disable_fog=True, target_game_loop=222)

        self.assertIsInstance(out, sc_pb.ResponseObservation)
        self.assertLen(self.client.multi_calls, 1)
        sent = self.client.multi_calls[0]
        self.assertIsInstance(sent[0][1], sc_pb.Request)
        self.assertEqual(sent[0][1].step.count, 6)
        self.assertIsInstance(sent[1][1], sc_pb.Request)
        self.assertEqual(sent[1][1].observation.game_loop, 222)
        self.assertTrue(sent[1][1].observation.disable_fog)
        self.assertEmpty(self.client.send_calls)


if __name__ == "__main__":
    absltest.main()
