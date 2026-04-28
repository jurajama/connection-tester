# connection-tester

A small Python 3 utility for exercising TCP and UDP connection stability.
A single script acts as either the server or the client depending on
command-line flags, and uses only the Python standard library.

## Requirements

- Python 3.10 or newer
- No third-party packages

## Usage

```
connection-tester.py -s [-u] [-p PORT] [-v] [-l FILE]
connection-tester.py -c HOST [-u] [-p PORT] [-t SECONDS] [-b BYTES] [-v] [-l FILE]
```

### Options

| Flag | Description |
| --- | --- |
| `-s`, `--server` | Run as a server that listens for connections. |
| `-c HOST`, `--client HOST` | Run as a client and connect repeatedly to `HOST`. |
| `-u`, `--udp` | Use UDP instead of TCP. Must be set on both client and server. The application does not handle TCP and UDP simultaneously. |
| `-p PORT`, `--port PORT` | Port to use (default `5500` for both TCP and UDP). |
| `-t SECONDS`, `--hold SECONDS` | TCP: seconds the client keeps each connection open before closing it. UDP: seconds the client waits after a successful echo before sending the next packet (and also the back-off delay after a UDP error). Default `5.0`. |
| `-b BYTES`, `--bytes BYTES` | Payload size the client sends and expects echoed back. TCP default `1500` (chosen to exercise full-MTU packet handling); UDP default `1300` (kept under typical Internet MTU to avoid IP fragmentation). Client-side only; the server echoes whatever it receives regardless of this flag. |
| `-v`, `--verbose` | Print one line per cycle with timestamps, peer address, and (UDP) round-trip time in milliseconds. |
| `-l FILE`, `--log FILE` | Also append log output to `FILE`. The log file always captures full per-cycle detail regardless of `-v`. |

`-s` and `-c` are mutually exclusive and one of them is required.

### Server

```
./connection-tester.py -s
./connection-tester.py -s -p 6000 -v
./connection-tester.py -s -l server.log
```

The server binds to `0.0.0.0` on the given port, accepts connections, and
reads until the peer closes the socket. Every byte received is echoed back
to the peer unchanged. Shut it down with `Ctrl-C`.

### Client

```
./connection-tester.py -c 10.20.30.1
./connection-tester.py -c 10.20.30.1 -p 6000 -t 2
./connection-tester.py -c server.example.com -v -l client.log
```

The client opens a TCP connection to `HOST:PORT`, sends a payload of
`--bytes` bytes, waits for the server to echo the same bytes back and
verifies they match, then holds the connection open for `--hold` seconds
before closing it and immediately opening a new one. This continues until
`Ctrl-C`. Send failures, echo timeouts, and payload mismatches are reported
on stderr. Example: `-b 65536` exercises large-packet / segmented I/O,
`-b 1` exercises tiny packets.

### UDP

```
./connection-tester.py -s -u
./connection-tester.py -c 127.0.0.1 -u
./connection-tester.py -c 10.20.30.1 -u -p 6000 -t 1 -v
```

With `-u` on both sides the tester switches to UDP. The server binds a UDP
socket on `0.0.0.0:PORT` and echoes every datagram it receives back to the
sender unchanged. The client sends a single datagram of `--bytes` bytes
(default `1300`), waits up to **3 seconds** for the echo, then waits
`--hold` seconds before sending the next test packet. If no response
arrives within 3 seconds, the client always prints an error to stderr
regardless of `-v`. With `-v` each successful round-trip prints the
response time in milliseconds.

## Output

By default both sides keep the console quiet:

- Each successful connection (TCP) or echoed datagram (UDP) prints a
  single `.` character.
- A `Ctrl-C` stops the loop and prints a short summary line.

With `-v` each cycle prints a timestamped line. For TCP this includes the
peer address and the connection duration; for UDP it includes the peer
address and the round-trip time in milliseconds.

Connection failures (and server-side early disconnects observed by the
client) are always reported verbosely to stderr — `-v` does not suppress
them and not using `-v` does not hide them.

When `-l FILE` is supplied, every open/close event and every error is
additionally written to the log file at DEBUG level, so the log file has
full detail even when the console is in brief mode.

## Example

Terminal A:

```
$ ./connection-tester.py -s
Server listening on 0.0.0.0:5500
....
```

Terminal B:

```
$ ./connection-tester.py -c 127.0.0.1 -t 1
Client connecting repeatedly to 127.0.0.1:5500, holding each connection 1.0s
....
```

On a connect failure the client prints something like:

```
[2026-04-23T10:11:12] attempt 7: connect to 10.20.30.1:5500 failed: TimeoutError: timed out
```
