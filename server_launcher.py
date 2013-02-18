from server import *
import sys

def main():
    """Main server process"""
    PORT = 42042 # arbitrary port number to connect on
    LOCALHOST = '127.0.0.1' # ip adress of localhost
    # ip = LOCALHOST
    # ip = '192.168.1.4'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT
    ip = sys.argv[1] if len(sys.argv) > 1 else LOCALHOST
    server = LobbyServer((ip, port))
    # server = IngamePartyServer((LOCALHOST, PORT))
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()
    server.send_parties_periodically()
    # threading.Thread(target=server.serve_forever).start()
    # server.send_actions_periodically()
    
if __name__ == "__main__":
    main()
