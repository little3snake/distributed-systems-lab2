# Lab 2, Part 1 — Multithreaded Server Report

## 1. Objective

Extend the Lab 1 TCP server to handle clients concurrently, demonstrate a
race condition on shared state, fix it with `threading.Lock`, and compare
sequential and multithreaded processing time.

## 2. Architecture

The server supports two execution modes:

- `sequential`: `accept()` calls `handle_client()` directly, so the next client
  waits until the current client disconnects.
- `threaded`: every successful `accept()` creates a new `threading.Thread` that
  runs `handle_client()`. The main thread immediately returns to `accept()`.

All handlers receive the same `SharedCounter` object. Normal Echo+ messages
increment this counter. `STATS` reads it without changing it.

## 3. Race condition

An increment is a read-modify-write operation:

```python
current_value = self.value
time.sleep(self.race_delay)
self.value = current_value + 1
```

Without synchronization, several threads can read the same old value. They
then write the same incremented value, so some increments disappear. The short
delay makes this interleaving easy to reproduce; it does not create the race,
but widens the interval in which it occurs.

## 4. Experiment 1 — before synchronization

Configuration:

- server mode: `threaded`
- counter mode: `unsafe`
- clients: 20 simultaneous clients
- messages per client: 25
- expected total: 500
- race delay: 2 ms

Measured result on 15 October 2026:

| Expected | Actual | Lost updates | Time |
|---:|---:|---:|---:|
| 500 | 26 | 474 | 0.092 s |

The result is incorrect because threads overwrite increments made by other
threads. Repeated runs may produce a different actual value, which shows the
non-deterministic nature of the race.

Evidence: `logs/race_unsafe.log` and `logs/experiment_results.txt`.

## 5. Experiment 2 — after synchronization

The corrected implementation executes the same read-modify-write operation
inside a lock:

```python
with self.lock:
    return self._increment_without_lock()
```

The test configuration is identical to Experiment 1.

| Expected | Actual | Result | Time |
|---:|---:|---|---:|
| 500 | 500 | Correct | 1.318 s |

Only one thread can update the shared counter at a time, so no increments are
lost. The race demonstration deliberately sleeps inside the critical section,
which explains the longer time in this particular correctness experiment.

Evidence: `logs/race_locked.log` and `logs/experiment_results.txt`.

## 6. Experiment 3 — sequential vs multithreaded

Both modes processed 20 clients. Each client sent one message, and the server
simulated 50 ms of work per message. The counter used the corrected locked
mode and no race delay.

| Server mode | Clients | Correct count | Time |
|---|---:|---:|---:|
| Sequential | 20 | 20 | 1.040 s |
| Threaded | 20 | 20 | 0.065 s |

Measured speedup:

```text
1.040 / 0.065 = 16.06×
```

The sequential server performs the simulated waits one after another. Threads
overlap those waits, so the concurrent run finishes sooner.

Evidence: `logs/performance_sequential.log`,
`logs/performance_threaded.log`, and `logs/experiment_results.txt`.

## 7. Reproduction

Run all experiments with:

```powershell
python load_test.py --suite
```

The script launches each server configuration on a free local port, starts the
clients with `ThreadPoolExecutor`, validates all Echo+ and `QUIT` replies,
queries `STATS`, prints the results, and terminates the test server.

## 8. Conclusion

The threaded server accepts and processes multiple clients concurrently. The
unsafe experiment demonstrates that shared mutable state can lose updates even
when every individual handler works correctly. `threading.Lock` makes the
counter deterministic. The timing experiment also shows the benefit of
concurrency when client work includes waiting.
