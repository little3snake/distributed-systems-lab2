# Part 1 — Multithreaded TCP Server


This part extends the Lab 1. Each accepted connection can run in
its own `threading.Thread`. All client threads share one processed-message
counter.

## Files

| File | Purpose                                                             |
|---|---------------------------------------------------------------------|
| `server.py` | server with sequential/threaded and unsafe/locked modes             |
| `load_test.py` | starts the server, emulates concurrent clients, and records results |
| `logs/` | Server logs and numeric experiment results                          |
| `report.md` | Experiment setup, results, and explanation                          |

## Server options

```powershell
python server.py --host 127.0.0.1 --port 5050 --mode threaded --counter-mode locked
```

- `--mode sequential` handles a client completely before accepting the next one.
- `--mode threaded` starts one thread for every accepted connection.
- `--counter-mode unsafe` performs an unprotected read-modify-write operation.
- `--counter-mode locked` protects the counter with `threading.Lock`.
- `--race-delay` widens the race window for a reproducible demonstration.
- `--processing-delay` simulates work for the performance comparison.

## Run all required experiments

```powershell
python load_test.py --suite
```

The suite performs:

1. 20 clients × 25 messages with the unsafe counter.
2. The same load with `threading.Lock`.
3. 20 clients against the sequential server with 50 ms simulated work.
4. The same 20 clients against the threaded server.

The terminal prints the expected and actual counter, elapsed time, lost
updates, and speedup. The same values are saved to
`logs/experiment_results.txt`.

## Repeat the experiments on Windows

Open PowerShell and move to the Part 1 directory:

```powershell
cd "C:\Users\user\Desktop\SI\4th year\DistributedSystems\lab2\part1"
```
or your path to the folder.

Run the complete experiment suite:

```powershell
python load_test.py --suite
```

If the `python` command is unavailable, use the full Python path:

```powershell
& "C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe" load_test.py --suite
```
or your path to python.exe

Every run replaces these files with new results:

```text
logs/race_unsafe.log
logs/race_locked.log
logs/performance_sequential.log
logs/performance_threaded.log
logs/experiment_results.txt
```

Display the numeric summary in PowerShell:

```powershell
Get-Content .\logs\experiment_results.txt
```

The unsafe counter and measured times may change between runs. The locked
counter must remain correct. After repeating the suite, copy the new values
from `experiment_results.txt` into the result tables in `report.md`.

## Run one custom experiment

```powershell
python load_test.py --server-mode threaded --counter-mode locked --clients 20 --messages 10
```

## Protocol additions

- On connection: `READY`
- `STATS`: returns `COUNT <value>` without incrementing the counter.
- `QUIT`: returns `BYE` and closes that client connection.
- Any other non-empty UTF-8 line increments the shared counter and receives an
  uppercase Echo+ response with timestamp and counter value.
