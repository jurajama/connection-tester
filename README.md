# connection-tester

A small Python 3 utility for exercising TCP connection stability. A single
script acts as either the server or the client depending on command-line
flags, and uses only the Python standard library.

## Requirements

- Python 3.10 or newer
- No third-party packages

## Usage

```
connection-tester.py -s [-p PORT] [-v] [-l FILE]
connection-tester.py -c HOST [-p PORT] [-t SECONDS] [-v] [-l FILE]
```

### Options

| Flag | Description |
| --- | --- |
| `-s`, `--server` | Run as a server that listens for connections. |
| `-c HOST`, `--client HOST` | Run as a client and connect repeatedly to `HOST`. |
| `-p PORT`, `--port PORT` | TCP port to use (default `5500`). |
| `-t SECONDS`, `--hold SECONDS` | Seconds the client keeps each connection open before closing it (default `5.0`). |
| `-v`, `--verbose` | Print one line per connection open/close with timestamps, peer address, and duration. |
| `-l FILE`, `--log FILE` | Also append log output to `FILE`. The log file always captures full per-connection detail regardless of `-v`. |

`-s` and `-c` are mutually exclusive and one of them is required.

### Server

```
./connection-tester.py -s
./connection-tester.py -s -p 6000 -v
./connection-tester.py -s -l server.log
```

The server binds to `0.0.0.0` on the given port, accepts connections, and
reads until the peer closes the socket. It does not echo or otherwise
interact with the data. Shut it down with `Ctrl-C`.

### Client

```
./connection-tester.py -c 10.20.30.1
./connection-tester.py -c 10.20.30.1 -p 6000 -t 2
./connection-tester.py -c server.example.com -v -l client.log
```

The client opens a TCP connection to `HOST:PORT`, holds it open for the
configured number of seconds, closes it, and immediately opens a new one.
This continues until `Ctrl-C`.

## Output

By default both sides keep the console quiet:

- Each successful connection prints a single `.` character.
- A `Ctrl-C` stops the loop and prints a short summary line.

With `-v` each open and close prints a timestamped line including the peer
address and the connection duration.

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
