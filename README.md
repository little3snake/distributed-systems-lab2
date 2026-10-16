# Lab 2 — Multithreaded Server and REST API

Lab 2 contains two independent parts.

| Part | Directory | Purpose |
|---|---|---|
| Part 1 | `part1/` | Concurrent TCP clients, a shared counter, race-condition demonstration, and `Lock` fix |
| Part 2 | `part2/` | A Flask REST API for an in-memory `potions` resource |

## Quick start

Run the complete Part 1 experiment suite:

```powershell
cd part1
python load_test.py --suite
```

Install Flask and run Part 2:

```powershell
cd part2
python -m pip install -r requirements.txt
python app.py --host 127.0.0.1 --port 5000
```

Each part has its own README and report with detailed commands and results.
