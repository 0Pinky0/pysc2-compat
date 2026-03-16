# Copyright 2017-2018 Google Inc. All Rights Reserved.
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
"""Launch the game and set up communication."""

import contextlib
import json
import os
import platform
import shutil
import socket
import subprocess
import tempfile
import time
from pysc2.lib import flags
from pysc2.lib import logging

from pysc2.lib import portspicker
from pysc2.lib import remote_controller
from pysc2.lib import stopwatch

flags.DEFINE_bool(
    'sc2_verbose', False, 'Enable SC2 verbose logging.', allow_hide_cpp=True)
flags.DEFINE_bool(
    'sc2_verbose_mp', False, 'Enable SC2 verbose multiplayer logging.')
flags.DEFINE_bool('sc2_gdb', False, 'Run SC2 in gdb.')
flags.DEFINE_bool('sc2_strace', False, 'Run SC2 in strace.')
flags.DEFINE_integer('sc2_port', None,
                     'If set, connect to the instance on '
                     'localhost:sc2_port instead of launching one.')
FLAGS = flags.FLAGS

sw = stopwatch.sw
_SC2_SHOW_STDERR = os.environ.get('SC2_SHOW_STDERR', '')
_LAUNCH_MAX_CONCURRENT_ENV = 'SC2_LAUNCH_MAX_CONCURRENT'
_LAUNCH_SEMAPHORE_DIR_ENV = 'SC2_LAUNCH_SEMAPHORE_DIR'
_LAUNCH_TIMEOUT_ENV = 'SC2_LAUNCH_ACQUIRE_TIMEOUT_SECONDS'
_DEFAULT_LAUNCH_MAX_CONCURRENT = 4
_DEFAULT_LAUNCH_TIMEOUT_SECONDS = 120
_DEFAULT_LAUNCH_SEMAPHORE_DIR = os.path.join(
    tempfile.gettempdir(),
    'pysc2-launch-semaphore',
)


class SC2LaunchError(Exception):
    pass


def _env_int(name, default):
    raw = str(os.environ.get(name, default)).strip()
    try:
        return int(raw)
    except ValueError:
        logging.warning('Invalid integer for %s: %r. Using %r.', name, raw, default)
        return int(default)


def _launch_max_concurrent():
    return max(0, _env_int(_LAUNCH_MAX_CONCURRENT_ENV, _DEFAULT_LAUNCH_MAX_CONCURRENT))


def _launch_timeout_seconds():
    return max(1, _env_int(_LAUNCH_TIMEOUT_ENV, _DEFAULT_LAUNCH_TIMEOUT_SECONDS))


def _launch_semaphore_dir():
    return os.environ.get(_LAUNCH_SEMAPHORE_DIR_ENV, _DEFAULT_LAUNCH_SEMAPHORE_DIR)


def _launch_slot_path(slot_idx):
    return os.path.join(_launch_semaphore_dir(), 'slot-%02d.lock' % int(slot_idx))


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


def _launch_slot_is_stale(path):
    try:
        with open(path, 'r', encoding='utf-8') as slot_file:
            payload = json.load(slot_file)
    except (OSError, ValueError, TypeError):
        return True
    if payload.get('hostname') != socket.gethostname():
        return False
    pid = payload.get('pid')
    if pid is None:
        return True
    return not _pid_is_alive(pid)


def _write_launch_slot(fd, slot_idx):
    payload = {
        'pid': os.getpid(),
        'hostname': socket.gethostname(),
        'slot': int(slot_idx),
        'created_at': time.time(),
    }
    with os.fdopen(fd, 'w', encoding='utf-8') as slot_file:
        json.dump(payload, slot_file, sort_keys=True)


@contextlib.contextmanager
def _launch_slot():
    max_concurrent = _launch_max_concurrent()
    if max_concurrent <= 0:
        yield
        return

    os.makedirs(_launch_semaphore_dir(), exist_ok=True)
    deadline = time.time() + _launch_timeout_seconds()
    slot_path = None
    while slot_path is None:
        for slot_idx in range(max_concurrent):
            candidate = _launch_slot_path(slot_idx)
            try:
                fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                if not _launch_slot_is_stale(candidate):
                    continue
                try:
                    os.remove(candidate)
                except FileNotFoundError:
                    pass
                continue
            _write_launch_slot(fd, slot_idx)
            slot_path = candidate
            break
        if slot_path is not None:
            break
        if time.time() >= deadline:
            raise SC2LaunchError('Timed out waiting for an SC2 launch slot.')
        time.sleep(0.25)

    try:
        yield
    finally:
        if slot_path:
            try:
                os.remove(slot_path)
            except FileNotFoundError:
                pass


class StarcraftProcess(object):
    """Launch a starcraft server, initialize a controller, and later, clean up.

    This is best used from run_configs, which decides which version to run, and
    where to find it.

    It is important to call `close` or use it as a context manager, otherwise
    you'll likely leak temp files and SC2 processes.
    """

    def __init__(self, run_config, exec_path, version, full_screen=False,
                 extra_args=None, verbose=False, host=None, port=None,
                 connect=True, timeout_seconds=None, window_size=(640, 480),
                 window_loc=(50, 50), **kwargs):
        """Launch the SC2 process.

        Args:
            run_config: `run_configs.lib.RunConfig` object.
            exec_path: Path to the binary to run.
            version: `run_configs.lib.Version` object.
            full_screen: Whether to launch the game window full_screen on win/mac.
            extra_args: List of additional args for the SC2 process.
            verbose: Whether to have the SC2 process do verbose logging.
            host: IP for the game to listen on for its websocket. This is
              usually "127.0.0.1", or "::1", but could be others as well.
            port: Port SC2 should listen on for the websocket.
            connect: Whether to create a RemoteController to connect.
            timeout_seconds: Timeout for the remote controller.
            window_size: Screen size if not full screen.
            window_loc: Screen location if not full screen.
            **kwargs: Extra arguments for _launch (useful for subclasses).
        """
        self._proc = None
        self._controller = None
        self._check_exists(exec_path)
        self._tmp_dir = tempfile.mkdtemp(prefix='sc-', dir=run_config.tmp_dir)
        self._host = host or '127.0.0.1'
        self._owns_port = False
        if FLAGS.sc2_port:
            self._port = FLAGS.sc2_port
        elif port is not None:
            self._port = port
        else:
            self._port = portspicker.pick_unused_port()
            self._owns_port = True
        self._version = version

        args = [
            exec_path,
            '-listen', self._host,
            '-port', str(self._port),
            '-dataDir', os.path.join(run_config.data_dir, ''),
            '-tempDir', os.path.join(self._tmp_dir, ''),
        ]
        if ':' in self._host:
            args += ['-ipv6']
        if platform.system() != 'Linux':
            if full_screen:
                args += ['-displayMode', '1']
            else:
                args += [
                    '-displayMode', '0',
                    '-windowwidth', str(window_size[0]),
                    '-windowheight', str(window_size[1]),
                    '-windowx', str(window_loc[0]),
                    '-windowy', str(window_loc[1]),
                ]

        if verbose or FLAGS.sc2_verbose:
            args += ['-verbose']
        if FLAGS.sc2_verbose_mp:
            args += ['-verboseMP']
        if self._version and self._version.data_version:
            args += ['-dataVersion', self._version.data_version.upper()]
        if extra_args:
            args += extra_args

        if FLAGS.sc2_gdb:
            print('Launching: gdb', args[0])
            print('GDB run command:')
            print('  run %s' % ' '.join(args[1:]))
            print('\n')
            args = ['gdb', args[0]]
            timeout_seconds = 3600 * 6
        elif FLAGS.sc2_strace:
            strace_out = '/tmp/sc2-strace.txt'
            print('Launching in strace. Redirecting output to', strace_out)
            args = ['strace', '-f', '-o', strace_out] + args
        else:
            logging.info('Launching SC2: %s', ' '.join(args))

        try:
            with sw('startup'):
                with _launch_slot():
                    if not FLAGS.sc2_port:
                        self._proc = self._launch(run_config, args, **kwargs)
                    if connect:
                        self._controller = remote_controller.RemoteController(
                            self._host, self._port, self, timeout_seconds=timeout_seconds)
        except:
            self.close()
            raise

    @sw.decorate
    def close(self):
        """Shut down the game and clean up."""
        if hasattr(self, '_controller') and self._controller:
            self._controller.quit()
            self._controller.close()
            self._controller = None
        self._shutdown()
        if hasattr(self, '_port') and self._port:
            if self._owns_port:
                portspicker.return_ports([self._port])
            self._port = None
            self._owns_port = False
        if hasattr(self, '_tmp_dir') and os.path.exists(self._tmp_dir):
            shutil.rmtree(self._tmp_dir)

    @property
    def controller(self):
        return self._controller

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    @property
    def version(self):
        return self._version

    def __enter__(self):
        return self.controller

    def __exit__(self, unused_exception_type, unused_exc_value, unused_traceback):
        self.close()

    def __del__(self):
        # Prefer using a context manager, but this cleans most other cases.
        self.close()

    def _check_exists(self, exec_path):
        if not os.path.isfile(exec_path):
            raise RuntimeError("Trying to run '%s', but it doesn't exist" % exec_path)
        if not os.access(exec_path, os.X_OK):
            raise RuntimeError(
                "Trying to run '%s', but it isn't executable." % exec_path)

    def _launch(self, run_config, args, **kwargs):
        """Launch the process and return the process object."""
        # Drop higher-level params (e.g. multiplayer extra_ports) that Popen
        # doesn't understand.
        kwargs.pop('extra_ports', None)
        if 'stderr' not in kwargs:
            show = str(_SC2_SHOW_STDERR).lower() in ('1', 'true', 'yes', 'on', 'debug')
            kwargs['stderr'] = None if show else subprocess.DEVNULL
        try:
            with sw('popen'):
                return subprocess.Popen(
                    args, cwd=run_config.cwd, env=run_config.env, **kwargs)
        except OSError as e:
            logging.exception('Failed to launch')
            raise SC2LaunchError('Failed to launch: %s' % args) from e

    def _shutdown(self):
        """Terminate the sub-process."""
        if self._proc:
            ret = _shutdown_proc(self._proc, 3)
            logging.info('Shutdown with return code: %s', ret)
            self._proc = None

    @property
    def running(self):
        if FLAGS.sc2_port:
            return True
        # poll returns None if it's running, otherwise the exit code.
        return self._proc and (self._proc.poll() is None)

    @property
    def pid(self):
        return self._proc.pid if self.running else None


def _shutdown_proc(p, timeout):
    """Wait for a proc to shut down, then terminate or kill it after
    `timeout`."""
    freq = 10  # how often to check per second
    for _ in range(1 + timeout * freq):
        p.terminate()
        ret = p.poll()
        if ret is not None:
            logging.info('Shutdown gracefully.')
            return ret
        time.sleep(1 / freq)
    logging.warning('Killing the process.')
    p.kill()
    return p.wait()
