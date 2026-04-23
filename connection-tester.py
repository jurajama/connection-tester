#!/usr/bin/env python3
import argparse
import logging
import socket
import sys
import time
from datetime import datetime

DEFAULT_PORT = 5500
DEFAULT_HOLD_SECONDS = 5.0

log = logging.getLogger("connection-tester")


def setup_logging(verbose: bool, log_path: str | None) -> None:
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    log.propagate = False

    if log_path:
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        log.addHandler(file_handler)


def brief(dot: str = ".") -> None:
    sys.stdout.write(dot)
    sys.stdout.flush()


def newline() -> None:
    sys.stdout.write("\n")
    sys.stdout.flush()


def run_server(port: int, verbose: bool) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("0.0.0.0", port))
    except OSError as e:
        msg = f"Failed to bind to port {port}: {e}"
        print(msg, file=sys.stderr)
        log.error(msg)
        sys.exit(1)

    sock.listen(16)
    msg = f"Server listening on 0.0.0.0:{port}"
    print(msg)
    log.info(msg)

    try:
        while True:
            try:
                client_sock, addr = sock.accept()
            except KeyboardInterrupt:
                raise
            except OSError as e:
                err = f"accept() failed: {e}"
                print(err, file=sys.stderr)
                log.error(err)
                continue

            opened_at = datetime.now()
            if verbose:
                msg = f"[{opened_at.isoformat(timespec='seconds')}] connection opened from {addr[0]}:{addr[1]}"
                print(msg)
                log.info(msg)
            else:
                brief(".")
                log.debug(f"connection opened from {addr[0]}:{addr[1]}")

            try:
                client_sock.settimeout(None)
                while True:
                    try:
                        data = client_sock.recv(4096)
                    except ConnectionResetError as e:
                        if verbose:
                            newline()
                            err = f"connection from {addr[0]}:{addr[1]} reset: {e}"
                            print(err, file=sys.stderr)
                        log.warning(f"connection from {addr[0]}:{addr[1]} reset: {e}")
                        break
                    if not data:
                        break
            finally:
                try:
                    client_sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                client_sock.close()

            closed_at = datetime.now()
            duration = (closed_at - opened_at).total_seconds()
            if verbose:
                msg = f"[{closed_at.isoformat(timespec='seconds')}] connection from {addr[0]}:{addr[1]} closed after {duration:.2f}s"
                print(msg)
                log.info(msg)
            else:
                log.debug(f"connection from {addr[0]}:{addr[1]} closed after {duration:.2f}s")
    except KeyboardInterrupt:
        newline()
        msg = "Server shutting down (keyboard interrupt)"
        print(msg)
        log.info(msg)
    finally:
        sock.close()


def run_client(host: str, port: int, hold_seconds: float, verbose: bool) -> None:
    msg = f"Client connecting repeatedly to {host}:{port}, holding each connection {hold_seconds}s"
    print(msg)
    log.info(msg)

    attempt = 0
    try:
        while True:
            attempt += 1
            opened_at = datetime.now()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            try:
                sock.connect((host, port))
            except (OSError, socket.timeout) as e:
                newline()
                err = f"[{opened_at.isoformat(timespec='seconds')}] attempt {attempt}: connect to {host}:{port} failed: {e.__class__.__name__}: {e}"
                print(err, file=sys.stderr)
                log.error(err)
                sock.close()
                time.sleep(1.0)
                continue

            if verbose:
                msg = f"[{opened_at.isoformat(timespec='seconds')}] attempt {attempt}: opened {sock.getsockname()} -> {host}:{port}"
                print(msg)
                log.info(msg)
            else:
                brief(".")
                log.debug(f"attempt {attempt}: opened {sock.getsockname()} -> {host}:{port}")

            try:
                sock.settimeout(hold_seconds + 1.0)
                end_at = time.monotonic() + hold_seconds
                while True:
                    remaining = end_at - time.monotonic()
                    if remaining <= 0:
                        break
                    sock.settimeout(remaining)
                    try:
                        data = sock.recv(4096)
                    except socket.timeout:
                        break
                    if not data:
                        newline()
                        err = f"attempt {attempt}: server closed connection early"
                        print(err, file=sys.stderr)
                        log.warning(err)
                        break
            finally:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                sock.close()

            closed_at = datetime.now()
            duration = (closed_at - opened_at).total_seconds()
            if verbose:
                msg = f"[{closed_at.isoformat(timespec='seconds')}] attempt {attempt}: closed after {duration:.2f}s"
                print(msg)
                log.info(msg)
            else:
                log.debug(f"attempt {attempt}: closed after {duration:.2f}s")
    except KeyboardInterrupt:
        newline()
        msg = f"Client stopping after {attempt} attempt(s) (keyboard interrupt)"
        print(msg)
        log.info(msg)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simple TCP connection stability tester (client/server)."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("-s", "--server", action="store_true", help="Run as server")
    mode.add_argument(
        "-c",
        "--client",
        metavar="HOST",
        help="Run as client and connect to HOST",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"TCP port to use (default {DEFAULT_PORT})",
    )
    parser.add_argument(
        "-t",
        "--hold",
        type=float,
        default=DEFAULT_HOLD_SECONDS,
        help=f"Seconds to hold each client connection open (default {DEFAULT_HOLD_SECONDS})",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose per-connection logging"
    )
    parser.add_argument(
        "-l",
        "--log",
        metavar="FILE",
        help="Also write log output to FILE",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    setup_logging(args.verbose, args.log)

    if args.server:
        run_server(args.port, args.verbose)
    else:
        run_client(args.client, args.port, args.hold, args.verbose)


if __name__ == "__main__":
    main()
