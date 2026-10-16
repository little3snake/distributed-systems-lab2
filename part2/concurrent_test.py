import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


APP_PATH = Path(__file__).with_name("app.py")


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def request_json(method, url, data=None, timeout=5.0):
    """Send one HTTP request and return its status code and decoded JSON."""
    body = None if data is None else json.dumps(data).encode("utf-8")
    headers = {} if body is None else {"Content-Type": "application/json"}
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def wait_until_ready(base_url, timeout=5.0):
    """Wait until the newly started Flask server accepts HTTP requests."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status, _ = request_json("GET", f"{base_url}/potions", timeout=0.25)
            if status == 200:
                return
        except (URLError, TimeoutError, ConnectionError):
            time.sleep(0.05)
    raise TimeoutError("Flask server did not start in time")


def create_potion(base_url, number):
    potion = {
        "name": f"Concurrent Potion {number}",
        "effect": f"Test effect {number}",
        "ingredients": ["water", f"ingredient-{number}"],
    }
    return request_json("POST", f"{base_url}/potions", potion)


def run_experiment(mode, request_count, workers, race_delay):
    """Start one server mode and send many POST requests simultaneously."""
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    command = [sys.executable, str(APP_PATH), "--host", "127.0.0.1", "--port", str(port), "--lock-mode", mode, "--race-delay", str(race_delay),]
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        wait_until_ready(base_url)
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(create_potion, base_url, number)
                for number in range(1, request_count + 1)
            ]
            results = [future.result() for future in as_completed(futures)]
        elapsed = time.perf_counter() - started

        status, stored_potions = request_json("GET", f"{base_url}/potions")
        if status != 200:
            raise RuntimeError(f"GET /potions returned HTTP {status}")

        successful = [body for status, body in results if status == 201]
        returned_ids = [potion["id"] for potion in successful]
        unique_returned_ids = len(set(returned_ids))
        correct = (
            len(successful) == request_count
            and len(stored_potions) == request_count
            and unique_returned_ids == request_count
        )
        return {
            "mode": mode,
            "requests": request_count,
            "successful_responses": len(successful),
            "stored_potions": len(stored_potions),
            "unique_returned_ids": unique_returned_ids,
            "elapsed_seconds": elapsed,
            "correct": correct,
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def print_result(result):
    """Print one experiment in a format convenient for screenshots."""
    print(f"\nMode: {result['mode']}")
    print(f"Requests sent: {result['requests']}")
    print(f"HTTP 201 responses: {result['successful_responses']}")
    print(f"Potions actually stored: {result['stored_potions']}")
    print(f"Unique ids returned: {result['unique_returned_ids']}")
    print(f"Elapsed time: {result['elapsed_seconds']:.3f} s")
    print(f"Correct result: {result['correct']}")


def parse_arguments():
    """Read load-test settings from the command line."""
    parser = argparse.ArgumentParser(description="Concurrent REST API test")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--race-delay", type=float, default=0.01)
    return parser.parse_args()


def main():
    args = parse_arguments()
    if args.requests < 1 or args.workers < 1 or args.race_delay < 0:
        raise SystemExit("Requests/workers must be positive and delay cannot be negative")

    unsafe = run_experiment("unsafe", args.requests, args.workers, args.race_delay)
    locked = run_experiment("locked", args.requests, args.workers, args.race_delay)
    print_result(unsafe)
    print_result(locked)

    print("\nSummary")
    print(f"Unsafe lost records: {args.requests - unsafe['stored_potions']}")
    print(f"Locked result correct: {locked['correct']}")


if __name__ == "__main__":
    main()
