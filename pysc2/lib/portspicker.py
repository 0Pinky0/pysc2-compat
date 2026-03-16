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
"""Portpicker for multiple ports."""

import atexit
import json
import os
import socket
import tempfile
import time

import portpicker

_owned_ports = {}
_LEASE_DIR_ENV = 'SC2_PORT_LEASE_DIR'
_LEASE_DISABLE_ENV = 'SC2_PORT_LEASE_DISABLE'
_DEFAULT_LEASE_DIR = os.path.join(tempfile.gettempdir(), 'pysc2-port-leases')


def _env_flag_enabled(name):
    return str(os.environ.get(name, '')).strip().lower() in (
        '1', 'true', 'yes', 'on')


def _lease_dir():
    return os.environ.get(_LEASE_DIR_ENV, _DEFAULT_LEASE_DIR)


def _lease_path(port):
    return os.path.join(_lease_dir(), '%d.lease' % int(port))


def _write_lease_file(fd, port):
    payload = {
        'pid': os.getpid(),
        'hostname': socket.gethostname(),
        'port': int(port),
        'created_at': time.time(),
    }
    with os.fdopen(fd, 'w', encoding='utf-8') as lease_file:
        json.dump(payload, lease_file, sort_keys=True)


def _pid_is_alive(pid):
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _lease_is_stale(path, port):
    try:
        with open(path, 'r', encoding='utf-8') as lease_file:
            payload = json.load(lease_file)
    except (OSError, ValueError, TypeError):
        return portpicker.is_port_free(port)
    if payload.get('hostname') != socket.gethostname():
        return False
    pid = payload.get('pid')
    if pid is None:
        return portpicker.is_port_free(port)
    return (not _pid_is_alive(pid)) and portpicker.is_port_free(port)


def _acquire_lease(port):
    if _env_flag_enabled(_LEASE_DISABLE_ENV):
        return None
    os.makedirs(_lease_dir(), exist_ok=True)
    path = _lease_path(port)
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            if not _lease_is_stale(path, port):
                return None
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            continue
        _write_lease_file(fd, port)
        return path


def _reserve_port(port, *, uses_portpicker_return):
    if int(port) in _owned_ports:
        return False
    lease_path = _acquire_lease(port)
    if lease_path is None and not _env_flag_enabled(_LEASE_DISABLE_ENV):
        return False
    _owned_ports[int(port)] = {
        'lease_path': lease_path,
        'uses_portpicker_return': bool(uses_portpicker_return),
    }
    return True


def pick_unused_port(retry_interval_secs=1, retry_attempts=5):
    """Reserves and returns one unused port."""
    return pick_unused_ports(
        1,
        retry_interval_secs=retry_interval_secs,
        retry_attempts=retry_attempts,
    )[0]


def pick_unused_ports(num_ports, retry_interval_secs=1, retry_attempts=5):
    """Reserves and returns a list of `num_ports` unused ports."""
    if num_ports <= 0:
        raise ValueError('Number of ports, must be >= 1, got: %s' % num_ports)
    ports = []
    for _ in range(retry_attempts):
        while len(ports) < num_ports:
            port = portpicker.pick_unused_port()
            if port is None:
                break
            if int(port) in _owned_ports or int(port) in ports:
                portpicker.return_port(port)
                continue
            if not _reserve_port(port, uses_portpicker_return=True):
                portpicker.return_port(port)
                continue
            ports.append(int(port))
        if len(ports) == num_ports:
            return ports
        time.sleep(retry_interval_secs)

    return_ports(ports)
    raise RuntimeError('Unable to obtain %d unused ports.' % num_ports)


def pick_contiguous_unused_ports(
        num_ports,
        retry_interval_secs=1,
        retry_attempts=5):
    """Reserves and returns a list of `num_ports` contiguous unused ports."""
    if num_ports <= 0:
        raise ValueError('Number of ports, must be >= 1, got: %s' % num_ports)
    for _ in range(retry_attempts):
        start_port = portpicker.pick_unused_port()
        if start_port is None:
            time.sleep(retry_interval_secs)
            continue

        ports = [start_port + offset for offset in range(num_ports)]
        reserved = []
        success = True
        for port in ports:
            if not portpicker.is_port_free(port):
                success = False
                break
            if not _reserve_port(
                port,
                uses_portpicker_return=(port == start_port),
            ):
                success = False
                break
            reserved.append(port)

        if success:
            return [int(port) for port in ports]

        if start_port not in reserved:
            portpicker.return_port(start_port)
        return_ports(reserved)
        time.sleep(retry_interval_secs)

    raise RuntimeError('Unable to obtain %d contiguous unused ports.' % num_ports)


def return_ports(ports):
    """Returns previously reserved ports so that may be reused."""
    for port in list(ports):
        port = int(port)
        metadata = _owned_ports.pop(port, None)
        if metadata is None:
            portpicker.return_port(port)
            continue
        lease_path = metadata.get('lease_path')
        if lease_path:
            try:
                os.remove(lease_path)
            except FileNotFoundError:
                pass
        if metadata.get('uses_portpicker_return'):
            portpicker.return_port(port)


def _cleanup_owned_ports():
    if _owned_ports:
        return_ports(list(_owned_ports.keys()))


atexit.register(_cleanup_owned_ports)
