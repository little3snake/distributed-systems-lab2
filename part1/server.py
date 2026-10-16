import argparse
import logging
import socket
import threading
import time
from datetime import datetime


BUFFER_SIZE = 4096
READY_MESSAGE = b"READY\n"


class SharedCounter:
    ## synchronized true or false
    ## if true use self.lock = threading.Lock()
    def __init__(self, synchronized, race_delay):
        self.value = 0
        self.race_delay = race_delay
        self.lock = threading.Lock() if synchronized else None

    def _increment_value(self):
        current_value = self.value
        if self.race_delay:
            time.sleep(self.race_delay)
        self.value = current_value + 1
        return self.value

    def increment(self):
        if self.lock is None:
            return self._increment_value()
        # with locker
        with self.lock:
            return self._increment_value()

    def get(self):
        if self.lock is None:
            return self.value
        # with locker
        with self.lock:
            return self.value


def configure_logging():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(threadName)s | %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
    )


def send_line(client_socket, message):
    client_socket.sendall((message + "\n").encode("utf-8"))

# exceptions:
# invalid UTF-8 data
# b"" - close connection

def handle_client(client_socket, client_address, counter, processing_delay):
    # client_address[0] - ip (in ipv4)
    # client_address[1] - port
    logging.info("Client connected: %s:%s", client_address[0], client_address[1])
    buffer = b"" # save bytes till the \n

    try:
        # write that connection is ready to work (in bytes)
        client_socket.sendall(READY_MESSAGE)

        while True:
            data = client_socket.recv(BUFFER_SIZE)
            # if empty line - b"" - end connection
            if not data:
                logging.info("Client %s:%s disconnected without QUIT",client_address[0], client_address[1],)
                return

            buffer += data

            while b"\n" in buffer:
                raw_line, buffer = buffer.split(b"\n", 1)
                try:
                    message = raw_line.decode("utf-8").strip()
                except UnicodeDecodeError:
                    send_line(client_socket, "ERROR: invalid UTF-8 data")
                    logging.warning("Malformed data from %s:%s",client_address[0],client_address[1],)
                    continue

                if not message:
                    send_line(client_socket, "ERROR: empty message")
                    continue
                command = message.upper()
                # if line was quit
                if command == "QUIT":
                    send_line(client_socket, "BYE")
                    return
                # if line was stats
                if command == "STATS":
                    current_count = counter.get() # get data from counter
                    logging.info("Counter requested: %s", current_count)
                    send_line(client_socket, f"COUNT {current_count}")
                    continue
                # sleep if
                if processing_delay:
                    time.sleep(processing_delay)
                # change counter
                count = counter.increment()
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                send_line(client_socket, f"[{timestamp}] {message.upper()} | COUNT {count}")

    except (ConnectionResetError, BrokenPipeError) as error:
        logging.warning("Connection lost for %s:%s: %s",client_address[0], client_address[1], error,)
    except OSError as error:
        logging.error("Socket error for %s:%s: %s",client_address[0], client_address[1], error,)
    finally:
        # close connection
        client_socket.close()
        logging.info("Connection closed: %s:%s", client_address[0], client_address[1])


def run_server(host, port, mode, counter_mode, race_delay, processing_delay):
    # create object SharedCounter
    counter = SharedCounter( synchronized=counter_mode == "locked", race_delay=race_delay,)
    # tcp connection (streams of bytes)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # tcp ipv4
    # разрешает быстрее повторно запустить сервер на том же IP и порту
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((host, port))
        server_socket.listen()
        logging.info("Server started on %s:%s | mode=%s | counter=%s",host, port, mode, counter_mode,)

        while True:
            client_socket, client_address = server_socket.accept()
            if mode == "sequential":
                handle_client(client_socket, client_address, counter, processing_delay)
                continue
            # target - what the thread should do
            # args - arguments: counter - shared counter
            # name - name of the thread
            # daemon - поток считается вспомогательным и не будет удерживать весь процесс после остановки главного потока
            worker = threading.Thread(target=handle_client,
                                      args=(client_socket, client_address, counter, processing_delay),
                                      name=f"client-{client_address[1]}",
                                      daemon=True,
                                      )
            worker.start() # start thread

    except KeyboardInterrupt:
        logging.info("Server interrupted by user")
    except OSError as error:
        logging.error("Server socket error: %s", error)
    finally:
        server_socket.close()
        logging.info("Server socket closed; final counter=%s", counter.get())


def parse_arguments():
    parser = argparse.ArgumentParser(description="Lab 2 multithreaded TCP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--mode", choices=("sequential", "threaded"), default="threaded")
    parser.add_argument("--counter-mode", choices=("unsafe", "locked"), default="locked")
    parser.add_argument("--race-delay", type=float, default=0.0)
    parser.add_argument("--processing-delay", type=float, default=0.0)
    return parser.parse_args()


def main():
    configure_logging()
    args = parse_arguments()

    if not 1 <= args.port <= 65535:
        raise SystemExit("Port must be between 1 and 65535")
    if args.race_delay < 0 or args.processing_delay < 0:
        raise SystemExit("Delay values cannot be negative")
    ## python server.py --host 127.0.0.1 --port 5050 --mode threaded --counter-mode locked --race_delay 10 --processing_delay 10
    run_server(args.host, args.port, args.mode, args.counter_mode, args.race_delay, args.processing_delay,)


if __name__ == "__main__":
    main()
