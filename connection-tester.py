#!/usr/bin/env python3
import argparse
import logging
import socket
import sys
import time
from datetime import datetime

DEFAULT_PORT = 5500
DEFAULT_HOLD_SECONDS = 5.0
DEFAULT_PAYLOAD_BYTES_TCP = 1500
DEFAULT_PAYLOAD_BYTES_UDP = 1300
UDP_RESPONSE_TIMEOUT = 3.0


def make_payload(size: int) -> bytes:
    base = bytes(range(256))
    full, tail = divmod(size, 256)
    return base * full + base[:tail]

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
    else:
        log.addHandler(logging.NullHandler())


def brief(dot: str = ".") -> None:
    sys.stdout.write(dot)
    sys.stdout.flush()


def newline() -> None:
    sys.stdout.write("\n")
    sys.stdout.flush()


def run_udp_server(port: int, verbose: bool) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("0.0.0.0", port))
    except OSError as e:
        msg = f"Failed to bind UDP port {port}: {e}"
        print(msg, file=sys.stderr)
        log.error(msg)
        sys.exit(1)

    msg = f"UDP server listening on 0.0.0.0:{port}"
    print(msg)
    log.info(msg)

    try:
        while True:
            try:
                data, addr = sock.recvfrom(65535)
            except KeyboardInterrupt:
                raise
            except OSError as e:
                err = f"recvfrom() failed: {e}"
                print(err, file=sys.stderr)
                log.error(err)
                continue

            received_at = datetime.now()
            if verbose:
                msg = (
                    f"[{received_at.isoformat(timespec='seconds')}] "
                    f"received {len(data)} bytes from {addr[0]}:{addr[1]}"
                )
                print(msg)
                log.info(msg)
            else:
                brief(".")
                log.debug(f"received {len(data)} bytes from {addr[0]}:{addr[1]}")

            try:
                sock.sendto(data, addr)
            except OSError as e:
                if verbose:
                    newline()
                err = f"echo to {addr[0]}:{addr[1]} failed: {e}"
                print(err, file=sys.stderr)
                log.warning(err)
    except KeyboardInterrupt:
        newline()
        msg = "UDP server shutting down (keyboard interrupt)"
        print(msg)
        log.info(msg)
    finally:
        sock.close()


def run_udp_client(
    host: str,
    port: int,
    hold_seconds: float,
    verbose: bool,
    payload_bytes: int,
) -> None:
    payload = make_payload(payload_bytes)
    msg = (
        f"UDP client sending to {host}:{port}, "
        f"waiting {hold_seconds}s between packets, payload {payload_bytes} bytes"
    )
    print(msg)
    log.info(msg)

    try:
        host_ip = socket.gethostbyname(host)
    except socket.gaierror as e:
        err = f"failed to resolve {host}: {e}"
        print(err, file=sys.stderr)
        log.error(err)
        sys.exit(1)

    attempt = 0
    try:
        while True:
            attempt += 1
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(UDP_RESPONSE_TIMEOUT)
            sent_at = datetime.now()
            send_monotonic = time.monotonic()
            try:
                try:
                    sock.sendto(payload, (host_ip, port))
                except OSError as e:
                    newline()
                    err = (
                        f"[{sent_at.isoformat(timespec='seconds')}] "
                        f"attempt {attempt}: sendto {host}:{port} failed: "
                        f"{e.__class__.__name__}: {e}"
                    )
                    print(err, file=sys.stderr)
                    log.error(err)
                    time.sleep(hold_seconds)
                    continue

                try:
                    data, addr = sock.recvfrom(65535)
                except socket.timeout:
                    newline()
                    err = (
                        f"[{datetime.now().isoformat(timespec='seconds')}] "
                        f"attempt {attempt}: no UDP response from {host}:{port} "
                        f"within {UDP_RESPONSE_TIMEOUT:.1f}s"
                    )
                    print(err, file=sys.stderr)
                    log.error(err)
                    time.sleep(hold_seconds)
                    continue
                except OSError as e:
                    newline()
                    err = (
                        f"attempt {attempt}: recvfrom failed: "
                        f"{e.__class__.__name__}: {e}"
                    )
                    print(err, file=sys.stderr)
                    log.error(err)
                    time.sleep(hold_seconds)
                    continue

                rtt_ms = (time.monotonic() - send_monotonic) * 1000.0

                if data != payload:
                    newline()
                    err = (
                        f"attempt {attempt}: UDP response payload mismatch "
                        f"({len(data)}/{len(payload)} bytes)"
                    )
                    print(err, file=sys.stderr)
                    log.error(err)
                    time.sleep(hold_seconds)
                    continue

                if verbose:
                    msg = (
                        f"[{sent_at.isoformat(timespec='seconds')}] "
                        f"attempt {attempt}: {len(payload)} bytes echoed by "
                        f"{addr[0]}:{addr[1]} in {rtt_ms:.2f} ms"
                    )
                    print(msg)
                    log.info(msg)
                else:
                    brief(".")
                    log.debug(
                        f"attempt {attempt}: {len(payload)} bytes echoed in "
                        f"{rtt_ms:.2f} ms"
                    )
            finally:
                sock.close()

            time.sleep(hold_seconds)
    except KeyboardInterrupt:
        newline()
        msg = f"UDP client stopping after {attempt} attempt(s) (keyboard interrupt)"
        print(msg)
        log.info(msg)


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
                    try:
                        client_sock.sendall(data)
                    except OSError as e:
                        if verbose:
                            newline()
                            err = f"echo to {addr[0]}:{addr[1]} failed: {e}"
                            print(err, file=sys.stderr)
                        log.warning(f"echo to {addr[0]}:{addr[1]} failed: {e}")
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


def run_client(
    host: str,
    port: int,
    hold_seconds: float,
    verbose: bool,
    payload_bytes: int,
) -> None:
    payload = make_payload(payload_bytes)
    msg = (
        f"Client connecting repeatedly to {host}:{port}, "
        f"holding each connection {hold_seconds}s, echo payload {payload_bytes} bytes"
    )
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

            echo_ok = True
            try:
                sock.settimeout(10.0)
                try:
                    sock.sendall(payload)
                except OSError as e:
                    newline()
                    err = f"attempt {attempt}: send of {len(payload)} bytes failed: {e}"
                    print(err, file=sys.stderr)
                    log.error(err)
                    echo_ok = False

                if echo_ok:
                    received = bytearray()
                    while len(received) < len(payload):
                        try:
                            chunk = sock.recv(
                                min(4096, len(payload) - len(received))
                            )
                        except socket.timeout:
                            newline()
                            err = (
                                f"attempt {attempt}: echo timeout after "
                                f"{len(received)}/{len(payload)} bytes"
                            )
                            print(err, file=sys.stderr)
                            log.error(err)
                            echo_ok = False
                            break
                        if not chunk:
                            newline()
                            err = (
                                f"attempt {attempt}: server closed after "
                                f"{len(received)}/{len(payload)} echo bytes"
                            )
                            print(err, file=sys.stderr)
                            log.warning(err)
                            echo_ok = False
                            break
                        received.extend(chunk)
                    if echo_ok and bytes(received) != payload:
                        newline()
                        err = f"attempt {attempt}: echo payload mismatch"
                        print(err, file=sys.stderr)
                        log.error(err)
                        echo_ok = False

                if echo_ok and hold_seconds > 0:
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
        description="Simple TCP/UDP connection stability tester (client/server)."
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
        "-b",
        "--bytes",
        type=int,
        default=None,
        dest="payload_bytes",
        help=(
            f"Bytes the client sends (and server echoes) per connection "
            f"(default {DEFAULT_PAYLOAD_BYTES_TCP} for TCP, "
            f"{DEFAULT_PAYLOAD_BYTES_UDP} for UDP). Client-side only."
        ),
    )
    parser.add_argument(
        "-u",
        "--udp",
        action="store_true",
        help="Use UDP instead of TCP (default is TCP).",
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

    if args.payload_bytes is None:
        args.payload_bytes = (
            DEFAULT_PAYLOAD_BYTES_UDP if args.udp else DEFAULT_PAYLOAD_BYTES_TCP
        )

    if args.payload_bytes < 0:
        print("--bytes must be >= 0", file=sys.stderr)
        sys.exit(2)

    if args.udp:
        if args.server:
            run_udp_server(args.port, args.verbose)
        else:
            run_udp_client(
                args.client, args.port, args.hold, args.verbose, args.payload_bytes
            )
    else:
        if args.server:
            run_server(args.port, args.verbose)
        else:
            run_client(
                args.client, args.port, args.hold, args.verbose, args.payload_bytes
            )


if __name__ == "__main__":
    main()
