To launch the server:
>> python server_launcher 'ip.to.listen.on'
if ip is not given, it will default to localhost.

To launch the user client (GUI):
>> python client_launcher 'ip.to.connect.on'
if ip is not given, it will default to localhost.
/!\ If using MacOSX, instead of the above line you need to type:
>> ppython client_launcher 'ip.to.connect.on'
to ensure compatibility with Panda3D.

The GUI client uses Panda3D, a 3D graphics engine for python (see http://www.panda3d.org/).
To run it, you need the Panda3D SDK installed.
The client was tested using the SDK 1.7.2, to download it please visit :
https://www.panda3d.org/download.php?sdk&version=1.7.2.

To launch the bot client:
>> python botclient 'ip.of.lobby.server' lobby_port party_no
OR
>> python botclient party_no # if server's address is (localhost, 42042)
- lobby_port should be the port of the lobby server (42042)
- party_no should be the party server's ID/no to connect on.

