# Launch Stability Progress

## Completed

- Captured the implementation plan for filesystem-backed port leases and launch
  throttling in the SC2 startup path.
- Added filesystem-backed per-port leases in `pysc2/lib/portspicker.py`.
- Added targeted lease tests covering duplicate retries, lease cleanup, stale
  lease reclaim, and contiguous-range blocking.
- Verified the stage-1 port lease behavior with:
  `pytest tests/lib/test_portspicker.py` (`18 passed`).
- Added a cross-process launch semaphore in `pysc2/lib/sc_process.py` and
  switched auto-assigned websocket ports to use the leased `portspicker`
  wrapper.
- Hardened `pysc2/env/sc2_env.py` partial multiplayer startup cleanup so failed
  launches release already-started processes and reserved side ports.
- Added focused unit coverage in `tests/lib/test_sc_process.py` and
  `tests/env/test_sc2_env.py`.
- Verified the combined launch-mitigation target suite with:
  `pytest tests/lib/test_portspicker.py tests/lib/test_sc_process.py`
  `tests/env/test_sc2_env.py -k "PortsTest or SCProcessTest or LaunchGameCleanupTest"`
  (`23 passed`).

## Pending

- Re-run the vector boundary probe after the mitigations land.
