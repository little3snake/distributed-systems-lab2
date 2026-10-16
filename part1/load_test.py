import argparse
import concurrent.futures
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path


BUFFER_SIZE = 4096
SERVER_PATH = Path(__file__).with_name("server.py")
LOG_DIRECTORY = Path(__file__).with_name("logs")


@dataclass
class ExperimentResult:
    """stores the configuration and measured result of one experiment"""
    name: str
    expected_count: int
    actual_count: int
    elapsed_seconds: float
    server_mode: str
    counter_mode: str
    log_path: Path

    @property
    def correct(self):
        """checks whether the actual counter equals the expected counter"""
        return self.expected_count == self.actual_count

# from wait_until_ready
def receive_line(client_socket):
    """receives and decodes one newline-terminated UTF-8 response"""
    buffer = b""
    while b"\n" not in buffer:
        data = client_socket.recv(BUFFER_SIZE)
        if not data:
            raise ConnectionError("Server closed the connection before sending a full line")
        buffer += data
    raw_line, _ = buffer.split(b"\n", 1)
    return raw_line.decode("utf-8")

# find free port
def find_free_port():
    """asks the operating system for an available local TCP port"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def wait_until_ready(host, port, timeout=5.0):
    """waits until the test server accepts a connection and sends READY"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.25) as client:
                if receive_line(client) != "READY":
                    raise RuntimeError("Unexpected server greeting")
                # do it bec we send only one message per client
                client.sendall(b"QUIT\n")
                receive_line(client)
                return
        except (ConnectionRefusedError, OSError):
            time.sleep(0.05)
    raise TimeoutError("Server did not start in time")


def client_worker(host, port, client_number, messages_per_client, start_barrier):
    """emulates one client and validates all responses from the server"""
    with socket.create_connection((host, port), timeout=10) as client:
        client.settimeout(10)
        if receive_line(client) != "READY":
            raise RuntimeError("Unexpected server greeting")

        if start_barrier is not None:
            start_barrier.wait(timeout=10)

        for message_number in range(messages_per_client):
            message = f"client {client_number} message {message_number}"
            client.sendall((message + "\n").encode("utf-8"))
            reply = receive_line(client)
            # just checker right words
            if message.upper() not in reply:
                raise RuntimeError(f"Unexpected echo response: {reply}")

        client.sendall(b"QUIT\n")
        if receive_line(client) != "BYE":
            raise RuntimeError("Server did not acknowledge QUIT")


def query_counter(host, port):
    """requests STATS and returns the server's shared counter value"""
    with socket.create_connection((host, port), timeout=5) as client:
        client.settimeout(5)
        if receive_line(client) != "READY":
            raise RuntimeError("Unexpected server greeting")
        client.sendall(b"STATS\n")
        response = receive_line(client)
        client.sendall(b"QUIT\n")
        receive_line(client)

    prefix = "COUNT "
    if not response.startswith(prefix):
        raise RuntimeError(f"Unexpected STATS response: {response}")
    return int(response[len(prefix):])


def run_experiment(name, server_mode, counter_mode, clients, messages_per_client, race_delay=0.0, processing_delay=0.0,):
    """runs one server configuration and measures its clients and counter"""
    host = "127.0.0.1"
    port = find_free_port()
    LOG_DIRECTORY.mkdir(exist_ok=True)
    log_path = LOG_DIRECTORY / f"{name}.log"

    command = [sys.executable, str(SERVER_PATH), "--host", host,
               "--port", str(port),
               "--mode", server_mode,
               "--counter-mode", counter_mode,
               "--race-delay", str(race_delay),
               "--processing-delay", str(processing_delay),
    ]

    with log_path.open("w", encoding="utf-8") as log_file:
        # Popen - запускает server.py как отдельный процесс
        server = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT, text=True,)

        try:
            wait_until_ready(host, port)
            # all clients start in one time
            barrier = threading.Barrier(clients) if server_mode == "threaded" else None
            started_at = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=clients) as executor:
                futures = [executor.submit(client_worker,host, port, client_number, messages_per_client,barrier,)
                    for client_number in range(1, clients + 1)
                ]
                # эксперимен успешный только если все клиенты успешны
                for future in futures: future.result()
            elapsed_seconds = time.perf_counter() - started_at
            actual_count = query_counter(host, port)
        finally:
            server.terminate()
            try:
                server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=3)

    expected_count = clients * messages_per_client
    result = ExperimentResult(name=name,
                              expected_count=expected_count,
                              actual_count=actual_count,
                              elapsed_seconds=elapsed_seconds,
                              server_mode=server_mode,
                              counter_mode=counter_mode,
                              log_path=log_path,
    )

    status = "CORRECT" if result.correct else "INCORRECT"
    print(
        f"{name}: mode={server_mode}, counter={counter_mode}, "
        f"expected={expected_count}, actual={actual_count} ({status}), "
        f"time={elapsed_seconds:.3f}s"
    )
    return result


def run_suite():
    """runs all race-condition and performance experiments"""

    # 1 experiment with race condition and without it
    print("Race-condition experiment")
    unsafe = run_experiment(
        name="race_unsafe",
        server_mode="threaded",
        counter_mode="unsafe",
        clients=20,
        messages_per_client=25,
        race_delay=0.002,
    )
    locked = run_experiment(
        name="race_locked",
        server_mode="threaded",
        counter_mode="locked",
        clients=20,
        messages_per_client=25,
        race_delay=0.002,
    )
    # 2 experiment just show the perfomance
    print("\nPerformance experiment")
    sequential = run_experiment(
        name="performance_sequential",
        server_mode="sequential",
        counter_mode="locked",
        clients=20,
        messages_per_client=1,
        processing_delay=0.05,
    )
    threaded = run_experiment(
        name="performance_threaded",
        server_mode="threaded",
        counter_mode="locked",
        clients=20,
        messages_per_client=1,
        processing_delay=0.05,
    )

    print("\nSummary")
    print(f"Unsafe counter lost updates: {unsafe.expected_count - unsafe.actual_count}")
    print(f"Locked counter correct: {locked.correct}")
    if threaded.elapsed_seconds > 0:
        speedup = sequential.elapsed_seconds / threaded.elapsed_seconds
        print(f"Threaded speedup: {speedup:.2f}x")
    else:
        speedup = float("inf")

    # just logging
    results_path = LOG_DIRECTORY / "experiment_results.txt"
    results_path.write_text(
        "\n".join(
            [
                "Lab 2 Part 1 experiment results",
                (
                    f"unsafe: expected={unsafe.expected_count}, "
                    f"actual={unsafe.actual_count}, time={unsafe.elapsed_seconds:.3f}s"
                ),
                (
                    f"locked: expected={locked.expected_count}, "
                    f"actual={locked.actual_count}, time={locked.elapsed_seconds:.3f}s"
                ),
                (
                    f"sequential: expected={sequential.expected_count}, "
                    f"actual={sequential.actual_count}, time={sequential.elapsed_seconds:.3f}s"
                ),
                (
                    f"threaded: expected={threaded.expected_count}, "
                    f"actual={threaded.actual_count}, time={threaded.elapsed_seconds:.3f}s"
                ),
                f"threaded_speedup={speedup:.2f}x",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Results saved to: {results_path}")

    if unsafe.correct:
        raise SystemExit("The unsafe run did not expose a race; run the suite again")
    if not locked.correct:
        raise SystemExit("The synchronized counter produced an incorrect result")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Concurrent load test for Lab 2 Part 1")
    parser.add_argument("--suite", action="store_true", help="Run all required experiments")
    parser.add_argument("--server-mode", choices=("sequential", "threaded"), default="threaded")
    parser.add_argument("--counter-mode", choices=("unsafe", "locked"), default="locked")
    parser.add_argument("--clients", type=int, default=20)
    parser.add_argument("--messages", type=int, default=10)
    parser.add_argument("--race-delay", type=float, default=0.0)
    parser.add_argument("--processing-delay", type=float, default=0.0)
    return parser.parse_args()


def main():
    args = parse_arguments()
    # just checker
    if args.clients < 1 or args.messages < 1:
        raise SystemExit("clients and messages must be positive")

    #suite - run all tests threaded + unsafe - race condition
    # threaded + locked - how to handle race condition
    # sequential + locked and threaded + locked - measure the time
    if args.suite:
        run_suite()
        return

    run_experiment(
        name="custom",
        server_mode=args.server_mode,
        counter_mode=args.counter_mode,
        clients=args.clients,
        messages_per_client=args.messages,
        race_delay=args.race_delay,
        processing_delay=args.processing_delay,
    )


if __name__ == "__main__":
    main()
