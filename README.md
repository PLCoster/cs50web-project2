# CS50 Web Project 2: Flack

## CS50 Web -  Programming with Python and JavaScript

### Project Aims:

The aim of this project was to build a message service, similar in spirit to Slack. Users are able to sign into the site with a display name, create channels to communicate in, as well as view and join already existing channels. On selecting a channel, users can send and receive messages with each other in real time.

#### Technologies:

* Back-end:
  * Python
  * Flask (with Jinja Templating)
  * Flask-Socket.IO
  * PostgreSQL Database using Flask-SQLAlchemy ORM

* Front-end:
  * HTML (with Handlebars Templating)
  * Sass / CSS (with some Bootstrap Components)
  * Socket.IO
  * Javascript
  * Livestamp.js for timestamping messages


### Project Requirements:

* Display Name: When a user visits your web application for the first time, they should be prompted to type in a display name that will eventually be associated with every message the user sends. If a user closes the page and returns to your app later, the display name should still be remembered.
* Channel Creation: Any user should be able to create a new channel, so long as its name doesn’t conflict with the name of an existing channel.
* Channel List: Users should be able to see a list of all current channels, and selecting one should allow the user to view the channel. We leave it to you to decide how to display such a list.
* Messages View: Once a channel is selected, the user should see any messages that have already been sent in that channel, up to a maximum of 100 messages. Your app should only store the 100 most recent messages per channel in server-side memory.
* Sending Messages: Once in a channel, users should be able to send text messages to others the channel. When a user sends a message, their display name and the timestamp of the message should be associated with the message. All users in the channel should then see the new message (with display name and timestamp) appear on their channel page. Sending and receiving messages should NOT require reloading the page.
* Remembering the Channel: If a user is on a channel page, closes the web browser window, and goes back to your web application, your application should remember what channel the user was on previously and take the user back to that channel.
* Personal Touch: Add at least one additional feature to your chat application of your choosing! Feel free to be creative, but if you’re looking for ideas, possibilities include: supporting deleting one’s own messages, supporting use attachments (file uploads) as messages, or supporting private messaging between two users.


### Project Writeup:

This project is a Slack / Microsoft Teams style messaging app called Flack Teams, built using the Flask micro web framework.

A heroku PostgreSQL database stores user information, allowing users to register for the app and log in. When registering users select a unique, unchangeable username, a screen name that is displayed to other users with their messages and can be changed, as well as their password and a profile icon. Users can upload their own custom image for their profile icon if desired.

Once logged in, the user's browser connects to the server using a web socket, and on initial login the user is connected to a default workspace, channel and personal private chatroom. Similar to Slack, a workspace contains a set of uniquely named channels where users can send messages to other users. Inside any workspace, users can create new uniquely named channels. Users can also create a new workspace with its own separate series of chat channels in it.

Clicking on a channel name in the side bar will join the user to that channel in their current workspace, and the server will send them the last 100 messages in that channel. The number of users logged into a workspace is displayed in the top right of the app screen. Clicking on this icon opens an animated panel that shows more details about the users logged into the workspace.

When a user posts a message in a channel, the user's icon, name, the date and a timestamp for the post are displayed. When a user hovers their cursor over the message, additional options are revealed allowing them to edit or delete their message. When this occurs the edited or deleted message is updated for all users in the channel, as well as in the chat history that is relayed to any user joining the channel.

If a user hovers their cursor over a post by another user, a 'Private Message' option will display. Clicking this connects the user to a private channel with the other user, allowing them to send each other private message.

An alert system highlights channel links and private chat links if another user posts a message in a channel that is not currently being viewed. This allows a user to see that messages have been posted in other channels, to go and view them.

An account options page allows users to change their password as well as their displayed screen-name and user icon. When their screen-name or icon is updated, this is updated in all their previous messages. Users can also log out of Flack Teams which clears their session and local storage, therfore requiring them to sign back in to access their workspaces, channels and private channels. When a user logs back into the website, their previous workspace and channel are remembered (using the SQL database), and rejoined as they log in.

* application.py - the main flask application file, which contains several app route and socket.io functions:
  * app routes:
    * index - the main page of the application, where users are connected by socket.io to a workspace, channel and private channel to communicate with other users.
    * login - this route allows users to login to the website, if they have already registered, using their username and password.
    * register - a user can register for Flack Teams by choosing a username, screen name, password and profile icon. Users can choose between picking a default profile icon or uploading their own image in png, jpg or gif format. Attempted registrations are checked to ensure usernames are unique (not already in use) and also that passwords meet a minimum length and character/digit requirement before a user is successfully registered. User's passwords are not stored in the database, rather they are hashed and the hash passwords are stored. When a user tries to log in the entered password is hashed and compared to the stored hash to determine if the correct password has been entered.
    * account - this route allows users to change their password (by first entering their current password), as well as update their screen name and profile icon (displayed with all the users messages), utilising the screen_name and profile_img routes respectively.
  * socket.io functions:
    * initial logon - this runs once as a user joins the main chat page in order to configure the user's last workspace and channel, as well as set up local storage on the user's browser
    * join workspace - this runs when a user clicks on a workspace link. The user is then connected to a default channel in that workspace and also sent the list of channels in the workspace. The last workspace the user has joined is saved in the SQL database so the user can rejoin their last joined workspace when they log back into the app.
    * join channel - this runs when a user clicks on a channel link, and also when a user joins a workspace. Users are sent the message history of the channel to display, and the last joined channel is saved in the SQL database so the user can rejoin their last joined channel when the log back into the app.
    * join private - runs when a user clicks on a private channel link. Users are sent the message history of the private channel to display.
    * send message - runs when a user sends a message in a workspace channel or a private channel. It sanitizes the message text of HTML special chars, creates the message object and saves it to the channel history, before sending the message out to all users in the relevant channel. Users with access to, but not currently viewing, a channel receiving a message will also receive an alert to indicate a new message has been posted in the channel.
    * delete message/edit message - runs when a user requests one of their own messages be deleted/edited. It checks that the message exists and that the message being deleted/edited belongs to the user before deleting/updating the message text in the channel history, and sending the deleted/edited message to all users in the channel.
    Edited message text is sanitised of HTML special chars before saving to history and sending to users.
    * create channel - runs when a user requests creation of a new channel in their current workspace. It checks that the channel name does not already exist in the workspace before creating it, and updating the list of all channels for any users in the workspace.
    * create workspace - similar to create channel but runs when a user requests creation of a new workspace with its own set of channels.
    * create private channel - runs when a user clicks on a private message link. It creates a private chat channel between the users if one does not already exist, and then joins the requesting user to that private channel.
    * log out - runs when the user clicks on the logout button, disconnecting them from their workspace, channel and private channels, as well as removing them as an acitive user of the workspace, before clearing the flask session for the user.

* helpers.py - this file contains several helper functions for application.py, for sanitizing messages, sanitizing workspace/channel names, checking strings for being all whitespaces, validating a password meets minimum length and character requirements, loading a users session, history and private channels, updating the number of users in a workspace, updating a user's screen name or profile icon, and checking/saving a user uploaded profile icon.

* models.py / create.py - models contains the 'User' SQL Alchemy ORM class for interacting with the 'users' table in the SQL database. The database table is initialised by running create.py.

* templates folder - contains all the templates used by the various routes/pages of the app. layout.html is extended by the login, register and account templates, while layou_index.html is extended by the index template.

* static folder - contains favicons, Images and profile icons for the site, a Sass .scss custom style sheet, as well as a scripts folder containing JS files:
  * jquery.js, livestamp.js, moment.js - these are required for the human readable timestamps displayed on each message, using livestamp.js.
  * index.js - this is the main custom script file for the chat page. It initially joins the user to the websocket and then runs some initial configuration functions to set up button functionality on the chat page. It then emits an 'initial logon' and 'join workspace' request to the server to log in to the last workspace and channel the user was using. Local Storage is set up with serveral keys and variables to enable the app functionality. The user then receives the list of available workspaces, channels in their current workspace, private chat channels, and message history of their current channel and private channel.


### Further Ideas/Improvements:

* Ability to create private workspaces, with a user search/invite system to give other users access to the workspace
* Admin privilege for users that create a workspace, allowing them to perhaps control creation of channels, and also delete channels in their own workspace.
* Ability for users to favourite channels or workspaces so they can customise the list of workspaces/channels displayed to them.