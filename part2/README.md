# Part 2 — Potions REST API

A single Flask service that stores potion recipes in memory and exchanges JSON.

## Potion format

```json
{
  "id": 1,
  "name": "Moonlight Elixir",
  "effect": "See clearly in darkness",
  "ingredients": ["moonwater", "silverleaf"]
}
```

## Install and run

```powershell
cd "C:\Users\user\Desktop\SI\4th year\DistributedSystems\lab2\part2"
python -m pip install -r requirements.txt
python app.py --host 127.0.0.1 --port 5000
```

Data exists only while the process is running. Restarting the service clears
all potions and resets the next id to 1.

## Endpoints

- `GET /potions` — return all potions. Success: `200 OK`.
- `GET /potions/<id>` — return one potion. Success: `200 OK`; missing id: `404 Not Found`.
- `POST /potions` — create a potion from JSON with `name`, `effect`, and `ingredients`. Success: `201 Created`; invalid body: `400 Bad Request`.
- `DELETE /potions/<id>` — delete and return one potion. Success: `200 OK`; missing id: `404 Not Found`.

## Error responses

- `400 Bad Request` — malformed JSON or invalid `name`, `effect`, or `ingredients`.
- `404 Not Found` — potion or route does not exist.
- `405 Method Not Allowed` — the route does not support the requested HTTP method.
- `409 Conflict` — another potion already has the same name (case-insensitive).
- `415 Unsupported Media Type` — a POST body was not sent with `Content-Type: application/json`.

## curl examples

List potions:

```powershell
curl.exe -i http://127.0.0.1:5000/potions
```

Create a potion:

```powershell
curl.exe -i -X POST http://127.0.0.1:5000/potions -H "Content-Type: application/json" -d '{"name":"Moonlight Elixir","effect":"See clearly in darkness","ingredients":["moonwater","silverleaf"]}'
```

Get potion 1:

```powershell
curl.exe -i http://127.0.0.1:5000/potions/1
```

Delete potion 1:

```powershell
curl.exe -i -X DELETE http://127.0.0.1:5000/potions/1
```

Request a missing potion:

```powershell
curl.exe -i http://127.0.0.1:5000/potions/999
```

Run the complete demonstration after starting the service:

```powershell
.\demo_requests.ps1
```

The captured example output is stored in `logs/curl_demo.txt`.

## Concurrent request and Lock experiment

Flask handles requests in separate threads. All of them share the `potions`
dictionary and `next_potion_id`. The server therefore supports two educational
modes:

- `--lock-mode locked` protects id generation and dictionary access with
  `threading.Lock` (default and correct mode).
- `--lock-mode unsafe` removes that protection to demonstrate a race condition.

Run both experiments automatically:

```powershell
python concurrent_test.py --requests 100 --workers 20 --race-delay 0.01
```

The test starts a fresh server for each mode, sends 100 POST requests using 20
client threads, fetches the final list, and compares the number of successful
responses, stored potions, and unique returned ids. `--race-delay` widens the
short interval between reading and updating `next_potion_id`, making the race
easy to reproduce.

Example manual server commands:

```powershell
python app.py --port 5000 --lock-mode unsafe --race-delay 0.01
python app.py --port 5000 --lock-mode locked --race-delay 0.01
```

Use `locked` for normal API work. The `unsafe` mode exists only for the
experiment.
