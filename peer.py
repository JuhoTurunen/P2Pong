import socket
import threading

PORT = 5000
LISTEN_HOST = "0.0.0.0"

# Edit this list to match the IPs of the other Multipass VMs.
# Example: ["10.97.0.2:5000", "10.97.0.3:5000"]
PEERS = [
    "10.97.0.2:5000",
]

peers = {}
lock = threading.Lock()


def connect_to_peer(address: str):
    host, port = address.split(":")
    port = int(port)
    try:
        sock = socket.create_connection((host, port), timeout=2)
        with lock:
            peers[address] = sock
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
            pass


def listen_loop():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((LISTEN_HOST, PORT))
        listener.listen(5)
        print(f"Listening on {LISTEN_HOST}:{PORT}")

        while True:
            conn, addr = listener.accept()
            with conn:
                remote = addr[0]
                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    print(f"\n[{remote}] {data.decode()}")


def user_input_loop():
    while True:
        message = input()
        if message:
            broadcast(message)


def main():
    for peer in PEERS:
        connect_to_peer(peer)

    listener_thread = threading.Thread(target=listen_loop, daemon=True)
    listener_thread.start()

    user_input_loop()


if __name__ == "__main__":
    main()
