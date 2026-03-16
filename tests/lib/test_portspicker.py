#!/usr/bin/python
# Copyright 2018 Google Inc. All Rights Reserved.
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
"""Tests for portspicker.py."""

import json
import os
import socket
import tempfile
from unittest import mock

from absl.testing import absltest
from absl.testing import parameterized

from pysc2.lib import portspicker


class PortsTest(parameterized.TestCase):

    def setUp(self):
        super().setUp()
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)
        env_patch = mock.patch.dict(
            os.environ,
            {
                'SC2_PORT_LEASE_DIR': self._tmp_dir.name,
            },
            clear=False,
        )
        env_patch.start()
        self.addCleanup(env_patch.stop)
        portspicker.return_ports(list(portspicker._owned_ports.keys()))

    @parameterized.parameters(range(1, 10))
    def testNonContiguousReservation(self, num_ports):
        reserved = portspicker.pick_unused_ports(num_ports)
        self.assertLen(reserved, num_ports)
        portspicker.return_ports(reserved)

    @parameterized.parameters(range(2, 5))
    def testContiguousReservation(self, num_ports):
        reserved = portspicker.pick_contiguous_unused_ports(num_ports)
        self.assertLen(reserved, num_ports)
        portspicker.return_ports(reserved)

    def testInvalidReservation(self):
        with self.assertRaises(ValueError):
            portspicker.pick_unused_ports(0)

    def testInvalidContiguousReservation(self):
        with self.assertRaises(ValueError):
            portspicker.pick_contiguous_unused_ports(0)

    def testDuplicateCandidatesAreRetriedUntilDistinct(self):
        with mock.patch.object(
            portspicker.portpicker,
            'pick_unused_port',
            side_effect=[12000, 12000, 12001],
        ), mock.patch.object(
            portspicker.portpicker,
            'return_port',
        ) as return_port:
            reserved = portspicker.pick_unused_ports(2, retry_attempts=1)

        self.assertEqual(reserved, [12000, 12001])
        self.assertEqual(return_port.call_args_list, [mock.call(12000)])
        portspicker.return_ports(reserved)

    def testReturnPortsRemovesLeaseFiles(self):
        with mock.patch.object(
            portspicker.portpicker,
            'pick_unused_port',
            side_effect=[13000],
        ), mock.patch.object(
            portspicker.portpicker,
            'return_port',
        ) as return_port:
            reserved = portspicker.pick_unused_ports(1, retry_attempts=1)
            lease_path = portspicker._lease_path(reserved[0])
            self.assertTrue(os.path.exists(lease_path))

            portspicker.return_ports(reserved)

        self.assertFalse(os.path.exists(lease_path))
        self.assertEqual(return_port.call_args_list, [mock.call(13000)])

    def testStaleLeaseIsReclaimed(self):
        stale_port = 14000
        with open(portspicker._lease_path(stale_port), 'w', encoding='utf-8') as lease_file:
            json.dump(
                {
                    'pid': 999999,
                    'hostname': socket.gethostname(),
                    'port': stale_port,
                    'created_at': 0.0,
                },
                lease_file,
            )

        with mock.patch.object(
            portspicker.portpicker,
            'pick_unused_port',
            return_value=stale_port,
        ), mock.patch.object(
            portspicker.portpicker,
            'is_port_free',
            return_value=True,
        ), mock.patch.object(
            portspicker,
            '_pid_is_alive',
            return_value=False,
        ):
            reserved = portspicker.pick_unused_ports(1, retry_attempts=1)

        self.assertEqual(reserved, [stale_port])
        portspicker.return_ports(reserved)

    def testContiguousReservationHonorsExistingLease(self):
        blocked_port = 15001
        with open(portspicker._lease_path(blocked_port), 'w', encoding='utf-8') as lease_file:
            json.dump(
                {
                    'pid': os.getpid(),
                    'hostname': socket.gethostname(),
                    'port': blocked_port,
                    'created_at': 0.0,
                },
                lease_file,
            )

        with mock.patch.object(
            portspicker.portpicker,
            'pick_unused_port',
            return_value=15000,
        ), mock.patch.object(
            portspicker.portpicker,
            'is_port_free',
            return_value=True,
        ), mock.patch.object(
            portspicker.portpicker,
            'return_port',
        ) as return_port:
            with self.assertRaises(RuntimeError):
                portspicker.pick_contiguous_unused_ports(3, retry_attempts=1)

        self.assertEqual(return_port.call_args_list, [mock.call(15000)])


if __name__ == '__main__':
    absltest.main()
