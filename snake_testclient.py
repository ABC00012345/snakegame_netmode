import time
import socket

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
addr = ("0.0.0.0", 5151)

client_socket.connect(addr)

message = b'test'
start = time.time()
client_socket.sendall(message)

try:
    while True:
        data = client_socket.recv(1024)
        if not data:
            break
        print(f'{data.decode("utf-8")}')
        break
    time.sleep(3)
    client_socket.sendall(b'DOWN')
    while True: client_socket.sendall(input("").encode("utf-8")); print(client_socket.recv(1024).decode("utf-8"))
except KeyboardInterrupt:
    client_socket.sendall(b'disconnect')
    print("Client stopped!")
    client_socket.close()
