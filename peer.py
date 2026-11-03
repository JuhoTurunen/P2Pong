import select
import socket
import sys
import termios
import threading
import time
import tty

PORT = 5000
LISTEN_HOST = "0.0.0.0"

# Put every peer IP here on every machine.
# Example:
# PEERS = ["10.97.0.2:5000", "10.97.0.3:5000"]
PEERS = [
    "10.75.151.146:5000",
]

peers = {}
lock = threading.Lock()


def add_peer(address: str, sock: socket.socket):
    with lock:
        peers[address] = sock


def remove_peer(sock):
    with lock:
        for address, existing in list(peers.items()):
            if existing is sock:
                del peers[address]
                break


def connect_to_peer(address: str):
    host, port = address.rsplit(":", 1)
    port = int(port)
    with lock:
        if address in peers:
            return

    try:
        sock = socket.create_connection((host, port), timeout=1)
        sock.setblocking(False)
        add_peer(address, sock)
        print(f"Connected to {address}")
    except OSError:
        print(f"Could not connect to {address}")


def broadcast(message: str):
    payload = message.encode()
    with lock:
        targets = list(peers.values())

    for sock in targets:
        try:
            sock.sendall(payload)
        except OSError:
            try:
                sock.close()
            except OSError:
                pass
            remove_peer(sock)


def handle_connection(conn: socket.socket, remote: str):
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            text = data.decode(errors="replace")
            print(f"\n[{remote}] {text}", end="", flush=True)
    except BlockingIOError:
        pass
    except OSError:
        pass
    finally:
        try:
            conn.close()
        except OSError:
            pass
        remove_peer(conn)


def listen_loop():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((LISTEN_HOST, PORT))
        listener.listen(10)
        print(f"Listening on {LISTEN_HOST}:{PORT}")

        while True:
            conn, addr = listener.accept()
            remote = f"{addr[0]}:{addr[1]}"
            conn.setblocking(False)
            add_peer(remote, conn)
            threading.Thread(target=handle_connection, args=(conn, remote), daemon=True).start()
            print(f"Accepted connection from {remote}")


def reconnect_loop():
    while True:
        for peer in PEERS:
            with lock:
                connected = peer in peers
            if not connected:
                connect_to_peer(peer)
        time.sleep(2)


def keyboard_input_loop():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)
        while True:
            ready, _, _ = select.select([sys.stdin], [], [], 0.05)
            if not ready:
                continue

            key = sys.stdin.read(1)
            if key == "\x03":
                break

            if key == "\r":
                key = "\n"

            print(key, end="", flush=True)
            broadcast(key)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def main():
    listener_thread = threading.Thread(target=listen_loop, daemon=True)
    listener_thread.start()

    reconnect_thread = threading.Thread(target=reconnect_loop, daemon=True)
    reconnect_thread.start()

    for peer in PEERS:
        connect_to_peer(peer)

    keyboard_input_loop()


if __name__ == "__main__":
    main()
