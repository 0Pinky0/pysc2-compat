# Launch Stability Progress

## Completed

- Captured the implementation plan for filesystem-backed port leases and launch
  throttling in the SC2 startup path.
- Added filesystem-backed per-port leases in `pysc2/lib/portspicker.py`.
- Added targeted lease tests covering duplicate retries, lease cleanup, stale
  lease reclaim, and contiguous-range blocking.
- Verified the stage-1 port lease behavior with:
  `pytest tests/lib/test_portspicker.py` (`18 passed`).

## Pending

- Implement launch throttling in `pysc2/lib/sc_process.py`.
- Harden partial startup cleanup in `pysc2/env/sc2_env.py`.
- Re-run the vector boundary probe after the mitigations land.
