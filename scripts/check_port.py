import socket, sys

port = int(sys.argv[1])
with socket.socket() as sock:
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        sys.exit(
            f"Port {port} is already in use. Stop the previous FaceIQ process or other service, then retry. No process was killed."
        )
