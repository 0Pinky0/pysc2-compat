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
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for lib.protocol additions."""

from absl.testing import absltest
from s2clientprotocol import sc2api_pb2 as sc_pb

from pysc2.lib import protocol


class _FakeInnerSocket(object):

    def getpeername(self):
        return ("127.0.0.1", 12345)


class _FakeWebSocket(object):

    def __init__(self, responses):
        self.sock = _FakeInnerSocket()
        self._responses = list(responses)
        self.sent = []

    def recv(self):
        if not self._responses:
            return b""
        return self._responses.pop(0)

    def send(self, data):
        self.sent.append(data)

    def close(self):
        pass


def _resp_bytes(name, request_id=None):
    kwargs = {
        "status": protocol.Status.in_game.value,
        name: getattr(sc_pb, "Response%s" % name.capitalize())(),
    }
    if request_id is not None:
        kwargs["id"] = request_id
    return sc_pb.Response(**kwargs).SerializeToString()


class ProtocolSendMultiTest(absltest.TestCase):

    def test_send_multi_reorders_by_id(self):
        # Responses are deliberately out of order: step(id=2) before action(id=1).
        ws = _FakeWebSocket([
            _resp_bytes("step", request_id=2),
            _resp_bytes("action", request_id=1),
        ])
        client = protocol.StarcraftProtocol(ws)

        out = client.send_multi([
            ("action", sc_pb.RequestAction()),
            ("step", sc_pb.RequestStep(count=8)),
        ])

        self.assertIsInstance(out[0], sc_pb.ResponseAction)
        self.assertIsInstance(out[1], sc_pb.ResponseStep)
        self.assertLen(ws.sent, 2)

        sent_action = sc_pb.Request.FromString(ws.sent[0])
        sent_step = sc_pb.Request.FromString(ws.sent[1])
        self.assertEqual(sent_action.WhichOneof("request"), "action")
        self.assertEqual(sent_step.WhichOneof("request"), "step")
        self.assertEqual(sent_step.step.count, 8)

    def test_send_multi_falls_back_to_response_order_without_ids(self):
        ws = _FakeWebSocket([
            _resp_bytes("action"),
            _resp_bytes("step"),
        ])
        client = protocol.StarcraftProtocol(ws)

        out = client.send_multi([
            ("action", sc_pb.RequestAction()),
            ("step", sc_pb.RequestStep(count=4)),
        ])

        self.assertIsInstance(out[0], sc_pb.ResponseAction)
        self.assertIsInstance(out[1], sc_pb.ResponseStep)

    def test_send_prebuilt_uses_existing_request_object(self):
        ws = _FakeWebSocket([_resp_bytes("step", request_id=1)])
        client = protocol.StarcraftProtocol(ws)
        req = sc_pb.Request(step=sc_pb.RequestStep(count=9))

        out = client.send_prebuilt("step", req)

        self.assertIsInstance(out, sc_pb.ResponseStep)
        self.assertEqual(req.id, 1)
        self.assertLen(ws.sent, 1)
        sent_req = sc_pb.Request.FromString(ws.sent[0])
        self.assertEqual(sent_req.step.count, 9)

    def test_send_multi_accepts_prebuilt_request_messages(self):
        ws = _FakeWebSocket([
            _resp_bytes("step", request_id=1),
            _resp_bytes("observation", request_id=2),
        ])
        client = protocol.StarcraftProtocol(ws)
        step_req = sc_pb.Request(step=sc_pb.RequestStep(count=4))
        obs_req = sc_pb.Request(observation=sc_pb.RequestObservation(game_loop=123))

        out = client.send_multi([
            ("step", step_req),
            ("observation", obs_req),
        ])

        self.assertIsInstance(out[0], sc_pb.ResponseStep)
        self.assertIsInstance(out[1], sc_pb.ResponseObservation)
        self.assertEqual(step_req.id, 1)
        self.assertEqual(obs_req.id, 2)

    def test_send_multi_raises_on_unexpected_id(self):
        ws = _FakeWebSocket([
            _resp_bytes("action", request_id=999999),
            _resp_bytes("step", request_id=2),
        ])
        client = protocol.StarcraftProtocol(ws)

        with self.assertRaises(protocol.ConnectionError):
            client.send_multi([
                ("action", sc_pb.RequestAction()),
                ("step", sc_pb.RequestStep(count=1)),
            ])


if __name__ == "__main__":
    absltest.main()
