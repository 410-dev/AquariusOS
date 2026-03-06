import socket
import threading
from datetime import datetime

# Print all HTTP requests received on the specified port
def main(session, port: int, bind: str = None):
    def handle_client_connection(client_socket):
        request = client_socket.recv(1024).decode('utf-8')
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Received HTTP request:\n{request}\n")

        # Print header
        headers = request.split('\r\n')
        if headers:
            print("Headers:")
            for header in headers[1:]:
                if header == '':
                    break
                print(header)
            print()
        else:
            print("No headers found.\n")

        # Print body if present
        if '\r\n\r\n' in request:
            body = request.split('\r\n\r\n', 1)[1]
            if body:
                print("Body:")
                print(body)
                print()
            else:
                print("No body found. (2)\n")
        else:
            print("No body found. (1)\n")

        # Send empty HTTP response
        http_response = "HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
        client_socket.sendall(http_response.encode('utf-8'))

        client_socket.close()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if bind:
        server.bind((bind, port))
    else:
        server.bind(('0.0.0.0', port))
    server.listen(5)

    print(f"[*] Listening for HTTP requests on port {port}...")

    # Handle incoming connections
    try:
        while True:
            client_sock, address = server.accept()
            client_handler = threading.Thread(
                target=handle_client_connection,
                args=(client_sock,)
            )
            client_handler.start()
    except KeyboardInterrupt:
        print("\n[*] Shutting down the server.")
        server.close()
        return 0, "Server stopped"

def help(session) -> str:
    return "Usage: capture-http-request <port> [bind_address]\nCaptures and prints all HTTP requests received on the specified port."
