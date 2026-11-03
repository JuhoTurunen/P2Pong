"""Edit PEERS on each laptop, then run: python3 peer.py

All laptops run the same code. Each opens a sending connection to the others
and accepts their sending connections. Two one-way connections per pair keep
this proof of concept simple: no server, handshake, or duplicate negotiation.
"""

import codecs
import socket
import sys
import termios
import threading
import time
import tty

PORT = 5000
# Set these to the OTHER two laptops' Wi-Fi IP addresses on each laptop.
PEERS = ["10.75.151.146", "10.75.151.248"]

outgoing = {}
lock = threading.Lock()


def close_connection(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    sock.close()


def receive(sock, host):
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    try:
        while True:
            try:
                data = sock.recv(4096)
            except socket.timeout:
                continue
            if not data:
                break
            # TCP is a byte stream; the decoder also handles split UTF-8 keys.
            for key in decoder.decode(data):
                print(f"[{host}] {key!r}", flush=True)
    except OSError:
        pass
    finally:
        close_connection(sock)


def listen(listener):
    while True:
        try:
            sock, address = listener.accept()
        except OSError:
            return
        threading.Thread(target=receive, args=(sock, address[0]), daemon=True).start()


def connect(host):
    waiting = False
    while True:
        try:
            sock = socket.create_connection((host, PORT), timeout=1)
        except OSError:
            if not waiting:
                print(f"Waiting for {host}:{PORT}", flush=True)
                waiting = True
        else:
            waiting = False
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(0.5)
            with lock:
                outgoing[host] = sock
            print(f"Connected to {host}", flush=True)
            # The other end only receives on this socket. Waiting here detects
            # its disconnect, so we can reconnect even when nobody types.
            receive(sock, host)
            with lock:
                if outgoing.get(host) is sock:
                    del outgoing[host]
            print(f"Disconnected from {host}; reconnecting", flush=True)
        time.sleep(1)


def broadcast(key):
    with lock:
        targets = list(outgoing.values())
    sent = 0
    for sock in targets:
        try:
            sock.sendall(key.encode("utf-8"))
            sent += 1
        except OSError:
            close_connection(sock)
    return sent


def keyboard():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)  # Immediate keys without Enter; Ctrl+C still works.
        while True:
            key = sys.stdin.read(1)
            if not key:
                break
            sent = broadcast(key)
            print(f"[you] {key!r} -> {sent} peer(s)", flush=True)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def main():
    if not sys.stdin.isatty():
        print("Run python3 peer.py in a terminal.", file=sys.stderr)
        return 1
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("0.0.0.0", PORT))
            listener.listen()
            print(f"Listening on port {PORT}. Ctrl+C quits.", flush=True)
            threading.Thread(target=listen, args=(listener,), daemon=True).start()
            for host in set(PEERS):
                threading.Thread(target=connect, args=(host,), daemon=True).start()
            keyboard()
    except KeyboardInterrupt:
        print("\nStopped.")
    except OSError as exc:
        print(f"Cannot run peer: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
