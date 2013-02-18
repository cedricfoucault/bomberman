import sys
import os
import subprocess

debug = True

if __name__ == "__main__":
    PORT = 42042 # the server's port number
    LOCALHOST = '127.0.0.1' # ip adress of localhost
    # lobby_ip = LOCALHOST
    # lobby_ip = '192.168.1.2'
    lobby_ip = sys.argv[1] if len(sys.argv) > 1 else LOCALHOST
    lobby_port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT
    # open a temporary file for the lobby client to write the party server address
    partyfile = os.tmpfile()
    party_fd = partyfile.fileno()
    # launch the lobby client
    if debug: print "launching lobby client"
    if sys.platform in ['darwin', 'win32']:
        val = subprocess.call(["ppython", "lobbyclient.py", lobby_ip, str(lobby_port), str(party_fd)])
    else:
        val = subprocess.call(["python", "lobbyclient.py", lobby_ip, str(lobby_port), str(party_fd)])
    # check if the lobby told us to connect to a party server
    if val == 0:
        partyfile.seek(0)
        # first line should be the ip of the party server
        party_ip = partyfile.readline().strip()
        # second line should be the port of the party server
        party_port = int(partyfile.readline().strip())
    partyfile.close()
    # launch the party client
    if debug: print "launching party client"
    if sys.platform in ['darwin', 'win32']:
        val = subprocess.call(["ppython", "partyclient.py", party_ip, str(party_port)])
    else:
        val = subprocess.call(["python", "partyclient.py", party_ip, str(party_port)])
