from lobbyserver import *
from partyserver import *
import sys
import threading

def main():
    """Main server process"""
    PORT = 42042 # arbitrary port number to connect on
    LOCALHOST = '127.0.0.1' # ip adress of localhost
    ip = sys.argv[1] if len(sys.argv) > 1 else LOCALHOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT
    server = LobbyServer((ip, port))
    server.do_in_thread(fun=server.serve_forever)
    server.send_loop()
    
if __name__ == "__main__":
    main()
