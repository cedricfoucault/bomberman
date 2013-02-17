from server import *
import sys

def main():
    """Main server process"""
    PORT = 42042 # arbitrary port number to connect on for the chat
    LOCALHOST = '127.0.0.1' # ip adress of localhost
    # ip = LOCALHOST
    # ip = '192.168.1.4'
    ip = sys.argv[1]
    server = LobbyServer((ip, PORT))
    # server = IngamePartyServer((LOCALHOST, PORT))
    threading.Thread(target=server.serve_forever).start()
    server.send_parties_periodically()
    # threading.Thread(target=server.serve_forever).start()
    # server.send_actions_periodically()
    
if __name__ == "__main__":
    main()
