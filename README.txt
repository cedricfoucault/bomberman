The programs have been run and tested under Python 2.5, 2.6 and 2.7.

--------------------------------- SERVER ---------------------------------

To launch the server:
>> python server_launcher 'ip.to.listen.on'
if ip is not given, it will default to localhost.

* Use CTRL+C to close the server.


------------------------------- USER CLIENT ------------------------------

The GUI client uses Panda3D, a 3D graphics engine for python
(see http://www.panda3d.org/).
To run it, you need the Panda3D SDK installed.
The client was tested using the SDK 1.7.2, to download it please visit :
https://www.panda3d.org/download.php?sdk&version=1.7.2.

To launch the user (GUI) client:
>> python client_launcher 'ip.to.connect.on'
if ip is not given, it will default to localhost.
/!\ If using MacOSX, instead of the above line you need to type:
>> ppython client_launcher 'ip.to.connect.on'
to ensure compatibility with Panda3D.

The client is used as follows:
- In the lobby client:
  * Type "C" to create a party.
  * Click one party button to connect to it.
- In the party client:
  * Use the directional arrows (UP-DOWN-LEFT-RIGHT) to move
  * Use 'X' to pose a bomb.
- In both:
  * Close the window or enter 'CTRL+C' (SIGINT) in the terminal to exit.


------------------------------- BOT CLIENT ------------------------------

To launch the bot client:
>> python botclient 'ip.of.lobby.server' lobby_port party_no
OR
>> python botclient party_no # if server's address is (localhost, 42042)
- lobby_port should be the port of the lobby server (42042)
- party_no should be the party server's ID/no to connect on.

* Use CTRL+C to close the bot.

--------------------------------- CONTACT -------------------------------
cedric.foucault@gmail.com

Thank you for checking this out!

