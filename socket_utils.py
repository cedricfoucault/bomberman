import socket

def send(sock, data):
    # call socket.send() until all data has been sent
    totalsent = 0
    size = len(data)
    while totalsent < size:
        sent = sock.send(data[totalsent:])
        if not sent:
            raise socket.error("socket connection broken")
        totalsent += sent

def recv(sock, size):
    # call socket.recv() until we have actually received data of size "size"
    data = ''
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise socket.error("socket connection broken")
        data += chunk
    return data

def shutdown_close(sock):
    try:
        sock.shutdown(socket.SHUT_WR)
    except socket.error, e:
        print >> sys.stderr, str(e)
    sock.close()

