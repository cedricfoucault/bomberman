import sys
import os
from lobbyclient import LobbyClient
from partyclient import PartyClient
from gameconst import *

def run_lobby_client(ip, port, partyfile):
    """Run the lobby client. The process where this procedure is called from
    will be exited once the user decides to join a party.
    The party server's address will be written"""
    client = LobbyClient(partyfile)
    client.connect((lobby_ip, lobby_port))
    client.run()

def run_party_client(ip, port):
    """Run the party client. The process where this procedure is called from
    will be exited once the user decides to join a party.
    The party server's address will be written"""
    partyclient = PartyClient()
    partyclient.connect((ip, port))
    partyclient.run()

# The client launcher will first run the lobby client in a child process,
# The lobby process will be done once the user decides to join a given party.
# Once this is done, the launcher will read the party server address from a
# tmp file, will launch the party client and tell him to connect on the
# address it has read.
# Using processes instead of threads is required for compatibility with Panda3D.

if __name__ == "__main__":
    PORT = 42042 # the lobby server default port number
    LOCALHOST = '127.0.0.1'
    # read the ip from the first arg or use localhost
    lobby_ip = sys.argv[1] if len(sys.argv) > 1 else LOCALHOST
    # read the port from the second arg or use the default port
    lobby_port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT
    # open a temporary file so that the lobby client can write on it
    partyfile = os.tmpfile()
    exitcode = -1
    # launch the lobby client in a child process
    if DEBUG: print "launching lobby client"
    if os.fork() == 0:
        # child process
        run_lobby_client(lobby_ip, lobby_port, partyfile)
    else:
        # parent process: wait until the lobby client process is done
        _, exitcode = os.wait()
        if DEBUG: print exitcode
        # in any case, terminate the child process before continuing
        # in order to exit gracefully
        # (e.g. if a kill signal was sent to the parent)
            
    # go on only if the lobby client was exited "normally"
    # (user deciding to join a party)
    if exitcode == 0:
        # read the party server's address to connect on
        partyfile.seek(0)
        # first line is the ip
        party_ip = partyfile.readline().strip()
        # second line is the port
        party_port = partyfile.readline().strip()
        # we don't need the temporary file anymore, close it
        partyfile.close()
        # if the address was read successfully, launch the party client on it
        if party_ip and party_port:
            run_party_client(party_ip, int(party_port))
