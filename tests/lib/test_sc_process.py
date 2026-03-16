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
"""Tests for sc_process.py."""

import os
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest import mock

from absl.testing import absltest

from pysc2.lib import sc_process


class SCProcessTest(absltest.TestCase):

    def test_close_returns_owned_port(self):
        tmp_dir = tempfile.mkdtemp()
        proc = sc_process.StarcraftProcess.__new__(sc_process.StarcraftProcess)
        proc._controller = None
        proc._proc = None
        proc._tmp_dir = tmp_dir
        proc._port = 4321
        proc._owns_port = True

        with mock.patch.object(sc_process.portspicker, 'return_ports') as return_ports:
            proc.close()

        return_ports.assert_called_once_with([4321])
        self.assertFalse(os.path.exists(tmp_dir))

    def test_close_does_not_return_explicit_port(self):
        tmp_dir = tempfile.mkdtemp()
        proc = sc_process.StarcraftProcess.__new__(sc_process.StarcraftProcess)
        proc._controller = None
        proc._proc = None
        proc._tmp_dir = tmp_dir
        proc._port = 5432
        proc._owns_port = False

        with mock.patch.object(sc_process.portspicker, 'return_ports') as return_ports:
            proc.close()

        return_ports.assert_not_called()
        self.assertFalse(os.path.exists(tmp_dir))

    def test_launch_slot_serializes_concurrent_startup(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        first_entered = threading.Event()
        release_first = threading.Event()
        second_entered = threading.Event()

        def first_worker():
            with sc_process._launch_slot():
                first_entered.set()
                release_first.wait(timeout=5.0)

        def second_worker():
            first_entered.wait(timeout=5.0)
            with sc_process._launch_slot():
                second_entered.set()

        with mock.patch.dict(
            os.environ,
            {
                'SC2_LAUNCH_SEMAPHORE_DIR': tmp_dir.name,
                'SC2_LAUNCH_MAX_CONCURRENT': '1',
                'SC2_LAUNCH_ACQUIRE_TIMEOUT_SECONDS': '5',
            },
            clear=False,
        ):
            thread_one = threading.Thread(target=first_worker)
            thread_two = threading.Thread(target=second_worker)
            thread_one.start()
            thread_two.start()
            self.assertTrue(first_entered.wait(timeout=5.0))
            time.sleep(0.5)
            self.assertFalse(second_entered.is_set())
            release_first.set()
            thread_one.join(timeout=5.0)
            thread_two.join(timeout=5.0)

        self.assertTrue(second_entered.is_set())

    def test_constructor_releases_owned_port_when_connect_fails(self):
        run_config = SimpleNamespace(
            tmp_dir=None,
            data_dir='.',
            cwd='.',
            env=dict(os.environ),
        )
        fake_proc = mock.Mock()

        with mock.patch.dict(
            os.environ,
            {'SC2_LAUNCH_MAX_CONCURRENT': '0'},
            clear=False,
        ), mock.patch.object(
            sc_process.StarcraftProcess,
            '_check_exists',
        ), mock.patch.object(
            sc_process.StarcraftProcess,
            '_launch',
            return_value=fake_proc,
        ), mock.patch.object(
            sc_process.StarcraftProcess,
            '_shutdown',
        ), mock.patch.object(
            sc_process.portspicker,
            'pick_unused_port',
            return_value=6543,
        ), mock.patch.object(
            sc_process.portspicker,
            'return_ports',
        ) as return_ports, mock.patch.object(
            sc_process.remote_controller,
            'RemoteController',
            side_effect=RuntimeError('connect failed'),
        ):
            with self.assertRaisesRegex(RuntimeError, 'connect failed'):
                sc_process.StarcraftProcess(
                    run_config=run_config,
                    exec_path='/bin/true',
                    version=None,
                )

        return_ports.assert_called_once_with([6543])


if __name__ == '__main__':
    absltest.main()
