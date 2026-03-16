# Launch Stability Plan

## Goal

Reduce high-concurrency SC2 startup failures during vector-environment scaling
by coordinating port allocation across processes and throttling how many SC2
processes attempt to boot at the same time.

## Plan

1. Add filesystem-backed port leases in `pysc2/lib/portspicker.py` so websocket
   and multiplayer side ports are coordinated across worker processes on the
   same machine.
2. Add a cross-process launch semaphore in `pysc2/lib/sc_process.py` so SC2
   startup and websocket connect happen under a bounded amount of parallelism.
3. Harden `pysc2/env/sc2_env.py` startup cleanup so partial multiplayer launch
   failures release already-started processes and reserved ports.
4. Add focused unit tests for lease behavior, semaphore behavior, and partial
   startup cleanup.
5. Re-run the vector-env boundary experiment to see whether the stable maximum
   env count moves beyond the current `18`-env boundary.
