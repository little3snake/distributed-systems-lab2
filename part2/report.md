# Lab 2, Part 2 — Potions REST API Report

## 1. Objective

Build one Flask web service with an in-memory `potions` resource, JSON request
and response bodies, four required REST operations, and clean 404 handling.

## 2. Service design

The service runs as one process on one port. Potion recipes are stored in a
Python dictionary keyed by integer id. Each potion contains a name, an effect,
and a list of ingredients. A lock protects the dictionary and id generation
because Flask may handle requests in different threads. No database or second
service is used.

## 3. Endpoint summary

| Method | Path | Purpose | Success |
|---|---|---|---|
| GET | `/potions` | List all potions | 200 |
| GET | `/potions/<id>` | Fetch one potion | 200 |
| POST | `/potions` | Create a potion | 201 |
| DELETE | `/potions/<id>` | Delete a potion | 200 |

`GET` or `DELETE` for an unknown id returns `404` with
`{"error":"Potion not found"}`.

Additional validation returns `400` for malformed fields, `409` for a
duplicate potion name, `415` when POST data is not marked as JSON, and `405`
for a method that the endpoint does not support. All error bodies use JSON.

## 4. Request and response walkthrough

### 4.1 GET all potions

```powershell
curl.exe -i http://127.0.0.1:5000/potions
```

Initial response:

```http
HTTP/1.1 200 OK
Content-Type: application/json

[]
```

### 4.2 POST a potion

```powershell
curl.exe -i -X POST http://127.0.0.1:5000/potions -H "Content-Type: application/json" -d '{"name":"Moonlight Elixir","effect":"See clearly in darkness","ingredients":["moonwater","silverleaf"]}'
```

Response:

```http
HTTP/1.1 201 CREATED
Content-Type: application/json

{"effect":"See clearly in darkness","id":1,"ingredients":["moonwater","silverleaf"],"name":"Moonlight Elixir"}
```

### 4.3 GET potion by id

```powershell
curl.exe -i http://127.0.0.1:5000/potions/1
```

Response:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"effect":"See clearly in darkness","id":1,"ingredients":["moonwater","silverleaf"],"name":"Moonlight Elixir"}
```

### 4.4 DELETE potion by id

```powershell
curl.exe -i -X DELETE http://127.0.0.1:5000/potions/1
```

Response:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"effect":"See clearly in darkness","id":1,"ingredients":["moonwater","silverleaf"],"name":"Moonlight Elixir"}
```

### 4.5 Missing id

```powershell
curl.exe -i http://127.0.0.1:5000/potions/999
```

Response:

```http
HTTP/1.1 404 NOT FOUND
Content-Type: application/json

{"error":"Potion not found"}
```

### 4.6 Additional errors

Creating `Moonlight Elixir` a second time returns:

```http
HTTP/1.1 409 CONFLICT

{"error":"Potion with this name already exists"}
```

Sending POST data without `Content-Type: application/json` returns:

```http
HTTP/1.1 415 UNSUPPORTED MEDIA TYPE

{"error":"Content-Type must be application/json"}
```

Sending `PUT /potions/1` returns:

```http
HTTP/1.1 405 METHOD NOT ALLOWED

{"error":"Method not allowed"}
```

## 5. Validation

The service is checked for an empty list, successful POST, list after
creation, GET by id, DELETE, 404 after deletion, 404 for id 999, and 400
responses for invalid potion fields. Duplicate names, unsupported methods,
and incorrect media types are also checked. The recorded status summary is stored in
`logs/api_test_results.txt`.

The required operations are also executed with `curl.exe` using
`demo_requests.ps1`. Full HTTP status lines, headers, and JSON bodies are
stored in `logs/curl_demo.txt`.

## 6. Conclusion

The service implements all required operations using one process, one port,
JSON, and in-memory storage. Missing potion recipes produce controlled JSON
404 responses instead of uncaught exceptions.

## 7. Concurrent request experiment

`concurrent_test.py` starts the API twice and sends 100 POST requests with 20
client threads. Every request uses a unique potion name, so a `409` response
cannot affect the result. A 0.01-second delay is inserted between reading and
updating `next_potion_id` to make competing thread execution visible.

### 7.1 Without Lock

All 100 requests returned `201`, but only 14 potions remained in the shared
dictionary and only 14 unique ids were returned. Several request threads read
the same value of `next_potion_id` before any of them updated it. They then
wrote different potions under the same dictionary key, overwriting earlier
records.

### 7.2 With Lock

The same test with `threading.Lock` produced 100 successful responses, 100
stored potions, and 100 unique ids. Only one thread at a time could check the
shared data, take an id, write the potion, and increment the id counter.

| Mode | POST requests | HTTP 201 | Stored | Unique ids | Time | Correct |
|---|---:|---:|---:|---:|---:|---|
| unsafe | 100 | 100 | 14 | 14 | 0.208 s | No |
| locked | 100 | 100 | 100 | 100 | 1.108 s | Yes |

The exact unsafe count and timing may change between runs because thread
scheduling is non-deterministic. The locked result remains correct.
